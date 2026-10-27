# TG Monitor — Personal AI Telegram Signal Filter

Мультиюзерный бот с AI-фильтрацией, системой подписок и пулом аккаунтов.

---

## Быстрый старт

```bash
git clone <repo> && cd tg_monitor
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполни
python main.py
```

---

## Настройка `.env`

### Обязательное

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) |
| `OWNER_CHAT_ID` | Твой ID [@userinfobot](https://t.me/userinfobot) |
| `ACCOUNT_POOL` | Аккаунты для прослушивания (см. ниже) |

### ACCOUNT_POOL

Формат: `API_ID:API_HASH:session_name` — через запятую для нескольких аккаунтов.

```
ACCOUNT_POOL=12345678:abcdef:main_session,87654321:fedcba:backup1_session
```

- `API_ID` и `API_HASH` — с [my.telegram.org/apps](https://my.telegram.org/apps)
- `session_name` — любое имя (файл сессии сохранится в `data/`)
- Первый аккаунт = основной, остальные подключаются по мере заполнения

При первом запуске Telethon попросит войти в каждый аккаунт.

---

## Архитектура

```
Пользователь добавляет каналы (/add_channel)
         ↓
Бесплатно: до 5 каналов → слушает основной аккаунт
Платно: Stars / TON → пул аккаунтов (основной → запасной → ...)
Своё: /own_account → неограниченно, на своём аккаунте
         ↓
Telethon слушает каналы → LLM классифицирует
         ↓
Score ≥ 70 → уведомление нужным пользователям
         ↓
👍/👎 → обновление весов интересов
```

---

## Команды пользователя

| Команда | Описание |
|---|---|
| `/add_channel @chan` | Добавить канал |
| `/my_channels` | Мои каналы |
| `/remove_channel @chan` | Удалить канал |
| `/add_interest тема` | Добавить интерес |
| `/list_interests` | Интересы с весами |
| `/remove_interest тема` | Удалить интерес |
| `/plan` | Текущий план |
| `/buy` | Купить подписку |
| `/own_account` | Инструкция по своему аккаунту |
| `/status` | Статус |

## Команды администратора (только ты)

| Команда | Описание |
|---|---|
| `/admin` | Общая сводка |
| `/admin_payments` | Ожидающие платежи TON |
| `/admin_users` | Список пользователей |

---

## Тарифы

| | Описание |
|---|---|
| 🆓 Free | До 5 каналов — бесплатно |
| ⭐ Stars | 50 Stars × доп. каналов × месяцев |
| 💎 TON | 0.5 TON × доп. каналов × месяцев |
| 🔑 Свой акк | Неограниченно, /own_account |

### Флоу оплаты Stars
Автоматически: счёт → оплата → подписка активируется мгновенно.

### Флоу оплаты TON
Пользователь → переводит TON → присылает чек → тебе уведомление с кнопками ✅/❌ → при подтверждении подписка активируется.

---

## Деплой

### systemd
```ini
[Unit]
Description=TG Monitor
After=network.target

[Service]
WorkingDirectory=/path/to/tg_monitor
ExecStart=/path/to/.venv/bin/python main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Docker
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```
