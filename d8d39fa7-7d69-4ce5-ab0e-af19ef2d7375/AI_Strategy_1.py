from surmount.base_class import Strategy, TargetAllocation
from surmount.technical_indicators import RSI, EMA, SMA, MACD, ATR
from surmount.logging import log

class WVV13Strategy(Strategy):
    def __init__(self):
        # Define the asset rotation based on availability during the Dotcom Crash
        self.tickers = ["MSTR", "SPY", "QQQ", "MSFT", "AAPL", "CSCO"]
        # Initialize additional parameters if needed

    @property
    def assets(self):
        return self.tickers

    @property
    def interval(self):
        return "1week"  # Weekly scanning as mentioned

    @property
    def data(self):
        # Returning empty list since no additional data sources specified
        return []

    def run(self, data):
        # Dictionary to hold the target allocations
        allocation_dict = {ticker: 0 for ticker in self.tickers}
        
        # Process each ticker
        for ticker in self.tickers:
            ohlcv = data["ohlcv"][ticker]
            try:
                # Calculate technical indicators
                macd = MACD(ticker, ohlcv, fast=12, slow=26)["MACD"][-1]
                sma = SMA(ticker, ohlcv, length=50)[-1]
                rsi = RSI(ticker, ohlcv, length=14)[-1]
                atr = ATR(ticker, ohlcv, length=14)[-1]

                # Implement trading logic based on the strategy's criteria
                if macd > 0 and ohlcv[-1]["close"] > sma and rsi < 40:
                    allocation = 0.35 if ohlcv[-1]["volatility"] < 0.1 else 1
                    allocation_dict[ticker] = allocation
                    # Implement 3x ATR trailing stop-loss logic here
                    # Due to simplicity, let's indicate it as a logging operation
                    log(f"3x ATR SL for {ticker}: {3*atr}")
                    # Note: Handling of $2,667 Extra Buy and partial shares is not directly implementable here.
                    # Needs more specific account/portfolio management functions not provided in this context

            except IndexError:
                # Handle case with insufficient data
                log(f"Insufficient data for {ticker}")

        return TargetAllocation(allocation_dict)

# To utilize this strategy, incorporate into your trading system or backtesting framework
# with the capacity to simulate trades and manage portfolio according to the strategy's logic.