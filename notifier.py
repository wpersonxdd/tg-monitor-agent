import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from classifier import ClassificationResult
from config import BOT_TOKEN

logger = logging.getLogger(__name__)

_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    return _bot


def _e(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def send_notification(
    user_id: int,
    channel: str,
    message_text: str,
    result: ClassificationResult,
    message_link: str | None = None,
    channel_msg_id: int | None = None,
):
    import database as db
    lang = db.get_lang(user_id)

    bot = get_bot()
    interests_str = ", ".join(result.matched_interests) if result.matched_interests else "—"
    preview = message_text[:600].strip()
    if len(message_text) > 600:
        preview += "…"

    link_label = "Открыть сообщение" if lang == "ru" else "Xabarni ochish"
    link_line = f'\n🔗 <a href="{message_link}">{link_label}</a>' if message_link else ""
    evidence_title = "Dalil" if lang == "uz" else "Доказательства"
    evidence_block = "".join(f"\n • {_e(e)}" for e in result.evidence)
    if evidence_block:
        evidence_block = f"\n🔎 <b>{evidence_title}:</b>{evidence_block}"

    if lang == "uz":
        text = (
            f"🚨 <b>Yangi tegishli post</b>\n\n"
            f"📢 <b>Kanal:</b> {_e(channel)}\n"
            f"🎯 <b>Ball:</b> {result.score}/100\n"
            f"💡 <b>Sabab:</b> {_e(result.reason)}\n"
            f"🏷 <b>Qiziqishlar:</b> {_e(interests_str)}"
            f"{evidence_block}"
            f"{link_line}\n\n"
            f"<blockquote>{_e(preview)}</blockquote>"
        )
    else:
        text = (
            f"🚨 <b>Новый релевантный пост</b>\n\n"
            f"📢 <b>Канал:</b> {_e(channel)}\n"
            f"🎯 <b>Score:</b> {result.score}/100\n"
            f"💡 <b>Причина:</b> {_e(result.reason)}\n"
            f"🏷 <b>Интересы:</b> {_e(interests_str)}"
            f"{evidence_block}"
            f"{link_line}\n\n"
            f"<blockquote>{_e(preview)}</blockquote>"
        )

    # Feedback buttons
    kb = None
    if channel_msg_id:
        channel_safe = channel.replace(":", "_")
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="👍", callback_data=f"fb:like:{channel_safe}:{channel_msg_id}"),
            InlineKeyboardButton(text="👎", callback_data=f"fb:dislike:{channel_safe}:{channel_msg_id}"),
        ]])

    try:
        await bot.send_message(chat_id=user_id, text=text, reply_markup=kb)
        db.increment_stat("notifications_sent")
        if channel_msg_id:
            db.record_sent_notification(
                channel=channel,
                message_id=channel_msg_id,
                user_id=user_id,
                matched_interests=result.matched_interests,
                score=result.score,
            )
    except Exception as exc:
        if "Forbidden" in str(exc):
            db.mark_bot_blocked(user_id)
        logger.error("Failed to send notification to %s: %s", user_id, exc)


async def close_bot():
    global _bot
    if _bot:
        await _bot.session.close()
        _bot = None
