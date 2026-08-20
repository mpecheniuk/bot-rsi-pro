#!/usr/bin/env python3
"""
RSI Pro Telegram Signal Bot — Binance Edition
==============================================
Використовує Binance Public API для 4h свічок BTCUSDT.
Не потребує OpenMarket API ключа. RSI Pro рахується локально 1:1 за kScript.

Логіка RSI Pro (з вихідного коду):
  rsi1    = RSI(close, 14)
  rsi2    = RSI(close, 20)
  smooth1 = EMA(rsi1, 3)
  smooth2 = EMA(rsi2, 3)
  sig     = SMA(rsi2, 14)
  obthres = 80
  osthres = 20
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
from typing import Optional, Dict, Any, List

# =============================================================================
# НАЛАШТУВАННЯ
# =============================================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

SYMBOL = "BTCUSDT"
INTERVAL = "4h"               # Binance формат: 1m, 5m, 15m, 1h, 4h, 1d
LOOKBACK_LIMIT = 100          # кількість свічок (достатньо для RSI(20)+SMA(14))

# Параметри RSI Pro
FAST_RSI = 14
SLOW_RSI = 20
EMA_SMOOTH = 3
SIG_LEN = 14
OB_THRES = 80
OS_THRES = 20

# Файл стану
STATE_FILE = "rsi_pro_state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("rsi_pro_bot")

# =============================================================================
# BINANCE API — БЕЗКОШТОВНО, БЕЗ КЛЮЧА
# =============================================================================

def fetch_binance_candles() -> pd.DataFrame:
    """
    Завантажує 4h свічки з Binance Public API.
    Документація: https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-data
    """
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "limit": LOOKBACK_LIMIT,
    }

    logger.info(f"Запит свічок: Binance {SYMBOL} {INTERVAL}")

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Binance повертає: [
    #   [openTime, open, high, low, close, volume, closeTime, ...]
    # ]
    rows = []
    for candle in data:
        open_time = pd.to_datetime(candle[0], unit="ms", utc=True)
        rows.append([
            open_time,
            float(candle[1]),   # open
            float(candle[2]),   # high
            float(candle[3]),   # low
            float(candle[4]),   # close
            float(candle[5]),   # volume
        ])

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df.sort_values("ts").reset_index(drop=True)

    logger.info(f"Отримано свічок: {len(df)} | Діапазон: {df['ts'].iloc[0]} → {df['ts'].iloc[-1]}")
    return df


# =============================================================================
# ТЕХНІЧНІ ІНДИКАТОРИ (1:1 з kScript)
# =============================================================================

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI — EMA з alpha=1/period (як у TradingView/Pine Script)."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def calculate_ema(series: pd.Series, period: int = 3) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calculate_sma(series: pd.Series, period: int = 14) -> pd.Series:
    return series.rolling(window=period).mean()


def calculate_rsi_pro(df: pd.DataFrame) -> pd.DataFrame:
    """Розраховує всі компоненти RSI Pro точно за логікою kScript."""
    df = df.copy()
    df["rsi1"] = calculate_rsi(df["close"], period=FAST_RSI)
    df["rsi2"] = calculate_rsi(df["close"], period=SLOW_RSI)
    df["smooth1"] = calculate_ema(df["rsi1"], period=EMA_SMOOTH)
    df["smooth2"] = calculate_ema(df["rsi2"], period=EMA_SMOOTH)
    df["sig"] = calculate_sma(df["rsi2"], period=SIG_LEN)

    df["idx1"] = (df["smooth1"] > df["sig"]).astype(int)
    df["idx2"] = (df["smooth2"] > df["sig"]).astype(int)

    return df


# =============================================================================
# СИГНАЛИ
# =============================================================================

def detect_signals(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Шукає сигнали на останній закритій свічці."""
    signals = []
    if len(df) < 2:
        return signals

    prev = df.iloc[-2]
    curr = df.iloc[-1]
    price = curr["close"]
    ts = curr["ts"]

    # 1. Fast Cross
    prev_above_fast = prev["smooth1"] > prev["sig"]
    curr_above_fast = curr["smooth1"] > curr["sig"]

    if prev_above_fast != curr_above_fast:
        if curr_above_fast:
            signals.append({
                "type": "FAST_CROSS_BULL",
                "emoji": "🟢",
                "title": "RSI Pro — Бичий перетин",
                "desc": f"Fast RSI перетнув сигнальну лінію знизу вгору\nSmooth1: {curr['smooth1']:.2f} | Sig: {curr['sig']:.2f}",
                "strength": "normal"
            })
        else:
            signals.append({
                "type": "FAST_CROSS_BEAR",
                "emoji": "🔴",
                "title": "RSI Pro — Ведмежий перетин",
                "desc": f"Fast RSI перетнув сигнальну лінію зверху вниз\nSmooth1: {curr['smooth1']:.2f} | Sig: {curr['sig']:.2f}",
                "strength": "normal"
            })

    # 2. Slow Cross
    prev_above_slow = prev["smooth2"] > prev["sig"]
    curr_above_slow = curr["smooth2"] > curr["sig"]

    if prev_above_slow != curr_above_slow:
        if curr_above_slow:
            signals.append({
                "type": "SLOW_CROSS_BULL",
                "emoji": "🟢🟢",
                "title": "RSI Pro — Сильний бичий перетин",
                "desc": f"Slow RSI перетнув сигнальну лінію знизу вгору\nSmooth2: {curr['smooth2']:.2f} | Sig: {curr['sig']:.2f}",
                "strength": "strong"
            })
        else:
            signals.append({
                "type": "SLOW_CROSS_BEAR",
                "emoji": "🔴🔴",
                "title": "RSI Pro — Сильний ведмежий перетин",
                "desc": f"Slow RSI перетнув сигнальну лінію зверху вниз\nSmooth2: {curr['smooth2']:.2f} | Sig: {curr['sig']:.2f}",
                "strength": "strong"
            })

    # 3. OB/OS Exit (Mean Reversion)
    if prev["smooth1"] >= OB_THRES and curr["smooth1"] < OB_THRES:
        signals.append({
            "type": "OB_EXIT",
            "emoji": "📉",
            "title": "RSI Pro — Вихід з Overbought",
            "desc": f"Fast RSI покинув зону >{OB_THRES}\nSmooth1: {curr['smooth1']:.2f} (було {prev['smooth1']:.2f})",
            "strength": "normal"
        })

    if prev["smooth1"] <= OS_THRES and curr["smooth1"] > OS_THRES:
        signals.append({
            "type": "OS_EXIT",
            "emoji": "📈",
            "title": "RSI Pro — Вихід з Oversold",
            "desc": f"Fast RSI покинув зону <{OS_THRES}\nSmooth1: {curr['smooth1']:.2f} (було {prev['smooth1']:.2f})",
            "strength": "normal"
        })

    # 4. OB/OS Entry (Momentum)
    if prev["smooth1"] < OB_THRES and curr["smooth1"] >= OB_THRES:
        signals.append({
            "type": "OB_ENTRY",
            "emoji": "🚀",
            "title": "RSI Pro — Вхід у Overbought (Momentum)",
            "desc": f"Fast RSI увійшов у зону >{OB_THRES}\nSmooth1: {curr['smooth1']:.2f}",
            "strength": "momentum"
        })

    if prev["smooth1"] > OS_THRES and curr["smooth1"] <= OS_THRES:
        signals.append({
            "type": "OS_ENTRY",
            "emoji": "💥",
            "title": "RSI Pro — Вхід у Oversold (Momentum)",
            "desc": f"Fast RSI увійшов у зону <{OS_THRES}\nSmooth1: {curr['smooth1']:.2f}",
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
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_signals": {}}


def save_state(state: Dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def should_send(signal: Dict, state: Dict) -> bool:
    sig_type = signal["type"]
    ts_str = str(signal["ts"])
    last = state["last_signals"].get(sig_type)
    if last == ts_str:
        return False
    return True


def mark_sent(signal: Dict, state: Dict):
    state["last_signals"][signal["type"]] = str(signal["ts"])


# =============================================================================
# TELEGRAM
# =============================================================================

def send_telegram(message: str) -> bool:
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
    curr = df.iloc[-1]

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
    logger.info("=== Запуск RSI Pro Bot (Binance Edition) ===")

    try:
        # 1. Дані з Binance (безкоштовно, без ключа)
        df = fetch_binance_candles()

        # 2. RSI Pro
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

        # 4. Відправка
        state = load_state()
        sent_count = 0

        for sig in signals:
            if should_send(sig, state):
                msg = format_signal(sig, df)
                if send_telegram(msg):
                    mark_sent(sig, state)
                    sent_count += 1
                    time.sleep(1)
            else:
                logger.info(f"Сигнал {sig['type']} вже відправлявся — пропускаємо")

        save_state(state)
        logger.info(f"Відправлено сигналів: {sent_count}/{len(signals)}")

    except Exception as e:
        logger.exception(f"Помилка: {e}")
        send_telegram(f"⚠️ <b>Помилка RSI Pro Bot</b>\n<code>{str(e)[:300]}</code>")


def run_loop(interval_minutes: int = 5):
    logger.info(f"Loop mode: перевірка кожні {interval_minutes} хв")
    while True:
        run_once()
        logger.info(f"Наступна перевірка через {interval_minutes} хв...")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()

    if args.loop:
        run_loop(args.interval)
    else:
        run_once()
