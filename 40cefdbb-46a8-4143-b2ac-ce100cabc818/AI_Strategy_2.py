from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import SMA, RSI, MACD, ATR
from surmount.data import Asset
from datetime import timedelta
import numpy as np

class VolatilityBasedPositionSizing(Strategy):
    def __init__(self):
        self.assets = ["PLTR", "TSLA", "SMCI", "ENPH", "MU", "LRCX", "QQQ", "VIX", "TBIL"]
        self.interval = "1day"
        self.risk_percentage = 0.02  # Default risk percentage, adjustable from 0.01 to 0.05
        self.restricted_stocks = {}  # To manage wash sale rule
    
    @property
    def data(self):
        return []

    def is_bull_regime(self, data):
        """Determines if the market is in a bull regime based on SMA, VIX change, put/call ratio, and RSI."""
        sma20 = SMA("QQQ", data, 20)[-1]
        sma50 = SMA("QQQ", data, 50)[-1]
        vix_change = (data["VIX"][-1]["close"] - data["VIX"][-15]["close"]) / data["VIX"][-15]["close"]
        put_call_ratio = 0.9  # This should be adjusted based on actual data, approximated here
        rsi14 = RSI("QQQ", data, 14)[-1]
        return sma20 > sma50 and vix_change < -0.1 and put_call_ratio < 1.2 and rsi14 > 30

    def is_bear_regime(self, data):
        """Determines if the market is in a bear regime."""
        sma20 = SMA("QQQ", data, 20)[-1]
        sma50 = SMA("QQQ", data, 50)[-1]
        vix_change = (data["VIX"][-1]["close"] - data["VIX"][-15]["close"]) / data["VIX"][-15]["close"]
        put_call_ratio = 1.3  # This needs actual data, approximated here for the example
        rsi14 = RSI("QQQ", data, 14)[-1]
        return sma20 < sma50 or (vix_change > 0.2 and put_call_ratio > 1.2 and rsi14 < 30)

    def calculate_volatility(self, ticker, data):
        """Calculates 20-day historical volatility (annualized)."""
        returns = np.log(np.array([x["close"] for x in data[-21:]]) / np.array([x["close"] for x in data[-22:-1]]))
        volatility = np.std(returns) * np.sqrt(252)
        return volatility

    def calculate_position_size(self, ticker, data, portfolio_value):
        """Calculates the position size based on volatility and asset price."""
        volatility = self.calculate_volatility(ticker, data)
        asset_price = data[-1]["close"]
        position_size = (portfolio_value * self.risk_percentage) / (volatility * asset_price)
        return min(1.0, position_size)  # Ensure the position size does not exceed 100% of the portfolio

    def run(self, data):
        portfolio_value = 100000  # Example portfolio value, should be dynamically adjusted
        allocation = {}

        if self.is_bear_regime(data):
            allocation["TBIL"] = 1  # Move entirely into TBIL in bear market regimes
        elif self.is_bull_regime(data):
            # Find the highest volatility stock for allocation, excluding restricted stocks
            max_volatility = 0
            selected_stock = None
            for asset in self.assets[:-3]:  # Exclude QQQ, VIX, and TBIL from selection
                if asset in self.restricted_stocks and self.restricted_stocks[asset] > data["date"][-1]:
                    continue  # Skip restricted stocks

                vol = self.calculate_volatility(asset, data)
                if vol > max_volatility:
                    max_volatility = vol
                    selected_stock = asset

            if selected_stock:
                allocation[selected_stock] = self.calculate_position_size(selected_stock, data, portfolio_value)
        
        return TargetAllocation(allocation)