"""
Manages multiple Telethon accounts for channel distribution.
Channels are assigned to accounts in order — when one fills up, the next is used.
"""
import logging
from config import ACCOUNT_POOL, MAX_CHANNELS_PER_ACCOUNT
import database as db

logger = logging.getLogger(__name__)


def get_account_for_new_channel() -> int | None:
    """
    Returns the index of the account that should listen to a new channel.
    Returns None if all accounts are full.
    """
    for idx, _ in enumerate(ACCOUNT_POOL):
        used = db.count_channels_on_account(idx)
        if used < MAX_CHANNELS_PER_ACCOUNT:
            logger.info("Assigning new channel to account[%d] (%d/%d used)",
                        idx, used, MAX_CHANNELS_PER_ACCOUNT)
            return idx
    logger.warning("All %d accounts are full!", len(ACCOUNT_POOL))
    return None


def get_pool_status() -> list[dict]:
    """Return capacity info for each account."""
    status = []
    for idx, acc in enumerate(ACCOUNT_POOL):
        used = db.count_channels_on_account(idx)
        status.append({
            "idx": idx,
            "session": acc["session"],
            "used": used,
            "capacity": MAX_CHANNELS_PER_ACCOUNT,
            "free": MAX_CHANNELS_PER_ACCOUNT - used,
        })
    return status
