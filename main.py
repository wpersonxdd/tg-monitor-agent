"""
TG Monitor — entry point.
Runs Telethon multi-account listener + aiogram bot in parallel.
"""
import asyncio
import logging
import sys

import database as db
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_CHAT_ID, ACCOUNT_POOL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


def check_config():
    errors = []
    if not API_ID:
        errors.append("API_ID не задан в .env")
    if not API_HASH:
        errors.append("API_HASH не задан в .env")
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN не задан в .env")
    if not OWNER_CHAT_ID:
        errors.append("OWNER_CHAT_ID не задан в .env")
    if not ACCOUNT_POOL:
        errors.append("ACCOUNT_POOL не задан — нет аккаунтов для прослушивания")
    if errors:
        for e in errors:
            logger.error("Ошибка конфига: %s", e)
        sys.exit(1)


from listener import MultiAccountListener
multi_listener_instance = None

async def run_listener():
    import listener
    ml = MultiAccountListener()
    listener.multi_listener = ml
    await ml.start()


async def run_bot():
    from bot import create_bot_and_dispatcher, _auto_nudge_loop
    bot, dp = create_bot_and_dispatcher()
    logger.info("Запуск aiogram бота (polling)...")
    asyncio.create_task(_auto_nudge_loop(bot))
    await dp.start_polling(bot)


async def run_classification_worker():
    """Run the classification worker in a separate OS thread so slow AI API
    calls (DeepSeek/OpenAI) never block the asyncio event loop that serves
    both the Telethon listener and the aiogram bot."""
    import concurrent.futures
    loop = asyncio.get_running_loop()

    def _thread_worker():
        """A brand-new event loop running only the classification coroutine."""
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            new_loop.run_until_complete(_classification_worker_thread())
        finally:
            new_loop.close()

    async def _classification_worker_thread():
        import config
        import database as db
        from listener import _classify_queue
        from agent import TriageAgent
        agent = TriageAgent()
        logger.info("Воркер классификации запущен в отдельном потоке")
        while True:
            # Block until an item is available — but in our own loop, not the main one.
            try:
                item = _classify_queue.get(block=True, timeout=1.0)
            except Exception:
                await asyncio.sleep(0)
                continue
            try:
                channel_name = item["channel"]
                message_id = item["message_id"]
                text = item["text"]
                chat_username = item["chat_username"]
                subscribers = item["subscribers"]
                for user_id in subscribers:
                    interests = db.get_interest_texts(user_id)
                    if not interests:
                        continue

                    lang = db.get_lang(user_id)
                    result = await agent.classify(
                        message_text=text,
                        interests=interests,
                        channel=channel_name,
                        lang=lang,
                        user_id=user_id,
                        message_id=message_id,
                    )

                    weighted_score = result.score
                    if result.matched_interests:
                        weights = db.get_interest_weights(user_id)
                        factors = [weights.get(i.lower(), 1.0) for i in result.matched_interests]
                        avg_factor = sum(factors) / len(factors)
                        weighted_score = result.score * avg_factor

                    if result.relevant and weighted_score >= config.RELEVANCE_THRESHOLD:
                        from notifier import send_notification
                        link = f"https://t.me/{chat_username}/{message_id}" if chat_username else None
                        await send_notification(
                            user_id=user_id,
                            channel=channel_name,
                            message_text=text,
                            result=result,
                            message_link=link,
                            channel_msg_id=message_id,
                        )

                await asyncio.sleep(0.3)  # ~3 msg/sec max to stay under Telegram rate limits
            except Exception as e:
                logger.error("Classification worker error: %s", e)
            finally:
                _classify_queue.task_done()

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="classifier")
    await loop.run_in_executor(executor, _thread_worker)


async def main():
    check_config()
    db.init_db()
    logger.info("БД инициализирована")
    logger.info("Аккаунтов в пуле: %d", len(ACCOUNT_POOL))

    await asyncio.gather(
        run_listener(),
        run_bot(),
        run_classification_worker(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановлено пользователем")


multi_listener = None
