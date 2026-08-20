#!/usr/bin/env python3
"""
Тест Telegram-зв'язку та вивід поточних значень RSI Pro.
"""

import os
import requests
import pandas as pd

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_test():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Змінні TELEGRAM_BOT_TOKEN або TELEGRAM_CHAT_ID не встановлені")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": "✅ <b>RSI Pro Bot — тест зв'язку</b>\nБот працює! Очікуємо сигналів...",
        "parse_mode": "HTML",
    }
    r = requests.post(url, json=payload, timeout=10)
    print(f"Статус: {r.status_code}")
    print(f"Відповідь: {r.json()}")

def show_current_values():
    """Показує поточні значення RSI Pro (для розуміння, чому немає сигналу)."""
    import requests

    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": "4h", "limit": 50}
    data = requests.get(url, params=params, timeout=10).json()

    rows = []
    for c in data:
        rows.append([float(c[4])])
    df = pd.DataFrame(rows, columns=["close"])

    # RSI
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rsi1 = 100 - (100 / (1 + avg_gain / avg_loss))

    avg_gain2 = gain.ewm(alpha=1/20, min_periods=20, adjust=False).mean()
    avg_loss2 = loss.ewm(alpha=1/20, min_periods=20, adjust=False).mean()
    rsi2 = 100 - (100 / (1 + avg_gain2 / avg_loss2))

    smooth1 = rsi1.ewm(span=3, adjust=False).mean()
    smooth2 = rsi2.ewm(span=3, adjust=False).mean()
    sig = rsi2.rolling(window=14).mean()

    print("\n📊 Поточні значення RSI Pro (остання свічка):")
    print(f"   Smooth1 (Fast): {smooth1.iloc[-1]:.2f}")
    print(f"   Smooth2 (Slow): {smooth2.iloc[-1]:.2f}")
    print(f"   Signal (SMA14): {sig.iloc[-1]:.2f}")
    print(f"   RSI(14):        {rsi1.iloc[-1]:.2f}")
    print(f"   RSI(20):        {rsi2.iloc[-1]:.2f}")
    print(f"   Ціна закриття:  ${df['close'].iloc[-1]:,.2f}")
    print(f"\n🎯 Чому немає сигналу:")

    s1, s2, sg = smooth1.iloc[-1], smooth2.iloc[-1], sig.iloc[-1]
    prev_s1, prev_sg = smooth1.iloc[-2], sig.iloc[-2]

    if prev_s1 > prev_sg and s1 <= sg:
        print("   ⚠️ Майже ведмежий перетин!")
    elif prev_s1 < prev_sg and s1 >= sg:
        print("   ⚠️ Майже бичий перетин!")
    else:
        print(f"   • Fast RSI {'вище' if s1 > sg else 'нижче'} сигнальної лінії (немає перетину)")

    if s1 >= 80:
        print("   • В зоні Overbought (>80)")
    elif s1 <= 20:
        print("   • В зоні Oversold (<20)")
    else:
        print(f"   • В нейтральній зоні ({s1:.1f}) — далеко від 80/20")

    print(f"\n⏱ Наступна перевірка: коли з'явиться перетин або вхід/вихід з зон.")

if __name__ == "__main__":
    print("=== RSI Pro Bot — Тест ===")
    send_test()
    show_current_values()
