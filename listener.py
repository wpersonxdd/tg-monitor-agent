"""
Multi-account Telethon listener.
One TelegramClient per account in the pool.
Each client listens only to channels assigned to it.
"""
import asyncio
import queue as _thread_queue
import logging
from telethon import TelegramClient, events
from telethon.tl.types import Message

import config
import database as db
from classifier import Classifier
from notifier import send_notification
from telethon.tl.functions.channels import JoinChannelRequest

logger = logging.getLogger(__name__)

# Internal queue for messages awaiting AI classification.
# The Telethon event handler just enqueues — a separate OS-thread worker drains it.
_classify_queue: _thread_queue.Queue = _thread_queue.Queue(maxsize=2000)


class AccountListener:
    def __init__(self, account: dict, account_idx: int, classifier: Classifier):
        self.account = account
        self.idx = account_idx
        self.classifier = classifier
        self.client = TelegramClient(
            account["session"],
            account["api_id"],
            account["api_hash"],
        )

    async def start(self):
        await self.client.start()
        logger.info("Account[%d] session=%s connected", self.idx, self.account["session"])

        @self.client.on(events.NewMessage())
        async def handle(event: events.NewMessage.Event):
            message: Message = event.message
            try:
                chat = await event.get_chat()
            except Exception:
                return

            # Only handle channels assigned to this account
            channel_name = f"@{chat.username}" if getattr(chat, "username", None) else str(chat.id)
            assigned_idx = db.get_channel_account(channel_name)
            if assigned_idx != self.idx:
                return

            text = message.text or ""
            if not text.strip():
                return

            message_id = message.id
            if db.is_processed(channel_name, message_id):
                return
            db.mark_processed(channel_name, message_id)

            subscribers = db.get_channel_subscribers(channel_name)
            if not subscribers:
                return

            # Enqueue for async AI classification — never block the event loop here.
            try:
                _classify_queue.put_nowait({
                    "channel": channel_name,
                    "message_id": message_id,
                    "text": text,
                    "chat_username": getattr(chat, "username", None),
                    "subscribers": subscribers,
                    "classifier": self.classifier,
                })
            except _thread_queue.Full:                logger.warning(
                    "Classify queue full (%d items) — dropping message %s/%d",
                    _classify_queue.qsize(), channel_name, message_id
                )

        await self.client.run_until_disconnected()

    async def stop(self):
        await self.client.disconnect()

    async def join_channel(self, channel: str):
        try:
            from telethon.tl.functions.channels import JoinChannelRequest
            await self.client(JoinChannelRequest(channel))
            logger.info("Account[%d] joined channel %s", self.idx, channel)
        except Exception as e:
            logger.error("Failed to join %s: %s", channel, e)

    async def leave_channel(self, channel: str):
        try:
            from telethon.tl.functions.channels import LeaveChannelRequest
            await self.client(LeaveChannelRequest(channel))
            logger.info("Account[%d] left channel %s", self.idx, channel)
        except Exception as e:
            logger.error("Failed to leave %s: %s", channel, e)

    async def fetch_channel_texts(self, channel: str) -> list[dict]:
        """Fetch every text post in a channel's full history.
        Used by the paid one-off 'full channel scan' feature — not for regular monitoring."""
        results = []
        async for msg in self.client.iter_messages(channel):
            text = msg.text or msg.message or ""
            if text and text.strip():
                results.append({"id": msg.id, "text": text})
        return results


class MultiAccountListener:
    def __init__(self):
        self.classifier = Classifier()
        self.listeners: list[AccountListener] = []

    async def start(self):
        pool = config.ACCOUNT_POOL
        if not pool:
            logger.error("No accounts in ACCOUNT_POOL. Check .env")
            return

        self.listeners = [
            AccountListener(acc, idx, self.classifier)
            for idx, acc in enumerate(pool)
        ]

        logger.info("Starting %d Telethon account(s)...", len(self.listeners))
        await asyncio.gather(*[l.start() for l in self.listeners])
