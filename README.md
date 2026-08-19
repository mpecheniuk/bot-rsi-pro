# 🤖 RSI Pro Telegram Signal Bot

Бот для відправки сигналів індикатора **RSI Pro** з [OpenMarket](https://openmarket.xyz) у Telegram-канал.

## 📋 Що робить бот

1. Завантажує 4h свічки **BTCUSDT** з Binance Futures через OpenMarket API
2. Розраховує **RSI Pro** точно за вихідним кодом kScript:
   - `RSI(14)` та `RSI(20)` на закритті
   - `EMA(3)` згладжування обох RSI
   - `SMA(14)` від RSI(20) як сигнальна лінія
   - Пороги **80/20**
3. Відправляє сигнали в Telegram при:
   - 🟢🔴 **Перетині** Fast/Slow RSI з сигнальною лінією
   - 📈📉 **Вході/виході** з зон Overbought/Oversold

## 🚀 Швидкий старт

### 1. Встановлення

```bash
# Клонування/завантаження файлів
cd rsi_pro_bot

# Віртуальне середовище (рекомендовано)
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Залежності
pip install -r requirements.txt
```

### 2. Налаштування змінних оточення

```bash
export OPENMARKET_API_KEY="om_your_key_here"
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
export TELEGRAM_CHAT_ID="-1001234567890"
```

**Як отримати:**
- `OPENMARKET_API_KEY` — у налаштуваннях акаунта на [openmarket.xyz](https://openmarket.xyz)
- `TELEGRAM_BOT_TOKEN` — пиши `@BotFather` → `/newbot`
- `TELEGRAM_CHAT_ID` — створи канал, додай бота адміном, потім:
  ```bash
  curl https://api.telegram.org/bot<TOKEN>/getUpdates
  ```
  Або використай `@userinfobot`.

### 3. Тестовий запуск

```bash
python3 rsi_pro_bot.py
```

При успішному запуску побачиш поточні значення RSI Pro. Якщо є сигнал — він відправиться в Telegram.

### 4. Автозапуск (рекомендовано)

#### Варіант A: Cron (на VPS)

Перевірка кожні 5 хвилин:
```cron
*/5 * * * * cd /path/to/rsi_pro_bot && /path/to/venv/bin/python3 rsi_pro_bot.py >> bot.log 2>&1
```

#### Варіант B: Systemd сервіс

Створи файл `/etc/systemd/system/rsi-pro-bot.service`:

```ini
[Unit]
Description=RSI Pro Telegram Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/rsi_pro_bot
Environment=OPENMARKET_API_KEY=your_key
Environment=TELEGRAM_BOT_TOKEN=your_token
Environment=TELEGRAM_CHAT_ID=-1001234567890
ExecStart=/path/to/venv/bin/python3 /path/to/rsi_pro_bot/rsi_pro_bot.py --loop --interval 5
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable rsi-pro-bot
sudo systemctl start rsi-pro-bot
sudo journalctl -u rsi-pro-bot -f
```

#### Варіант C: Безперервний loop (локально)

```bash
python3 rsi_pro_bot.py --loop --interval 5
```

## 📊 Логіка сигналів

| Сигнал | Emoji | Умова |
|--------|-------|-------|
| Бичий перетин | 🟢 | `smooth1` перетинає `sig` знизу вгору |
| Ведмежий перетин | 🔴 | `smooth1` перетинає `sig` зверху вниз |
| Сильний бичий | 🟢🟢 | `smooth2` перетинає `sig` знизу вгору |
| Сильний ведмежий | 🔴🔴 | `smooth2` перетинає `sig` зверху вниз |
| Вихід з OB | 📉 | `smooth1` покидає зону >80 |
| Вихід з OS | 📈 | `smooth1` покидає зону <20 |
| Вхід у OB | 🚀 | `smooth1` входить у зону >80 |
| Вхід у OS | 💥 | `smooth1` входить у зону <20 |

## 🛡 Дедуплікація

Бот зберігає стан у файлі `rsi_pro_state.json` і не відправляє той самий сигнал на тій же свічці двічі. Це запобігає спаму при частих запусках.

## 📁 Файли

- `rsi_pro_bot.py` — основний скрипт
- `requirements.txt` — Python-залежності
- `rsi_pro_state.json` — файл стану (створюється автоматично)
- `bot.log` — логи (якщо перенаправляєш stdout)

## ⚠️ Важливо

- Таймфрейм 4h → свічка закривається о :00, :04, :08... UTC. Рекомендовано запускати на 2-5 хвилині після закриття.
- OpenMarket API має rate limits. Запит свічок важить мало, але не запускай щохвилини без потреби.
- Ніколи не коміть `.env` файли з ключами в публічні репозиторії!

## 🔧 Кастомізація

У коді можеш змінити:
- `FAST_RSI`, `SLOW_RSI`, `EMA_SMOOTH`, `SIG_LEN` — параметри індикатора
- `OB_THRES`, `OS_THRES` — пороги зон
- `INTERVAL` — таймфрейм (напр. `HOUR`, `DAY`)
- `RAW_SYMBOL` — інший символ (напр. `ETHUSDT`)

## 📜 Ліцензія

MIT — використовуй на свій розсуд. Це не фінансова порада.
