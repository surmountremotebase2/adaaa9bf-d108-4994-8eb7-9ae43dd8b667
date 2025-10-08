import pandas as pd
import numpy as np
from alpha_vantage.timeseries import TimeSeries
from ta.trend import MACD, ADX, SMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
# from twilio.rest import Client  # Uncomment for live
import datetime
import warnings
import logging
import csv
import os
import time

# Suppress warnings
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    filename='wvv1_3_backtest.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Alpha Vantage API key (replace with your own from alphavantage.co)
ALPHA_VANTAGE_API_KEY = "YOUR_API_KEY"

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

# Download data from Alpha Vantage
logging.info("Fetching data for tickers from Alpha Vantage")
ts = TimeSeries(key=ALPHA_VANTAGE_API_KEY, output_format='pandas')
data = {}
for ticker in tickers:
    try:
        df, _ = ts.get_daily_adjusted(symbol=ticker, outputsize='full')
        df = df.loc['2023-10-01':'2025-10-06']  # Filter to backtest period
        if df.empty:
            raise ValueError(f"No data for {ticker}")
        # Rename columns to match yfinance format
        df = df.rename(columns={
            '1. open': 'Open',
            '2. high': 'High',
            '3. low': 'Low',
            '4. close': 'Close',
            '5. adjusted close': 'Adj Close',
            '6. volume': 'Volume'
        })
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df['macd'], df['macd_signal'], _ = MACD(df['Close'], window_slow=26, window_fast=12, window_sign=9).macd()
        df['sma_50'] = SMAIndicator(df['Close'], window=50).sma_indicator()
        df['rsi'] = RSIIndicator(df['Close'], window=14).rsi()
        df['adx'] = ADX(df['High'], df['Low'], df['Close'], window=14).adx()
        df['atr'] = AverageTrueRange(df['High'], df['Low'], df['Close'], window=14).average_true_range()
        df['volatility'] = df['Close'].pct_change().rolling(window=20).std() * np.sqrt(252) * 100
        data[ticker] = df
        time.sleep(12)  # Respect Alpha Vantage rate limit (5 calls/min)
    except Exception as e:
        logging.error(f"Error fetching data for {ticker}: {e}")
        data[ticker] = pd.DataFrame()

# Align indices to common dates
logging.info("Aligning data indices")
common_dates = data['MSTR'].index.intersection(data['SPY'].index)
for ticker in qqq_tickers + ['RGTI', 'PSIX']:
    if ticker in data and not data[ticker].empty:
        common_dates = common_dates.intersection(data[ticker].index)
for ticker in tickers:
    if ticker in data and not data[ticker].empty:
        data[ticker] = data[ticker].loc[common_dates].ffill()
    else:
        data[ticker] = pd.DataFrame(index=common_dates)

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
final_close = df_current['Close'][-1]
final_value = portfolio['shares'] * final_close + portfolio['cash'] + portfolio['tbill']
print(f"WVV1.3 Final Portfolio Value: ${final_value:.2f}")
print(f"WVV1.3 Return: {(final_value - 10000) / 10000 * 100:.2f}%")
print(f"WVV1.3 Current Ticker: {current_ticker}")
print(f"WVV1.3 Number of Switches: {sum(1 for t in trades if 'SWITCH' in str(t[1]))}")
print(f"WVV1.3 Number of Trades: {len(trades)}")
logging.info(f"WVV1.3 Final Portfolio Value: ${final_value:.2f}")
logging.info(f"WVV1.3 Return: {(final_value - 10000) / 10000 * 100:.2f}%")
logging.info(f"WVV1.3 Current Ticker: {current_ticker}")
logging.info(f"WVV1.3 Number of Switches: {sum(1 for t in trades if 'SWITCH' in str(t[1]))}")
logging.info(f"WVV1.3 Number of Trades: {len(trades)}")

# Save trades to CSV
with open('trades_log.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Date', 'Action', 'Shares', 'Price', 'PortfolioValue'])
    for trade in trades:
        writer.writerow([trade[0], trade[1], f"{trade[2]:.2f}", f"{trade[3]:.2f}", f"{trade[4]:.2f}"])

logging.info("Backtest completed successfully")