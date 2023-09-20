import ccxt
import pandas as pd

from src.config import Config


class Exchange:
    def __init__(self):
        self.binance = ccxt.binance()

    # Fetch historical data from the ccxt library
    def fetch_historical_data(self, config: Config):
        since = self.timestamp_from_date(config.start_date)
        ohlcv = self.binance.fetch_ohlcv(config.symbol, config.timeframe, limit=config.limit, since=since)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')  # Convert timestamp to datetime
        df.set_index('timestamp', inplace=True)
        return df

    def timestamp_from_date(self, date_str):
        # Convert a date string to a timestamp in milliseconds
        return int(pd.Timestamp(date_str).timestamp() * 1000)

class Portfolio:
    def __init__(self, config: Config):
        # Initialize the portfolio with USDT balance
        self.usdt_balance = config.initial_usdt_balance
        self.commission_rate = config.commission_rate
        self.btc_balance = 0

    def buy_btc(self, price, amount):
        cost = price * amount
        if cost > self.usdt_balance:
            return False
        commission = amount * self.commission_rate
        self.btc_balance += amount - commission
        self.usdt_balance -= cost
        print("buy")
        return True

    def sell_btc(self, price, amount):
        if amount > self.btc_balance:
            amount = self.btc_balance
        commission = amount * price * self.commission_rate
        self.btc_balance -= amount
        self.usdt_balance += price * amount - commission
        print("sell")
        return True


class TradingStrategy:
    def __init__(self, exchange, portfolio, config: Config):
        self.exchange = exchange
        self.portfolio = portfolio
        self.entry_intervals_down = config.entry_intervals_down
        self.entry_intervals_up = config.entry_intervals_up
        self.grid_down = self.calculate_grid(
            config.start_usdt_btc_price,
            config.entry_intervals_down
        )
        self.is_strategy_in_progress = False
        self.fixed_price = config.initial_usdt_balance / len(config.entry_intervals_down)
        self.last_3_close = [None, None, None]

    # def calculate_sma(self, data, window):
    #     return data['close'].rolling(window=window).mean()
    #
    # def calculate_ema(self, data, window):
    #     return data['close'].ewm(span=window, adjust=False).mean()
    #
    # def should_start_trading(self, data):
    #     sma = self.calculate_sma(data, window=50)
    #     ema = self.calculate_ema(data, window=20)
    #
    #     # Determine trading conditions based on your strategy
    #     if data['close'].iloc[-1] > sma.iloc[-1] and data['close'].iloc[-1] > ema.iloc[-1]:
    #         return True  # Start trading when price is above both SMA and EMA
    #     elif data['close'].iloc[-1] < sma.iloc[-1] and data['close'].iloc[-1] < ema.iloc[-1]:
    #         return True  # Start trading when price is below both SMA and EMA
    #     else:
    #         return False

    def should_start_trading2(self, row):
        self.last_3_close.append(row['close'])
        self.last_3_close.pop(0)
        if None in self.last_3_close:
            return False
        if sum(self.last_3_close) / len(self.last_3_close) > row['close']:
            print("start")
            return True
        return False

    def simulate(self, data):
        grid_up_step_usdt = data.iloc[0]['close'] * self.entry_intervals_up

        results = []

        current_line_ind = 0
        current_line = self.grid_down[current_line_ind]

        for index, row in data.iterrows():
            current_price = row['close']

            if not self.is_strategy_in_progress and self.should_start_trading2(row):  # check for new entry point
                self.is_strategy_in_progress = True
                self.grid_down = self.calculate_grid(row['close'], Config.entry_intervals_down)
                current_line_ind = 0
                current_line = self.grid_down[current_line_ind]
                print("Timestep: ", index)
                print("close: ", row['close'], "open: ", row['open'], "high: ", row['high'], "low: ", row['low'])
                print("self.grid_down: ", self.grid_down)

            # Buy BTC
            if current_price <= self.grid_down[current_line_ind + 1]:
                step, current_line_ind = self.get_step_down(current_price, self.grid_down, current_line_ind)
                btc_to_buy = self.fixed_price * step / current_price

                if self.portfolio.buy_btc(current_price, btc_to_buy):
                    results.append({'timestamp': index, 'action': 'buy', 'current_price': current_price,
                                    'btc_balance': self.portfolio.btc_balance,
                                    'usdt_balance': self.portfolio.usdt_balance})
                    current_line = self.grid_down[current_line_ind]

            # Sell BTC
            if current_price >= self.grid_down[current_line_ind] + grid_up_step_usdt and self.portfolio.btc_balance > 0:
                step = int((current_price - self.grid_down[current_line_ind]) // grid_up_step_usdt)
                btc_to_sell = min(self.portfolio.btc_balance, self.fixed_price * step / current_price)
                current_line_ind = self.get_step_up(current_price, self.grid_down, current_line_ind)

                if self.portfolio.sell_btc(current_price, btc_to_sell):
                    results.append({'timestamp': index, 'action': 'sell', 'current_price': current_price,
                                    'btc_balance': self.portfolio.btc_balance,
                                    'usdt_balance': self.portfolio.usdt_balance})
                    current_line = self.grid_down[current_line_ind]

                if self.portfolio.btc_balance == 0:
                    self.is_strategy_in_progress = False

        results_df = pd.DataFrame(results)
        results_df.to_csv('strategy_results.csv', index=False)
        print("Simulation done")

    def calculate_grid(self, start_usdt_btc_price, entry_intervals_down):
        grid = []
        cur_line = start_usdt_btc_price
        grid.append(cur_line)
        for interval_perc in entry_intervals_down:
            step_grid = start_usdt_btc_price * interval_perc
            grid.append(cur_line - step_grid)
            cur_line = cur_line - step_grid
        return grid

    @staticmethod
    def get_step_down(current_price, grid, current_line_ind):
        step = 0
        while current_price <= grid[current_line_ind + 1]:
            step += 1
            current_line_ind += 1
        return step, current_line_ind

    @staticmethod
    def get_step_up(current_price, grid, current_line_ind):
        while current_price >= grid[current_line_ind] and current_line_ind > 0:
            current_line_ind -= 1
            if current_price < grid[current_line_ind - 1]:
                break
        return current_line_ind


if __name__ == '__main__':
    exchange = Exchange()
    portfolio = Portfolio(Config)

    strategy = TradingStrategy(exchange, portfolio, Config)

    historical_data = exchange.fetch_historical_data(Config)
    strategy.simulate(historical_data)
