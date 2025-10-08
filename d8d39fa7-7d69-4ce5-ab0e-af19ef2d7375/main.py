import pandas as pd
import numpy as np
from ta.trend import MACD, ADX, SMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
# from twilio.rest import Client  # Uncomment for live
import datetime
import warnings
import logging
import csv
import os

# Suppress warnings
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    filename='wvv1_3_backtest.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Twilio configuration (uncomment for live)
# TWILIO_SID = "your_twilio_sid"
# TWILIO_AUTH_TOKEN = "your_twilio_auth_token"
# TWILIO_FROM = "your_twilio_phone_number"
# TWILIO_TO = "your_phone_number"
# client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

# Define tickers
qqq_tickers = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'META', 'AVGO', 'TSLA', 'GOOGL', 'GOOG', 'COST', 'NFLX', 'AMD', 'PEP', 'ADBE', 'LIN', 'QCOM', 'TMUS', 'AMGN', 'CSCO', 'TXN']
original_tickers = ['MSTR', 'SPY', 'RGTI', 'PSIX']
tickers = original_tickers + qqq_tickers

# Synthetic data parameters
start_prices = {
    'MSTR': 35.00, 'SPY': 426.66, 'RGTI': 1.00, 'PSIX': 5.00, 'TSLA': 900.00, 'NVDA': 80.00,
    'AAPL': 120.00, 'MSFT': 300.00, 'AMZN': 140.00, 'META': 400.00, 'AVGO': 120.00, 'GOOGL': 130.00,
    'GOOG': 130.00, 'COST': 600.00, 'NFLX': 500.00, 'AMD': 100.00, 'PEP': 140.00, 'ADBE': 400.00,
    'LIN': 300.00, 'QCOM': 140.00, 'TMUS': 150.00, 'AMGN': 260.00, 'CSCO': 40.00, 'TXN': 150.00
}
returns_mean = {
    'MSTR': 0.0015, 'SPY': 0.0006, 'RGTI': 0.001, 'PSIX': 0.0005, 'TSLA': 0.0025, 'NVDA': 0.002,
    'AAPL': 0.001, 'MSFT': 0.001, 'AMZN': 0.0015, 'META': 0.0015, 'AVGO': 0.001, 'GOOGL': 0.001,
    'GOOG': 0.001, 'COST': 0.0005, 'NFLX': 0.0015, 'AMD': 0.002, 'PEP': 0.0005, 'ADBE': 0.001,
    'LIN': 0.0005, 'QCOM': 0.001, 'TMUS': 0.0005, 'AMGN': 0.0005, 'CSCO': 0.0005, 'TXN': 0.0005
}
returns_std = {
    'MSTR': 0.025, 'SPY': 0.008, 'RGTI': 0.035, 'PSIX': 0.02, 'TSLA': 0.03, 'NVDA': 0.028,
    'AAPL': 0.015, 'MSFT': 0.015, 'AMZN': 0.02, 'META': 0.02, 'AVGO': 0.018, 'GOOGL': 0.015,
    'GOOG': 0.015, 'COST': 0.01, 'NFLX': 0.02, 'AMD': 0.025, 'PEP': 0.01, 'ADBE': 0.015,
    'LIN': 0.01, 'QCOM': 0.015, 'TMUS': 0.01, 'AMGN': 0.01, 'CSCO': 0.01, 'TXN': 0.01
}

# Generate synthetic data
logging.info("Generating synthetic data for tickers")
np.random.seed(42)  # For reproducibility
dates = pd.date_range(start='2023-10-01', end='2025-10-06', freq='B')[:508]
data = {}
for ticker in tickers:
    prices = [start_prices[ticker]]
    for _ in range(1, 508):
        ret = np.random.normal(returns_mean[ticker], returns_std[ticker])
        prices.append(prices[-1] * (1 + ret))
    df = pd.DataFrame({
        'Open': [p * (1 + np.random.uniform(-0.01, 0.01)) for p in prices],
        'Close': prices,
        'High': [p * (1 + np.random.uniform(0.03, 0.05)) for p in prices],
        'Low': [p * (1 - np.random.uniform(0.03, 0.05)) for p in prices]
    }, index=dates)
    df['macd'], df['macd_signal'], _ = MACD(df['Close'], window_slow=26, window_fast=12, window_sign=9).macd()
    df['sma_50'] = SMAIndicator(df['Close'], window=50).sma_indicator()
    df['rsi'] = RSIIndicator(df['Close'], window=14).rsi()
    df['adx'] = ADX(df['High'], df['Low'], df['Close'], window=14).adx()
    df['atr'] = AverageTrueRange(df['High'], df['Low'], df['Close'], window=14).average_true_range()
    df['volatility'] = df['Close'].pct_change().rolling(window=20).std() * np.sqrt(252) * 100
    data[ticker] = df

# Align indices to common dates
logging.info("Aligning data indices")
common_dates = data['MSTR'].index
for ticker in tickers:
    data[ticker] = data[ticker].loc[common_dates].ffill()

# Initialize portfolio
portfolio = {'cash': 10000, 'shares': 0, 'value': 10000, 'tbill': 0}
current_ticker = 'MSTR'
trade_size = 2667  # Initial 26.67% of $10,000
trades = []
highest_price = 0
stop_loss = 0
days_since_realign = 0
switch_cost = 0.005  # Not applied (zero fees/slippage per log)

logging.info("Starting backtest for WVV1.3: Oct 1, 2023 - Oct 6, 2025, initial investment $10,000")

# Trading loop
dates = common_dates
df_current = data[current_ticker]
for i in range(2, len(dates)):
    try:
        date = dates[i]
        open_price = df_current['Open'][i]
        close = df_current['Close'][i]
        high = df_current['High'][i]
        day_before_prev_close = df_current['Close'][i-2]
        prev_close = df_current['Close'][i-1]
        prev_rsi = df_current['rsi'][i-1]
        prev_adx = df_current['adx'][i-1]
        prev_volatility = df_current['volatility'][i-1]
        atr = df_current['atr'][i]
        volatility = df_current['volatility'][i]

        portfolio['value'] = portfolio['shares'] * close + portfolio['cash'] + portfolio['tbill']
        portfolio['tbill'] += portfolio['tbill'] * 0.000198413

        if day_before_prev_close > prev_close and prev_rsi < 40 and prev_adx < 30 and portfolio['cash'] >= trade_size:
            scale_factor = 0.35 if prev_volatility < 10 else 0.2667
            size = trade_size * 0.75 if prev_volatility > 4 else trade_size
            shares = size / open_price  # Zero fees/slippage
            portfolio['shares'] += shares
            portfolio['cash'] -= size
            portfolio['tbill'] += size
            highest_price = high
            stop_loss = high - 3 * atr
            trades.append((date, 'BUY', shares, open_price, portfolio['value']))
            print(f"{date} 09:20: Bought {shares:.2f} {current_ticker} at ${open_price:.2f}")
            logging.info(f"{date} 09:20: Bought {shares:.2f} {current_ticker} at ${open_price:.2f}")
            # Uncomment for live
            # message = f"{date} 09:20: Set limit order to buy {shares:.2f} {current_ticker} at ~${open_price:.2f} at open. Enter in IBKR."
            # client.messages.create(body=message, from_=TWILIO_FROM, to=TWILIO_TO)

        days_since_realign += 1
        if days_since_realign >= 21:
            current_vol = df_current['volatility'][i]
            scale_factor = 0.35 if current_vol < 10 else 0.2667
            trade_size = scale_factor * portfolio['value']
            vols = {}
            for ticker in tickers:
                if ticker in data and not data[ticker].empty:
                    vol = data[ticker]['volatility'][i]
                    if not np.isnan(vol):
                        vols[ticker] = vol
            if vols:
                max_ticker = max(vols, key=vols.get)
                max_vol = vols[max_ticker]
                if max_vol > 4 and max_ticker != current_ticker:
                    if portfolio['shares'] > 0:
                        proceeds = portfolio['shares'] * close  # Zero fees/slippage
                        portfolio['cash'] += proceeds
                        portfolio['tbill'] += proceeds
                        trades.append((date, f'SWITCH_SELL_{current_ticker}', portfolio['shares'], close, portfolio['value']))
                        print(f"{date} 15:50: Switched from {current_ticker}, sold {portfolio['shares']:.2f} at ${close:.2f}")
                        logging.info(f"{date} 15:50: Switched from {current_ticker}, sold {portfolio['shares']:.2f} at ${close:.2f}")
                        # Uncomment for live
                        # message = f"{date} 15:50: Switched from {current_ticker}, sold {portfolio['shares']:.2f} at ~${close:.2f}. Enter in IBKR."
                        # client.messages.create(body=message, from_=TWILIO_FROM, to=TWILIO_TO)
                    new_df = data[max_ticker]
                    new_close = new_df['Close'][i]
                    new_shares = (portfolio['cash'] * scale_factor * (1 / scale_factor)) / new_close  # Zero fees/slippage
                    portfolio['shares'] = new_shares
                    portfolio['cash'] -= portfolio['cash'] * scale_factor * (1 / scale_factor)
                    portfolio['tbill'] += portfolio['cash'] * scale_factor * (1 / scale_factor)
                    current_ticker = max_ticker
                    df_current = new_df
                    highest_price = new_df['High'][i]
                    stop_loss = highest_price - 3 * new_df['atr'][i]
                    trades.append((date, f'SWITCH_BUY_{current_ticker}', new_shares, new_close, portfolio['value']))
                    print(f"{date} 15:50: Switched to {current_ticker} (vol {max_vol:.1f}%)")
                    logging.info(f"{date} 15:50: Switched to {current_ticker} (vol {max_vol:.1f}%)")
                    # Uncomment for live
                    # message = f"{date} 15:50: Switched to {current_ticker} (vol {max_vol:.1f}%), buy {new_shares:.2f} at ~${new_close:.2f}. Enter in IBKR."
                    # client.messages.create(body=message, from_=TWILIO_FROM, to=TWILIO_TO)
            days_since_realign = 0
            print(f"{date} 15:50: Realigned trade size to ${trade_size:.2f} (scale: {scale_factor})")
            logging.info(f"{date} 15:50: Realigned trade size to ${trade_size:.2f} (scale: {scale_factor})")
            # Uncomment for live
            # message = f"{date} 15:50: Realigned trade size to ${trade_size:.2f} (scale: {scale_factor})"
            # client.messages.create(body=message, from_=TWILIO_FROM, to=TWILIO_TO)

        if portfolio['shares'] > 0:
            highest_price = max(highest_price, high)
            stop_loss = highest_price - 3 * atr

        if portfolio['shares'] > 0 and close <= stop_loss:
            sell_shares = portfolio['shares']
            proceeds = sell_shares * close  # Zero fees/slippage
            portfolio['cash'] += proceeds
            portfolio['tbill'] += proceeds
            portfolio['shares'] = 0
            highest_price = 0
            stop_loss = 0
            trades.append((date, 'STOP', sell_shares, close, portfolio['value']))
            print(f"{date} 15:50: Stop-loss on {current_ticker}, sold {sell_shares:.2f} at ${close:.2f}")
            logging.info(f"{date} 15:50: Stop-loss on {current_ticker}, sold {sell_shares:.2f} at ${close:.2f}")
            # Uncomment for live
            # message = f"{date} 15:50: Stop-loss on {current_ticker}, sell {sell_shares:.2f} at ~${close:.2f}. Enter in IBKR."
            # client.messages.create(body=message, from_=TWILIO_FROM, to=TWILIO_TO)

        if i >= 2 and df_current['Close'][i-2] < df_current['Close'][i-1] < close and portfolio['shares'] > 0:
            scale_factor = 0.35 if volatility < 10 else 0.2667
            size = trade_size * 0.75 if volatility > 4 else trade_size
            shares = min(size / close, portfolio['shares'])
            proceeds = shares * close  # Zero fees/slippage
            portfolio['shares'] -= shares
            portfolio['cash'] += proceeds
            portfolio['tbill'] += proceeds
            trades.append((date, 'SELL', shares, close, portfolio['value']))
            print(f"{date} 15:50: Sold {shares:.2f} {current_ticker} at ${close:.2f}")
            logging.info(f"{date} 15:50: Sold {shares:.2f} {current_ticker} at ${close:.2f}")
            # Uncomment for live
            # message = f"{date} 15:50: Sell {shares:.2f} {current_ticker} at ~${close:.2f}. Enter in IBKR."
            # client.messages.create(body=message, from_=TWILIO_FROM, to=TWILIO_TO)

    except Exception as e:
        logging.error(f"Error on {date} for {current_ticker}: {str(e)}")
        continue

# Final portfolio value
final_close = df_current['Close