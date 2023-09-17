import pandas as pd

from historical_data import historical_data


def get_step_down(current_price: float, grid: list[float], current_line_ind: int) -> int:
    step = 0
    while current_price <= grid[current_line_ind]:
        step += 1
        current_line_ind += 1
    return step


def simulate_strategy(dataframe):
    fixed_price = 100  # Фиксированная цена для каждой покупки и продажи (в USDT)
    start_price = dataframe.iloc[0]['close']  # Начальная цена
    entry_intervals_down = [0.02, 0.02, 0.02, 0.02, 0.02, 0.04, 0.04, 0.04, 0.04, 0.04, 0.06, 0.06, 0.06, 0.06, 0.06]
    entry_intervals_up = 0.04
    grid_up_step_usdt = start_price * entry_intervals_up

    # make fixed grid for down
    grid_down = []  # grid_down = [29400.0, 28800.0, 28200.0, 27600.0, 27000.0, 25800.0, 24600.0, 23400.0, 22200.0, 21000.0, 19200.0, 17400.0, 15600.0, 13800.0, 12000.0]
    cur_line = start_price
    for interval_perc in entry_intervals_down:
        step_grid = start_price * interval_perc
        grid_down.append(cur_line - step_grid)
        cur_line = cur_line - step_grid

    exit_percentage = 0.04  # Процент для выхода из каждой позиции
    commission_rate = 0.001  # Комиссия (0.1%)

    # Список для хранения результатов
    results = []

    # Начальные значения
    btc_balance = 0
    usdt_balance = 0  # Теперь начальный баланс USDT равен 0
    current_line_ind = 0
    current_line = grid_down[current_line_ind]

    # Итерируйтесь по историческим данным
    for index, row in dataframe.iterrows():
        current_price = row['close']

        # Проверка условия для размещения ордера на покупку
        if current_price <= grid_down[current_line_ind + 1]:

            step = get_step_down(current_price, grid_down, current_line_ind)
            current_line_ind += step

            # Рассчитайте количество BTC, которое вы можете купить по фиксированной цене
            btc_to_buy = fixed_price / current_price
            # Рассчитайте комиссию за покупку
            commission = btc_to_buy * commission_rate
            # Покупка BTC
            btc_balance += btc_to_buy - commission
            usdt_balance -= fixed_price
            # Запись результатов
            results.append(
                {'timestamp': index, 'action': 'buy', 'current_price': current_price, 'btc_balance': btc_balance,
                 'usdt_balance': usdt_balance})
            current_line += step


        # Проверка условия для размещения ордера на продажу
        if current_price >= grid_down[current_line_ind] + grid_up_step_usdt and btc_balance > 0:
            step = int((current_price - grid_down[current_line_ind]) // grid_up_step_usdt)
            current_line_ind -= step

            # Рассчитайте количество BTC, которое вы продаете
            btc_to_sell = min(btc_balance, fixed_price * step / current_price)
            # Рассчитайте комиссию за продажу
            commission = btc_to_sell * current_price * commission_rate
            # Продажа BTC
            usdt_balance += (btc_to_sell * current_price) - commission
            btc_balance -= btc_to_sell
            # Запись результатов
            results.append(
                {'timestamp': index, 'action': 'sell', 'current_price': current_price, 'btc_balance': btc_balance,
                 'usdt_balance': usdt_balance})
            current_line -= step


    # Создайте DataFrame из результатов и сохраните его в CSV файл
    results_df = pd.DataFrame(results)
    results_df.to_csv('strategy_results.csv', index=False)
    print("simulation done")



if __name__ == '__main__':
    simulate_strategy(historical_data)



