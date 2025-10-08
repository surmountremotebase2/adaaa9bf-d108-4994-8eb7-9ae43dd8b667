from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import RSI, SMA, MACD, ATR
from surmount.logging import log

class WVV13Strategy(Strategy):
    def __init__(self):
        self.initial_tickers = ["MSTR", "SPY", "RGTI", "PSIX", 
                                "AAPL", "MSFT", "NVDA", "AMZN", "META", 
                                "AVGO", "TSLA", "GOOGL", "GOOG", "COST", 
                                "NFLX", "AMD", "PEP", "ADBE", "LIN", "QCOM", 
                                "TMUS", "AMGN", "CSCO", "TXN"]
        self.excluded_tickers = ["RGTI", "PSIX", "TSLA", "META", "AVGO", "GOOG", "NFLX", "LIN"]
        self.available_tickers = [ticker for ticker in self.initial_tickers if ticker not in self.excluded_tickers]
        self.tickers = self.available_tickers  # This may be dynamically updated based on the date range for backtesting

    @property
    def interval(self):
        return "1week"  # Assuming weekly scanning for QQQ holdings adjustments

    @property
    def assets(self):
        # This could be dynamically updated if the strategy requires
        return self.tickers

    @property
    def data(self):
        # Additional data sources can be specified if needed
        return []

    def run(self, data):
        allocation_dict = {}
        extra_buy_amount = 2667
        atr_multiplier = 3  # 3x ATR for stop loss
        rsi_threshold = 40
        vol_threshold = 0.1  # 10%

        for ticker in self.tickers:
            ohlcv_data = data["ohlcv"]
            if len(ohlcv_data) < 2:  # Make sure there's enough data
                continue

            # Calculate technical indicators
            rsi = RSI(ticker, ohlcv_data, 14)[-1]
            atr = ATR(ticker, ohlcv_data, 14)[-1] * atr_multiplier
            macd_dict = MACD(ticker, ohlcv_data, 12, 26)
            sma = SMA(ticker, ohlcv_data, 50)[-1]
            current_price = ohlcv_data[-1][ticker]["close"]
            previous_price = ohlcv_data[-2][ticker]["close"]

            # Decision-making logic
            if rsi < rsi_threshold and macd_dict["MACD"][-1] > macd_dict["signal"][-1] and current_price > sma:
                # Calculate position size based on extra buy, volatility, and ATR
                vol = (abs(current_price - previous_price) / previous_price)
                size_scaling = 0.35 if vol < vol_threshold else 1
                # Assuming 'extra_buy_amount' is a monetary value, not shares; calculation for shares not shown
                position_size = size_scaling  # Simplify. In actual implementation, calculate based on account value and risk management rules.
                allocation_dict[ticker] = position_size
            else:
                allocation_dict[ticker] = 0

        return TargetAllocation(allocation_dict)