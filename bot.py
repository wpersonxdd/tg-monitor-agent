"""
aiogram 3.x bot — multi-user, payments, admin panel.
"""
import logging
import asyncio
import re
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    LabeledPrice, PreCheckoutQuery,
    ContentType,
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import config
import database as db
from account_pool import get_account_for_new_channel, get_pool_status
from payments import calc_price, payment_text, calc_scan_price, estimate_scan_tokens, ton_to_sum
from i18n import t, AI_LANG_INSTRUCTION

logger = logging.getLogger(__name__)
router = Router()

# Пароль-подтверждение для чувствительных админских действий (бан/разбан).
ADMIN_ACTION_PASSWORD = config.ADMIN_ACTION_PASSWORD


# ─── FSM States ───────────────────────────────────────────────────────────────

class PayTON(StatesGroup):
    waiting_receipt = State()
    waiting_months = State()

class BuyFlow(StatesGroup):
    choose_method = State()
    choose_months = State()

class AdminConfirm(StatesGroup):
    waiting_password = State()

class LangSelect(StatesGroup):
    choosing = State()

class AdminDM(StatesGroup):
    waiting_user_id = State()
    waiting_message = State()

class AdminBroadcastState(StatesGroup):
    waiting_text = State()        # таргетированная рассылка (по фильтру)

class AdminBroadcastAll(StatesGroup):
    waiting_text = State()        # обычная рассылка всем

class MenuFlow(StatesGroup):
    waiting_channel_to_add = State()
    waiting_channel_to_remove = State()
    waiting_interest_to_add = State()
    waiting_interest_to_remove = State()
    waiting_promo_code = State()

class FullScanFlow(StatesGroup):
    waiting_channel = State()
    waiting_interest = State()
    waiting_receipt = State()


# ─── Reply-keyboard menus ───────────────────────────────────────────────────────

def kb_main_menu(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_channels")), KeyboardButton(text=t(lang, "btn_interests"))],
            [KeyboardButton(text=t(lang, "btn_subscription")), KeyboardButton(text=t(lang, "btn_packs"))],
            [KeyboardButton(text=t(lang, "btn_more"))],
            [KeyboardButton(text=t(lang, "btn_scan"))],
        ],
        resize_keyboard=True,
    )


def kb_channels_menu(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_add_channel")), KeyboardButton(text=t(lang, "btn_my_channels"))],
            [KeyboardButton(text=t(lang, "btn_remove_channel"))],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
    )


def kb_interests_menu(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_add_interest")), KeyboardButton(text=t(lang, "btn_list_interests"))],
            [KeyboardButton(text=t(lang, "btn_remove_interest"))],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
    )


def kb_subscription_menu(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_buy")), KeyboardButton(text=t(lang, "btn_my_plan"))],
            [KeyboardButton(text=t(lang, "btn_promo"))],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
    )


def kb_packs_menu(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_add_pack")), KeyboardButton(text=t(lang, "btn_my_packs"))],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
    )


def kb_more_menu(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_status")), KeyboardButton(text=t(lang, "btn_own_account"))],
            [KeyboardButton(text=t(lang, "btn_help")), KeyboardButton(text="🌐 Язык / Til")],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
    )


def kb_admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="💬 Написать юзеру"), KeyboardButton(text="📋 История DM")],
            [KeyboardButton(text="🚫 Чёрный список"), KeyboardButton(text="💳 Платежи")],
            [KeyboardButton(text="🧹 Очистить каналы"), KeyboardButton(text="📢 Рассылка")],
            [KeyboardButton(text="🎯 Рассылка по фильтру")],
            [KeyboardButton(text="🔙 Выйти из админки")],
        ],
        resize_keyboard=True,
    )


def _extract_channel_username(text: str) -> str:
    """Accepts @username, plain username, or a t.me link and normalizes to @username."""
    text = text.strip()
    m = re.search(r"(?:https?://)?t\.me/([A-Za-z0-9_]+)", text, re.IGNORECASE)
    if m:
        return f"@{m.group(1)}"
    return text if text.startswith("@") else f"@{text}"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _e(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _is_owner(user_id: int) -> bool:
    return user_id == config.OWNER_CHAT_ID


@router.message.outer_middleware()
async def _ban_check_message(handler, event: Message, data: dict):
    if event.from_user and db.is_banned(event.from_user.id) and not _is_owner(event.from_user.id):
        await event.answer("🚫 Ты заблокирован и не можешь использовать этого бота.")
        return
    return await handler(event, data)


@router.callback_query.outer_middleware()
async def _ban_check_callback(handler, event: CallbackQuery, data: dict):
    if event.from_user and db.is_banned(event.from_user.id) and not _is_owner(event.from_user.id):
        await event.answer("🚫 Ты заблокирован.", show_alert=True)
        return
    return await handler(event, data)


def _can_add_channel(user_id: int) -> tuple[bool, str]:
    """Check if user can add more channels (pack channels don't count toward this limit)."""
    count = db.count_user_paid_channels(user_id)
    if count < config.FREE_CHANNEL_LIMIT:
        return True, ""
    if db.has_own_account(user_id):
        return True, ""
    limit = config.FREE_CHANNEL_LIMIT + db.get_extra_channels(user_id)
    if count < limit:
        return True, ""
    return False, (
        f"У тебя уже {count} каналов — это лимит твоего плана ({limit}).\n\n"
        f"Чтобы добавить больше:\n"
        f"• /buy — оплатить подписку (Stars или TON)\n"
        f"• /own_account — добавить свой аккаунт Telegram"
    )


# ─── /start ───────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    db.upsert_user(user_id, message.from_user.username, message.from_user.first_name)
    lang = db.get_lang(user_id)
    # First-time users: ask language
    if not lang or lang not in ("ru", "uz"):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang:ru")],
            [InlineKeyboardButton(text="🇺🇿 O'zbek (lotin)", callback_data="set_lang:uz")],
        ])
        await message.answer(t("ru", "choose_language"), reply_markup=kb)
        return
    await _send_start(message, lang)


async def _send_start(message, lang: str):
    name = message.from_user.first_name or ("друг" if lang == "ru" else "do'st")
    await message.answer(
        t(lang, "start_greeting", name=_e(name), limit=config.FREE_CHANNEL_LIMIT),
        reply_markup=kb_main_menu(lang),
    )


@router.callback_query(F.data.startswith("set_lang:"))
async def set_lang_callback(callback: CallbackQuery):
    lang = callback.data.split(":")[1]
    user_id = callback.from_user.id
    db.upsert_user(user_id, callback.from_user.username, callback.from_user.first_name)
    db.set_lang(user_id, lang)
    await callback.message.edit_text(t(lang, "lang_set"))
    await callback.answer()
    name = callback.from_user.first_name or ("друг" if lang == "ru" else "do'st")
    await callback.bot.send_message(
        user_id,
        t(lang, "start_greeting", name=_e(name), limit=config.FREE_CHANNEL_LIMIT),
        reply_markup=kb_main_menu(lang),
    )


@router.message(Command("language"))
async def cmd_language(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang:ru")],
        [InlineKeyboardButton(text="🇺🇿 O'zbek (lotin)", callback_data="set_lang:uz")],
    ])
    await message.answer(
        t("ru", "choose_language") + "\n" + t("uz", "choose_language"),
        reply_markup=kb
    )


# ─── Reply-keyboard navigation ─────────────────────────────────────────────────

@router.message(F.text.in_({"📡 Каналы", "📡 Kanallar"}))
async def menu_channels(message: Message, state: FSMContext):
    await state.clear()
    lang=db.get_lang(message.from_user.id)
    await message.answer(t(lang,"section_channels"), reply_markup=kb_channels_menu(lang))


@router.message(F.text.in_({"🏷 Интересы", "🏷 Qiziqishlar"}))
async def menu_interests(message: Message, state: FSMContext):
    await state.clear()
    lang=db.get_lang(message.from_user.id)
    await message.answer(t(lang,"section_interests"), reply_markup=kb_interests_menu(lang))


@router.message(F.text.in_({"⭐ Подписка", "⭐ Obuna"}))
async def menu_subscription(message: Message, state: FSMContext):
    await state.clear()
    lang=db.get_lang(message.from_user.id)
    await message.answer(t(lang,"section_subscription"), reply_markup=kb_subscription_menu(lang))


@router.message(F.text.in_({"📦 Паки", "📦 Paklar"}))
async def menu_packs_section(message: Message, state: FSMContext):
    await state.clear()
    lang=db.get_lang(message.from_user.id)
    await message.answer(t(lang,"section_packs"), reply_markup=kb_packs_menu(lang))


@router.message(F.text.in_({"⚙️ Ещё", "⚙️ Ko'proq"}))
async def menu_more(message: Message, state: FSMContext):
    await state.clear()
    lang=db.get_lang(message.from_user.id)
    await message.answer(t(lang,"section_more"), reply_markup=kb_more_menu(lang))


@router.message(F.text.in_({"◀️ Назад", "◀️ Orqaga"}))
async def menu_back(message: Message, state: FSMContext):
    await state.clear()
    lang=db.get_lang(message.from_user.id)
    await message.answer(t(lang,"main_menu"), reply_markup=kb_main_menu(lang))


# Прямые действия (без доп. ввода) — просто переиспользуют логику существующих команд.

@router.message(F.text.in_({"📋 Мои каналы", "📋 Mening kanallarim"}))
async def menu_my_channels(message: Message):
    await cmd_my_channels(message)


@router.message(F.text.in_({"📋 Список интересов", "📋 Qiziqishlar ro'yxati"}))
async def menu_list_interests(message: Message):
    await cmd_list_interests(message)


@router.message(F.text.in_({"📋 Мой план", "📋 Mening rejam"}))
async def menu_plan(message: Message):
    await cmd_plan(message)


@router.message(F.text.in_({"💳 Купить подписку", "💳 Obuna sotib olish"}))
async def menu_buy(message: Message, state: FSMContext):
    await cmd_buy(message, state)


@router.message(F.text.in_({"📦 Мои паки", "📦 Mening paklarim"}))
async def menu_my_packs(message: Message):
    packs = db.get_user_packs(message.from_user.id)
    if not packs:
        await message.answer("У тебя пока нет подключенных паков. Нажми «➕ Добавить пак».")
        return
    text_lines = [
        f"📦 <b>{_e(p['name'])}</b> — {p['channels_count']} кан., {p['interests_count']} интересов\n"
        f"   подключён: {p['added_at'][:10]}"
        for p in packs
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗑 Отключить «{p['name']}»", callback_data=f"unpack:{p['id']}")]
        for p in packs
    ])
    await message.answer(
        "📦 <b>Твои подключенные паки:</b>\n\n" + "\n".join(text_lines),
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("unpack:"))
async def unpack_callback(callback: CallbackQuery):
    pack_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    if not db.has_user_added_pack(user_id, pack_id):
        await callback.answer("Этот пак у тебя не подключён.", show_alert=True)
        return

    pack = db.get_pack_by_id(pack_id)
    pack_name = pack["name"] if pack else "неизвестный пак"

    channels = db.get_user_pack_channels(user_id, pack_id)
    from listener import multi_listener
    for channel in channels:
        db.remove_user_channel(user_id, channel)
        if not db.get_channel_subscribers(channel):
            account_idx = db.get_channel_account(channel)
            if multi_listener and account_idx < len(multi_listener.listeners):
                await multi_listener.listeners[account_idx].leave_channel(channel)
            db.remove_channel_account(channel)

    db.remove_user_pack(user_id, pack_id)
    await callback.message.edit_text(
        f"✅ Пак «{_e(pack_name)}» отключён.\n"
        f"📡 Каналов убрано: {len(channels)}\n\n"
        f"<i>Интересы, добавленные из этого пака, остались — убрать их можно отдельно в разделе «Интересы».</i>"
    )
    await callback.answer()


@router.message(F.text.in_({"➕ Добавить пак", "➕ Pak qo'shish"}))
async def menu_add_pack_prompt(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    packs = db.get_all_packs()
    available = [p for p in packs if not db.has_user_added_pack(user_id, p["id"])]
    if not available:
        await message.answer("Нет паков для подключения — либо их пока нет, либо ты уже подключил все существующие.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"📦 {p['name']} ({p['channels_count']} кан., {p['interests_count']} инт.)",
            callback_data=f"pick_pack:{p['id']}"
        )]
        for p in available
    ])
    await message.answer("📦 Выбери пак, который хочешь подключить:", reply_markup=kb)


@router.callback_query(F.data.startswith("pick_pack:"))
async def pick_pack_callback(callback: CallbackQuery):
    pack_id = int(callback.data.split(":")[1])
    pack = db.get_pack_by_id(pack_id)
    if not pack:
        await callback.answer("Пак не найден.", show_alert=True)
        return
    text = await _add_pack_core(
        callback.bot, callback.from_user.id,
        callback.from_user.username, callback.from_user.first_name, pack
    )
    await callback.message.edit_text(text)
    await callback.answer()


@router.message(F.text.in_({"⚙️ Статус", "⚙️ Holat"}))
async def menu_status(message: Message):
    await cmd_status(message)


@router.message(F.text.in_({"🔑 Свой аккаунт", "🔑 O'z akkaunt"}))
async def menu_own_account(message: Message):
    await cmd_own_account(message)


@router.message(F.text.in_({"❓ Помощь", "❓ Yordam"}))
async def menu_help(message: Message):
    await cmd_help(message)


@router.message(F.text == "🌐 Язык / Til")
async def menu_language(message: Message):
    await cmd_language(message)


# Действия, которым нужен текстовый ввод — спрашиваем, затем переиспользуем core-логику.

@router.message(F.text.in_({"➕ Добавить канал", "➕ Kanal qo'shish"}))
async def menu_add_channel_prompt(message: Message, state: FSMContext):
    lang = db.get_lang(message.from_user.id)
    await state.set_state(MenuFlow.waiting_channel_to_add)
    await message.answer(t(lang, "add_channel_input"))


@router.message(MenuFlow.waiting_channel_to_add)
async def menu_add_channel_input(message: Message, state: FSMContext):
    await state.clear()
    await _add_channel_logic(message, message.text or "")


@router.message(F.text.in_({"🗑 Удалить канал", "🗑 Kanalni o'chirish"}))
async def menu_remove_channel_prompt(message: Message, state: FSMContext):
    await state.set_state(MenuFlow.waiting_channel_to_remove)
    lang=db.get_lang(message.from_user.id)
    await message.answer(t(lang,"remove_channel_input"))


@router.message(MenuFlow.waiting_channel_to_remove)
async def menu_remove_channel_input(message: Message, state: FSMContext):
    await state.clear()
    await _remove_channel_logic(message, message.text or "")


@router.message(F.text.in_({"➕ Добавить интерес", "➕ Qiziqish qo'shish"}))
async def menu_add_interest_prompt(message: Message, state: FSMContext):
    await state.set_state(MenuFlow.waiting_interest_to_add)
    lang=db.get_lang(message.from_user.id)
    await message.answer(t(lang,"add_interest_prompt"))


@router.message(MenuFlow.waiting_interest_to_add)
async def menu_add_interest_input(message: Message, state: FSMContext):
    await state.clear()
    await _add_interest_logic(message, (message.text or "").strip())


@router.message(F.text.in_({"🗑 Удалить интерес", "🗑 Qiziqishni o'chirish"}))
async def menu_remove_interest_prompt(message: Message, state: FSMContext):
    await state.set_state(MenuFlow.waiting_interest_to_remove)
    lang=db.get_lang(message.from_user.id)
    await message.answer(t(lang,"remove_interest_input"))


@router.message(MenuFlow.waiting_interest_to_remove)
async def menu_remove_interest_input(message: Message, state: FSMContext):
    await state.clear()
    await _remove_interest_logic(message, (message.text or "").strip())


@router.message(F.text.in_({"🎁 Промокод", "🎁 Promo-kod"}))
async def menu_promo_prompt(message: Message, state: FSMContext):
    await state.set_state(MenuFlow.waiting_promo_code)
    lang=db.get_lang(message.from_user.id)
    await message.answer(t(lang,"promo_prompt"))


@router.message(MenuFlow.waiting_promo_code)
async def menu_promo_input(message: Message, state: FSMContext):
    await state.clear()
    await _promo_logic(message, (message.text or "").strip())


# ─── /help ────────────────────────────────────────────────────────────────────

@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = db.get_lang(message.from_user.id)
    await message.answer(t(lang, "help_text"))


# ─── /plan ────────────────────────────────────────────────────────────────────

@router.message(Command("plan"))
async def cmd_plan(message: Message):
    user_id = message.from_user.id
    db.upsert_user(user_id, message.from_user.username, message.from_user.first_name)
    user = db.get_user(user_id)
    paid_count = db.count_user_paid_channels(user_id)
    pack_count = db.count_user_pack_channels(user_id)

    if db.is_premium(user_id):
        until = user["premium_until"][:10] if user.get("premium_until") else "∞"
        limit = config.FREE_CHANNEL_LIMIT + db.get_extra_channels(user_id)
        plan = f"⭐ <b>Premium</b> до {until} (лимит: {limit} каналов)"
    elif db.has_own_account(user_id):
        plan = "🔑 <b>Свой аккаунт</b>"
        limit = None
    else:
        limit = config.FREE_CHANNEL_LIMIT
        plan = f"🆓 <b>Free</b> (до {config.FREE_CHANNEL_LIMIT} каналов)"

    paid_line = f"Платных каналов: <b>{paid_count}/{limit}</b>" if limit is not None else f"Платных каналов: <b>{paid_count}</b>"
    pack_line = f"📦 Из паков (бесплатно): <b>{pack_count}</b>\n" if pack_count else ""

    await message.answer(
        f"📋 <b>Твой план</b>\n\n"
        f"{plan}\n"
        f"{paid_line}\n"
        f"{pack_line}"
        f"\nДобавить больше: /buy или /own_account"
    )


# ─── /add_channel ─────────────────────────────────────────────────────────────

@router.message(Command("add_channel"))
async def cmd_add_channel(message: Message):
    args = message.text.partition(" ")[2].strip()
    if not args:
        await message.answer("Укажи канал: /add_channel <b>@channel</b>")
        return
    await _add_channel_logic(message, args)


async def _add_channel_logic(message: Message, raw_arg: str):
    user_id = message.from_user.id
    lang = db.get_lang(user_id)
    db.upsert_user(user_id, message.from_user.username, message.from_user.first_name)

    channel = _extract_channel_username(raw_arg)

    ok, reason = _can_add_channel(user_id)
    if not ok:
        await message.answer(reason)
        return

    account_idx = get_account_for_new_channel()
    if account_idx is None:
        await message.answer(t(lang, "accounts_full"))
        return

    added = db.add_user_channel(user_id, channel, account_idx)
    if added:
        from listener import multi_listener
        if multi_listener and account_idx < len(multi_listener.listeners):
            await multi_listener.listeners[account_idx].join_channel(channel)

        count = db.count_user_paid_channels(user_id)
        limit = "∞" if db.has_own_account(user_id) else str(config.FREE_CHANNEL_LIMIT + db.get_extra_channels(user_id))
        await message.answer(t(lang, "channel_added", channel=_e(channel), count=count, limit=limit))
    else:
        await message.answer(t(lang, "channel_already_added", channel=_e(channel)))


# ─── /my_channels ─────────────────────────────────────────────────────────────

@router.message(Command("my_channels"))
async def cmd_my_channels(message: Message):
    user_id = message.from_user.id
    channels = db.get_user_channels_detailed(user_id)
    if not channels:
        await message.answer("У тебя нет каналов. Добавь: /add_channel @channel")
        return
    lang = db.get_lang(user_id)
    lines = []
    for i, c in enumerate(channels, 1):
        tag = f" 📦 <i>({_e(c['pack_name'])})</i>" if c.get("pack_name") else ""
        lines.append(f"  {i}. {_e(c['channel'])}{tag}")
    header = "📡 <b>Мои каналы</b>" if lang == "ru" else "📡 <b>Mening kanallarim</b>"
    await message.answer(f"{header} ({len(channels)}):\n" + "\n".join(lines))


# ─── /remove_channel ──────────────────────────────────────────────────────────
@router.message(Command("remove_channel"))
async def cmd_remove_channel(message: Message):
    args = message.text.partition(" ")[2].strip()
    if not args:
        await message.answer("Укажи канал: /remove_channel <b>@channel</b>")
        return
    await _remove_channel_logic(message, args)


async def _remove_channel_logic(message: Message, raw_arg: str):
    channel = _extract_channel_username(raw_arg)

    lang = db.get_lang(message.from_user.id)
    pack_name = db.get_user_channel_pack(message.from_user.id, channel)
    if pack_name:
        await message.answer(t(lang, "channel_from_pack", channel=_e(channel), pack=_e(pack_name)))
        return

    removed = db.remove_user_channel(message.from_user.id, channel)
    if not removed:
        await message.answer(t(lang, "channel_not_found", channel=_e(channel)))
        return

    await message.answer(t(lang, "channel_removed", channel=_e(channel)))

    # Если этот канал больше никто не отслеживает — отписываем аккаунт от него,
    # чтобы освободить слот в пуле и не висеть в канале без необходимости.
    if not db.get_channel_subscribers(channel):
        account_idx = db.get_channel_account(channel)
        from listener import multi_listener
        if multi_listener and account_idx < len(multi_listener.listeners):
            await multi_listener.listeners[account_idx].leave_channel(channel)
        db.remove_channel_account(channel)


# ─── /add_interest ────────────────────────────────────────────────────────────

@router.message(Command("add_interest"))
async def cmd_add_interest(message: Message):
    args = message.text.partition(" ")[2].strip()
    if not args:
        await message.answer("Укажи интерес: /add_interest <b>хакатон</b>")
        return
    await _add_interest_logic(message, args)


async def _add_interest_logic(message: Message, raw_arg: str):
    lang = db.get_lang(message.from_user.id)
    db.upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    added = db.add_interest(message.from_user.id, raw_arg)
    if added:
        await message.answer(t(lang, "interest_added", interest=_e(raw_arg)))
    else:
        await message.answer(t(lang, "interest_exists", interest=_e(raw_arg)))


# ─── /list_interests ──────────────────────────────────────────────────────────

@router.message(Command("list_interests"))
async def cmd_list_interests(message: Message):
    interests = db.list_interests(message.from_user.id)
    if not interests:
        await message.answer("Нет интересов. Добавь: /add_interest хакатон")
        return
    lines = []
    for i, item in enumerate(interests, 1):
        bar = "█" * int(item["weight"] * 5)
        lines.append(f"{i}. {item['interest']}  <code>[{bar}]</code> {item['weight']:.1f}")
    await message.answer("📋 <b>Интересы:</b>\n\n" + "\n".join(lines))


# ─── /remove_interest ─────────────────────────────────────────────────────────

@router.message(Command("remove_interest"))
async def cmd_remove_interest(message: Message):
    args = message.text.partition(" ")[2].strip()
    if not args:
        await message.answer("Укажи: /remove_interest <b>тема</b>")
        return
    await _remove_interest_logic(message, args)


async def _remove_interest_logic(message: Message, raw_arg: str):
    lang = db.get_lang(message.from_user.id)
    removed = db.remove_interest(message.from_user.id, raw_arg)
    if removed:
        await message.answer(t(lang, "interest_removed", interest=_e(raw_arg)))
    else:
        await message.answer(t(lang, "interest_not_found", interest=_e(raw_arg)))


# ─── Packs ────────────────────────────────────────────────────────────────────

@router.message(Command("packs"))
async def cmd_packs(message: Message):
    lang = db.get_lang(message.from_user.id)
    packs = db.get_all_packs()
    if not packs:
        await message.answer(t(lang, "packs_empty"))
        return
    ch_word = "кан." if lang == "ru" else "kanal"
    int_word = "интересов" if lang == "ru" else "qiziqish"
    lines = [
        f"📦 <b>{_e(p['name'])}</b> — {p['channels_count']} {ch_word}, {p['interests_count']} {int_word}"
        for p in packs
    ]
    await message.answer(t(lang, "packs_title") + "\n".join(lines) + t(lang, "packs_add_hint"))


@router.message(Command("add_pack"))
async def cmd_add_pack(message: Message):
    name = message.text.partition(" ")[2].strip()
    if not name:
        await message.answer("Укажи название: /add_pack <b>Название</b>\n\nСписок доступных: /packs")
        return
    await _add_pack_logic(message, name)


async def _add_pack_core(bot, user_id: int, username: str, first_name: str, pack: dict) -> str:
    db.upsert_user(user_id, username, first_name)

    if db.has_user_added_pack(user_id, pack["id"]):
        return "ℹ️ Ты уже добавил этот пак."

    from listener import multi_listener
    added_channels = 0
    for channel in pack["channels"]:
        account_idx = get_account_for_new_channel()
        if account_idx is None:
            continue  # пул аккаунтов заполнен, пропускаем этот канал
        added = db.add_user_channel(user_id, channel, account_idx, from_pack_id=pack["id"])
        if added:
            added_channels += 1
            if multi_listener and account_idx < len(multi_listener.listeners):
                await multi_listener.listeners[account_idx].join_channel(channel)

    added_interests = sum(1 for interest in pack["interests"] if db.add_interest(user_id, interest))
    db.record_user_pack(user_id, pack["id"])

    skipped = len(pack["channels"]) - added_channels
    warn = f"\n⚠️ {skipped} канал(ов) не добавлены — пул аккаунтов заполнен." if skipped else ""

    return (
        f"🎉 Пак <b>{_e(pack['name'])}</b> добавлен!\n\n"
        f"📡 Каналов добавлено: <b>{added_channels}</b>\n"
        f"🏷 Интересов добавлено: <b>{added_interests}</b>\n\n"
        f"Эти каналы бесплатные и не учитываются в твоём лимите.{warn}"
    )


async def _add_pack_logic(message: Message, raw_arg: str):
    pack = db.get_pack_by_name(raw_arg)
    if not pack:
        await message.answer(f"❓ Пак <b>{_e(raw_arg)}</b> не найден. Список доступных: /packs")
        return
    text = await _add_pack_core(
        message.bot, message.from_user.id, message.from_user.username, message.from_user.first_name, pack
    )
    await message.answer(text)


# ─── Фильтрация канала за всё время (разовая платная функция) ────────────────

@router.message(F.text.in_({"🔍 Фильтрация канала за всё время", "🔍 Kanal tarixini filtrlash"}))
async def menu_full_scan_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(FullScanFlow.waiting_channel)
    await message.answer(
        "🔍 <b>Фильтрация канала за всё время</b>\n\n"
        "Я просмотрю ВСЮ историю указанного канала через AI и пришлю посты, "
        "подходящие под твой интерес. Это разовая платная функция — после завершения "
        "канал и интерес никуда не сохраняются, обычный мониторинг тут не подключается.\n\n"
        "Цена зависит от объёма канала и считается заранее, до оплаты.\n\n"
        "Скинь ссылку (t.me/...) или @username канала:"
    )


@router.message(FullScanFlow.waiting_channel)
async def menu_full_scan_channel(message: Message, state: FSMContext):
    channel = _extract_channel_username((message.text or "").strip())
    await state.update_data(channel=channel)
    await state.set_state(FullScanFlow.waiting_interest)
    await message.answer("Какой интерес искать в этом канале? Напиши текстом:")


@router.message(FullScanFlow.waiting_interest)
async def menu_full_scan_interest(message: Message, state: FSMContext):
    data = await state.get_data()
    channel = data["channel"]
    interest = (message.text or "").strip()
    if not interest:
        await message.answer("Напиши текстом, что искать.")
        return

    await message.answer("⏳ Считаю объём канала, подожди немного...")

    from listener import multi_listener
    if not multi_listener or not multi_listener.listeners:
        await message.answer("⚠️ Сервис временно недоступен (нет подключённых аккаунтов).")
        await state.clear()
        return

    try:
        texts = await multi_listener.listeners[0].fetch_channel_texts(channel)
    except Exception as e:
        logger.error("Scan estimate fetch failed for %s: %s", channel, e)
        await message.answer(
            f"❌ Не удалось получить доступ к каналу <b>{_e(channel)}</b>. "
            f"Возможно, он приватный, не существует, или аккаунт не может его прочитать."
        )
        await state.clear()
        return

    if not texts:
        await message.answer("В этом канале не нашлось текстовых постов.")
        await state.clear()
        return

    message_texts = [t["text"] for t in texts]
    estimated_tokens = estimate_scan_tokens(message_texts)
    price = calc_scan_price(estimated_tokens)

    await state.update_data(
        interest=interest, message_count=len(texts),
        estimated_tokens=estimated_tokens, usd_price=price["usd"], ton_price=price["ton"],
    )
    await state.set_state(None)  # данные сохраняем, просто ждём нажатия кнопки, а не текста

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить и оплатить", callback_data="scan_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="scan_cancel"),
    ]])
    await message.answer(
        f"📊 Найдено постов: <b>{len(texts)}</b>\n"
        f"Канал: <b>{_e(channel)}</b>\n"
        f"Интерес: <b>{_e(interest)}</b>\n\n"
        f"💰 Цена: <b>{price['ton']} TON</b> (≈ ${price['usd']})\n"
        f"<i>Это итоговая сумма к оплате.</i>\n\n"
        f"Подтвердить и перейти к оплате?",
        reply_markup=kb
    )


@router.callback_query(F.data == "scan_cancel")
async def scan_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Отменено.")
    await callback.answer()


@router.callback_query(F.data == "scan_confirm")
async def scan_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ton_price = data.get("ton_price")
    sum_price = ton_to_sum(ton_price)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💎 {ton_price} TON", callback_data="scan_pay:ton")],
        [InlineKeyboardButton(text=f"💳 {sum_price} сум", callback_data="scan_pay:card")],
    ])
    await callback.message.edit_text("Выбери способ оплаты:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("scan_pay:"))
async def scan_pay_method(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split(":")[1]
    data = await state.get_data()
    ton_price = data.get("ton_price")

    await state.update_data(method=method)
    await state.set_state(FullScanFlow.waiting_receipt)

    if method == "card":
        sum_price = ton_to_sum(ton_price)
        await callback.message.edit_text(
            f"💳 Переведи <b>{sum_price} сум</b> на карту:\n"
            f"<code>{config.CARD_NUMBER}</code>\n"
            f"Получатель: <b>{config.CARD_OWNER}</b>\n\n"
            f"Затем пришли сюда скриншот перевода."
        )
    else:
        await callback.message.edit_text(
            f"💎 Переведи <b>{ton_price} TON</b> на адрес:\n"
            f"<code>{config.TON_WALLET}</code>\n\n"
            f"Затем пришли сюда скриншот или хэш транзакции."
        )
    await callback.answer()


@router.message(FullScanFlow.waiting_receipt)
async def scan_receipt_received(message: Message, state: FSMContext):
    data = await state.get_data()
    channel = data["channel"]
    interest = data["interest"]
    message_count = data["message_count"]
    estimated_tokens = data["estimated_tokens"]
    usd_price = data["usd_price"]
    ton_price = data["ton_price"]
    method = data.get("method", "ton")

    receipt_file_id = None
    receipt_text = None
    if message.photo:
        receipt_file_id = message.photo[-1].file_id
    elif message.document:
        receipt_file_id = message.document.file_id
    elif message.text:
        receipt_text = message.text
    else:
        await message.answer("Пришли скриншот или хэш транзакции.")
        return

    job_id = db.create_scan_job(
        user_id=message.from_user.id, channel=channel, interest=interest,
        message_count=message_count, estimated_tokens=estimated_tokens,
        usd_price=usd_price, ton_price=ton_price, method=method,
    )
    db.attach_scan_receipt(job_id, receipt_file_id, receipt_text)

    await message.answer("✅ Чек получен! Ожидай подтверждения — обычно до 1 часа.")
    await state.clear()

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_scan:{job_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_scan:{job_id}"),
    ]])
    amount_line = (
        f"Сумма: <b>{ton_to_sum(ton_price)} сум</b> (карта) (${usd_price})\n"
        if method == "card" else
        f"Сумма: <b>{ton_price} TON</b> (${usd_price})\n"
    )
    caption = (
        f"🔍 <b>Заявка на сканирование канала</b>\n\n"
        f"Пользователь: <code>{message.from_user.id}</code>\n"
        f"Канал: <b>{_e(channel)}</b>\n"
        f"Интерес: <b>{_e(interest)}</b>\n"
        f"Постов: <b>{message_count}</b>\n"
        f"{amount_line}"
        f"Заявка #<b>{job_id}</b>"
    )
    if receipt_text:
        caption += f"\n\nТекст: <code>{_e(receipt_text[:300])}</code>"

    try:
        bot = message.bot
        if receipt_file_id:
            await bot.send_photo(config.OWNER_CHAT_ID, photo=receipt_file_id, caption=caption, reply_markup=kb)
        else:
            await bot.send_message(config.OWNER_CHAT_ID, caption, reply_markup=kb)
    except Exception as e:
        logger.error("Failed to notify owner about scan payment: %s", e)


@router.callback_query(F.data.startswith("approve_scan:"))
async def approve_scan(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return
    job_id = int(callback.data.split(":")[1])
    job = db.get_scan_job(job_id)
    if not job:
        await callback.answer("Заявка не найдена.")
        return
    if job["status"] != "awaiting_approval":
        await callback.answer(f"Уже обработана: {job['status']}")
        return

    db.set_scan_job_status(job_id, "running")
    await callback.message.edit_caption(
        caption=(callback.message.caption or "") + "\n\n✅ <b>ПОДТВЕРЖДЕНО, ЗАПУЩЕНО</b>"
    )
    await callback.answer("Запускаю сканирование...")

    try:
        await callback.bot.send_message(
            job["user_id"],
            "✅ <b>Оплата подтверждена!</b> Запускаю сканирование канала — "
            "это может занять время, пришлю результаты по ходу работы."
        )
    except Exception as e:
        logger.error("Failed to notify user %s: %s", job["user_id"], e)

    asyncio.create_task(_run_scan_job(callback.bot, job_id))


@router.callback_query(F.data.startswith("reject_scan:"))
async def reject_scan(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return
    job_id = int(callback.data.split(":")[1])
    job = db.get_scan_job(job_id)
    if not job:
        await callback.answer("Заявка не найдена.")
        return

    db.set_scan_job_status(job_id, "rejected")
    await callback.message.edit_caption(
        caption=(callback.message.caption or "") + "\n\n❌ <b>ОТКЛОНЕНО</b>"
    )
    await callback.answer("Отклонено.")

    try:
        await callback.bot.send_message(
            job["user_id"],
            "❌ <b>Оплата не подтверждена.</b>\n\n"
            "Возможно, сумма не совпадает. Напиши в поддержку (@wpersonxd) или попробуй снова."
        )
    except Exception as e:
        logger.error("Failed to notify user %s: %s", job["user_id"], e)


async def _run_scan_job(bot, job_id: int):
    job = db.get_scan_job(job_id)
    if not job:
        return
    channel = job["channel"]
    interest = job["interest"]
    user_id = job["user_id"]

    from listener import multi_listener
    if not multi_listener or not multi_listener.listeners:
        await bot.send_message(user_id, "⚠️ Не удалось запустить сканирование — сервис недоступен.")
        db.set_scan_job_status(job_id, "failed")
        return
    classifier = multi_listener.classifier

    try:
        texts = await multi_listener.listeners[0].fetch_channel_texts(channel)
    except Exception as e:
        logger.error("Scan run fetch failed for %s: %s", channel, e)
        await bot.send_message(user_id, f"⚠️ Не удалось получить историю канала {channel} для запуска.")
        db.set_scan_job_status(job_id, "failed")
        return

    matches = 0
    for item in texts:
        text = item["text"]
        result = await classifier.classify(message_text=text, interests=[interest], channel=channel)
        if result.relevant and result.score >= config.RELEVANCE_THRESHOLD:
            matches += 1
            link = None
            m = re.match(r"@([A-Za-z0-9_]+)", channel)
            if m:
                link = f"https://t.me/{m.group(1)}/{item['id']}"
            quote = text[:300] + ("…" if len(text) > 300 else "")
            caption = (
                f"🔍 <b>{_e(channel)}</b> | оценка {result.score}/100\n"
                f"<i>{_e(result.reason)}</i>\n\n"
                f"{_e(quote)}"
            )
            if link:
                caption += f'\n\n<a href="{link}">Открыть пост</a>'
            try:
                await bot.send_message(user_id, caption)
            except Exception as e:
                logger.error("Failed to send scan match to %s: %s", user_id, e)
            await asyncio.sleep(0.1)

    db.finish_scan_job(job_id, matches)
    try:
        await bot.send_message(
            user_id,
            f"✅ <b>Готово!</b>\nПросмотрено постов: {len(texts)}\nНайдено подходящих: <b>{matches}</b>"
        )
    except Exception as e:
        logger.error("Failed to send scan completion to %s: %s", user_id, e)


# ─── /own_account ─────────────────────────────────────────────────────────────

@router.message(Command("own_account"))
async def cmd_own_account(message: Message):
    await message.answer(
        "🔑 <b>Добавить свой аккаунт</b>\n\n"
        "Это позволит подключить неограниченное количество каналов.\n\n"
        "<b>Инструкция:</b>\n"
        "1. Зайди на https://my.telegram.org/apps\n"
        "2. Создай приложение, получи <code>API_ID</code> и <code>API_HASH</code>\n"
        "3. Напиши мне: /set_account API_ID:API_HASH\n\n"
        "⚠️ Данные хранятся только на сервере, не передаются третьим лицам."
    )


@router.message(Command("set_account"))
async def cmd_set_account(message: Message):
    args = message.text.partition(" ")[2].strip()
    if not args or ":" not in args:
        await message.answer("Формат: /set_account <b>API_ID:API_HASH</b>")
        return
    # In production you'd save these and spin up a new Telethon session.
    # Here we just flag the user as having own account.
    db.set_own_account(message.from_user.id, True)
    await message.answer(
        "✅ Аккаунт отмечен! Теперь ты можешь добавлять неограниченное количество каналов.\n\n"
        "⚙️ Администратор настроит сессию вручную и уведомит тебя."
    )
    # Notify owner
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await bot.send_message(
            config.OWNER_CHAT_ID,
            f"🔑 Пользователь <b>{message.from_user.full_name}</b> "
            f"(id: <code>{message.from_user.id}</code>) "
            f"запросил подключение своего аккаунта.\n\n"
            f"Данные: <code>{_e(args)}</code>"
        )
    except Exception as e:
        logger.error("Failed to notify owner: %s", e)
    finally:
        await bot.session.close()


# ─── /buy ─────────────────────────────────────────────────────────────────────

@router.message(Command("promo"))
async def cmd_promo(message: Message):
    code = message.text.partition(" ")[2].strip()
    if not code:
        await message.answer("Укажи код: /promo <b>КОД</b>")
        return
    await _promo_logic(message, code)


async def _promo_logic(message: Message, raw_arg: str):
    user_id = message.from_user.id
    db.upsert_user(user_id, message.from_user.username, message.from_user.first_name)

    code = raw_arg
    valid, reason, promo = db.check_promo_code(code)
    if not valid:
        msg = {
            "not_found": "❓ Такого промокода не существует.",
            "expired": "⏰ Этот промокод уже истёк.",
            "exhausted": "😔 У этого промокода закончились активации.",
        }.get(reason, "❌ Промокод недействителен.")
        await message.answer(msg)
        return

    if not db.redeem_promo_code(code):
        await message.answer("😔 Этот промокод только что закончился — кто-то успел раньше.")
        return

    db.set_pending_promo(user_id, code, promo["discount_percent"])
    await message.answer(
        f"🎉 Промокод <b>{_e(code.upper())}</b> применён!\n"
        f"Скидка <b>{promo['discount_percent']}%</b> учтётся при следующей покупке — заходи в /buy."
    )


@router.message(Command("buy"))
async def cmd_buy(message: Message, state: FSMContext):
    user_id = message.from_user.id
    db.upsert_user(user_id, message.from_user.username, message.from_user.first_name)
    current = db.count_user_paid_channels(user_id)

    if current <= config.FREE_CHANNEL_LIMIT:
        extra = 1
    else:
        extra = current - config.FREE_CHANNEL_LIMIT

    await state.update_data(extra_channels=extra, user_id=user_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 месяц", callback_data="buy_months:1")],
        [InlineKeyboardButton(text="3 месяца (-0%)", callback_data="buy_months:3")],
        [InlineKeyboardButton(text="6 месяцев", callback_data="buy_months:6")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="buy_cancel")],
    ])

    await message.answer(
        f"🛒 <b>Покупка подписки</b>\n\n"
        f"Текущих каналов: <b>{current}</b>\n"
        f"Лишних каналов сверх бесплатных {config.FREE_CHANNEL_LIMIT}: <b>{extra}</b>\n\n"
        f"Цена: <b>{extra * config.STARS_PER_EXTRA_CHANNEL} Stars</b> или "
        f"<b>{round(extra * config.TON_PER_EXTRA_CHANNEL, 2)} TON</b> в месяц\n\n"
        f"Выбери период:",
        reply_markup=kb
    )
    await state.set_state(BuyFlow.choose_months)


@router.callback_query(F.data == "buy_cancel")
async def buy_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Отменено.")


@router.callback_query(F.data.startswith("buy_months:"))
async def buy_choose_months(callback: CallbackQuery, state: FSMContext):
    months = int(callback.data.split(":")[1])
    data = await state.get_data()
    extra = data.get("extra_channels", 1)
    user_id = callback.from_user.id

    pending_promo = db.get_pending_promo(user_id)
    discount = pending_promo["discount_percent"] if pending_promo else 0

    price = calc_price(0, extra + config.FREE_CHANNEL_LIMIT, months, discount_percent=discount)
    sum_amount = ton_to_sum(price["ton"])

    await state.update_data(months=months)
    await state.set_state(BuyFlow.choose_method)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"⭐ {price['stars']} Stars",
            callback_data=f"pay_stars:{extra}:{months}"
        )],
        [InlineKeyboardButton(
            text=f"💎 {price['ton']} TON",
            callback_data=f"pay_ton:{extra}:{months}"
        )],
        [InlineKeyboardButton(
            text=f"💳 {sum_amount} сум",
            callback_data=f"pay_card:{extra}:{months}"
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="buy_back")],
    ])

    await callback.message.edit_text(
        payment_text(extra, months, discount_percent=discount),
        reply_markup=kb
    )


@router.callback_query(F.data == "buy_back")
async def buy_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Используй /buy чтобы начать заново.")


# ─── Stars payment ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pay_stars:"))
async def pay_stars(callback: CallbackQuery, state: FSMContext):
    _, extra_str, months_str = callback.data.split(":")
    extra = int(extra_str)
    months = int(months_str)
    user_id = callback.from_user.id

    pending_promo = db.get_pending_promo(user_id)
    discount = pending_promo["discount_percent"] if pending_promo else 0
    stars = extra * config.STARS_PER_EXTRA_CHANNEL * months
    if discount:
        stars = round(stars * (100 - discount) / 100)

    await state.clear()

    bot = callback.bot
    await bot.send_invoice(
        chat_id=user_id,
        title="TG Monitor — подписка",
        description=f"{extra} доп. каналов на {months} мес.",
        payload=f"sub:{extra}:{months}:{user_id}",
        currency="XTR",  # Telegram Stars
        prices=[LabeledPrice(label="Подписка", amount=stars)],
        provider_token="",  # empty for Stars
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split(":")
    if parts[0] == "sub" and len(parts) == 4:
        extra, months, user_id_str = int(parts[1]), int(parts[2]), int(parts[3])
        db.set_premium(user_id_str, months, extra_channels=extra)
        db.clear_pending_promo(user_id_str)
        db.create_payment_request(
            user_id=user_id_str,
            method="stars",
            amount=str(message.successful_payment.total_amount),
            extra_channels=extra,
            months=months,
        )
        await message.answer(
            f"✅ <b>Оплата прошла!</b>\n\n"
            f"Подписка активирована на {months} мес.\n"
            f"Теперь ты можешь добавить ещё каналы: /add_channel"
        )
        # Notify owner
        bot = message.bot
        await bot.send_message(
            config.OWNER_CHAT_ID,
            f"⭐ <b>Новая оплата Stars</b>\n"
            f"Пользователь: <code>{user_id_str}</code>\n"
            f"Каналов: {extra}, месяцев: {months}\n"
            f"Сумма: {message.successful_payment.total_amount} Stars\n"
            f"<i>Подписка активирована автоматически.</i>"
        )


# ─── TON / Card payment (manual, owner-approved) ──────────────────────────────

@router.callback_query(F.data.startswith("pay_ton:"))
async def pay_ton_start(callback: CallbackQuery, state: FSMContext):
    await _start_manual_payment(callback, state, method="ton")


@router.callback_query(F.data.startswith("pay_card:"))
async def pay_card_start(callback: CallbackQuery, state: FSMContext):
    await _start_manual_payment(callback, state, method="card")


async def _start_manual_payment(callback: CallbackQuery, state: FSMContext, method: str):
    _, extra_str, months_str = callback.data.split(":")
    extra = int(extra_str)
    months = int(months_str)
    user_id = callback.from_user.id

    pending_promo = db.get_pending_promo(user_id)
    discount = pending_promo["discount_percent"] if pending_promo else 0
    ton = round(extra * config.TON_PER_EXTRA_CHANNEL * months, 2)
    if discount:
        ton = round(ton * (100 - discount) / 100, 2)

    await state.set_state(PayTON.waiting_receipt)
    await state.update_data(extra=extra, months=months, method=method, ton=ton, user_id=user_id)

    if method == "card":
        sum_amount = ton_to_sum(ton)
        await callback.message.edit_text(
            f"💳 <b>Оплата картой</b>\n\n"
            f"Переведи <b>{sum_amount} сум</b> на карту:\n"
            f"<code>{config.CARD_NUMBER}</code>\n"
            f"Получатель: <b>{config.CARD_OWNER}</b>\n\n"
            f"Затем пришли сюда скриншот перевода.\n\n"
            f"После проверки подписка будет активирована (обычно до 1 часа)."
        )
    else:
        await callback.message.edit_text(
            f"💎 <b>Оплата через TON</b>\n\n"
            f"Переведи <b>{ton} TON</b> на адрес:\n"
            f"<code>{config.TON_WALLET}</code>\n\n"
            f"Затем пришли сюда:\n"
            f"• скриншот транзакции, или\n"
            f"• хэш транзакции текстом\n\n"
            f"После проверки подписка будет активирована (обычно до 1 часа)."
        )
    await callback.answer()


@router.message(PayTON.waiting_receipt)
async def ton_receipt_received(message: Message, state: FSMContext):
    data = await state.get_data()
    extra = data["extra"]
    months = data["months"]
    ton = data["ton"]
    method = data.get("method", "ton")
    user_id = data["user_id"]

    receipt_file_id = None
    receipt_text = None

    if message.photo:
        receipt_file_id = message.photo[-1].file_id
    elif message.document:
        receipt_file_id = message.document.file_id
    elif message.text:
        receipt_text = message.text
    else:
        await message.answer("Пришли скриншот или хэш транзакции.")
        return

    amount_str = str(ton_to_sum(ton)) if method == "card" else str(ton)
    req_id = db.create_payment_request(
        user_id=user_id,
        method=method,
        amount=amount_str,
        extra_channels=extra,
        months=months,
        receipt_file_id=receipt_file_id,
        receipt_text=receipt_text,
    )

    await message.answer(
        "✅ Чек получен! Ожидай подтверждения — обычно до 1 часа."
    )
    await state.clear()

    # Notify owner with approve/reject buttons
    bot = message.bot
    user = message.from_user
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_ton:{req_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_ton:{req_id}"),
    ]])

    if method == "card":
        title = "💳 <b>Новый платёж картой</b>\n\n"
        amount_line = f"Сумма: <b>{ton_to_sum(ton)} сум</b>\n"
    else:
        title = "💎 <b>Новый платёж TON</b>\n\n"
        amount_line = f"Сумма: <b>{ton} TON</b>\n"

    caption = (
        f"{title}"
        f"Пользователь: <b>{_e(user.full_name)}</b> (<code>{user_id}</code>)\n"
        f"{amount_line}"
        f"Каналов: <b>{extra}</b>, месяцев: <b>{months}</b>\n"
        f"Заявка #<b>{req_id}</b>"
    )
    if receipt_text:
        caption += f"\n\nТекст: <code>{_e(receipt_text[:300])}</code>"

    try:
        if receipt_file_id:
            await bot.send_photo(
                config.OWNER_CHAT_ID,
                photo=receipt_file_id,
                caption=caption,
                reply_markup=kb,
            )
        else:
            await bot.send_message(
                config.OWNER_CHAT_ID,
                caption,
                reply_markup=kb,
            )
    except Exception as e:
        logger.error("Failed to notify owner about manual payment: %s", e)


# ─── Owner: approve / reject TON ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("approve_ton:"))
async def approve_ton(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return

    req_id = int(callback.data.split(":")[1])
    req = db.get_payment_request(req_id)
    if not req:
        await callback.answer("Заявка не найдена.")
        return
    if req["status"] != "pending":
        await callback.answer(f"Уже обработана: {req['status']}")
        return

    db.resolve_payment(req_id, "approved")
    db.set_premium(req["user_id"], req["months"], extra_channels=req["extra_channels"])
    db.clear_pending_promo(req["user_id"])

    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n✅ <b>ПОДТВЕРЖДЕНО</b>"
        if callback.message.caption else callback.message.text + "\n\n✅ <b>ПОДТВЕРЖДЕНО</b>"
    )
    await callback.answer("Подписка активирована!")

    # Notify user
    try:
        await callback.bot.send_message(
            req["user_id"],
            f"✅ <b>Оплата подтверждена!</b>\n\n"
            f"Подписка активирована на {req['months']} мес.\n"
            f"Добавляй каналы: /add_channel"
        )
    except Exception as e:
        logger.error("Failed to notify user %s: %s", req["user_id"], e)


@router.callback_query(F.data.startswith("reject_ton:"))
async def reject_ton(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return

    req_id = int(callback.data.split(":")[1])
    req = db.get_payment_request(req_id)
    if not req:
        await callback.answer("Заявка не найдена.")
        return

    db.resolve_payment(req_id, "rejected")
    await callback.message.edit_caption(
        caption=(callback.message.caption or callback.message.text) + "\n\n❌ <b>ОТКЛОНЕНО</b>"
    )
    await callback.answer("Отклонено.")

    try:
        await callback.bot.send_message(
            req["user_id"],
            "❌ <b>Оплата не подтверждена.</b>\n\n"
            "Возможно, сумма или адрес не совпадают. "
            "Напиши в поддержку (@wpersonxd) или попробуй снова: /buy"
        )
    except Exception as e:
        logger.error("Failed to notify user %s: %s", req["user_id"], e)


# ─── Feedback (👍/👎) ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("fb:"))
async def handle_feedback(callback: CallbackQuery):
    parts = callback.data.split(":")
    _, feedback, channel, mid_str = parts[0], parts[1], parts[2], parts[3]
    channel = channel.replace("_", ":")
    message_id = int(mid_str)
    user_id = callback.from_user.id

    sent = db.get_sent_notification(channel, message_id, user_id)
    score = sent["score"] if sent else 0
    if sent and sent["matched_interests"]:
        db.adjust_interest_weights(user_id, sent["matched_interests"], feedback)

    db.save_feedback(
        channel=channel,
        message_id=message_id,
        user_id=user_id,
        feedback=feedback,
        score=score,
    )
    emoji = "👍" if feedback == "like" else "👎"
    await callback.answer(f"{emoji} Учтено!")
    await callback.message.edit_reply_markup(reply_markup=None)


# ─── /status ──────────────────────────────────────────────────────────────────

@router.message(Command("status"))
async def cmd_status(message: Message):
    user_id = message.from_user.id
    interests = db.list_interests(user_id)
    channels = db.get_user_channels(user_id)
    premium = db.is_premium(user_id)
    own = db.has_own_account(user_id)

    plan = "Premium ⭐" if premium else ("Свой акк 🔑" if own else f"Free ({config.FREE_CHANNEL_LIMIT} каналов)")

    await message.answer(
        f"⚙️ <b>Статус</b>\n\n"
        f"🤖 LLM: <code>{config.LLM_PROVIDER.upper()}</code>\n"
        f"📋 План: <b>{plan}</b>\n"
        f"📡 Каналов: <b>{len(channels)}</b>\n"
        f"🏷 Интересов: <b>{len(interests)}</b>\n"
        f"🎯 Порог: <b>{config.RELEVANCE_THRESHOLD}/100</b>"
    )


# ─── Admin commands (owner only) ──────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not _is_owner(message.from_user.id):
        return
    pool = get_pool_status()
    pool_lines = "\n".join(
        f"  Акк {s['idx']}: {s['used']}/{s['capacity']} каналов"
        for s in pool
    )
    users = db.get_all_users()
    premium_count = sum(1 for u in users if u["is_premium"])
    pending = db.get_pending_payments()
    await message.answer(
        f"🛠 <b>Панель администратора</b>\n\n"
        f"👥 Пользователей: <b>{len(users)}</b>\n"
        f"⭐ Premium: <b>{premium_count}</b>\n"
        f"🕐 Ожидают оплаты: <b>{len(pending)}</b>\n\n"
        f"📡 <b>Аккаунты:</b>\n{pool_lines}\n\n"
        f"Используй кнопки ниже или команды /admin_*",
        reply_markup=kb_admin_menu(),
    )


# ─── Admin keyboard button handlers ────────────────────────────────────────────

@router.message(F.text == "🔙 Выйти из админки")
async def admin_exit_menu(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    await state.clear()
    lang=db.get_lang(message.from_user.id)
    await message.answer(t(lang,"main_menu"), reply_markup=kb_main_menu(lang))


@router.message(F.text == "👥 Пользователи")
async def admin_btn_users(message: Message):
    if not _is_owner(message.from_user.id):
        return
    await cmd_admin_users(message)


@router.message(F.text == "📊 Статистика")
async def admin_btn_stats(message: Message):
    if not _is_owner(message.from_user.id):
        return
    await cmd_admin_stats(message)


@router.message(F.text == "🚫 Чёрный список")
async def admin_btn_blacklist(message: Message):
    if not _is_owner(message.from_user.id):
        return
    await cmd_admin_blacklist(message)


@router.message(F.text == "💳 Платежи")
async def admin_btn_payments(message: Message):
    if not _is_owner(message.from_user.id):
        return
    await cmd_admin_payments(message)


@router.message(F.text == "🧹 Очистить каналы")
async def admin_btn_cleanup(message: Message):
    if not _is_owner(message.from_user.id):
        return
    await cmd_admin_cleanup_channels(message)


@router.message(F.text == "🎯 Рассылка по фильтру")
async def admin_btn_targeted_broadcast(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    await cmd_admin_targeted_broadcast(message, state)


@router.message(F.text == "📢 Рассылка")
async def admin_btn_broadcast_prompt(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    await state.set_state(AdminBroadcastAll.waiting_text)
    c = len(db.get_all_users())
    await message.answer(
        f"Рассылка всем пользователям (<b>{c}</b> чел.).\n\n"
        f"Напиши текст (HTML-теги Telegram поддерживаются). /cancel для отмены:"
    )


@router.message(Command("cancel"), AdminBroadcastAll.waiting_text)
async def admin_broadcast_all_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=kb_admin_menu())


@router.message(AdminBroadcastAll.waiting_text)
async def admin_broadcast_all_send(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    text = message.text or ""
    await state.clear()
    if not text:
        await message.answer("Текст не получен.", reply_markup=kb_admin_menu())
        return
    users = db.get_all_users()
    status_msg = await message.answer(f"📤 Рассылка для {len(users)} пользователей начата...")
    sent, failed = 0, 0
    for u in users:
        try:
            await message.bot.send_message(u["user_id"], text)
            sent += 1
        except Exception as e:
            if "Forbidden" in str(e):
                db.mark_bot_blocked(u["user_id"])
            failed += 1
            logger.error("Broadcast failed for user %s: %s", u["user_id"], e)
        await asyncio.sleep(0.05)
    await status_msg.edit_text(
        f"✅ Рассылка завершена.\n"
        f"Доставлено: <b>{sent}</b>\n"
        f"Не доставлено: <b>{failed}</b>"
    )


@router.message(F.text == "💬 Написать юзеру")
async def admin_btn_dm_prompt(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    await state.set_state(AdminDM.waiting_user_id)
    await message.answer("Введи USER_ID получателя:")


@router.message(AdminDM.waiting_user_id)
async def admin_dm_get_id(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("USER_ID должен быть числом. Попробуй ещё раз:")
        return
    await state.update_data(target_id=int(text))
    await state.set_state(AdminDM.waiting_message)
    await message.answer(f"Теперь напиши сообщение для <code>{text}</code>:")


@router.message(AdminDM.waiting_message)
async def admin_dm_send(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    data = await state.get_data()
    target_id = data["target_id"]
    text = message.text or ""
    await state.clear()
    try:
        await message.bot.send_message(target_id, text)
        db.log_dm(target_id, text, sent_by="admin")
        await message.answer(f"✅ Сообщение отправлено пользователю <code>{target_id}</code>.", reply_markup=kb_admin_menu())
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}", reply_markup=kb_admin_menu())


@router.message(F.text == "📋 История DM")
async def admin_btn_dm_stats(message: Message):
    if not _is_owner(message.from_user.id):
        return
    await cmd_admin_dm_stats(message)



@router.message(Command("admin_make_ad_post"))
async def cmd_admin_make_ad_post(message: Message):
    if not _is_owner(message.from_user.id):
        return
    raw = message.caption if message.photo else message.text
    text = (raw or "").partition(" ")[2].strip()
    if not text:
        await message.answer(
            "Использование:\n"
            "• текстом: /admin_make_ad_post <текст рекламного поста>\n"
            "• с картинкой: пришли фото с подписью «/admin_make_ad_post текст»\n\n"
            "Бот пришлёт тебе готовое сообщение с кнопкой-ссылкой на бота — "
            "перешли его тому, кто публикует в канале. У кнопок-ссылок (в отличие от "
            "кнопок с логикой) есть шанс сохраниться при пересылке."
        )
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🤖 Zapустить бота / Botni ishga tushirish", url="https://t.me/tg_monitoring_aibot")
    ]])
    from aiogram.enums import ParseMode
    if message.photo:
        try:
            await message.answer_photo(message.photo[-1].file_id, caption=text, reply_markup=kb)
        except Exception:
            await message.answer_photo(message.photo[-1].file_id, caption=text, reply_markup=kb, parse_mode=None)
        return
    try:
        await message.answer(text, reply_markup=kb)
    except Exception as e:
        if "can't parse entities" in str(e):
            # Fallback: send without HTML parsing
            await message.answer(text, reply_markup=kb, parse_mode=None)
        else:
            raise


@router.message(Command("admin_dm"))
async def cmd_admin_dm(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    args = message.text.partition(" ")[2].strip()
    parts = args.split(" ", 1)
    if len(parts) < 2 or not parts[0].isdigit():
        await message.answer("Использование: /admin_dm <b>USER_ID</b> текст сообщения")
        return
    target_id = int(parts[0])
    text = parts[1].strip()
    try:
        await message.bot.send_message(target_id, text)
        db.log_dm(target_id, text, sent_by="admin")
        await message.answer(f"✅ Сообщение отправлено пользователю <code>{target_id}</code>.")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")


@router.message(Command("admin_dm_stats"))
async def cmd_admin_dm_stats(message: Message):
    if not _is_owner(message.from_user.id):
        return
    log = db.get_dm_log(limit=50)
    if not log:
        await message.answer("История DM пуста.")
        return
    lines = []
    for entry in log:
        who = "🤖 авто" if entry["sent_by"] == "auto" else "👤 вручную"
        date = entry["sent_at"][:16].replace("T", " ")
        preview = entry["message"][:60] + ("…" if len(entry["message"]) > 60 else "")
        lines.append(f"{who} → <code>{entry['user_id']}</code> | {date}\n   {_e(preview)}")

    CHUNK = 20
    chunks = [lines[i:i+CHUNK] for i in range(0, len(lines), CHUNK)]
    for i, chunk in enumerate(chunks, 1):
        header = f"📋 <b>История DM (стр. {i}/{len(chunks)}):</b>\n\n" if len(chunks) > 1 \
            else "📋 <b>История DM:</b>\n\n"
        await message.answer(header + "\n".join(chunk))


@router.message(Command("cancel"), AdminBroadcastState.waiting_text)
async def admin_broadcast_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=kb_admin_menu())


@router.message(Command("admin_targeted_broadcast"))
async def cmd_admin_targeted_broadcast(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    c0 = len(db.get_users_by_channel_count(0))
    c1 = len(db.get_users_by_channel_count(1))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"0 каналов ({c0} чел.)", callback_data="tbroadcast:0")],
        [InlineKeyboardButton(text=f"1 канал ({c1} чел.)", callback_data="tbroadcast:1")],
        [InlineKeyboardButton(text=f"0 или 1 канал ({c0+c1} чел.)", callback_data="tbroadcast:0+1")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="tbroadcast:cancel")],
    ])
    await message.answer("Кому отправить рассылку?", reply_markup=kb)


@router.callback_query(F.data.startswith("tbroadcast:"))
async def tbroadcast_choose(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return
    target = callback.data.split(":")[1]
    if target == "cancel":
        await callback.message.edit_text("Отменено.")
        await callback.answer()
        return
    await state.update_data(tbroadcast_target=target)
    await state.set_state(AdminBroadcastState.waiting_text)
    c0 = len(db.get_users_by_channel_count(0))
    c1 = len(db.get_users_by_channel_count(1))
    count = c0 + c1 if target == "0+1" else (c0 if target == "0" else c1)
    await callback.message.edit_text(
        f"Выбрано: <b>{target} канал(ов)</b> → {count} получателей.\n\n"
        f"Напиши текст рассылки (HTML-теги Telegram поддерживаются). /cancel для отмены:"
    )
    await callback.answer()


@router.message(AdminBroadcastState.waiting_text)
async def admin_targeted_broadcast_send(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    data = await state.get_data()
    target = data.get("tbroadcast_target")
    text = message.text or ""
    await state.clear()

    if not text:
        await message.answer("Текст не получен.", reply_markup=kb_admin_menu())
        return

    # Если target не задан — это рассылка через кнопку "📢 Рассылка" (всем)
    if target is None:
        users = db.get_all_users()
    elif target == "0+1":
        users = db.get_users_by_channel_count(0) + db.get_users_by_channel_count(1)
    else:
        users = db.get_users_by_channel_count(int(target))

    status_msg = await message.answer(f"📤 Рассылка для {len(users)} пользователей начата...")
    sent, failed = 0, 0
    for u in users:
        try:
            await message.bot.send_message(u["user_id"], text)
            sent += 1
        except Exception as e:
            if "Forbidden" in str(e):
                db.mark_bot_blocked(u["user_id"])
            failed += 1
            logger.error("Targeted broadcast failed for user %s: %s", u["user_id"], e)
        await asyncio.sleep(0.05)
    await status_msg.edit_text(
        f"✅ Рассылка завершена.\n"
        f"Доставлено: <b>{sent}</b>\n"
        f"Не доставлено: <b>{failed}</b>"
    )


async def _auto_nudge_loop(bot):
    """Background loop: sends staged nudges to users with 0 channels."""
    import asyncio as _asyncio
    while True:
        await _asyncio.sleep(3600)
        try:
            stats = db.get_admin_stats()
            processed = stats["processed"]
            sent_count = stats["sent"]
            users = db.get_users_needing_nudge()
            for u in users:
                days = u.get("days_since_join", 0)
                if days <= 3:
                    stage = "first"
                elif days <= 7:
                    stage = "second"
                elif days <= 14:
                    stage = "third"
                else:
                    stage = "repeat"

                stage_line = {
                    "first":  "Ты с нами уже 3 дня — самое время начать!",
                    "second": "Прошла неделя, как ты зарегистрировался.",
                    "third":  "Уже 2 недели, а бот ещё не начал работать для тебя.",
                    "repeat": "Бот всё ещё ждёт тебя.",
                }[stage]

                text = (
                    f"📊 За последние 24 часа бот обработал <b>{processed}</b> сообщений "
                    f"и нашёл <b>{sent_count}</b> релевантных.\n\n"
                    f"Но для вашего аккаунта пока нечего анализировать. {stage_line}\n\n"
                    f"Добавьте хотя бы один <b>канал</b> (раздел 📡 Каналы) — и бот сразу начнёт работать."
                )
                try:
                    await bot.send_message(u["user_id"], text)
                    db.log_dm(u["user_id"], text, sent_by="auto")
                    logger.info("Auto-nudge (%s) sent to user %s", stage, u["user_id"])
                except Exception as e:
                    if "Forbidden" in str(e):
                        db.mark_bot_blocked(u["user_id"])
                    logger.error("Auto-nudge failed for user %s: %s", u["user_id"], e)
        except Exception as e:
            logger.error("Auto-nudge loop error: %s", e)



async def cmd_admin_fix_channel(message: Message):
    if not _is_owner(message.from_user.id):
        return
    args = message.text.partition(" ")[2].strip()
    if not args:
        await message.answer("Использование: /admin_fix_channel <b>@channel</b>")
        return
    channel = _extract_channel_username(args)

    account_idx = db.get_channel_account(channel)

    from listener import multi_listener
    if not multi_listener or not multi_listener.listeners:
        await message.answer("⚠️ Сервис недоступен — нет подключённых аккаунтов.")
        return
    if account_idx >= len(multi_listener.listeners):
        account_idx = 0

    await multi_listener.listeners[account_idx].join_channel(channel)
    db.set_channel_account(channel, account_idx)

    await message.answer(
        f"✅ Канал <b>{_e(channel)}</b> закреплён за аккаунтом #{account_idx} и переподписан.\n"
        f"Проверь через /admin_diagnose, что у пользователя теперь ✅ вместо ⚠️/❌."
    )


@router.message(Command("admin_rejoin_all"))
async def cmd_admin_rejoin_all(message: Message):
    if not _is_owner(message.from_user.id):
        return

    from listener import multi_listener
    if not multi_listener or not multi_listener.listeners:
        await message.answer("⚠️ Сервис недоступен — нет подключённых аккаунтов.")
        return

    mappings = db.get_all_channel_account_mappings()
    if not mappings:
        await message.answer("Нет каналов для подписки.")
        return

    status_msg = await message.answer(f"⏳ Подписываюсь на {len(mappings)} каналов...")

    ok, failed = 0, 0
    for m in mappings:
        channel = m["channel"]
        account_idx = m["account_idx"]
        if account_idx >= len(multi_listener.listeners):
            account_idx = 0
        try:
            await multi_listener.listeners[account_idx].join_channel(channel)
            ok += 1
        except Exception as e:
            logger.error("Rejoin failed for %s: %s", channel, e)
            failed += 1
        await asyncio.sleep(0.5)  # небольшая пауза чтобы не словить FloodWait

    await status_msg.edit_text(
        f"✅ Готово!\n"
        f"Подписался: <b>{ok}</b>\n"
        f"Ошибок: <b>{failed}</b>"
    )


@router.message(Command("admin_diagnose"))
async def cmd_admin_diagnose(message: Message):
    if not _is_owner(message.from_user.id):
        return
    args = message.text.partition(" ")[2].strip()
    if not args.isdigit():
        await message.answer("Использование: /admin_diagnose <b>USER_ID</b>")
        return
    target_id = int(args)

    diag = db.get_user_diagnostics(target_id)
    if not diag["user"]:
        await message.answer(f"❓ Пользователь <code>{target_id}</code> не найден в базе.")
        return

    u = diag["user"]
    icon = "🚫" if u.get("is_banned") else ("⭐" if u["is_premium"] else ("🔑" if u["own_account"] else "🆓"))
    name = u.get("first_name") or str(target_id)
    username = f"@{u['username']}" if u.get("username") else "—"

    lines = [
        f"🔎 <b>Диагностика пользователя</b>\n",
        f"{icon} {_e(name)} ({_e(username)}) — <code>{target_id}</code>",
        f"Регистрация: {u['joined_at'][:10] if u.get('joined_at') else '—'}",
        f"Уведомлений получено всего: <b>{diag['sent_count']}</b>\n",
        f"<b>📡 Каналы ({len(diag['channels'])}):</b>",
    ]

    if not diag["channels"]:
        lines.append("  нет добавленных каналов")
    else:
        for c in diag["channels"]:
            if c["mapped_account"] is None:
                status = "❌ НЕ закреплён за аккаунтом — слушатель не подключён!"
            elif c["mapped_account"] != c["assigned_account"]:
                status = f"⚠️ рассинхрон (записан как акк.{c['assigned_account']}, реально слушает акк.{c['mapped_account']})"
            else:
                status = "✅"
            pack_tag = " 📦" if c["from_pack_id"] else ""
            lines.append(
                f"  • {_e(c['channel'])}{pack_tag} — обработано постов: {c['processed_count']} — {status}"
            )

    lines.append(f"\n<b>🏷 Интересы ({len(diag['interests'])}):</b>")
    if not diag["interests"]:
        lines.append("  ⚠️ нет интересов — уведомления в принципе не могут приходить")
    else:
        for i in diag["interests"]:
            lines.append(f"  • {_e(i['interest'])} (вес {i['weight']:.1f})")

    await message.answer("\n".join(lines))


@router.message(Command("admin_create_promo"))
async def cmd_admin_create_promo(message: Message):
    if not _is_owner(message.from_user.id):
        return

    args = message.text.partition(" ")[2].strip().split()
    if len(args) != 4:
        await message.answer(
            "Использование:\n"
            "<code>/admin_create_promo КОД СКИДКА% АКТИВАЦИИ ДНЕЙ</code>\n\n"
            "Например:\n"
            "<code>/admin_create_promo SALE20 20 50 7</code>\n"
            "— код SALE20, скидка 20%, 50 активаций, действует 7 дней."
        )
        return

    code, discount_str, max_act_str, days_str = args
    try:
        discount = int(discount_str)
        max_activations = int(max_act_str)
        days_valid = int(days_str)
    except ValueError:
        await message.answer("Скидка, активации и дни должны быть целыми числами.")
        return

    if not (0 < discount <= 100):
        await message.answer("Скидка должна быть от 1 до 100.")
        return
    if max_activations <= 0 or days_valid <= 0:
        await message.answer("Активации и дни должны быть больше нуля.")
        return

    created = db.create_promo_code(code, discount, max_activations, days_valid)
    if not created:
        await message.answer(f"❌ Промокод <code>{_e(code.upper())}</code> уже существует.")
        return

    promo = db.get_promo_code(code)
    await message.answer(
        f"✅ Промокод создан!\n\n"
        f"Код: <code>{_e(promo['code'])}</code>\n"
        f"Скидка: <b>{promo['discount_percent']}%</b>\n"
        f"Активаций: <b>{promo['max_activations']}</b>\n"
        f"Действует до: <b>{promo['expires_at'][:10]}</b>"
    )


@router.message(Command("admin_create_pack"))
async def cmd_admin_create_pack(message: Message):
    if not _is_owner(message.from_user.id):
        return

    args = message.text.partition(" ")[2].strip()
    parts = args.split("|")
    if len(parts) != 3:
        await message.answer(
            "Использование:\n"
            "<code>/admin_create_pack Название | интерес1, интерес2 | @канал1, @канал2</code>\n\n"
            "Например:\n"
            "<code>/admin_create_pack Хакатоны | хакатоны, гранты | @hackathons_ru, @grants_news</code>"
        )
        return

    name = parts[0].strip()
    interests = [i.strip() for i in parts[1].split(",") if i.strip()]
    channels = [c.strip() for c in parts[2].split(",") if c.strip()]

    if not name or not interests or not channels:
        await message.answer("Нужно указать название, хотя бы один интерес и хотя бы один канал.")
        return

    pack_id = db.create_pack(name, interests, channels)
    if pack_id is None:
        await message.answer(f"❌ Пак с названием <b>{_e(name)}</b> уже существует.")
        return

    await message.answer(
        f"✅ Пак <b>{_e(name)}</b> создан!\n\n"
        f"🏷 Интересов: <b>{len(interests)}</b>\n"
        f"📡 Каналов: <b>{len(channels)}</b>\n\n"
        f"Пользователи добавляют его командой: <code>/add_pack {_e(name)}</code>"
    )


@router.message(Command("admin_edit_pack"))
async def cmd_admin_edit_pack(message: Message):
    if not _is_owner(message.from_user.id):
        return

    args = message.text.partition(" ")[2].strip()
    parts = args.split("|")
    if len(parts) != 4:
        await message.answer(
            "Использование:\n"
            "<code>/admin_edit_pack СтароеНазвание | НовоеНазвание | интерес1, интерес2 | @канал1, @канал2</code>\n\n"
            "Можно оставить название тем же — просто повтори его.\n\n"
            "⚠️ Изменения касаются только новых подключений пака — у тех, кто уже подключил его, "
            "набор каналов/интересов не меняется."
        )
        return

    old_name, new_name, interests_raw, channels_raw = (p.strip() for p in parts)
    pack = db.get_pack_by_name(old_name)
    if not pack:
        await message.answer(f"❓ Пак <b>{_e(old_name)}</b> не найден.")
        return

    interests = [i.strip() for i in interests_raw.split(",") if i.strip()]
    channels = [c.strip() for c in channels_raw.split(",") if c.strip()]
    if not new_name or not interests or not channels:
        await message.answer("Нужно указать название, хотя бы один интерес и хотя бы один канал.")
        return

    updated = db.update_pack(pack["id"], new_name, interests, channels)
    if not updated:
        await message.answer(f"❌ Пак с названием <b>{_e(new_name)}</b> уже существует.")
        return

    await message.answer(
        f"✅ Пак обновлён!\n\n"
        f"Название: <b>{_e(new_name)}</b>\n"
        f"🏷 Интересов: <b>{len(interests)}</b>\n"
        f"📡 Каналов: <b>{len(channels)}</b>"
    )


@router.message(Command("admin_delete_pack"))
async def cmd_admin_delete_pack(message: Message):
    if not _is_owner(message.from_user.id):
        return
    name = message.text.partition(" ")[2].strip()
    if not name:
        await message.answer("Использование: /admin_delete_pack <b>Название</b>")
        return
    pack = db.get_pack_by_name(name)
    if not pack:
        await message.answer(f"❓ Пак <b>{_e(name)}</b> не найден.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Удалить", callback_data=f"admin_delpack:{pack['id']}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel_action"),
    ]])
    await message.answer(
        f"⚠️ Точно удалить пак <b>{_e(pack['name'])}</b>?\n"
        f"Каталог потеряет его, новые подключения станут невозможны "
        f"(у тех, кто уже подключил — каналы останутся).",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("admin_delpack:"))
async def admin_delete_pack_confirm(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return
    pack_id = int(callback.data.split(":")[1])
    pack = db.get_pack_by_id(pack_id)
    if not pack:
        await callback.answer("Пак уже не существует.")
        return
    db.delete_pack(pack_id)
    await callback.message.edit_text(f"🗑 Пак <b>{_e(pack['name'])}</b> удалён.")
    await callback.answer()


@router.message(Command("admin_broadcast"))
async def cmd_admin_broadcast(message: Message):
    if not _is_owner(message.from_user.id):
        return

    text = message.text.partition(" ")[2].strip()
    if not text:
        await message.answer(
            "Использование: /admin_broadcast <b>текст сообщения</b>\n\n"
            "Можно использовать HTML-теги (<code>&lt;b&gt;</code>, <code>&lt;i&gt;</code>, "
            "<code>&lt;a href=...&gt;</code>), как в обычных сообщениях бота."
        )
        return

    users = db.get_all_users()
    status_msg = await message.answer(f"📤 Рассылка для {len(users)} пользователей начата...")

    sent, failed = 0, 0
    for u in users:
        try:
            await message.bot.send_message(u["user_id"], text)
            sent += 1
        except Exception as e:
            if "Forbidden" in str(e):
                db.mark_bot_blocked(u["user_id"])
            failed += 1
            logger.error("Broadcast failed for user %s: %s", u["user_id"], e)
        await asyncio.sleep(0.05)  # бережём лимиты Telegram API на массовую отправку

    await status_msg.edit_text(
        f"✅ Рассылка завершена.\n"
        f"Доставлено: <b>{sent}</b>\n"
        f"Не доставлено: <b>{failed}</b> (заблокировали бота / удалили аккаунт)"
    )


@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message):
    if not _is_owner(message.from_user.id):
        return

    s = db.get_admin_stats()
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <b>{s['users']}</b> (заблокировали бота: {s['blocked']})\n"
        f"📡 Каналов отслеживается: <b>{s['channels']}</b>\n"
        f"📨 Сообщений обработано: <b>{s['processed']}</b>\n"
        f"🚨 Отправлено релевантных: <b>{s['sent']}</b>\n"
        f"👍 Лайков: <b>{s['likes']}</b>\n"
        f"👎 Дизлайков: <b>{s['dislikes']}</b>\n"
        f"🔍 Воспользовались «Фильтрацией канала»: <b>{s['scan_users']}</b> "
        f"(запусков: {s['scan_runs']})"
    )


@router.message(Command("admin_payments"))
async def cmd_admin_payments(message: Message):
    if not _is_owner(message.from_user.id):
        return
    pending = db.get_pending_payments()
    if not pending:
        await message.answer("Нет ожидающих платежей.")
        return
    for p in pending:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅", callback_data=f"approve_ton:{p['id']}"),
            InlineKeyboardButton(text="❌", callback_data=f"reject_ton:{p['id']}"),
        ]])
        await message.answer(
            f"#{p['id']} | user <code>{p['user_id']}</code>\n"
            f"Метод: {p['method']} | Сумма: {p['amount']}\n"
            f"Каналов: {p['extra_channels']}, месяцев: {p['months']}\n"
            f"Дата: {p['created_at'][:10]}",
            reply_markup=kb
        )


@router.message(Command("admin_users"))
async def cmd_admin_users(message: Message):
    if not _is_owner(message.from_user.id):
        return
    users = db.get_active_users()
    if not users:
        await message.answer("Нет пользователей.")
        return
    lines = []
    for u in users:
        icon = "⭐" if u["is_premium"] else ("🔑" if u["own_account"] else "🆓")
        if u.get("is_banned"):
            icon = "🚫"
        name = u.get("first_name") or str(u["user_id"])
        username = f"@{u['username']}" if u.get("username") else "—"
        joined = u["joined_at"][:10] if u.get("joined_at") else "—"
        count = db.count_user_channels(u["user_id"])
        lines.append(
            f"{icon} <code>{u['user_id']}</code> {_e(name)} ({_e(username)}) — {count} кан.\n"
            f"   рег. {joined}"
        )

    # Telegram режет сообщения длиннее 4096 символов — шлём списком пачек, чтобы видеть всех, а не первые 30.
    CHUNK_SIZE = 25
    chunks = [lines[i:i + CHUNK_SIZE] for i in range(0, len(lines), CHUNK_SIZE)]
    for i, chunk in enumerate(chunks, 1):
        header = f"👥 <b>Пользователи ({len(users)}), стр. {i}/{len(chunks)}:</b>\n\n" if len(chunks) > 1 \
            else f"👥 <b>Пользователи ({len(users)}):</b>\n\n"
        await message.answer(header + "\n".join(chunk))


@router.message(Command("admin_ban"))
async def cmd_admin_ban(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    args = message.text.partition(" ")[2].strip()
    if not args.isdigit():
        await message.answer("Использование: /admin_ban <b>USER_ID</b>")
        return
    target_id = int(args)
    if target_id == config.OWNER_CHAT_ID:
        await message.answer("Нельзя забанить самого себя.")
        return
    target = db.get_user(target_id)
    if not target:
        await message.answer(f"❓ Пользователь <code>{target_id}</code> не найден в базе.")
        return

    name = target.get("first_name") or target.get("username") or str(target_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_confirm:ban:{target_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel_action"),
    ]])
    await message.answer(
        f"⚠️ Точно забанить <b>{_e(name)}</b> (<code>{target_id}</code>)?\n"
        f"Он потеряет доступ ко всем командам бота.",
        reply_markup=kb
    )


@router.message(Command("admin_unban"))
async def cmd_admin_unban(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    args = message.text.partition(" ")[2].strip()
    if not args.isdigit():
        await message.answer("Использование: /admin_unban <b>USER_ID</b>")
        return
    target_id = int(args)
    target = db.get_user(target_id)
    if not target:
        await message.answer(f"❓ Пользователь <code>{target_id}</code> не найден в базе.")
        return

    name = target.get("first_name") or target.get("username") or str(target_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_confirm:unban:{target_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel_action"),
    ]])
    await message.answer(
        f"Точно разбанить <b>{_e(name)}</b> (<code>{target_id}</code>)?",
        reply_markup=kb
    )


@router.callback_query(F.data == "admin_cancel_action")
async def admin_cancel_action(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return
    await state.clear()
    await callback.message.edit_text("❌ Отменено.")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_confirm:"))
async def admin_confirm_action(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.")
        return
    _, action, target_str = callback.data.split(":")
    await state.set_state(AdminConfirm.waiting_password)
    await state.update_data(action=action, target_id=int(target_str))
    await callback.message.edit_text("🔒 Введи пароль подтверждения (или /cancel чтобы отменить):")
    await callback.answer()


@router.message(Command("cancel"), AdminConfirm.waiting_password)
async def admin_cancel_password(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.")


@router.message(AdminConfirm.waiting_password)
async def admin_check_password(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    data = await state.get_data()
    action = data.get("action")
    target_id = data.get("target_id")
    await state.clear()

    if message.text != ADMIN_ACTION_PASSWORD:
        await message.answer("❌ Неверный пароль. Действие отменено.")
        return

    if action == "ban":
        db.ban_user(target_id)
        await message.answer(f"🚫 Пользователь <code>{target_id}</code> заблокирован.")
        try:
            await message.bot.send_message(
                target_id,
                "🚫 <b>Ты заблокирован в этом боте.</b>\n\n"
                "Если считаешь, что это ошибка — напиши @wpersonxd."
            )
        except Exception as e:
            logger.error("Failed to notify banned user %s: %s", target_id, e)
    elif action == "unban":
        db.unban_user(target_id)
        await message.answer(f"✅ Пользователь <code>{target_id}</code> разблокирован.")
        try:
            await message.bot.send_message(
                target_id,
                "✅ <b>Блокировка снята.</b> Можешь снова пользоваться ботом."
            )
        except Exception as e:
            logger.error("Failed to notify unbanned user %s: %s", target_id, e)


@router.message(Command("admin_blacklist"))
async def cmd_admin_blacklist(message: Message):
    if not _is_owner(message.from_user.id):
        return
    banned = db.get_banned_users()
    if not banned:
        await message.answer("Чёрный список пуст.")
        return
    lines = []
    for u in banned:
        name = u.get("first_name") or str(u["user_id"])
        username = f"@{u['username']}" if u.get("username") else "—"
        banned_at = u["banned_at"][:10] if u.get("banned_at") else "—"
        lines.append(
            f"🚫 <code>{u['user_id']}</code> {_e(name)} ({_e(username)})\n"
            f"   забанен: {banned_at}"
        )
    CHUNK_SIZE = 25
    chunks = [lines[i:i + CHUNK_SIZE] for i in range(0, len(lines), CHUNK_SIZE)]
    for i, chunk in enumerate(chunks, 1):
        header = f"🚫 <b>Чёрный список ({len(banned)}), стр. {i}/{len(chunks)}:</b>\n\n" if len(chunks) > 1 \
            else f"🚫 <b>Чёрный список ({len(banned)}):</b>\n\n"
        await message.answer(header + "\n".join(chunk))





@router.message(Command("admin_cleanup_channels"))
async def cmd_admin_cleanup_channels(message: Message):
    """Find channels in channel_accounts with no real subscribers left
    (leftover from before the leave-channel fix) and properly unsubscribe + free the slot."""
    if not _is_owner(message.from_user.id):
        return

    mappings = db.get_all_channel_account_mappings()
    orphaned = [m for m in mappings if not db.get_channel_subscribers(m["channel"])]

    if not orphaned:
        await message.answer("✅ Осиротевших каналов не найдено, всё чисто.")
        return

    from listener import multi_listener
    cleaned = []
    for m in orphaned:
        channel, account_idx = m["channel"], m["account_idx"]
        if multi_listener and account_idx < len(multi_listener.listeners):
            await multi_listener.listeners[account_idx].leave_channel(channel)
        db.remove_channel_account(channel)
        cleaned.append(channel)

    lines = "\n".join(f"  • {_e(c)}" for c in cleaned)
    await message.answer(
        f"🧹 Подчищено {len(cleaned)} осиротевших канала(ов):\n{lines}\n\n"
        f"Аккаунт(ы) отписаны, слоты освобождены."
    )


# ─── Factory ──────────────────────────────────────────────────────────────────

def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    return bot, dp
