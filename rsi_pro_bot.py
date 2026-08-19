#!/usr/bin/env python3
"""
RSI Pro Telegram Signal Bot for OpenMarket + Binance Futures BTCUSDT 4h
=======================================================================
Відтворює логіку індикатора RSI Pro з OpenMarket (kScript) у Python.

Логіка індикатора (з вихідного коду):
  rsi1   = RSI(close, 14)
  rsi2   = RSI(close, 20)
  smooth1 = EMA(rsi1, 3)
  smooth2 = EMA(rsi2, 3)
  sig     = SMA(rsi2, 14)
  obthres = 80
  osthres = 20

Сигнали:
  - Fast Cross: smooth1 перетинає sig
  - OB/OS Zone: вихід/вхід у зони 80/20
  - Divergence: (опціонально, потребує більше історії)

Запуск:
  1. Встанови змінні оточення (див. нижче)
  2. python3 rsi_pro_bot.py
  3. Для cron: */5 * * * * cd /path && python3 rsi_pro_bot.py >> bot.log 2>&1

Змінні оточення:
  OPENMARKET_API_KEY  - твій ключ з openmarket.xyz
  TELEGRAM_BOT_TOKEN  - токен від @BotFather
  TELEGRAM_CHAT_ID    - ID каналу (напр. -1001234567890)
"""

import os
import sys
import json
import time
import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple

# =============================================================================
# НАЛАШТУВАННЯ
# =============================================================================

OPENMARKET_KEY = os.getenv("OPENMARKET_API_KEY", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Таймфрейм і символ
EXCHANGE = "BINANCE_FUTURES"
RAW_SYMBOL = "BTCUSDT"
INTERVAL = "FOUR_HOURS"      # 4h свічки
LOOKBACK_PERIOD = 604800     # 7 днів у секундах (достатньо для RSI(20)+SMA(14))

# Параметри RSI Pro (з вихідного коду kScript)
FAST_RSI = 14
SLOW_RSI = 20
EMA_SMOOTH = 3
SIG_LEN = 14
OB_THRES = 80
OS_THRES = 20

# Файл стану (щоб не спамити повторними сигналами)
STATE_FILE = "rsi_pro_state.json"

# Логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("rsi_pro_bot")

# =============================================================================
# ТЕХНІЧНІ ІНДИКАТОРИ
# =============================================================================

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI — використовує EMA з alpha=1/period (як у TradingView/Pine)."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def calculate_ema(series: pd.Series, period: int = 3) -> pd.Series:
    """EMA згладжування."""
    return series.ewm(span=period, adjust=False).mean()


def calculate_sma(series: pd.Series, period: int = 14) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period).mean()


def calculate_rsi_pro(df: pd.DataFrame) -> pd.DataFrame:
    """
    Розраховує всі компоненти RSI Pro точно за логікою kScript:
      rsi1    = RSI(close, fast=14)
      rsi2    = RSI(close, slow=20)
      smooth1 = EMA(rsi1, emas=3)
      smooth2 = EMA(rsi2, emas=3)
      sig     = SMA(rsi2, sig_len=14)
    """
    df = df.copy()
    df["rsi1"] = calculate_rsi(df["close"], period=FAST_RSI)
    df["rsi2"] = calculate_rsi(df["close"], period=SLOW_RSI)
    df["smooth1"] = calculate_ema(df["rsi1"], period=EMA_SMOOTH)
    df["smooth2"] = calculate_ema(df["rsi2"], period=EMA_SMOOTH)
    df["sig"] = calculate_sma(df["rsi2"], period=SIG_LEN)

    # Додаткові метрики для сигналів
    df["idx1"] = (df["smooth1"] > df["sig"]).astype(int)   # 1 = бичий, 0 = ведмежий
    df["idx2"] = (df["smooth2"] > df["sig"]).astype(int)

    return df


# =============================================================================
# OPENMARKET API
# =============================================================================

def fetch_candles() -> pd.DataFrame:
    """
    Завантажує 4h свічки BTCUSDT з OpenMarket API.
    Повертає DataFrame з колонками: ts, open, high, low, close, volume
    """
    if not OPENMARKET_KEY:
        raise ValueError("OPENMARKET_API_KEY не встановлено!")

    url = "https://api.openmarket.xyz/v1/points"
    params = {
        "type": "TRADE_SIDE_AGNOSTIC_AGG",
        "exchange": EXCHANGE,
        "rawSymbol": RAW_SYMBOL,
        "interval": INTERVAL,
        "period": LOOKBACK_PERIOD,
    }
    headers = {"X-OpenMarket-Key": OPENMARKET_KEY}

    logger.info(f"Запит свічок: {EXCHANGE} {RAW_SYMBOL} {INTERVAL}")

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not data.get("series"):
        raise ValueError("API повернуло порожній series")

    points = data["series"][0]["points"]

    # Розпаковка timestamp (може бути {s, ns} або просто число)
    rows = []
    for p in points:
        ts_raw = p[0]
        if isinstance(ts_raw, dict):
            ts = pd.to_datetime(ts_raw["s"], unit="s", utc=True)
        else:
            ts = pd.to_datetime(ts_raw, unit="s", utc=True)
        rows.append([ts, float(p[1]), float(p[2]), float(p[3]), float(p[4]), float(p[5])])

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df.sort_values("ts").reset_index(drop=True)

    logger.info(f"Отримано свічок: {len(df)} | Діапазон: {df['ts'].iloc[0]} → {df['ts'].iloc[-1]}")
    return df


# =============================================================================
# СИГНАЛИ
# =============================================================================

def detect_signals(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Шукає торгові сигнали на останній закритій свічці.
    Повертає список сигналів (максимум 1-2 за раз).
    """
    signals = []
    if len(df) < 2:
        return signals

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    price = curr["close"]
    ts = curr["ts"]

    # --- 1. Fast Cross (smooth1 vs sig) ---
    prev_above_fast = prev["smooth1"] > prev["sig"]
    curr_above_fast = curr["smooth1"] > curr["sig"]

    if prev_above_fast != curr_above_fast:
        if curr_above_fast:
            signals.append({
                "type": "FAST_CROSS_BULL",
                "emoji": "🟢",
                "title": "RSI Pro — Бичий перетин",
                "desc": f"Fast RSI перетнув сигнальну лінію знизу вгору\n"
                        f"Smooth1: {curr['smooth1']:.2f} | Sig: {curr['sig']:.2f}",
                "strength": "normal"
            })
        else:
            signals.append({
                "type": "FAST_CROSS_BEAR",
                "emoji": "🔴",
                "title": "RSI Pro — Ведмежий перетин",
                "desc": f"Fast RSI перетнув сигнальну лінію зверху вниз\n"
                        f"Smooth1: {curr['smooth1']:.2f} | Sig: {curr['sig']:.2f}",
                "strength": "normal"
            })

    # --- 2. Slow Cross (smooth2 vs sig) ---
    prev_above_slow = prev["smooth2"] > prev["sig"]
    curr_above_slow = curr["smooth2"] > curr["sig"]

    if prev_above_slow != curr_above_slow:
        if curr_above_slow:
            signals.append({
                "type": "SLOW_CROSS_BULL",
                "emoji": "🟢🟢",
                "title": "RSI Pro — Сильний бичий перетин",
                "desc": f"Slow RSI перетнув сигнальну лінію знизу вгору\n"
                        f"Smooth2: {curr['smooth2']:.2f} | Sig: {curr['sig']:.2f}",
                "strength": "strong"
            })
        else:
            signals.append({
                "type": "SLOW_CROSS_BEAR",
                "emoji": "🔴🔴",
                "title": "RSI Pro — Сильний ведмежий перетин",
                "desc": f"Slow RSI перетнув сигнальну лінію зверху вниз\n"
                        f"Smooth2: {curr['smooth2']:.2f} | Sig: {curr['sig']:.2f}",
                "strength": "strong"
            })

    # --- 3. OB/OS Zone Exit (Mean Reversion style) ---
    # Вихід з Overbought (>80) вниз — ведмежий
    if prev["smooth1"] >= OB_THRES and curr["smooth1"] < OB_THRES:
        signals.append({
            "type": "OB_EXIT",
            "emoji": "📉",
            "title": "RSI Pro — Вихід з Overbought",
            "desc": f"Fast RSI покинув зону >{OB_THRES}\n"
                    f"Smooth1: {curr['smooth1']:.2f} (було {prev['smooth1']:.2f})",
            "strength": "normal"
        })

    # Вихід з Oversold (<20) вгору — бичий
    if prev["smooth1"] <= OS_THRES and curr["smooth1"] > OS_THRES:
        signals.append({
            "type": "OS_EXIT",
            "emoji": "📈",
            "title": "RSI Pro — Вихід з Oversold",
            "desc": f"Fast RSI покинув зону <{OS_THRES}\n"
                    f"Smooth1: {curr['smooth1']:.2f} (було {prev['smooth1']:.2f})",
            "strength": "normal"
        })

    # --- 4. OB/OS Entry (Momentum style — контртренд) ---
    # Вхід в Overbought — можливе продовження руху
    if prev["smooth1"] < OB_THRES and curr["smooth1"] >= OB_THRES:
        signals.append({
            "type": "OB_ENTRY",
            "emoji": "🚀",
            "title": "RSI Pro — Вхід у Overbought (Momentum)",
            "desc": f"Fast RSI увійшов у зону >{OB_THRES}\n"
                    f"Smooth1: {curr['smooth1']:.2f}",
            "strength": "momentum"
        })

    if prev["smooth1"] > OS_THRES and curr["smooth1"] <= OS_THRES:
        signals.append({
            "type": "OS_ENTRY",
            "emoji": "💥",
            "title": "RSI Pro — Вхід у Oversold (Momentum)",
            "desc": f"Fast RSI увійшов у зону <{OS_THRES}\n"
                    f"Smooth1: {curr['smooth1']:.2f}",
            "strength": "momentum"
        })

    for s in signals:
        s["ts"] = ts
        s["price"] = price

    return signals


# =============================================================================
# СТАН ТА ДЕДУПЛІКАЦІЯ
# =============================================================================

def load_state() -> Dict:
    """Завантажує стан (останні відправлені сигнали)."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_signals": {}}


def save_state(state: Dict):
    """Зберігає стан."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def should_send(signal: Dict, state: Dict) -> bool:
    """
    Перевіряє, чи варто відправляти сигнал.
    Не відправляємо дубль того ж типу на тій же свічці.
    """
    sig_type = signal["type"]
    ts_str = str(signal["ts"])

    last = state["last_signals"].get(sig_type)
    if last == ts_str:
        return False
    return True


def mark_sent(signal: Dict, state: Dict):
    """Позначає сигнал як відправлений."""
    state["last_signals"][signal["type"]] = str(signal["ts"])


# =============================================================================
# TELEGRAM
# =============================================================================

def send_telegram(message: str) -> bool:
    """Відправляє повідомлення в Telegram канал."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_BOT_TOKEN або TELEGRAM_CHAT_ID не встановлено!")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        logger.info("Повідомлення відправлено в Telegram")
        return True
    except Exception as e:
        logger.error(f"Помилка відправки в Telegram: {e}")
        return False


def format_signal(signal: Dict, df: pd.DataFrame) -> str:
    """Форматує повідомлення про сигнал."""
    curr = df.iloc[-1]

    # Визначаємо кольорову зону
    zone = "нейтральна"
    if curr["smooth1"] >= OB_THRES:
        zone = f"<b>OVERBOUGHT</b> (>={OB_THRES})"
    elif curr["smooth1"] <= OS_THRES:
        zone = f"<b>OVERSOLD</b> (<={OS_THRES})"

    msg = (
        f"{signal['emoji']} <b>{signal['title']}</b>\n"
        f"{'━' * 30}\n"
        f"💰 <b>BTC/USDT</b> @ <code>${signal['price']:,.2f}</code>\n"
        f"⏱ Таймфрейм: <b>4H</b> | Свічка: <code>{signal['ts'].strftime('%Y-%m-%d %H:%M UTC')}</code>\n"
        f"{'━' * 30}\n"
        f"📊 <b>RSI Pro Values:</b>\n"
        f"   Smooth1 (Fast): <code>{curr['smooth1']:.2f}</code>\n"
        f"   Smooth2 (Slow): <code>{curr['smooth2']:.2f}</code>\n"
        f"   Signal (SMA14): <code>{curr['sig']:.2f}</code>\n"
        f"{'━' * 30}\n"
        f"🎯 {signal['desc']}\n"
        f"{'━' * 30}\n"
        f"🌡 Зона: {zone}\n"
        f"📈 RSI(14): <code>{curr['rsi1']:.2f}</code> | RSI(20): <code>{curr['rsi2']:.2f}</code>"
    )
    return msg


# =============================================================================
# ГОЛОВНИЙ ЦИКЛ
# =============================================================================

def run_once():
    """Один прохід: завантажити дані → розрахувати → перевірити сигнали → відправити."""
    logger.info("=== Запуск RSI Pro Bot ===")

    try:
        # 1. Дані
        df = fetch_candles()

        # 2. Індикатор
        df = calculate_rsi_pro(df)

        # 3. Сигнали
        signals = detect_signals(df)

        if not signals:
            curr = df.iloc[-1]
            logger.info(
                f"Сигналів немає. RSI Pro: smooth1={curr['smooth1']:.2f}, "
                f"sig={curr['sig']:.2f}, zone={'OB' if curr['smooth1']>=OB_THRES else 'OS' if curr['smooth1']<=OS_THRES else 'neutral'}"
            )
            return

        # 4. Стан та відправка
        state = load_state()
        sent_count = 0

        for sig in signals:
            if should_send(sig, state):
                msg = format_signal(sig, df)
                if send_telegram(msg):
                    mark_sent(sig, state)
                    sent_count += 1
                    # Невелика пауза між повідомленнями
                    time.sleep(1)
            else:
                logger.info(f"Сигнал {sig['type']} вже відправлявся на цій свічці — пропускаємо")

        save_state(state)
        logger.info(f"Відправлено сигналів: {sent_count}/{len(signals)}")

    except Exception as e:
        logger.exception(f"Помилка виконання: {e}")
        # Спробуємо відправити сповіщення про помилку (опціонально)
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            send_telegram(f"⚠️ <b>Помилка RSI Pro Bot</b>\n<code>{str(e)[:300]}</code>")


def run_loop(interval_minutes: int = 5):
    """Безперервний цикл з перевіркою кожні N хвилин."""
    logger.info(f"Запуск у режимі loop (перевірка кожні {interval_minutes} хв)")
    while True:
        run_once()
        logger.info(f"Наступна перевірка через {interval_minutes} хв...")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RSI Pro Telegram Bot")
    parser.add_argument("--loop", action="store_true", help="Запуск у безперервному режимі")
    parser.add_argument("--interval", type=int, default=5, help="Інтервал перевірки у хвилинах (за замовчуванням 5)")
    args = parser.parse_args()

    if args.loop:
        run_loop(args.interval)
    else:
        run_once()
