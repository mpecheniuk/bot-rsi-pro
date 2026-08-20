🤖 RSI Pro Telegram Signal Bot — Binance Edition
Бот для відправки сигналів індикатора RSI Pro у Telegram-канал.
✅ Що змінилося
Table
Стара версія	Ця версія
Джерело даних	OpenMarket API (платний, 403 помилки)	Binance API (безкоштовно, публічний)
Потрібен API ключ	Так (OpenMarket)	Ні
Rate limits	Обмежені	1200 запитів/хв (більш ніж достатньо)
Доступність	Залежить від тарифу	24/7 без обмежень
📋 Що робить бот
Завантажує 4h свічки BTCUSDT з Binance Public API (безкоштовно)
Розраховує RSI Pro точно за вихідним кодом kScript:
RSI(14) та RSI(20) на закритті
EMA(3) згладжування обох RSI
SMA(14) від RSI(20) як сигнальна лінія
Пороги 80/20
Відправляє сигнали в Telegram при перетинах та вході/виході з зон
🚀 Швидкий старт
1. Завантаж файли
rsi_pro_bot.py
requirements.txt
Procfile
railway.toml
.gitignore
2. Налаштуй тільки Telegram (2 змінні)
bash
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
export TELEGRAM_CHAT_ID="-1001234567890"
Як отримати:
TELEGRAM_BOT_TOKEN — пиши @BotFather → /newbot
TELEGRAM_CHAT_ID — створи канал, додай бота адміном, потім:
bash
curl https://api.telegram.org/bot<TOKEN>/getUpdates
3. Тест локально
bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
python3 rsi_pro_bot.py
4. Деплой на Railway
bash
git init
git add .
git commit -m "RSI Pro Bot"
# створи репо на GitHub і запуш
На railway.app:
New Project → Deploy from GitHub repo
Вибери свій репозиторій
Перейди у Variables → додай:
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
Deploy
Готово! Бот працює 24/7.
📊 Логіка сигналів
Table
Сигнал	Emoji	Умова
Бичий перетин	🟢	smooth1 перетинає sig знизу вгору
Ведмежий перетин	🔴	smooth1 перетинає sig зверху вниз
Сильний бичий	🟢🟢	smooth2 перетинає sig знизу вгору
Сильний ведмежий	🔴🔴	smooth2 перетинає sig зверху вниз
Вихід з OB	📉	smooth1 покидає зону >80
Вихід з OS	📈	smooth1 покидає зону <20
Вхід у OB	🚀	smooth1 входить у зону >80
Вхід у OS	💥	smooth1 входить у зону <20
⏰ Автозапуск
bash
# Railway (рекомендовано)
# Вже налаштовано в railway.toml — просто деплой

# Локально в loop
python3 rsi_pro_bot.py --loop --interval 5

# Cron на VPS
*/5 * * * * cd /path && python3 rsi_pro_bot.py >> bot.log 2>&1
🔧 Кастомізація
У коді можеш змінити:
SYMBOL — інша пара (напр. ETHUSDT, SOLUSDT)
INTERVAL — таймфрейм (1h, 2h, 1d)
FAST_RSI, SLOW_RSI, EMA_SMOOTH, SIG_LEN — параметри індикатора
OB_THRES, OS_THRES — пороги зон
⚠️ Важливо
Binance API має ліміт 1200 запитів/хв — наш бот використовує 1 запит кожні 5 хв, це безпечно
Якщо Binance API недоступний (рідко), бот відправить помилку в Telegram
OPENMARKET_API_KEY більше не потрібен — можеш видалити цю змінну
📜 Ліцензія
MIT — використовуй на свій розсуд. Це не фінансова порада.
