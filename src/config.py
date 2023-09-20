class Config:
    symbol = 'BTC/USDT'
    timeframe = '1h'  # Хронологический интервал одной свечи
    limit = 24 * 30  # Количество свечей, для загрузки
    start_date = '2023-02-01'
    initial_usdt_balance = 15000  # USDT balance
    start_usdt_btc_price = 16000
    entry_intervals_down = [
            0.02, 0.02, 0.02, 0.02, 0.02, 0.04, 0.04, 0.04, 0.04, 0.04, 0.06, 0.06, 0.06, 0.06, 0.06
        ]
    entry_intervals_up = 0.04
    commission_rate = 0.001
