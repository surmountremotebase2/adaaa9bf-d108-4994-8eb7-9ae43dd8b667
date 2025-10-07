from surmount.base_class import Strategy, TargetAllocation
from surmount.logging import log
from surmount.technical_indicators import RSI, ATR, STDEV
import numpy as np

class TradingStrategy(Strategy):
    def __init__(self):
        self.tickers = ["SPY", "NVDA", "BIL"]  # Changed TBIL to BIL, which has data from 2007
        self.data_list = []  # No additional data sources
        self.trade_size_pct = 0.2667
        self.tbil_price = 91.50  # Approximate price for BIL
        self.tbil_min_weight = self.tbil_price / 10000.0  # Approximate minimum for $10k portfolio
        self.consecutive_up_days = 0
        self.consecutive_down_days = 0
        self.stop_loss = None
        self.highest_price = None
        self.prev_closes = {'SPY': 0.0, 'NVDA': 0.0}
        self.current_stock = 'SPY'

    @property
    def interval(self):
        return "1day"

    @property
    def assets(self):
        return self.tickers

    @property
    def data(self):
        return self.data_list

    def run(self, data):
        ohlcv = data.get("ohlcv", [])
        if not ohlcv:
            return TargetAllocation({t: 0.0 for t in self.tickers})

        current_data = ohlcv[-1]
        holdings = data.get("holdings", {t: 0.0 for t in self.tickers})

        # Compute volatility for selection
        def get_current_ind(ticker, indicator_func, length):
            try:
                ind_values = indicator_func(ticker, ohlcv, length)
                return ind_values[-1] if ind_values and len(ind_values) > 0 else np.nan
            except:
                return np.nan

        spy_vol20 = get_current_ind('SPY', STDEV, 20)
        nvda_vol20 = get_current_ind('NVDA', STDEV, 20)
        if np.isnan(spy_vol20):
            spy_vol20 = 1.5  # Fallback
        if np.isnan(nvda_vol20):
            nvda_vol20 = 5.5  # Fallback

        volatilities = [('SPY', spy_vol20), ('NVDA', nvda_vol20)]
        self.current_stock = max(volatilities, key=lambda x: x[1])[0]

        # Get current bar data for current_stock
        if self.current_stock not in current_data:
            # Fallback: hold current allocations
            alloc = {t: holdings.get(t, 0.0) for t in self.tickers}
            remaining = 1.0 - sum(alloc.values())
            if remaining >= self.tbil_min_weight:
                alloc['BIL'] += remaining
            return TargetAllocation(alloc)

        p = current_data[self.current_stock]
        price = p['open']
        high = p['high']
        low = p['low']
        close = p['close']

        # Indicators for current_stock
        rsi = get_current_ind(self.current_stock, RSI, 14)
        atr = get_current_ind(self.current_stock, ATR, 14)
        if np.isnan(rsi):
            rsi = 50.0 if self.current_stock == 'SPY' else 39.0  # Fallback, adjust as needed
        if np.isnan(atr):
            atr = 5.00 if self.current_stock == 'SPY' else 1.50  # Fallback
        vol20_current = spy_vol20 if self.current_stock == 'SPY' else nvda_vol20

        # Daily return
        prev_close = self.prev_closes[self.current_stock]
        daily_return = (close - prev_close) / prev_close if prev_close != 0 else 0
        self.prev_closes[self.current_stock] = close

        # Update consecutive days
        if daily_return > 0:
            self.consecutive_up_days += 1
            self.consecutive_down_days = 0
        elif daily_return < 0:
            self.consecutive_down_days += 1
            self.consecutive_up_days = 0
        else:
            self.consecutive_up_days = 0
            self.consecutive_down_days = 0

        current_holding = holdings.get(self.current_stock, 0.0)
        unallocated = 1.0 - sum(holdings.values())

        # Effective pct
        effective_pct = self.trade_size_pct
        if vol20_current > 4:
            effective_pct *= 0.75

        # Initialize allocation to current holdings
        allocation = {t: holdings.get(t, 0.0) for t in self.tickers}

        is_first = len(ohlcv) == 1
        if is_first:
            allocation = {t: 0.0 for t in self.tickers}
            allocation['SPY'] = 1.0
            # Switch if necessary
            if self.current_stock != 'SPY':
                allocation['SPY'] = 0.0
                allocation[self.current_stock] = 1.0
            # Set initial highest and stop after "buy"
            self.highest_price = high
            self.stop_loss = high - 3 * atr
        else:
            # Update highest if holding
            if current_holding > 0:
                self.highest_price = max(self.highest_price or price, high)
                self.stop_loss = self.highest_price - 3 * atr

            # Stop-loss check
            if current_holding > 0 and low <= self.stop_loss:
                allocation[self.current_stock] = 0.0
                self.stop_loss = None
                self.highest_price = None
                self.consecutive_up_days = 0
                self.consecutive_down_days = 0
            else:
                allocation[self.current_stock] = current_holding

            # Sell on consecutive up days
            if self.consecutive_up_days >= 2 and current_holding > 0:
                sell_pct = effective_pct
                if self.consecutive_up_days > 2:
                    sell_pct *= 0.5
                allocation[self.current_stock] = max(0.0, allocation[self.current_stock] - sell_pct)

            # Buy condition
            if (self.consecutive_down_days >= 1 and rsi < 40 and
                unallocated >= effective_pct):
                allocation[self.current_stock] += effective_pct
                self.highest_price = high
                self.stop_loss = high - 3 * atr

        # Allocate remaining to BIL if sufficient
        current_sum = sum(allocation.values())
        remaining = 1.0 - current_sum
        if remaining >= self.tbil_min_weight:
            allocation['BIL'] += remaining

        # Ensure total <= 1.0 (trim if over due to approximations)
        total = sum(allocation.values())
        if total > 1.0:
            scale = 1.0 / total
            allocation = {k: v * scale for k, v in allocation.items()}

        log(f"Date: {current_data.get('SPY', {}).get('date', 'N/A') if 'SPY' in current_data else 'N/A'}, Allocation: {allocation}, Current Stock: {self.current_stock}, RSI: {rsi:.2f}, ATR: {atr:.2f}")
        return TargetAllocation(allocation)