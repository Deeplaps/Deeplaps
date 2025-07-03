import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
import time

# ---------------- CONFIG ----------------
TIMEFRAMES = ['4h', '1d']
LIMIT = 50
PA_LOOKBACK = 10
CLOSE_ENTRY_THRESHOLD = 0.02
# ----------------------------------------

exchange = ccxt.binance()

def get_top_volume_usdt_pairs(limit=30):
    print("📊 Lấy danh sách top coin theo volume...")
    tickers = exchange.fetch_tickers()
    usdt_pairs = [(k, v['quoteVolume']) for k, v in tickers.items()
                  if k.endswith('/USDT') and '/' in k and v['quoteVolume'] is not None]
    sorted_pairs = sorted(usdt_pairs, key=lambda x: x[1], reverse=True)
    return [pair[0] for pair in sorted_pairs[:limit]]

def fetch_ohlcv(symbol, timeframe):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=LIMIT)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"⚠️ Lỗi khi tải dữ liệu {symbol} - {timeframe}: {e}")
        return None

def is_bullish(candle): return candle['close'] > candle['open']
def is_bearish(candle): return candle['close'] < candle['open']

def detect_engulfing(df):
    signals = []
    for i in range(1, len(df)):
        c1 = df.iloc[i-1]
        c2 = df.iloc[i]
        if is_bearish(c1) and is_bullish(c2) and c2['open'] < c1['close'] and c2['close'] > c1['open']:
            signals.append((i, 'bullish_engulfing', c2))
        elif is_bullish(c1) and is_bearish(c2) and c2['open'] > c1['close'] and c2['close'] < c1['open']:
            signals.append((i, 'bearish_engulfing', c2))
    return signals

def detect_pinbar_with_confirmation(df):
    signals = []
    for i in range(1, len(df) - 1):
        candle = df.iloc[i]
        next_candle = df.iloc[i + 1]
        body = abs(candle['close'] - candle['open'])
        full_range = candle['high'] - candle['low']
        upper_shadow = candle['high'] - max(candle['close'], candle['open'])
        lower_shadow = min(candle['close'], candle['open']) - candle['low']

        if full_range == 0 or body / full_range > 0.3:
            continue  # tránh chia 0 hoặc thân quá lớn

        if lower_shadow > 2 * body and lower_shadow > upper_shadow and is_bullish(next_candle):
            signals.append((i, 'bullish_pinbar', candle))
        elif upper_shadow > 2 * body and upper_shadow > lower_shadow and is_bearish(next_candle):
            signals.append((i, 'bearish_pinbar', candle))
    return signals

def price_near_entry(current_price, entry_price, threshold=0.02):
    return abs(current_price - entry_price) / entry_price < threshold

def scan_market():
    coins = get_top_volume_usdt_pairs(limit=30)
    print(f"✅ Đang quét {len(coins)} cặp coin...")

    for symbol in coins:
        for tf in TIMEFRAMES:
            df = fetch_ohlcv(symbol, tf)
            time.sleep(0.2)  # tránh rate limit

            if df is None or len(df) < LIMIT:
                continue

            engulfings = detect_engulfing(df)
            pinbars = detect_pinbar_with_confirmation(df)
            last_price = df.iloc[-1]['close']

            found = False
            for idx, signal_type, signal_candle in engulfings + pinbars:
                if idx >= len(df) - PA_LOOKBACK:
                    if "engulfing" in signal_type:
                        entry = (signal_candle['open'] + signal_candle['close']) / 2
                    else:
                        entry = (signal_candle['high'] + signal_candle['low']) / 2

                    if price_near_entry(last_price, entry) or True:  # điều kiện OR luôn đúng
                        ago = len(df) - 1 - idx
                        print(f"✅ {symbol} | {tf.upper()} | {signal_type} | {ago} candle(s) ago | Entry ≈ {entry:.2f} | Price ≈ {last_price:.2f}")
                        found = True

            if found:
                print("-" * 60)

if __name__ == "__main__":
    scan_market()