from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import SMA, RSI, ATR, HistoricalVolatility
from surmount.data import OHLCV, PutCallRatio, VIX
import numpy as np

class VolatilityBasedPositionSizing(Strategy):
    def __init__(self, starting_portfolio_value=1000, risk_percentage=0.02):
        self.assets = ["QQQ", "TBIL", "PLTR", "TSLA", "SMCI", "ENPH", "MU", "LRCX"]
        self.interval = "1day"
        self.starting_portfolio_value = starting_portfolio_value
        self.risk_percentage = risk_percentage
        self.restricted_stocks = []  # To handle wash sale rule
        self.last_traded_prices = {}  # To calculate losses and apply the wash sale rule

    @property
    def data(self):
        return [OHLCV(asset) for asset in self.assets] + [PutCallRatio(), VIX()]

    def run(self, data):
        # 1. Determine the market regime
        regime = self.determine_regime(data)

        # 2. Select the asset based on the regime
        selected_asset, asset_volatility = self.select_asset(data, regime)

        # 3. Calculate the position size
        current_portfolio_value = self.starting_portfolio_value  # This would be updated based on actual portfolio performance
        asset_price = data["ohlcv"][selected_asset][-1]["close"]  # Using the latest closing price
        position_size = self.calculate_position_size(current_portfolio_value, self.risk_percentage, asset_volatility, asset_price)

        # 4. Apply the position to the selected asset
        allocation = {asset: 0 for asset in self.assets}  # Initialize all assets to 0 allocation
        allocation[selected_asset] = position_size

        # Update the last traded price for the selected asset
        self.last_traded_prices[selected_asset] = asset_price

        return TargetAllocation(allocation)

    def determine_regime(self, data):
        # Logic to determine the current market regime based on the input data
        # Should return a string like "bull" or "bear" based on criteria such as SMA comparison, VIX change, put/call ratio, and RSI
        pass

    def select_asset(self, data, regime):
        # Depending on the regime, select either the high-volatility asset or TBIL
        # For the high-volatility pool, it might also involve selecting the asset with the highest 20-day historical volatility that is not restricted
        pass

    def calculate_position_size(self, portfolio_value, risk_percentage, volatility, asset_price):
        return min(1.0, (portfolio_value * risk_percentage) / (volatility * asset_price))