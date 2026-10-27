"""
Payment flow helpers.
Stars: native Telegram Payments (invoice → pre_checkout → successful_payment).
TON: manual — user sends TON to wallet, uploads screenshot/tx hash, owner approves.
"""
from config import (
    TON_WALLET, STARS_PER_EXTRA_CHANNEL, TON_PER_EXTRA_CHANNEL, FREE_CHANNEL_LIMIT,
    SCAN_TOKEN_PRICE_USD, SCAN_TOKEN_DIVISOR, SCAN_FLAT_FEE_USD, SCAN_SAFETY_MARGIN, USD_PER_TON,
    SUM_PER_TON,
)


def ton_to_sum(ton_amount: float) -> int:
    """Card payments are quoted in сум, converted from the TON price at a fixed rate."""
    return round(ton_amount * SUM_PER_TON)


try:
    import tiktoken
    _ENCODER = tiktoken.get_encoding("cl100k_base")
except Exception:
    tiktoken = None
    _ENCODER = None


def estimate_scan_tokens(message_texts: list[str]) -> int:
    """Token estimate for running one classify() call per message.

    Uses tiktoken — real BPE tokenization, same algorithm family as the LLM's
    own tokenizer — for the post text itself. DeepSeek doesn't publish an
    exact tiktoken-compatible encoding, so this is still an approximation for
    that provider, but a much closer one than counting characters. Falls back
    to a character heuristic only if tiktoken isn't installed.

    A fixed per-call overhead is added for the system prompt, interest text
    and JSON response schema, which aren't part of the post text itself.
    """
    FIXED_OVERHEAD_PER_CALL = 250

    if _ENCODER is not None:
        token_counts = (len(_ENCODER.encode(t)) for t in message_texts)
    else:
        token_counts = (len(t) // 3 for t in message_texts)

    return sum(token_counts) + FIXED_OVERHEAD_PER_CALL * len(message_texts)


def calc_scan_price(estimated_tokens: int) -> dict:
    """Price for the one-off full-channel-history scan, based on estimated token usage.

    price_usd = SCAN_SAFETY_MARGIN * (tokens * SCAN_TOKEN_PRICE_USD) / SCAN_TOKEN_DIVISOR + SCAN_FLAT_FEE_USD
    """
    usd = SCAN_SAFETY_MARGIN * (estimated_tokens * SCAN_TOKEN_PRICE_USD) / SCAN_TOKEN_DIVISOR + SCAN_FLAT_FEE_USD
    ton = usd / USD_PER_TON
    return {
        "estimated_tokens": estimated_tokens,
        "usd": round(usd, 2),
        "ton": round(ton, 2),
    }


def calc_price(current_channels: int, desired_total: int, months: int = 1, discount_percent: int = 0) -> dict:
    """Calculate what the user needs to pay."""
    extra = max(0, desired_total - FREE_CHANNEL_LIMIT)
    stars = extra * STARS_PER_EXTRA_CHANNEL * months
    ton = round(extra * TON_PER_EXTRA_CHANNEL * months, 2)
    if discount_percent:
        stars = round(stars * (100 - discount_percent) / 100)
        ton = round(ton * (100 - discount_percent) / 100, 2)
    return {
        "extra_channels": extra,
        "months": months,
        "stars": stars,
        "ton": ton,
        "discount_percent": discount_percent,
    }


def payment_text(extra_channels: int, months: int, discount_percent: int = 0) -> str:
    stars = extra_channels * STARS_PER_EXTRA_CHANNEL * months
    ton = round(extra_channels * TON_PER_EXTRA_CHANNEL * months, 2)
    discount_line = ""
    if discount_percent:
        stars = round(stars * (100 - discount_percent) / 100)
        ton = round(ton * (100 - discount_percent) / 100, 2)
        discount_line = f"🎁 Применена скидка по промокоду: <b>-{discount_percent}%</b>\n\n"
    return (
        f"💳 <b>Оплата подписки</b>\n\n"
        f"{discount_line}"
        f"Лишних каналов: <b>{extra_channels}</b>\n"
        f"Период: <b>{months} мес.</b>\n\n"
        f"Сумма:\n"
        f"  ⭐ <b>{stars} Stars</b>  или\n"
        f"  💎 <b>{ton} TON</b>\n\n"
        f"<b>Как оплатить:</b>\n"
        f"1️⃣ <b>Stars</b> — нажми кнопку ниже, оплата прямо в Telegram\n"
        f"2️⃣ <b>TON</b> — переведи <code>{ton}</code> TON на адрес:\n"
        f"   <code>{TON_WALLET}</code>\n"
        f"   затем отправь сюда скриншот или хэш транзакции"
    )
