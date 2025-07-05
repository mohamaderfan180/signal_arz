import ccxt
import pandas as pd
import pandas_ta as ta
import asyncio
from telegram import Bot
import logging
import os
import json

# --- خواندن توکن و آیدی از سکرت‌های گیت‌هاب ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# --- تنظیمات لاگ ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- نام فایل برای ذخیره وضعیت‌ها ---
STATE_FILE = "signal_states.json"

def save_states(states):
    """وضعیت سیگنال‌ها را در یک فایل JSON ذخیره می‌کند."""
    with open(STATE_FILE, 'w') as f:
        json.dump(states, f)
    logger.info(f"States saved to {STATE_FILE}")

def load_states():
    """وضعیت سیگنال‌ها را از فایل JSON می‌خواند."""
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("State file not found. Starting with an empty state.")
        return {} # اگر فایل وجود نداشت، یک دیکشنری خالی برمی‌گرداند

async def analyze_coin(symbol, exchange, signal_states):
    """این تابع یک ارز مشخص را تحلیل کرده و در صورت نیاز سیگنال ارسال می‌کند."""
    try:
        current_state = signal_states.get(symbol)
        bars = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['RSI'] = ta.rsi(df['close'], length=14)
        last_rsi = df['RSI'].iloc[-1]
        entry_price = df['close'].iloc[-1]

        message = ""
        # ... (بقیه منطق تحلیل و ساخت پیام بدون تغییر باقی می‌ماند) ...
        # --- استراتژی Long ---
        if last_rsi <= 30 and current_state != 'long':
            signal_states[symbol] = 'long'
            tp1, tp2, sl = entry_price * 1.02, entry_price * 1.04, entry_price * 0.98
            message = (f"🟢 **#{symbol.replace('/', '')} - Long** ...") # پیام کامل
        # --- استراتژی Short ---
        elif last_rsi >= 70 and current_state != 'short':
            signal_states[symbol] = 'short'
            tp1, tp2, sl = entry_price * 0.98, entry_price * 0.96, entry_price * 1.02
            message = (f"🔴 **#{symbol.replace('/', '')} - Short** ...") # پیام کامل
        # ریست کردن وضعیت
        elif 30 < last_rsi < 70:
            signal_states[symbol] = None

        if message:
            bot = Bot(token=TELEGRAM_TOKEN)
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='HTML')
            logger.info(f"Signal sent for {symbol}")

    except Exception as e:
        logger.warning(f"Could not analyze {symbol}. Reason: {e}")

async def main():
    """تابع اصلی که لیست ۲۰۰ ارز برتر را گرفته و تحلیل می‌کند."""
    logger.info("Bot execution started by GitHub Actions...")
    
    # خواندن وضعیت‌های قبلی از فایل
    signal_states = load_states()

    try:
        exchange = ccxt.binance({'options': {'defaultType': 'future'}})
        markets = exchange.load_markets()
        usdt_futures = [m for m in markets.values() if m.get('quote', '').upper() == 'USDT' and m.get('type') == 'future' and m.get('info', {}).get('contractType') == 'PERPETUAL']
        sorted_markets = sorted(usdt_futures, key=lambda m: m.get('quoteVolume', 0), reverse=True)
        top_symbols = [m['symbol'] for m in sorted_markets[:200]]
        
        logger.info("Top 200 symbols fetched. Starting analysis...")
        for symbol in top_symbols:
            await analyze_coin(symbol, exchange, signal_states)
            await asyncio.sleep(0.5) # وقفه کوتاه برای احترام به API Limit

    except Exception as e:
        logger.error(f"An error occurred in the main process: {e}")
    finally:
        # ذخیره وضعیت نهایی برای اجرای بعدی
        save_states(signal_states)
        logger.info("Bot execution finished.")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logger.error("TELEGRAM_TOKEN or CHAT_ID not set in environment variables!")
    else:
        asyncio.run(main())