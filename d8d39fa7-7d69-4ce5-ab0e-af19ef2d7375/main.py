#Type 
import pandas as pd
import numpy as np

# Data Setup
dates = pd.date_range('2025-09-29', '2025-10-06', freq='B')[:6]

spy_data = pd.DataFrame({
    'Open': [664.36, 662.93, 663.17, 668.29, 669.99, 669.50],
    'High': [665.28, 666.65, 669.37, 669.45, 672.675, 671.00],
    'Low': [661.86, 661.61, 663.06, 667.45, 668.16, 668.80],
    'Close': [663.68, 666.18, 668.45, 669.45, 669.21, 670.25]
}, index=dates)

nvda_data = pd.DataFrame({
    'Open': [180.43, 181.85, 185.7492, 186.9497, 188.9785, 188.9785],
    'High': [184.00, 185.75, 187.00, 189.00, 190.00, 190.50],
    'Low': [180.35, 180.50, 184.50, 186.00, 188.00, 187.50],
    'Close': [181.85, 185.7492, 186.9497, 188.9785, 187.489, 189.00]
}, index=dates)

# Static Indicators
spy_data['RSI'], spy_data['ATR'], spy_data['Vol20'] = 50, 5.00, 1.5
nvda_data['RSI'], nvda_data['ATR'], nvda_data['Vol20'] = 50, 1.50, 5.5
nvda_data.loc['2025-10-03', 'RSI'] = 39

class WVV15:
    def __init__(self, initial_cash=10000, trade_size_pct=0.2667, tbil_price=50.00, tbil_rate=0.000198413):
        self.name = 'WVV1.5'
        self.cash = initial_cash
        self.trade_size_pct = trade_size_pct
        self.tbil_price = tbil_price
        self.tbil_rate = tbil_rate
        self.holdings = {'SPY': 0, 'NVDA': 0, 'TBIL': 0}
        self.cost_basis = {'SPY': 0, 'NVDA': 0, 'TBIL': tbil_price}
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
            if stock == 'TBIL':
                value += shares * self.tbil_price * (1 + self.tbil_rate)
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

        if self.cash >= self.tbil_price:
            tbil_shares = self.cash / self.tbil_price
            cost = self.cash * 0.008
            self.holdings['TBIL'] += tbil_shares
            self.cash -= self.cash
            self.costs += cost
            self.alerts.append(f"Buy {tbil_shares:.4f} shares of TBIL at ${self.tbil_price:.2f}.")

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
            self.select_stock(date, spy_data, nvda_data)
            if self.current_stock != 'SPY':
                shares_to_sell = self.holdings['SPY']
                proceeds = shares_to_sell * spy_data.loc[date, 'Close']
                cost = proceeds * 0.008
                self.cash = proceeds - cost
                self.costs += cost
                self.holdings['SPY'] = 0
                self.alerts.append(f"Switch stock from SPY to {self.current_stock}. Sell {shares_to_sell:.4f} shares of SPY at ${spy_data.loc[date, 'Close']:.2f}.")
                shares_to_buy = self.cash / prices[self.current_stock]
                cost = self.cash * 0.008
                self.holdings[self.current_stock] = shares_to_buy
                self.cost_basis[self.current_stock] = prices[self.current_stock]
                self.cash -= self.cash
                self.costs += cost
                self.alerts.append(f"Buy {shares_to_buy:.4f} shares of {self.current_stock} at ${prices[self.current_stock]:.2f}.")
        self.update_portfolio_value(prices)
        self.alerts.append(f"Daily Trading Alert: {date.strftime('%Y-%m-%d')}. Portfolio Value: ${self.portfolio_value:.2f}. Trade size realigned to ${self.trade_size:.2f}.")
        data = {'SPY': spy_data, 'NVDA': nvda_data}
        self.execute_trade(date, prices, data[self.current_stock])
        self.update_portfolio_value(prices)
        return self.alerts

# Run Simulation
wvv15 = WVV15()
print("=== WVV1.5 Simulation ===")
for date in dates:
    alerts = wvv15.simulate_day(date, spy_data, nvda_data)
    for alert in alerts:
        print(alert)

# Performance Summary
print("\nWVV1.5 Performance Summary")
print(f"Final Value: ${wvv15.portfolio_value:.2f}")
print(f"Return: {(wvv15.portfolio_value / 10000 - 1) * 100:.2f}%")
print(f"Costs: ${wvv15.costs:.2f}")
print(f"Holdings: {wvv15.holdings}")