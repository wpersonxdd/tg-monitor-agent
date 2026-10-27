"""
Internationalisation strings for TG Monitor bot.
Supported languages: ru (Russian), uz (Uzbek Latin).
Usage: t(lang, "key") or t(lang, "key", var=value)
"""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    # ── Language selection ──────────────────────────────────────────────────────
    "choose_language": {
        "ru": "Выбери язык / Tilni tanlang:",
        "uz": "Tilni tanlang / Выбери язык:",
    },
    "lang_set": {
        "ru": "Язык установлен: Русский 🇷🇺",
        "uz": "Til o'rnatildi: O'zbek 🇺🇿",
    },

    # ── /start ──────────────────────────────────────────────────────────────────
    "start_greeting": {
        "ru": (
            "👋 Привет, <b>{name}</b>!\n"
            "Я — AI-фильтр для Telegram-каналов: добавляешь каналы и говоришь, что тебе интересно, "
            "а я сам читаю все посты и присылаю только то, что реально подходит. Остальное отсеивается.\n"
            "Вот что делают кнопки внизу 👇\n"
            "📡 Каналы — добавить канал (просто кинь ссылку или @username), посмотреть список, убрать ненужный.\n"
            "🏷 Интересы — темы, по которым я подбираю посты (например: «хакатоны», «вакансии Python»). "
            "Чем конкретнее напишешь — тем точнее совпадения. P.S: Без них я не пришлю ничего так как не пойму что тебе нужно\n"
            "⭐ Подписка — бесплатно до {limit} каналов. Больше — оплата (Stars, TON или карта) или промокод со скидкой.\n"
            "📦 Паки — готовые бесплатные подборки каналов+интересов, подключаются одной кнопкой и не входят в лимит.\n"
            "⚙️ Ещё — статус системы, подключение своего Telegram-аккаунта (для безлимита), помощь.\n"
            "🔍 Фильтрация канала за всё время — разовая платная функция: указываешь канал и интерес, "
            "я прохожу ВСЮ историю канала через AI и присылаю всё подходящее. Цена считается заранее, "
            "до запуска нужно подтвердить оплату.\n"
            "На каждое уведомление можно нажать 👍/👎 — это влияет на то, что я буду присылать в будущем.\n"
            "Жми на кнопки внизу, чтобы начать — или /help для текстовой справки."
        ),
        "uz": (
            "👋 Salom, <b>{name}</b>!\n"
            "Men Telegram-kanallar uchun AI-filtrman: kanallarni qo'shasan va nima qiziqishingni aytasan, "
            "men esa barcha postlarni o'qib, faqat keraklisini yubora man. Qolganlari saqlanib qoladi.\n"
            "Pastdagi tugmalar nima qiladi 👇\n"
            "📡 Kanallar — kanal qo'shish (havola yoki @username tashlash), ro'yxatni ko'rish, o'chirish.\n"
            "🏷 Qiziqishlar — postlarni tanlash uchun mavzular (masalan: «hackathon», «Python ish o'rinlari»). "
            "Aniqroq yozsang — natijalar to'g'riroq bo'ladi. E.S: Ularsiz hech narsa yubormayman.\n"
            "⭐ Obuna — {limit} tagacha kanal bepul. Ko'proq — to'lov (Stars, TON yoki karta) yoki chegirma kodi.\n"
            "📦 Paklar — tayyor bepul kanal+qiziqish to'plamlari, bir tugma bilan qo'shiladi va limitga kirmaydi.\n"
            "⚙️ Ko'proq — tizim holati, o'z Telegram-akkauntingni ulash (limitsiz), yordam.\n"
            "🔍 Kanal tarixini filtrlash — bir martalik pullik funksiya: kanal va qiziqish kiritasan, "
            "men AI orqali kanalning BUTUN tarixini ko'rib, keraklisini yubora man. Narx oldin hisoblanadi.\n"
            "Har bir bildirishnomaga 👍/👎 bosish mumkin — bu kelajakdagi filtrga ta'sir qiladi.\n"
            "Boshlash uchun pastdagi tugmalardan foydalaning — yoki /help buyrug'i."
        ),
    },

    # ── /help ───────────────────────────────────────────────────────────────────
    "help_text": {
        "ru": (
            "📖 <b>Команды</b>\n\n"
            "<b>Каналы:</b>\n"
            "  /add_channel @channel\n"
            "  /my_channels\n"
            "  /remove_channel @channel\n\n"
            "<b>Паки (бесплатные подборки):</b>\n"
            "  /packs — список доступных\n"
            "  /add_pack Название\n\n"
            "<b>Интересы:</b>\n"
            "  /add_interest тема\n"
            "  /list_interests\n"
            "  /remove_interest тема\n\n"
            "<b>Подписка:</b>\n"
            "  /plan — текущий план\n"
            "  /buy — купить подписку\n"
            "  /promo КОД — применить промокод\n"
            "  /own_account — добавить свой аккаунт\n\n"
            "<b>Другое:</b>\n"
            "  /status — статус системы\n"
            "  /language — сменить язык\n\n"
            "На каждое уведомление можно нажать 👍 или 👎.\n\n"
            "💬 Поддержка: @wpersonxd"
        ),
        "uz": (
            "📖 <b>Buyruqlar</b>\n\n"
            "<b>Kanallar:</b>\n"
            "  /add_channel @channel\n"
            "  /my_channels\n"
            "  /remove_channel @channel\n\n"
            "<b>Paklar (bepul to'plamlar):</b>\n"
            "  /packs — mavjud ro'yxat\n"
            "  /add_pack Nomi\n\n"
            "<b>Qiziqishlar:</b>\n"
            "  /add_interest mavzu\n"
            "  /list_interests\n"
            "  /remove_interest mavzu\n\n"
            "<b>Obuna:</b>\n"
            "  /plan — joriy reja\n"
            "  /buy — obuna sotib olish\n"
            "  /promo KOD — promo-kod ishlatish\n"
            "  /own_account — o'z akkauntni ulash\n\n"
            "<b>Boshqalar:</b>\n"
            "  /status — tizim holati\n"
            "  /language — tilni o'zgartirish\n\n"
            "Har bir bildirishnomaga 👍 yoki 👎 bosish mumkin.\n\n"
            "💬 Qo'llab-quvvatlash: @wpersonxd"
        ),
    },

    # ── Channels ─────────────────────────────────────────────────────────────────
    "channel_added": {
        "ru": "✅ Канал <b>{channel}</b> добавлен!\nПлатных каналов: {count}/{limit}",
        "uz": "✅ Kanal <b>{channel}</b> qo'shildi!\nPullik kanallar: {count}/{limit}",
    },
    "channel_already_added": {
        "ru": "ℹ️ Канал <b>{channel}</b> уже добавлен.",
        "uz": "ℹ️ Kanal <b>{channel}</b> allaqachon qo'shilgan.",
    },
    "channel_removed": {
        "ru": "🗑 Канал <b>{channel}</b> удалён.",
        "uz": "🗑 Kanal <b>{channel}</b> o'chirildi.",
    },
    "channel_not_found": {
        "ru": "❓ Канал <b>{channel}</b> не найден.",
        "uz": "❓ Kanal <b>{channel}</b> topilmadi.",
    },
    "channel_from_pack": {
        "ru": "🔒 Канал <b>{channel}</b> входит в пак «{pack}» — каналы из паков нельзя удалять по отдельности.",
        "uz": "🔒 Kanal <b>{channel}</b> «{pack}» pakiga kiradi — pak kanallarini alohida o'chirib bo'lmaydi.",
    },
    "no_channels": {
        "ru": "У тебя нет каналов. Добавь: /add_channel @channel",
        "uz": "Kanalingiz yo'q. Qo'shish: /add_channel @channel",
    },
    "add_channel_prompt": {
        "ru": "Укажи канал: /add_channel <b>@channel</b>",
        "uz": "Kanalni ko'rsating: /add_channel <b>@channel</b>",
    },
    "accounts_full": {
        "ru": "⚠️ Все аккаунты заполнены. Свяжись с администратором.",
        "uz": "⚠️ Barcha akkauntlar to'lgan. Administrator bilan bog'laning.",
    },
    "add_channel_input": {
        "ru": "Скинь ссылку (t.me/...) или @username канала, который хочешь отслеживать:",
        "uz": "Kuzatmoqchi bo'lgan kanalning havolasi (t.me/...) yoki @username ni yuboring:",
    },
    "remove_channel_input": {
        "ru": "Скинь ссылку или @username канала, который хочешь убрать:",
        "uz": "O'chirmoqchi bo'lgan kanalning havolasi yoki @username ni yuboring:",
    },

    # ── Interests ────────────────────────────────────────────────────────────────
    "interest_added": {
        "ru": "✅ Интерес добавлен: <b>{interest}</b>",
        "uz": "✅ Qiziqish qo'shildi: <b>{interest}</b>",
    },
    "interest_exists": {
        "ru": "ℹ️ Интерес <b>{interest}</b> уже есть.",
        "uz": "ℹ️ <b>{interest}</b> qiziqishi allaqachon mavjud.",
    },
    "interest_removed": {
        "ru": "🗑 Интерес <b>{interest}</b> удалён.",
        "uz": "🗑 <b>{interest}</b> qiziqishi o'chirildi.",
    },
    "interest_not_found": {
        "ru": "❓ Интерес <b>{interest}</b> не найден.",
        "uz": "❓ <b>{interest}</b> qiziqishi topilmadi.",
    },
    "no_interests": {
        "ru": "Нет интересов. Добавь: /add_interest хакатон",
        "uz": "Qiziqishlar yo'q. Qo'shish: /add_interest hackathon",
    },
    "add_interest_prompt": {
        "ru": "Напиши тему интереса (например: хакатоны):",
        "uz": "Qiziqish mavzusini yozing (masalan: hackathonlar):",
    },
    "remove_interest_input": {
        "ru": "Какой интерес убрать? Напиши его текстом:",
        "uz": "Qaysi qiziqishni o'chirish kerak? Matn ko'rinishida yozing:",
    },

    # ── Plan / subscription ───────────────────────────────────────────────────────
    "plan_title": {
        "ru": "📋 <b>Твой план</b>",
        "uz": "📋 <b>Sizning rejangiz</b>",
    },
    "plan_premium": {
        "ru": "⭐ <b>Premium</b> до {until} (лимит: {limit} каналов)",
        "uz": "⭐ <b>Premium</b> {until} gacha (limit: {limit} kanal)",
    },
    "plan_own_account": {
        "ru": "🔑 <b>Свой аккаунт</b>",
        "uz": "🔑 <b>O'z akkaunt</b>",
    },
    "plan_free": {
        "ru": "🆓 <b>Free</b> (до {limit} каналов)",
        "uz": "🆓 <b>Bepul</b> ({limit} tagacha kanal)",
    },
    "plan_paid_channels": {
        "ru": "Платных каналов: <b>{count}/{limit}</b>",
        "uz": "Pullik kanallar: <b>{count}/{limit}</b>",
    },
    "plan_paid_unlimited": {
        "ru": "Платных каналов: <b>{count}</b>",
        "uz": "Pullik kanallar: <b>{count}</b>",
    },
    "plan_pack_channels": {
        "ru": "📦 Из паков (бесплатно): <b>{count}</b>\n",
        "uz": "📦 Paklardan (bepul): <b>{count}</b>\n",
    },
    "plan_upgrade": {
        "ru": "\nДобавить больше: /buy или /own_account",
        "uz": "\nKo'proq qo'shish: /buy yoki /own_account",
    },

    # ── Menu buttons ──────────────────────────────────────────────────────────────
    "btn_channels": {"ru": "📡 Каналы", "uz": "📡 Kanallar"},
    "btn_interests": {"ru": "🏷 Интересы", "uz": "🏷 Qiziqishlar"},
    "btn_subscription": {"ru": "⭐ Подписка", "uz": "⭐ Obuna"},
    "btn_packs": {"ru": "📦 Паки", "uz": "📦 Paklar"},
    "btn_more": {"ru": "⚙️ Ещё", "uz": "⚙️ Ko'proq"},
    "btn_scan": {"ru": "🔍 Фильтрация канала за всё время", "uz": "🔍 Kanal tarixini filtrlash"},
    "btn_add_channel": {"ru": "➕ Добавить канал", "uz": "➕ Kanal qo'shish"},
    "btn_my_channels": {"ru": "📋 Мои каналы", "uz": "📋 Mening kanallarim"},
    "btn_remove_channel": {"ru": "🗑 Удалить канал", "uz": "🗑 Kanalni o'chirish"},
    "btn_add_interest": {"ru": "➕ Добавить интерес", "uz": "➕ Qiziqish qo'shish"},
    "btn_list_interests": {"ru": "📋 Список интересов", "uz": "📋 Qiziqishlar ro'yxati"},
    "btn_remove_interest": {"ru": "🗑 Удалить интерес", "uz": "🗑 Qiziqishni o'chirish"},
    "btn_buy": {"ru": "💳 Купить подписку", "uz": "💳 Obuna sotib olish"},
    "btn_my_plan": {"ru": "📋 Мой план", "uz": "📋 Mening rejam"},
    "btn_promo": {"ru": "🎁 Промокод", "uz": "🎁 Promo-kod"},
    "btn_available_packs": {"ru": "📦 Доступные паки", "uz": "📦 Mavjud paklar"},
    "btn_my_packs": {"ru": "📦 Мои паки", "uz": "📦 Mening paklarim"},
    "btn_add_pack": {"ru": "➕ Добавить пак", "uz": "➕ Pak qo'shish"},
    "btn_status": {"ru": "⚙️ Статус", "uz": "⚙️ Holat"},
    "btn_own_account": {"ru": "🔑 Свой аккаунт", "uz": "🔑 O'z akkaunt"},
    "btn_help": {"ru": "❓ Помощь", "uz": "❓ Yordam"},
    "btn_back": {"ru": "◀️ Назад", "uz": "◀️ Orqaga"},
    "btn_language": {"ru": "🌐 Язык", "uz": "🌐 Til"},

    # ── Notifications ─────────────────────────────────────────────────────────────
    "notification_text": {
        "ru": (
            "📬 <b>{channel}</b>\n\n"
            "{quote}\n\n"
            "🎯 Совпадение: <b>{score}/100</b>\n"
            "💡 {reason}\n"
            "🏷 Интересы: {interests}"
        ),
        "uz": (
            "📬 <b>{channel}</b>\n\n"
            "{quote}\n\n"
            "🎯 Moslik: <b>{score}/100</b>\n"
            "💡 {reason}\n"
            "🏷 Qiziqishlar: {interests}"
        ),
    },
    "btn_like": {"ru": "👍", "uz": "👍"},
    "btn_dislike": {"ru": "👎", "uz": "👎"},
    "feedback_accepted": {"ru": "👍 Учтено!", "uz": "👍 Qabul qilindi!"},
    "feedback_dislike_accepted": {"ru": "👎 Учтено!", "uz": "👎 Qabul qilindi!"},

    # ── Status ────────────────────────────────────────────────────────────────────
    "status_text": {
        "ru": (
            "⚙️ <b>Статус</b>\n\n"
            "🤖 LLM: <code>{llm}</code>\n"
            "📋 План: <b>{plan}</b>\n"
            "📡 Каналов: <b>{channels}</b>\n"
            "🏷 Интересов: <b>{interests}</b>\n"
            "🎯 Порог: <b>{threshold}/100</b>"
        ),
        "uz": (
            "⚙️ <b>Holat</b>\n\n"
            "🤖 LLM: <code>{llm}</code>\n"
            "📋 Reja: <b>{plan}</b>\n"
            "📡 Kanallar: <b>{channels}</b>\n"
            "🏷 Qiziqishlar: <b>{interests}</b>\n"
            "🎯 Chegara: <b>{threshold}/100</b>"
        ),
    },

    # ── Promo ─────────────────────────────────────────────────────────────────────
    "promo_not_found": {
        "ru": "❓ Такого промокода не существует.",
        "uz": "❓ Bunday promo-kod mavjud emas.",
    },
    "promo_expired": {
        "ru": "⏰ Этот промокод уже истёк.",
        "uz": "⏰ Bu promo-kod muddati o'tgan.",
    },
    "promo_exhausted": {
        "ru": "😔 У этого промокода закончились активации.",
        "uz": "😔 Bu promo-kodning aktivatsiyalari tugagan.",
    },
    "promo_race": {
        "ru": "😔 Этот промокод только что закончился — кто-то успел раньше.",
        "uz": "😔 Bu promo-kod hozirgina tugadi — kimdir oldinda bo'ldi.",
    },
    "promo_applied": {
        "ru": "🎉 Промокод <b>{code}</b> применён!\nСкидка <b>{pct}%</b> учтётся при следующей покупке — заходи в /buy.",
        "uz": "🎉 Promo-kod <b>{code}</b> ishlatildi!\n<b>{pct}%</b> chegirma keyingi xaridda hisobga olinadi — /buy ga o'ting.",
    },
    "promo_prompt": {
        "ru": "Введи промокод:",
        "uz": "Promo-kodni kiriting:",
    },

    # ── Subscription payment ──────────────────────────────────────────────────────
    "payment_confirmed": {
        "ru": "✅ <b>Оплата прошла!</b>\n\nПодписка активирована на {months} мес.\nТеперь ты можешь добавить ещё каналы: /add_channel",
        "uz": "✅ <b>To'lov amalga oshdi!</b>\n\nObuna {months} oyga faollashtirildi.\nEndi yangi kanallar qo'shishingiz mumkin: /add_channel",
    },
    "ton_receipt_received": {
        "ru": "✅ Чек получен! Ожидай подтверждения — обычно до 1 часа.",
        "uz": "✅ Chek qabul qilindi! Tasdiqlashni kuting — odatda 1 soatgacha.",
    },
    "payment_rejected": {
        "ru": "❌ <b>Оплата не подтверждена.</b>\n\nВозможно, сумма или адрес не совпадают. Напиши в поддержку (@wpersonxd) или попробуй снова: /buy",
        "uz": "❌ <b>To'lov tasdiqlanmadi.</b>\n\nEhtimol, summa yoki manzil mos kelmaydi. Qo'llab-quvvatlash (@wpersonxd) ga yozing yoki qayta urinib ko'ring: /buy",
    },
    "receipt_send_prompt": {
        "ru": "Пришли скриншот или хэш транзакции.",
        "uz": "Skrinshot yoki tranzaksiya xeshini yuboring.",
    },

    # ── Scan feature ──────────────────────────────────────────────────────────────
    "scan_intro": {
        "ru": (
            "🔍 <b>Фильтрация канала за всё время</b>\n\n"
            "Я просмотрю ВСЮ историю указанного канала через AI и пришлю посты, "
            "подходящие под твой интерес. Это разовая платная функция.\n\n"
            "Цена зависит от объёма канала и считается заранее.\n\n"
            "Скинь ссылку (t.me/...) или @username канала:"
        ),
        "uz": (
            "🔍 <b>Kanal tarixini filtrlash</b>\n\n"
            "Men ko'rsatilgan kanalning BUTUN tarixini AI orqali ko'rib, "
            "qiziqishingizga mos postlarni yuboraman. Bu bir martalik pullik funksiya.\n\n"
            "Narx kanal hajmiga qarab hisoblanadi.\n\n"
            "Havola (t.me/...) yoki kanal @username ini yuboring:"
        ),
    },
    "scan_ask_interest": {
        "ru": "Какой интерес искать в этом канале? Напиши текстом:",
        "uz": "Bu kanalda qaysi qiziqishni qidirish kerak? Matn ko'rinishida yozing:",
    },
    "scan_counting": {
        "ru": "⏳ Считаю объём канала, подожди немного...",
        "uz": "⏳ Kanal hajmini hisoblamoqda, biroz kuting...",
    },
    "scan_no_access": {
        "ru": "❌ Не удалось получить доступ к каналу <b>{channel}</b>. Возможно, он приватный или не существует.",
        "uz": "❌ <b>{channel}</b> kanaliga kirish imkoni bo'lmadi. Ehtimol, u maxfiy yoki mavjud emas.",
    },
    "scan_no_texts": {
        "ru": "В этом канале не нашлось текстовых постов.",
        "uz": "Bu kanalda matnli postlar topilmadi.",
    },
    "scan_price_confirm": {
        "ru": (
            "📊 Найдено постов: <b>{count}</b>\n"
            "Канал: <b>{channel}</b>\n"
            "Интерес: <b>{interest}</b>\n\n"
            "💰 Цена: <b>{ton} TON</b> (≈ ${usd})\n\n"
            "Подтвердить и перейти к оплате?"
        ),
        "uz": (
            "📊 Topilgan postlar: <b>{count}</b>\n"
            "Kanal: <b>{channel}</b>\n"
            "Qiziqish: <b>{interest}</b>\n\n"
            "💰 Narx: <b>{ton} TON</b> (≈ ${usd})\n\n"
            "Tasdiqlash va to'lovga o'tish?"
        ),
    },
    "scan_confirm_btn": {"ru": "✅ Подтвердить и оплатить", "uz": "✅ Tasdiqlash va to'lash"},
    "scan_cancel_btn": {"ru": "❌ Отмена", "uz": "❌ Bekor qilish"},
    "scan_cancelled": {"ru": "❌ Отменено.", "uz": "❌ Bekor qilindi."},
    "scan_approved_user": {
        "ru": "✅ <b>Оплата подтверждена!</b> Запускаю сканирование канала — пришлю результаты по ходу работы.",
        "uz": "✅ <b>To'lov tasdiqlandi!</b> Kanal skanerlashni boshlamoqda — natijalarni yuboraman.",
    },
    "scan_done": {
        "ru": "✅ <b>Готово!</b>\nПросмотрено постов: {total}\nНайдено подходящих: <b>{matches}</b>",
        "uz": "✅ <b>Tayyor!</b>\nKo'rib chiqilgan postlar: {total}\nMos kelganlari: <b>{matches}</b>",
    },

    # ── Own account ───────────────────────────────────────────────────────────────
    "own_account_info": {
        "ru": (
            "🔑 <b>Добавить свой аккаунт</b>\n\n"
            "Это позволит подключить неограниченное количество каналов.\n\n"
            "<b>Инструкция:</b>\n"
            "1. Зайди на https://my.telegram.org/apps\n"
            "2. Создай приложение, получи <code>API_ID</code> и <code>API_HASH</code>\n"
            "3. Напиши мне: /set_account API_ID:API_HASH\n\n"
            "⚠️ Данные хранятся только на сервере, не передаются третьим лицам."
        ),
        "uz": (
            "🔑 <b>O'z akkauntingizni ulash</b>\n\n"
            "Bu cheksiz miqdorda kanallar qo'shish imkonini beradi.\n\n"
            "<b>Ko'rsatma:</b>\n"
            "1. https://my.telegram.org/apps ga kiring\n"
            "2. Ilova yarating, <code>API_ID</code> va <code>API_HASH</code> oling\n"
            "3. Menga yozing: /set_account API_ID:API_HASH\n\n"
            "⚠️ Ma'lumotlar faqat serverda saqlanadi, uchinchi shaxslarga uzatilmaydi."
        ),
    },
    "own_account_set": {
        "ru": "✅ Аккаунт отмечен! Теперь ты можешь добавлять неограниченное количество каналов.\n\n⚙️ Администратор настроит сессию вручную и уведомит тебя.",
        "uz": "✅ Akkaunt belgilandi! Endi cheksiz miqdorda kanallar qo'shishingiz mumkin.\n\n⚙️ Administrator sessiyani qo'lda sozlaydi va sizga xabar beradi.",
    },

    # ── Packs ─────────────────────────────────────────────────────────────────────
    "packs_title": {
        "ru": "📦 <b>Доступные паки</b> (бесплатно, не входят в лимит):\n\n",
        "uz": "📦 <b>Mavjud paklar</b> (bepul, limitga kirmaydi):\n\n",
    },
    "packs_empty": {
        "ru": "Пока нет доступных паков.",
        "uz": "Hozircha mavjud paklar yo'q.",
    },
    "packs_add_hint": {
        "ru": "\n\nДобавить себе: /add_pack Название",
        "uz": "\n\nQo'shish: /add_pack Nomi",
    },
    "my_packs_title": {
        "ru": "📦 <b>Твои подключенные паки:</b>\n\n",
        "uz": "📦 <b>Sizning paklaringiz:</b>\n\n",
    },
    "my_packs_empty": {
        "ru": "У тебя пока нет подключенных паков. Нажми «➕ Добавить пак».",
        "uz": "Sizda hozircha paklar yo'q. «➕ Pak qo'shish» tugmasini bosing.",
    },
    "pack_not_found": {
        "ru": "❓ Пак <b>{name}</b> не найден. Список доступных: /packs",
        "uz": "❓ <b>{name}</b> paki topilmadi. Mavjud ro'yxat: /packs",
    },
    "pack_already_added": {
        "ru": "ℹ️ Ты уже добавил этот пак.",
        "uz": "ℹ️ Siz bu pakni allaqachon qo'shgansiz.",
    },
    "pack_added": {
        "ru": "🎉 Пак <b>{name}</b> добавлен!\n\n📡 Каналов добавлено: <b>{channels}</b>\n🏷 Интересов добавлено: <b>{interests}</b>\n\nЭти каналы бесплатные и не учитываются в твоём лимите.",
        "uz": "🎉 <b>{name}</b> paki qo'shildi!\n\n📡 Qo'shilgan kanallar: <b>{channels}</b>\n🏷 Qo'shilgan qiziqishlar: <b>{interests}</b>\n\nBu kanallar bepul va limitingizga kirmaydi.",
    },
    "pack_disconnected": {
        "ru": "✅ Пак «{name}» отключён.\n📡 Каналов убрано: {count}\n\n<i>Интересы, добавленные из этого пака, остались — убрать их можно отдельно в разделе «Интересы».</i>",
        "uz": "✅ «{name}» paki uzildi.\n📡 O'chirilgan kanallar: {count}\n\n<i>Ushbu pakdan qo'shilgan qiziqishlar qoldi — ularni «Qiziqishlar» bo'limida alohida o'chirishingiz mumkin.</i>",
    },
    "pack_add_prompt": {
        "ru": "Выбери пак, который хочешь подключить:",
        "uz": "Ulamoqchi bo'lgan pakni tanlang:",
    },
    "pack_all_connected": {
        "ru": "Нет паков для подключения — либо их пока нет, либо ты уже подключил все существующие.",
        "uz": "Ulash uchun paklar yo'q — yoki hozircha yo'q, yoki barchasini allaqachon ulagansiz.",
    },
    "btn_disconnect_pack": {
        "ru": "🗑 Отключить «{name}»",
        "uz": "🗑 «{name}» ni uzish",
    },

    # ── Misc ──────────────────────────────────────────────────────────────────────
    "cancelled": {"ru": "❌ Отменено.", "uz": "❌ Bekor qilindi."},
    "main_menu": {"ru": "Главное меню:", "uz": "Asosiy menyu:"},
    "section_channels": {"ru": "📡 Раздел «Каналы»:", "uz": "📡 «Kanallar» bo'limi:"},
    "section_interests": {"ru": "🏷 Раздел «Интересы»:", "uz": "🏷 «Qiziqishlar» bo'limi:"},
    "section_subscription": {"ru": "⭐ Раздел «Подписка»:", "uz": "⭐ «Obuna» bo'limi:"},
    "section_packs": {"ru": "📦 Раздел «Паки»:", "uz": "📦 «Paklar» bo'limi:"},
    "section_more": {"ru": "⚙️ Ещё:", "uz": "⚙️ Ko'proq:"},

    # ── Auto-nudge ────────────────────────────────────────────────────────────────
    "nudge_day3": {
        "ru": "📊 За последние 24 часа бот обработал <b>{processed}</b> сообщений и нашёл <b>{sent}</b> релевантных.\n\nНо для вашего аккаунта пока нечего анализировать. Ты с нами уже 3 дня — самое время начать!\n\nДобавьте хотя бы один <b>канал</b> (раздел 📡 Каналы) — и бот сразу начнёт работать.",
        "uz": "📊 So'nggi 24 soat ichida bot <b>{processed}</b> ta xabarni qayta ishladi va <b>{sent}</b> ta tegishlisini topdi.\n\nLekin sizning akkauntingiz uchun hali tahlil qilish narsa yo'q. Siz biz bilan 3 kun bo'ldingiz — boshlash vaqti keldi!\n\nKamida bitta <b>kanal</b> qo'shing (📡 Kanallar bo'limi) — bot darhol ishlay boshlaydi.",
    },
    "nudge_day7": {
        "ru": "📊 За последние 24 часа бот обработал <b>{processed}</b> сообщений и нашёл <b>{sent}</b> релевантных.\n\nНо для вашего аккаунта пока нечего анализировать. Прошла неделя, как ты зарегистрировался.\n\nДобавьте хотя бы один <b>канал</b> (раздел 📡 Каналы) — и бот сразу начнёт работать.",
        "uz": "📊 So'nggi 24 soat ichida bot <b>{processed}</b> ta xabarni qayta ishladi va <b>{sent}</b> ta tegishlisini topdi.\n\nLekin sizning akkauntingiz uchun hali tahlil qilish narsa yo'q. Ro'yxatdan o'tganingizdan beri bir hafta o'tdi.\n\nKamida bitta <b>kanal</b> qo'shing (📡 Kanallar bo'limi) — bot darhol ishlay boshlaydi.",
    },
    "nudge_day14": {
        "ru": "📊 За последние 24 часа бот обработал <b>{processed}</b> сообщений и нашёл <b>{sent}</b> релевантных.\n\nНо для вашего аккаунта пока нечего анализировать. Уже 2 недели, а бот ещё не начал работать для тебя.\n\nДобавьте хотя бы один <b>канал</b> (раздел 📡 Каналы) — и бот сразу начнёт работать.",
        "uz": "📊 So'nggi 24 soat ichida bot <b>{processed}</b> ta xabarni qayta ishladi va <b>{sent}</b> ta tegishlisini topdi.\n\nLekin sizning akkauntingiz uchun hali tahlil qilish narsa yo'q. Allaqachon 2 hafta bo'ldi, bot siz uchun hali ishlamadi.\n\nKamida bitta <b>kanal</b> qo'shing (📡 Kanallar bo'limi) — bot darhol ishlay boshlaydi.",
    },
    "nudge_repeat": {
        "ru": "📊 За последние 24 часа бот обработал <b>{processed}</b> сообщений и нашёл <b>{sent}</b> релевантных.\n\nНо для вашего аккаунта пока нечего анализировать. Бот всё ещё ждёт тебя.\n\nДобавьте хотя бы один <b>канал</b> (раздел 📡 Каналы) — и бот сразу начнёт работать.",
        "uz": "📊 So'nggi 24 soat ichida bot <b>{processed}</b> ta xabarni qayta ishladi va <b>{sent}</b> ta tegishlisini topdi.\n\nLekin sizning akkauntingiz uchun hali tahlil qilish narsa yo'q. Bot sizni hali ham kutmoqda.\n\nKamida bitta <b>kanal</b> qo'shing (📡 Kanallar bo'limi) — bot darhol ishlay boshlaydi.",
    },
}

# AI prompt suffix — appended to the classifier prompt when user has a language preference
AI_LANG_INSTRUCTION = {
    "ru": "Write the 'reason' field in Russian.",
    "uz": "Write the 'reason' field in Uzbek (Latin script).",
}


def t(lang: str, key: str, **kwargs) -> str:
    """Return the translated string for key in lang, with optional format args."""
    lang = lang if lang in ("ru", "uz") else "ru"
    entry = STRINGS.get(key, {})
    text = entry.get(lang) or entry.get("ru", f"[{key}]")
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text
