import ccxt
import pandas as pd


def fetch_binance_historical_data(symbol, timeframe, limit):
    binance = ccxt.binance()
    ohlcv = binance.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(
        ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(
        df["timestamp"], unit="ms"
    )  # Convert timestamp to datetime
    df.set_index("timestamp", inplace=True)
    return df


symbol = "BTC/USDT"
timeframe = "1h"  # Хронологический интервал одной свечи
limit = 24 * 30  # Количество свечей, для загрузки

historical_data = fetch_binance_historical_data(symbol, timeframe, limit)


"""
Manual ccxt: https://github.com/ccxt/ccxt/wiki/Manual
timeframes': {
        '1m': '1minute',
        '1h': '1hour',
        '1d': '1day',
        '1M': '1month',
        '1y': '1year',
    }
    """
