import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID", "0"))

# LLM — выбор: openai | gemini | deepseek
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek").lower()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Classification
RELEVANCE_THRESHOLD = int(os.getenv("RELEVANCE_THRESHOLD", "70"))

# Database
DB_PATH = os.getenv("DB_PATH", "data/bot.db")

# Payment
TON_WALLET = os.getenv("TON_WALLET", "")
CARD_NUMBER = os.getenv("CARD_NUMBER", "")
CARD_OWNER = os.getenv("CARD_OWNER", "")
ADMIN_ACTION_PASSWORD = os.getenv("ADMIN_ACTION_PASSWORD", "")
SUM_PER_TON = float(os.getenv("SUM_PER_TON", "26000"))
STARS_PER_EXTRA_CHANNEL = int(os.getenv("STARS_PER_EXTRA_CHANNEL", "50"))
TON_PER_EXTRA_CHANNEL = float(os.getenv("TON_PER_EXTRA_CHANNEL", "0.5"))
FREE_CHANNEL_LIMIT = int(os.getenv("FREE_CHANNEL_LIMIT", "5"))

# Полное сканирование канала за всё время — разовая платная функция.
# price_usd = SCAN_SAFETY_MARGIN * (tokens * SCAN_TOKEN_PRICE_USD) / SCAN_TOKEN_DIVISOR + SCAN_FLAT_FEE_USD
SCAN_TOKEN_PRICE_USD = float(os.getenv("SCAN_TOKEN_PRICE_USD", "2.12"))
SCAN_TOKEN_DIVISOR = float(os.getenv("SCAN_TOKEN_DIVISOR", "14000000"))
SCAN_FLAT_FEE_USD = float(os.getenv("SCAN_FLAT_FEE_USD", "1.5"))
SCAN_SAFETY_MARGIN = float(os.getenv("SCAN_SAFETY_MARGIN", "1.15"))
USD_PER_TON = float(os.getenv("USD_PER_TON", "2.0"))

# Multi-account pool
ACCOUNT_POOL_RAW = os.getenv("ACCOUNT_POOL", "")
MAX_CHANNELS_PER_ACCOUNT = int(os.getenv("MAX_CHANNELS_PER_ACCOUNT", "450"))

def parse_account_pool() -> list[dict]:
    accounts = []
    for entry in ACCOUNT_POOL_RAW.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) != 3:
            continue
        accounts.append({
            "api_id": int(parts[0].strip()),
            "api_hash": parts[1].strip(),
            "session": f"data/{parts[2].strip()}",
        })
    if not accounts and API_ID and API_HASH:
        accounts.append({
            "api_id": API_ID,
            "api_hash": API_HASH,
            "session": "data/main_session",
        })
    return accounts

ACCOUNT_POOL = parse_account_pool()
