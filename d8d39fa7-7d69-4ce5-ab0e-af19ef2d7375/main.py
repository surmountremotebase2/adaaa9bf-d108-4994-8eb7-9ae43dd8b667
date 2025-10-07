import pandas as pd
import numpy as np

# Data Setup (2009-12-29 to 2012-08-30)
dates = pd.date_range('2009-12-29', '2012-08-30', freq='B')
# Approximate SPY prices (based on historical data, adjusted)
spy_prices = np.linspace(110, 141, len(dates))  # Linear approximation from $110 to $141
spy_data = pd.DataFrame({
    'Open': spy_prices,
    'High': spy_prices + 0.5,
    'Low': spy_prices - 0.5,
    'Close': spy_prices,
    'RSI': [60.89, 77.37, 77.42] + [50] * (len(dates) - 3),  # From log, then assume 50
    'ATR': [1.132, 0.01, 0.01] + [0.01] * (len(dates) - 3),   # From log, then assume 0.01
    'Vol20': [1.5] * len(dates)
}, index=dates)

nvda_data = pd.DataFrame({
    'Open': [0.015] * len(dates),  # Approx NVDA price, post-split adjusted
    'High': [0.016] * len(dates),
    'Low': [0.014] * len(dates),
    'Close': [0.015 + i * 0.00005 for i in range(len(dates))],
    'RSI': [60.89, 77.37, 52.68, 74.21, 75.75, 76.42, 69.97, 70.26, 65.78, 56.52, 58.93, 55.09, 48.75, 52.38, 51.46, 47.78, 41.58, 45.21, 40.13, 45.60, 40.53, 35.25, 47.63, 49.14, 50.41, 42.44, 45.47] + [50] * (len(dates) - 27),
    'ATR': [0.01] * len(dates),
    'Vol20': [0.06, 0.07, 0.06, 0.06, 0.06, 0.06, 0.06, 0.06, 0.06, 0.06, 0.07, 0.07, 0.07, 0.07, 0.07, 0.07, 0.07, 0.07, 0.07, 0.07, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08] + [0.05] * (len(dates) - 27)
}, index=dates)

class WVV15:
    def __init__(self, initial_cash=10000, trade_size_pct=0.2667, bil_price=45.00, bil_rate=0.000198413):
        self.name = 'WVV1.5'
        self.cash = initial_cash
        self.trade_size_pct = trade_size_pct
        self.bil_price = bil_price
        self.bil_rate = bil_rate
        self.holdings = {'SPY': 0, 'NVDA': 0, 'BIL': 0}
        self.cost_basis = {'SPY': 0, 'NVDA': 0, 'BIL': bil_price}
        self.portfolio_value = initial_cash
        self.trade_size = initial_cash * trade_size_pct
        self.consecutive_up_days = 0
        self.consecutive_down_days = 0
        self.stop_loss = None
        self.current_stock = 'SPY'
        self.costs = 0
        self.alerts = []
        self.highest_price = None

    def update_portfolio_value(self, prices):
        value = self.cash
        for stock, shares in self.holdings.items():
            if stock == 'BIL':
                value += shares * self.bil_price * (1 + self.bil_rate)
            else:
                value += shares * prices.get(stock, 0)
        self.portfolio_value = value
        self.trade_size = self.portfolio_value * self.trade_size_pct
        if prices.get(self.current_stock + '_Vol20', 0) > 4:
            self.trade_size *= 0.75

    def select_stock(self, date, spy_data, nvda_data):
        stocks = [('SPY', spy_data), ('NVDA', nvda_data)]
        volatilities = [(stock, data.loc[date, 'Vol20']) for stock, data in stocks if date in data.index]
        self.current_stock = max(volatilities, key=lambda x: x[1])[0]

    def execute_trade(self, date, prices, data):
        price = prices[self.current_stock]
        rsi = data.loc[date, 'RSI']
        atr = data.loc[date, 'ATR']
        prev_close = data.loc[date, 'Close'] if date == data.index[0] else data.loc[data.index[data.index.get_loc(date) - 1], 'Close']
        daily_return = (data.loc[date, 'Close'] - prev_close) / prev_close if prev_close else 0

        if daily_return > 0:
            self.consecutive_up_days += 1
            self.consecutive_down_days = 0
        elif daily_return < 0:
            self.consecutive_down_days += 1
            self.consecutive_up_days = 0
        else:
            self.consecutive_down_days = 0
            self.consecutive_up_days = 0

        if self.holdings[self.current_stock] > 0:
            self.highest_price = max(self.highest_price or price, data.loc[date, 'High'])
            self.stop_loss = self.highest_price - 3 * atr

        if self.holdings[self.current_stock] > 0 and data.loc[date, 'Low'] <= self.stop_loss:
            shares_to_sell = self.holdings[self.current_stock]
            proceeds = shares_to_sell * data.loc[date, 'Close']
            cost = proceeds * 0.008
            self.cash += proceeds - cost
            self.costs += cost
            self.alerts.append(f"Stop-loss triggered: Sell {shares_to_sell:.4f} shares of {self.current_stock} at ${data.loc[date, 'Close']:.2f}.")
            self.holdings[self.current_stock] = 0
            self.stop_loss = None
            self.highest_price = None
            self.consecutive_up_days = 0
            self.consecutive_down_days = 0

        if self.consecutive_up_days >= 2 and self.holdings[self.current_stock] > 0:
            shares_to_sell = min(self.holdings[self.current_stock], self.trade_size / data.loc[date, 'Close'])
            if self.consecutive_up_days > 2:
                shares_to_sell *= 0.5
            proceeds = shares_to_sell * data.loc[date, 'Close']
            cost = proceeds * 0.008
            self.cash += proceeds - cost
            self.holdings[self.current_stock] -= shares_to_sell
            self.costs += cost
            self.alerts.append(f"Sell {shares_to_sell:.4f} shares of {self.current_stock} at ${data.loc[date, 'Close']:.2f}.")

        if self.consecutive_down_days >= 1 and rsi < 40 and self.cash >= self.trade_size:
            shares_to_buy = self.trade_size / price
            cost = self.trade_size * 0.008
            if self.cash >= self.trade_size + cost:
                self.holdings[self.current_stock] += shares_to_buy
                self.cash -= self.trade_size + cost
                self.costs += cost
                self.cost_basis[self.current_stock] = (self.cost_basis[self.current_stock] * self.holdings[self.current_stock] + self.trade_size) / (self.holdings[self.current_stock] + shares_to_buy)
                self.alerts.append(f"Buy {shares_to_buy:.4f} shares of {self.current_stock} at ${price:.2f}.")
                self.highest_price = data.loc[date, 'High']
                self.stop_loss = self.highest_price - 3 * atr

        if self.cash >= self.bil_price:
            bil_shares = self.cash / self.bil_price
            cost = self.cash * 0.008
            self.holdings['BIL'] += bil_shares
            self.cash -= self.cash
            self.costs += cost
            self.alerts.append(f"Buy {bil_shares:.4f} shares of BIL at ${self.bil_price:.2f}.")

    def simulate_day(self, date, spy_data, nvda_data):
        self.alerts = []
        prices = {
            'SPY': spy_data.loc[date, 'Open'] if date in spy_data.index else 0,
            'NVDA': nvda_data.loc[date, 'Open'] if date in nvda_data.index else 0,
            'SPY_Close': spy_data.loc[date, 'Close'] if date in spy_data.index else 0,
            'NVDA_Close': nvda_data.loc[date, 'Close'] if date in nvda_data.index else 0,
            'SPY_Vol20': spy_data.loc[date, 'Vol20'] if date in spy_data.index else 0,
            'NVDA_Vol20': nvda_data.loc[date, 'Vol20'] if date in nvda_data.index else 0
        }
        if date == dates[0]:
            self.holdings['SPY'] = self.cash / prices['SPY']
            self.cost_basis['SPY'] = prices['SPY']
            self.cash = 0
            self.alerts.append(f"Initial buy: {self.holdings['SPY']:.4f} shares of SPY at ${prices['SPY']:.2f}.")
        self.update_portfolio_value(prices)
        self.select_stock(date, spy_data, nvda_data)
        self.alerts.append(f"Daily Trading Alert: {date.strftime('%Y-%m-%d')}. Portfolio Value: ${self.portfolio_value:.2f}. Trade size realigned to ${self.trade_size:.2f}. Selected: {self.current_stock}")
        data = {'SPY': spy_data, 'NVDA': nvda_data}
        self.execute_trade(date, prices, data[self.current_stock])
        self.update_portfolio_value(prices)
        return self.alerts

# Run Simulation
wvv15 = WVV15()
print("=== WVV1.5 Single-Asset Simulation (2009-12-29 to 2012-08-30) ===")
for date in dates[:10]:  # Limited to first 10 days for brevity
    alerts = wvv15.simulate_day(date, spy_data, nvda_data)
    for alert in alerts:
        print(alert)

# Performance Summary
print("\nWVV1.5)