# Type code herimport backtrader as bt
import pandas as pd
from datetime import datetime, timedelta

class MACD_SMA_Strategy(bt.Strategy):
    params = (
        ('macd1', 12), ('macd2', 26), ('signal', 9),  # MACD parameters
        ('sma_period', 50),  # SMA period
        ('rsi_period', 14),  # RSI period
        ('rsi_threshold', 40),  # RSI < 40 filter
        ('atr_period', 14),  # ATR period for trailing stop
        ('atr_multiplier', 3),  # 3x ATR trailing stop
        ('initial_cash', 3000),  # Initial portfolio value
        ('extra_buy_ratio', 0.2667),  # 26.67% for Extra Buy
        ('rebalance_period', 90),  # Quarterly (90 days) realignment
    )

    def __init__(self):
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.macd1,
            period_me2=self.params.macd2,
            period_signal=self.params.signal
        )
        self.sma = bt.indicators.SMA(self.data.close, period=self.params.sma_period)
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
        self.atr = bt.indicators.ATR(self.data, period=self.params.atr_period)
        self.trailing_stop = None
        self.last_rebalance = self.data.datetime.date(0)
        self.order = None
        self.position_size = 0

    def next(self):
        portfolio_value = self.broker.getvalue()
        extra_buy_amount = self.params.initial_cash * self.params.extra_buy_ratio  # $800
        current_date = self.data.datetime.date(0)

        # Quarterly rebalance check (every 90 days)
        if (current_date - self.last_rebalance).days >= self.params.rebalance_period:
            target_size = portfolio_value * self.params.extra_buy_ratio  # 26.67% of current portfolio
            self.adjust_position(target_size)
            self.last_rebalance = current_date

        # Buy signal: MACD line crosses above signal line, price above SMA, RSI < 40
        if not self.position:
            if (self.macd.macd[0] > self.macd.signal[0] and
                self.macd.macd[-1] <= self.macd.signal[-1] and
                self.data.close[0] > self.sma[0] and
                self.rsi[0] < self.params.rsi_threshold):
                self.position_size = extra_buy_amount / self.data.close[0]
                self.order = self.buy(size=self.position_size)
                self.trailing_stop = self.data.close[0] - self.atr[0] * self.params.atr_multiplier

        # Sell signal: Trailing stop-loss or MACD line crosses below signal line
        elif self.position:
            # Update trailing stop
            self.trailing_stop = max(self.trailing_stop, self.data.close[0] - self.atr[0] * self.params.atr_multiplier)
            
            if (self.data.close[0] <= self.trailing_stop or
                (self.macd.macd[0] < self.macd.signal[0] and
                 self.macd.macd[-1] >= self.macd.signal[-1])):
                self.order = self.sell(size=self.position_size)
                self.position_size = 0
                self.trailing_stop = None

    def adjust_position(self, target_size):
        if self.position:
            current_size = self.position.size
            target_shares = target_size / self.data.close[0]
            if abs(target_shares - current_size) > 0.01:  # Adjust if difference is significant
                if target_shares > current_size:
                    self.order = self.buy(size=target_shares - current_size)
                else:
                    self.order = self.sell(size=current_size - target_shares)
                self.position_size = target_shares

# Backtesting setup
cerebro = bt.Cerebro()
data = bt.feeds.YahooFinanceData(dataname='SPY', fromdate=datetime(2020, 1, 1), todate=datetime(2025, 9, 30))
cerebro.adddata(data)
cerebro.addstrategy(MACD_SMA_Strategy)
cerebro.broker.setcash(3000)
cerebro.broker.setcommission(commission=0.001)  # 0.1% commission
cerebro.addsizer(bt.sizers.FixedSize, stake=1)  # Allow partial shares
cerebro.run()
cerebro.plot()e