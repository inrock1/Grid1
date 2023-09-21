class Config:
    symbol = "BTC/USDT"
    timeframe = "1h"  # Chronological interval of one candle
    limit = 24 * 30 * 15  # Number of candles to load
    start_date = "2022-07-01"
    initial_usdt_balance = 15000  # USDT balance
    start_usdt_btc_price = 20000
    entry_intervals_down = [
        0.02, 0.02, 0.02, 0.02, 0.02,
        0.04, 0.04, 0.04, 0.04, 0.04,
        0.06, 0.06, 0.06, 0.06, 0.06,
    ]
    entry_intervals_up = 0.04
    commission_rate = 0.001
    volatility_threshold = 100
    count_for_std = 6  # count of last price for calculate standard deviation
