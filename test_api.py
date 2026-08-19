#!/usr/bin/env python3
"""
Тестовий скрипт для перевірки з'єднання з OpenMarket API.
Запусти перед основним ботом, щоб переконатися, що ключ працює.
"""

import os
import requests
import sys

API_KEY = os.getenv("OPENMARKET_API_KEY", "")
if not API_KEY:
    print("❌ Встанови змінну OPENMARKET_API_KEY")
    sys.exit(1)

print(f"🔑 Ключ: {API_KEY[:8]}...{API_KEY[-4:]}")
print("🌐 Тестуємо з'єднання з api.openmarket.xyz...")

# Тест 1: Usage (zero-weight endpoint)
try:
    r = requests.get(
        "https://api.openmarket.xyz/v1/usage",
        headers={"X-OpenMarket-Key": API_KEY},
        timeout=10
    )
    r.raise_for_status()
    print(f"✅ /v1/usage: {r.status_code}")
    print(f"   Ліміти: {r.json()}")
except Exception as e:
    print(f"❌ /v1/usage помилка: {e}")
    sys.exit(1)

# Тест 2: Останні 3 свічки BTCUSDT 4h
print("\n📊 Завантажуємо тестові свічки BTCUSDT 4h...")
try:
    r = requests.get(
        "https://api.openmarket.xyz/v1/points",
        params={
            "type": "TRADE_SIDE_AGNOSTIC_AGG",
            "exchange": "BINANCE_FUTURES",
            "rawSymbol": "BTCUSDT",
            "interval": "FOUR_HOURS",
            "period": 43200,  # 12 годин
        },
        headers={"X-OpenMarket-Key": API_KEY},
        timeout=15
    )
    r.raise_for_status()
    data = r.json()
    series = data.get("series", [])
    if series:
        points = series[0]["points"]
        print(f"✅ Отримано свічок: {len(points)}")
        if points:
            last = points[-1]
            print(f"   Остання свічка: O={last[1]} H={last[2]} L={last[3]} C={last[4]} Vol={last[5]}")
    else:
        print("⚠️ Порожня відповідь (можливо, невірні параметри)")
except Exception as e:
    print(f"❌ Помилка свічок: {e}")
    sys.exit(1)

print("\n🎉 Все працює! Можеш запускати rsi_pro_bot.py")
