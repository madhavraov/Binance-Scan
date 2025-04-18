import os
from dotenv import load_dotenv
import requests
import time
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException
import schedule

# Environment variables (from GitHub Secrets)
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_SECRET_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

client = Client(API_KEY, API_SECRET)

def send_telegram(msg):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': msg}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Telegram Error:", e)

def get_usdt_spot_pairs():
    try:
        info = client.get_exchange_info()
        symbols = [
            s['symbol'] for s in info['symbols']
            if s['quoteAsset'] == 'USDT'
            and s['status'] == 'TRADING'
            and s.get('isSpotTradingAllowed', False)
            and not any(x in s['symbol'] for x in ['UP', 'DOWN', 'BULL', 'BEAR'])
        ]
        return symbols
    except Exception as e:
        print("Error fetching symbols:", e)
        return []

def fetch_ema_and_volume(symbol):
    try:
        candles = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_15MINUTE, limit=100)
        df = pd.DataFrame(candles, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'num_trades',
            'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
        ])
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        df['EMA_99'] = df['close'].ewm(span=99).mean()

        current_close = df['close'].iloc[-1]
        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].iloc[-11:-1].mean()
        current_ema = df['EMA_99'].iloc[-1]

        if current_close > current_ema and current_volume > avg_volume * 1.1:  # 10% higher volume
            return True, current_close, current_volume, current_ema, avg_volume
    except BinanceAPIException as e:
        print(f"Binance API error for {symbol}: {e}")
    except Exception as e:
        print(f"Error processing {symbol}: {e}")
    return False, None, None, None, None

def scan_market():
    print(f"Scanning market at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    symbols = get_usdt_spot_pairs()
    for symbol in symbols:
        signal, price, vol, ema, avg_vol = fetch_ema_and_volume(symbol)
        if signal:
            msg = (
                f"📈 Signal for {symbol}\n"
                f"Price: {price:.4f}\n"
                f"EMA 99: {ema:.4f}\n"
                f"Volume: {vol:.2f}\n"
                f"Avg Volume (10): {avg_vol:.2f}"
            )
            print(msg.encode('utf-8', errors='replace').decode())  # Safe print
            send_telegram(msg)

# Run once on push
scan_market()
