import ccxt
import numpy as np
import pandas as pd

from src.config import Config as config


class Exchange:
    def __init__(self):
        self.binance = ccxt.binance()

    # Fetch historical data from the ccxt library
    def fetch_historical_data(self, config):
        since = self.timestamp_from_date(config.start_date)
        limit = config.limit
        timeframe = config.timeframe

        data_frames = []

        while limit > 0:
            if limit > 1000:
                current_limit = 1000
            else:
                current_limit = limit

            ohlcv = self.binance.fetch_ohlcv(
                config.symbol, timeframe, limit=current_limit, since=since
            )

            if not ohlcv:
                break

            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            # Convert timestamp to datetime
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)

            data_frames.append(df)

            # Reduce the limit and update the start date for the next request
            limit -= current_limit
            since = int(df.index[-1].timestamp()) * 1000

        # Combine all received data into one DataFrame
        if data_frames:
            combined_df = pd.concat(data_frames)
            print("count of candles = ", len(combined_df))
            return combined_df
        else:
            return pd.DataFrame()

    def timestamp_from_date(self, date_str):
        # Convert a date string to a timestamp in milliseconds
        return int(pd.Timestamp(date_str).timestamp() * 1000)


class Portfolio:
    def __init__(self, config):
        self.usdt_balance = config.initial_usdt_balance
        self.commission_rate = config.commission_rate
        self.btc_balance = 0
        self.total_buy = 0
        self.total_sell = 0

    def buy_btc(self, price, amount):
        cost = price * amount
        if cost > self.usdt_balance:
            return False
        commission = amount * self.commission_rate
        self.btc_balance += amount - commission
        self.usdt_balance -= cost
        self.total_buy += 1
        print("buy")
        return True

    def sell_btc(self, price, amount):
        if amount > self.btc_balance:
            amount = self.btc_balance
        commission = amount * price * self.commission_rate
        self.btc_balance -= amount
        self.usdt_balance += price * amount - commission
        self.total_sell += 1
        print("sell")
        return True


class TradingStrategy:
    def __init__(self, exchange, portfolio, config):
        self.exchange = exchange
        self.portfolio = portfolio
        self.initial_usdt_balance = config.initial_usdt_balance
        self.fixed_price = config.initial_usdt_balance / len(
            config.entry_intervals_down
        )
        self.entry_intervals_down = config.entry_intervals_down
        self.grid_down = self.calculate_grid(
            config.start_usdt_btc_price, config.entry_intervals_down
        )
        self.is_strategy_in_progress = False
        self.open_sell_orders = []
        self.sell_price_percent = 1 + config.entry_intervals_up
        self.price_history = []
        self.count_for_std = config.count_for_std
        self.volatility_threshold = config.volatility_threshold

    def should_start_trading(self):
        count_for_std = self.count_for_std
        if len(self.price_history) < count_for_std:
            return False

        # standard deviation
        std_dev = np.std(self.price_history[-count_for_std:])

        if std_dev < self.volatility_threshold:
            print("Start trading - Low volatility detected")
            return True
        return False

    def add_result(self, results, timestamp, action, current_price, current_line_ind):
        results.append(
            {
                "timestamp": timestamp,
                "action": action,
                "current_price": current_price,
                "btc_balance": self.portfolio.btc_balance,
                "usdt_balance": round(self.portfolio.usdt_balance, 2),
                "current_line_ind": current_line_ind,
            }
        )

    def simulate(self, data):
        results = []
        current_line_ind = 0
        current_price = 0

        for index, row in data.iterrows():
            current_price = row["close"]
            self.price_history.append(current_price)

            # Check for new entry point
            if not self.is_strategy_in_progress and self.should_start_trading():
                self.grid_down = self.calculate_grid(
                    row["close"], config.entry_intervals_down
                )
                current_line_ind = 0
                self.print_grid(index, row)

            # Buy BTC
            # move to next grid line
            if (
                current_line_ind < len(self.grid_down) - 1
            ) and current_price <= self.grid_down[current_line_ind + 1]:
                step, current_line_ind = self.get_step_down(
                    current_price, self.grid_down, current_line_ind
                )
                btc_to_buy = self.fixed_price * step / current_price

                # Buy
                if self.portfolio.buy_btc(current_price, btc_to_buy):
                    # create order to sell
                    sell_price = current_price * self.sell_price_percent
                    self.open_sell_orders.append(
                        {
                            "buy_price": current_price,
                            "sell_price": sell_price,
                            "btc_to_sell": btc_to_buy,
                        }
                    )
                    self.add_result(
                        results, index, "buy", current_price, current_line_ind
                    )
                    self.is_strategy_in_progress = True

            # Move up grid line
            if current_price >= self.grid_down[current_line_ind - 1]:
                current_line_ind = self.get_step_up(
                    current_price, self.grid_down, current_line_ind
                )

            # Sell BTC (Check open sell orders)
            for order in self.open_sell_orders:
                if current_price >= order["sell_price"]:
                    # Sell BTC for the corresponding sell price
                    if self.portfolio.sell_btc(current_price, order["btc_to_sell"]):
                        self.add_result(
                            results, index, "sell", current_price, current_line_ind
                        )
                        self.open_sell_orders.remove(order)

                # Finish grid circle
                if self.portfolio.btc_balance == 0:
                    self.is_strategy_in_progress = False

        results_df = pd.DataFrame(results)
        results_df.to_csv("strategy_results.csv", index=False)
        print("Simulation done")
        self.print_summary(current_price, data)

    def calculate_grid(self, usdt_btc_price, entry_intervals_down):
        grid = []
        cur_line = usdt_btc_price
        grid.append(cur_line)
        for interval_perc in entry_intervals_down:
            step_grid = usdt_btc_price * interval_perc
            grid.append(round(cur_line - step_grid, 2))
            cur_line = cur_line - step_grid
        return grid

    def print_grid(self, index, row):
        print("New Grid.  Timestep: ", index, end="  ")
        print(
            "open=", row["open"],
            " close=", row["close"],
            " high=", row["high"],
            " low=", row["low"],
        )
        print("grid_levels: ", self.grid_down)

    @staticmethod
    def get_step_down(current_price, grid, current_line_ind):
        step = 0
        print("current_line_ind: ", current_line_ind)
        while (current_line_ind < len(grid) - 1) and (
            current_price <= grid[current_line_ind + 1]
        ):
            current_line_ind += 1
            step += 1
        return step, current_line_ind

    @staticmethod
    def get_step_up(current_price, grid, current_line_ind):
        while current_price >= grid[current_line_ind] and current_line_ind > 0:
            current_line_ind -= 1
            if current_price < grid[current_line_ind - 1]:
                break
        return current_line_ind

    def print_summary(self, last_price, data):
        final_btc_balance = self.portfolio.btc_balance
        final_usdt_balance = self.portfolio.usdt_balance
        initial_usdt_balance = self.initial_usdt_balance

        # Calculate the current value of remaining BTC in USDT
        if final_btc_balance > 0:
            btc_value_in_usdt = final_btc_balance * last_price
            total_usdt_balance = final_usdt_balance + btc_value_in_usdt
        else:
            total_usdt_balance = final_usdt_balance

        open_order_count = len(self.open_sell_orders)
        profit_or_loss = total_usdt_balance - initial_usdt_balance

        # Calculate percentage profit
        percentage_profit = (profit_or_loss / initial_usdt_balance) * 100

        # Calculate the profit per year
        total_hours_loaded = len(data)
        years_loaded = total_hours_loaded / (24 * 365)
        annualized_profit_perc = (
                (profit_or_loss / (years_loaded * initial_usdt_balance)) * 100
        )

        print("------ Final Summary: ------")
        print(f"    Total buy orders: {self.portfolio.total_buy}")
        print(f"    Total sell orders: {self.portfolio.total_sell}")
        print(f"    Remaining open orders: {open_order_count}")
        print(f"    Initial USDT balance: {initial_usdt_balance:.0f}")
        print(f"    Final USDT balance: {final_usdt_balance:.0f}")
        print(f"    Final BTC balance: {final_btc_balance:.4f}")
        print(f"    Absolute Profit/Loss: {profit_or_loss:.0f} USDT")
        print(f"    Percentage Profit/Loss: {percentage_profit:.2f}%")
        print(f"    Annualized Profit/Loss: {annualized_profit_perc:.2f}% per year")


if __name__ == "__main__":
    exchange = Exchange()
    portfolio = Portfolio(config)
    strategy = TradingStrategy(exchange, portfolio, config)
    historical_data = exchange.fetch_historical_data(config)
    strategy.simulate(historical_data)
