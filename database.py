import sqlite3
import os
from datetime import datetime, timezone
from config import DB_PATH


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id         INTEGER PRIMARY KEY,
                username        TEXT,
                first_name      TEXT,
                joined_at       TEXT NOT NULL,
                is_premium      INTEGER DEFAULT 0,
                premium_until   TEXT,
                own_account     INTEGER DEFAULT 0,  -- 1 if user added their own account
                extra_channels  INTEGER DEFAULT 0   -- extra channel slots purchased, on top of FREE_CHANNEL_LIMIT
            );

            -- Channels per user
            CREATE TABLE IF NOT EXISTS user_channels (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                channel     TEXT NOT NULL,
                account_idx INTEGER DEFAULT 0,  -- which pool account listens to this
                added_at    TEXT NOT NULL,
                from_pack_id INTEGER DEFAULT NULL,  -- set if added via /add_pack (free, not capped)
                UNIQUE(user_id, channel)
            );

            -- Admin-curated bundles of interest(s) + channels, free and fixed (not editable by users)
            CREATE TABLE IF NOT EXISTS packs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT UNIQUE NOT NULL,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pack_interests (
                pack_id     INTEGER NOT NULL,
                interest    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pack_channels (
                pack_id     INTEGER NOT NULL,
                channel     TEXT NOT NULL
            );

            -- Which users have added which packs (prevents re-adding, marks origin)
            CREATE TABLE IF NOT EXISTS user_packs (
                user_id     INTEGER NOT NULL,
                pack_id     INTEGER NOT NULL,
                added_at    TEXT NOT NULL,
                UNIQUE(user_id, pack_id)
            );

            -- Global channel → account mapping (one Telethon session per channel)
            CREATE TABLE IF NOT EXISTS channel_accounts (
                channel     TEXT PRIMARY KEY,
                account_idx INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS processed_messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                channel     TEXT NOT NULL,
                message_id  INTEGER NOT NULL,
                timestamp   TEXT NOT NULL,
                UNIQUE(channel, message_id)
            );

            CREATE TABLE IF NOT EXISTS interests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                interest    TEXT NOT NULL,
                weight      REAL DEFAULT 1.0,
                created_at  TEXT NOT NULL,
                UNIQUE(user_id, interest)
            );

            CREATE TABLE IF NOT EXISTS interactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id  INTEGER NOT NULL,
                channel     TEXT NOT NULL,
                user_id     INTEGER NOT NULL,
                feedback    TEXT,
                score       INTEGER,
                timestamp   TEXT NOT NULL
            );

            -- Pending payment requests
            CREATE TABLE IF NOT EXISTS payment_requests (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                method          TEXT NOT NULL,  -- 'stars' | 'ton'
                amount          TEXT NOT NULL,
                extra_channels  INTEGER NOT NULL,
                months          INTEGER NOT NULL DEFAULT 1,
                status          TEXT DEFAULT 'pending',  -- pending | approved | rejected
                receipt_file_id TEXT,
                receipt_text    TEXT,
                created_at      TEXT NOT NULL,
                resolved_at     TEXT
            );
            -- Which interests matched a notification that was sent — needed to adjust
            -- weights correctly when the user reacts with 👍/👎 afterwards.
            CREATE TABLE IF NOT EXISTS sent_notifications (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                channel             TEXT NOT NULL,
                message_id          INTEGER NOT NULL,
                user_id             INTEGER NOT NULL,
                matched_interests   TEXT,  -- JSON list
                score               INTEGER,
                timestamp           TEXT NOT NULL,
                UNIQUE(channel, message_id, user_id)
            );

            -- Promo codes for percentage discounts
            CREATE TABLE IF NOT EXISTS promo_codes (
                code                TEXT PRIMARY KEY,
                discount_percent    INTEGER NOT NULL,
                max_activations     INTEGER NOT NULL,
                used_count          INTEGER NOT NULL DEFAULT 0,
                expires_at          TEXT NOT NULL,
                created_at          TEXT NOT NULL
            );

            -- One-off paid full-channel-history scans
            CREATE TABLE IF NOT EXISTS scan_jobs (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id             INTEGER NOT NULL,
                channel             TEXT NOT NULL,
                interest            TEXT NOT NULL,
                message_count       INTEGER,
                estimated_tokens    INTEGER,
                usd_price           REAL,
                ton_price           REAL,
                method              TEXT NOT NULL DEFAULT 'ton',
                status              TEXT NOT NULL DEFAULT 'pending_payment',
                receipt_file_id     TEXT,
                receipt_text        TEXT,
                matches_found       INTEGER,
                created_at          TEXT NOT NULL,
                completed_at        TEXT
            );

            -- Admin direct messages log
            CREATE TABLE IF NOT EXISTS dm_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                message     TEXT NOT NULL,
                sent_at     TEXT NOT NULL,
                sent_by     TEXT NOT NULL DEFAULT 'admin'  -- 'admin' or 'auto'
            );

            -- Simple key→value counters (e.g. total notifications sent)
            CREATE TABLE IF NOT EXISTS stats (
                key     TEXT PRIMARY KEY,
                value   INTEGER NOT NULL DEFAULT 0
            );
        """)
        # Migration: older DBs created before extra_channels existed.
        try:
            conn.execute("ALTER TABLE users ADD COLUMN extra_channels INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # column already exists
        # Migration: pending promo code applied via /promo, consumed on next purchase.
        try:
            conn.execute("ALTER TABLE users ADD COLUMN pending_promo TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN pending_promo_discount INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        # Migration: marks a channel as added via a free pack (excluded from the paid-limit count).
        try:
            conn.execute("ALTER TABLE user_channels ADD COLUMN from_pack_id INTEGER DEFAULT NULL")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE scan_jobs ADD COLUMN method TEXT NOT NULL DEFAULT 'ton'")
        except sqlite3.OperationalError:
            pass
        # Migration: lets the owner block a user from using the bot entirely.
        try:
            conn.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN banned_at TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN bot_blocked INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'ru'")
        except sqlite3.OperationalError:
            pass


# ─── Users ────────────────────────────────────────────────────────────────────

def upsert_user(user_id: int, username: str | None, first_name: str | None):
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, first_name, joined_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name
        """, (user_id, username, first_name, _now()))


def get_user(user_id: int) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def is_premium(user_id: int) -> bool:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT is_premium, premium_until FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
        if not row:
            return False
        if not row["is_premium"]:
            return False
        if row["premium_until"]:
            until = datetime.fromisoformat(row["premium_until"])
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) <= until
        return True


def set_premium(user_id: int, months: int, extra_channels: int = 0):
    """Extend or set premium for N months from now (or from current expiry).
    extra_channels is ADDED to the user's existing purchased channel allowance.
    """
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT premium_until, extra_channels FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        if row and row["premium_until"]:
            current = datetime.fromisoformat(row["premium_until"])
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
            base = max(now, current)
        else:
            base = now
        current_extra = (row["extra_channels"] or 0) if row else 0
        new_until = base + timedelta(days=30 * months)
        conn.execute("""
            UPDATE users SET is_premium=1, premium_until=?, extra_channels=? WHERE user_id=?
        """, (new_until.isoformat(), current_extra + extra_channels, user_id))


def get_extra_channels(user_id: int) -> int:
    """Extra channel slots purchased on top of FREE_CHANNEL_LIMIT, valid only while premium is active."""
    if not is_premium(user_id):
        return 0
    with _get_conn() as conn:
        row = conn.execute("SELECT extra_channels FROM users WHERE user_id=?", (user_id,)).fetchone()
        return (row["extra_channels"] or 0) if row else 0


def has_own_account(user_id: int) -> bool:
    with _get_conn() as conn:
        row = conn.execute("SELECT own_account FROM users WHERE user_id=?", (user_id,)).fetchone()
        return bool(row and row["own_account"])


def set_own_account(user_id: int, value: bool = True):
    with _get_conn() as conn:
        conn.execute("UPDATE users SET own_account=? WHERE user_id=?", (int(value), user_id))


def mark_bot_blocked(user_id: int):
    """Called when Telegram returns Forbidden: bot was blocked by the user."""
    with _get_conn() as conn:
        conn.execute("UPDATE users SET bot_blocked=1 WHERE user_id=?", (user_id,))


def get_lang(user_id: int) -> str:
    with _get_conn() as conn:
        row = conn.execute("SELECT lang FROM users WHERE user_id=?", (user_id,)).fetchone()
        return (row["lang"] or "ru") if row else "ru"


def set_lang(user_id: int, lang: str):
    with _get_conn() as conn:
        conn.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))


def is_bot_blocked(user_id: int) -> bool:
    with _get_conn() as conn:
        row = conn.execute("SELECT bot_blocked FROM users WHERE user_id=?", (user_id,)).fetchone()
        return bool(row and row["bot_blocked"])
    with _get_conn() as conn:
        conn.execute("UPDATE users SET is_banned=1, banned_at=? WHERE user_id=?", (_now(), user_id))


def unban_user(user_id: int):
    with _get_conn() as conn:
        conn.execute("UPDATE users SET is_banned=0, banned_at=NULL WHERE user_id=?", (user_id,))


def is_banned(user_id: int) -> bool:
    with _get_conn() as conn:
        row = conn.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,)).fetchone()
        return bool(row and row["is_banned"])


def get_active_users() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM users WHERE (is_banned=0 OR is_banned IS NULL) AND (bot_blocked=0 OR bot_blocked IS NULL) ORDER BY joined_at"
        ).fetchall()
        return [dict(r) for r in rows]


def get_banned_users() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM users WHERE is_banned=1 ORDER BY banned_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Channels ─────────────────────────────────────────────────────────────────

def get_user_channels(user_id: int) -> list[str]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT channel FROM user_channels WHERE user_id=? ORDER BY added_at",
            (user_id,)
        ).fetchall()
        return [r["channel"] for r in rows]


def get_user_channels_detailed(user_id: int) -> list[dict]:
    """Like get_user_channels but includes pack origin, for /my_channels display."""
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT uc.channel, uc.from_pack_id, p.name AS pack_name
            FROM user_channels uc
            LEFT JOIN packs p ON p.id = uc.from_pack_id
            WHERE uc.user_id=?
            ORDER BY uc.added_at
        """, (user_id,)).fetchall()
        return [dict(r) for r in rows]


def count_user_channels(user_id: int) -> int:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM user_channels WHERE user_id=?", (user_id,)
        ).fetchone()
        return row["c"]


def count_user_paid_channels(user_id: int) -> int:
    """Channels that count against the free/paid limit — excludes free pack channels."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM user_channels WHERE user_id=? AND from_pack_id IS NULL",
            (user_id,)
        ).fetchone()
        return row["c"]


def count_user_pack_channels(user_id: int) -> int:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM user_channels WHERE user_id=? AND from_pack_id IS NOT NULL",
            (user_id,)
        ).fetchone()
        return row["c"]


def add_user_channel(user_id: int, channel: str, account_idx: int = 0, from_pack_id: int | None = None) -> bool:
    """Returns True if added."""
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO user_channels (user_id, channel, account_idx, added_at, from_pack_id) VALUES (?,?,?,?,?)",
                (user_id, channel.lower(), account_idx, _now(), from_pack_id)
            )
            # Also record global channel → account mapping
            conn.execute(
                "INSERT OR IGNORE INTO channel_accounts (channel, account_idx) VALUES (?,?)",
                (channel.lower(), account_idx)
            )
        return True
    except sqlite3.IntegrityError:
        return False


def get_user_channel_pack(user_id: int, channel: str) -> str | None:
    """If this channel was added via a pack, returns the pack's name (so it can be protected from individual removal)."""
    with _get_conn() as conn:
        row = conn.execute("""
            SELECT p.name FROM user_channels uc
            JOIN packs p ON p.id = uc.from_pack_id
            WHERE uc.user_id=? AND uc.channel=?
        """, (user_id, channel.lower())).fetchone()
        return row["name"] if row else None


def remove_user_channel(user_id: int, channel: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM user_channels WHERE user_id=? AND channel=?",
            (user_id, channel.lower())
        )
        return cur.rowcount > 0


def get_all_channels() -> list[str]:
    """All unique channels across all users."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT channel FROM user_channels ORDER BY channel"
        ).fetchall()
        return [r["channel"] for r in rows]


def get_channel_subscribers(channel: str) -> list[int]:
    """All user_ids watching this channel."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT user_id FROM user_channels WHERE channel=?", (channel.lower(),)
        ).fetchall()
        return [r["user_id"] for r in rows]


def count_channels_on_account(account_idx: int) -> int:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(DISTINCT channel) as c FROM channel_accounts WHERE account_idx=?",
            (account_idx,)
        ).fetchone()
        return row["c"]


def get_channel_account(channel: str) -> int:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT account_idx FROM channel_accounts WHERE channel=?", (channel.lower(),)
        ).fetchone()
        return row["account_idx"] if row else 0


def set_channel_account(channel: str, account_idx: int):
    """Force-fix the channel→account mapping (unlike add_user_channel's INSERT OR IGNORE,
    this overwrites whatever was there — used by /admin_fix_channel)."""
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO channel_accounts (channel, account_idx) VALUES (?, ?)
            ON CONFLICT(channel) DO UPDATE SET account_idx=excluded.account_idx
        """, (channel.lower(), account_idx))


def get_all_channel_account_mappings() -> list[dict]:
    """All (channel, account_idx) pairs currently registered in channel_accounts."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT channel, account_idx FROM channel_accounts ORDER BY channel"
        ).fetchall()
        return [dict(r) for r in rows]


def remove_channel_account(channel: str) -> bool:
    """Drop the global channel→account mapping (call only once no user tracks it anymore)."""
    with _get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM channel_accounts WHERE channel=?", (channel.lower(),)
        )
        return cur.rowcount > 0


# ─── Processed messages ───────────────────────────────────────────────────────

def is_processed(channel: str, message_id: int) -> bool:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_messages WHERE channel=? AND message_id=?",
            (channel, message_id)
        ).fetchone()
        return row is not None


def mark_processed(channel: str, message_id: int):
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO processed_messages (channel, message_id, timestamp) VALUES (?,?,?)",
            (channel, message_id, _now())
        )


# ─── Interests ────────────────────────────────────────────────────────────────

def add_interest(user_id: int, interest: str) -> bool:
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO interests (user_id, interest, created_at) VALUES (?,?,?)",
                (user_id, interest.strip().lower(), _now())
            )
        return True
    except sqlite3.IntegrityError:
        return False


def remove_interest(user_id: int, interest: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM interests WHERE user_id=? AND interest=?",
            (user_id, interest.strip().lower())
        )
        return cur.rowcount > 0


def list_interests(user_id: int) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT interest, weight FROM interests WHERE user_id=? ORDER BY weight DESC, interest",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_interest_texts(user_id: int) -> list[str]:
    return [r["interest"] for r in list_interests(user_id)]


def get_interest_weights(user_id: int) -> dict[str, float]:
    """interest(lowercase) -> weight, for applying weight to AI scores without extra AI calls."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT interest, weight FROM interests WHERE user_id=?", (user_id,)
        ).fetchall()
        return {r["interest"]: r["weight"] for r in rows}


def adjust_interest_weights(user_id: int, matched_interests: list[str], feedback: str):
    delta = 0.1 if feedback == "like" else -0.1
    with _get_conn() as conn:
        for interest in matched_interests:
            conn.execute("""
                UPDATE interests SET weight = MAX(0.1, MIN(2.0, weight + ?))
                WHERE user_id=? AND interest=?
            """, (delta, user_id, interest.lower()))


def record_sent_notification(channel: str, message_id: int, user_id: int,
                              matched_interests: list[str], score: int):
    """Remember which interests matched a sent notification, so feedback later
    can adjust the right weights."""
    import json
    with _get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO sent_notifications
                (channel, message_id, user_id, matched_interests, score, timestamp)
            VALUES (?,?,?,?,?,?)
        """, (channel.lower(), message_id, user_id, json.dumps(matched_interests), score, _now()))


def get_sent_notification(channel: str, message_id: int, user_id: int) -> dict | None:
    import json
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sent_notifications WHERE channel=? AND message_id=? AND user_id=?",
            (channel.lower(), message_id, user_id)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["matched_interests"] = json.loads(d["matched_interests"]) if d["matched_interests"] else []
        return d


# ─── Feedback ─────────────────────────────────────────────────────────────────

def save_feedback(channel: str, message_id: int, user_id: int, feedback: str, score: int):
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO interactions (message_id, channel, user_id, feedback, score, timestamp)
            VALUES (?,?,?,?,?,?)
        """, (message_id, channel, user_id, feedback, score, _now()))


# ─── Payments ─────────────────────────────────────────────────────────────────

def create_payment_request(user_id: int, method: str, amount: str,
                            extra_channels: int, months: int,
                            receipt_file_id: str | None = None,
                            receipt_text: str | None = None) -> int:
    with _get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO payment_requests
            (user_id, method, amount, extra_channels, months, receipt_file_id, receipt_text, created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (user_id, method, amount, extra_channels, months,
              receipt_file_id, receipt_text, _now()))
        return cur.lastrowid


def get_payment_request(req_id: int) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM payment_requests WHERE id=?", (req_id,)
        ).fetchone()
        return dict(row) if row else None


def resolve_payment(req_id: int, status: str):
    with _get_conn() as conn:
        conn.execute("""
            UPDATE payment_requests SET status=?, resolved_at=? WHERE id=?
        """, (status, _now(), req_id))


def get_pending_payments() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM payment_requests WHERE status='pending' ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_users() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY joined_at").fetchall()
        return [dict(r) for r in rows]


# ─── Stats ────────────────────────────────────────────────────────────────────

def increment_stat(key: str, by: int = 1):
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO stats (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = value + ?
        """, (key, by, by))


def get_admin_stats() -> dict:
    with _get_conn() as conn:
        users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        blocked = conn.execute("SELECT COUNT(*) c FROM users WHERE bot_blocked=1").fetchone()["c"]
        channels = conn.execute("SELECT COUNT(DISTINCT channel) c FROM user_channels").fetchone()["c"]
        processed = conn.execute("SELECT COUNT(*) c FROM processed_messages").fetchone()["c"]
        sent_row = conn.execute("SELECT value FROM stats WHERE key='notifications_sent'").fetchone()
        sent = sent_row["value"] if sent_row else 0
        likes = conn.execute("SELECT COUNT(*) c FROM interactions WHERE feedback='like'").fetchone()["c"]
        dislikes = conn.execute("SELECT COUNT(*) c FROM interactions WHERE feedback='dislike'").fetchone()["c"]
        scan_users = conn.execute(
            "SELECT COUNT(DISTINCT user_id) c FROM scan_jobs WHERE status='done'"
        ).fetchone()["c"]
        scan_runs = conn.execute(
            "SELECT COUNT(*) c FROM scan_jobs WHERE status='done'"
        ).fetchone()["c"]
        return {
            "users": users,
            "blocked": blocked,
            "channels": channels,
            "processed": processed,
            "sent": sent,
            "likes": likes,
            "dislikes": dislikes,
            "scan_users": scan_users,
            "scan_runs": scan_runs,
        }


# ─── Promo codes ──────────────────────────────────────────────────────────────

def create_promo_code(code: str, discount_percent: int, max_activations: int, days_valid: int) -> bool:
    from datetime import timedelta
    expires_at = (datetime.now(timezone.utc) + timedelta(days=days_valid)).isoformat()
    try:
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO promo_codes (code, discount_percent, max_activations, used_count, expires_at, created_at)
                VALUES (?,?,?,0,?,?)
            """, (code.strip().upper(), discount_percent, max_activations, expires_at, _now()))
        return True
    except sqlite3.IntegrityError:
        return False


def get_promo_code(code: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM promo_codes WHERE code=?", (code.strip().upper(),)).fetchone()
        return dict(row) if row else None


def check_promo_code(code: str) -> tuple[bool, str, dict | None]:
    """Validate without consuming. Returns (valid, reason, promo_row)."""
    promo = get_promo_code(code)
    if not promo:
        return False, "not_found", None
    expires = datetime.fromisoformat(promo["expires_at"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        return False, "expired", promo
    if promo["used_count"] >= promo["max_activations"]:
        return False, "exhausted", promo
    return True, "ok", promo


def redeem_promo_code(code: str) -> bool:
    """Atomically consume one activation if still valid. Returns True on success."""
    valid, _reason, _promo = check_promo_code(code)
    if not valid:
        return False
    with _get_conn() as conn:
        cur = conn.execute("""
            UPDATE promo_codes SET used_count = used_count + 1
            WHERE code=? AND used_count < max_activations
        """, (code.strip().upper(),))
        return cur.rowcount > 0


def set_pending_promo(user_id: int, code: str, discount_percent: int):
    with _get_conn() as conn:
        conn.execute(
            "UPDATE users SET pending_promo=?, pending_promo_discount=? WHERE user_id=?",
            (code.strip().upper(), discount_percent, user_id)
        )


def get_pending_promo(user_id: int) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT pending_promo, pending_promo_discount FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
        if not row or not row["pending_promo"]:
            return None
        return {"code": row["pending_promo"], "discount_percent": row["pending_promo_discount"] or 0}


def clear_pending_promo(user_id: int):
    with _get_conn() as conn:
        conn.execute(
            "UPDATE users SET pending_promo=NULL, pending_promo_discount=0 WHERE user_id=?", (user_id,)
        )


# ─── Packs ────────────────────────────────────────────────────────────────────

def create_pack(name: str, interests: list[str], channels: list[str]) -> int | None:
    """Returns the new pack's id, or None if a pack with this name already exists."""
    try:
        with _get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO packs (name, created_at) VALUES (?, ?)",
                (name.strip(), _now())
            )
            pack_id = cur.lastrowid
            for interest in interests:
                conn.execute(
                    "INSERT INTO pack_interests (pack_id, interest) VALUES (?, ?)",
                    (pack_id, interest.strip().lower())
                )
            for channel in channels:
                ch = channel.strip()
                if not ch.startswith("@"):
                    ch = f"@{ch}"
                conn.execute(
                    "INSERT INTO pack_channels (pack_id, channel) VALUES (?, ?)",
                    (pack_id, ch.lower())
                )
            return pack_id
    except sqlite3.IntegrityError:
        return None


def get_pack_by_name(name: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM packs WHERE name=? COLLATE NOCASE", (name.strip(),)
        ).fetchone()
        if not row:
            return None
        pack = dict(row)
        pack["interests"] = [r["interest"] for r in conn.execute(
            "SELECT interest FROM pack_interests WHERE pack_id=?", (pack["id"],)
        ).fetchall()]
        pack["channels"] = [r["channel"] for r in conn.execute(
            "SELECT channel FROM pack_channels WHERE pack_id=?", (pack["id"],)
        ).fetchall()]
        return pack


def get_pack_by_id(pack_id: int) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM packs WHERE id=?", (pack_id,)).fetchone()
        if not row:
            return None
        pack = dict(row)
        pack["interests"] = [r["interest"] for r in conn.execute(
            "SELECT interest FROM pack_interests WHERE pack_id=?", (pack["id"],)
        ).fetchall()]
        pack["channels"] = [r["channel"] for r in conn.execute(
            "SELECT channel FROM pack_channels WHERE pack_id=?", (pack["id"],)
        ).fetchall()]
        return pack


def get_user_packs(user_id: int) -> list[dict]:
    """Packs this specific user has already connected via /add_pack (or the inline picker)."""
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT p.id, p.name, up.added_at
            FROM user_packs up
            JOIN packs p ON p.id = up.pack_id
            WHERE up.user_id=?
            ORDER BY up.added_at DESC
        """, (user_id,)).fetchall()
        packs = []
        for row in rows:
            pack = dict(row)
            pack["channels_count"] = conn.execute(
                "SELECT COUNT(*) c FROM pack_channels WHERE pack_id=?", (pack["id"],)
            ).fetchone()["c"]
            pack["interests_count"] = conn.execute(
                "SELECT COUNT(*) c FROM pack_interests WHERE pack_id=?", (pack["id"],)
            ).fetchone()["c"]
            packs.append(pack)
        return packs


def get_all_packs() -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM packs ORDER BY name").fetchall()
        packs = []
        for row in rows:
            pack = dict(row)
            pack["interests_count"] = conn.execute(
                "SELECT COUNT(*) c FROM pack_interests WHERE pack_id=?", (pack["id"],)
            ).fetchone()["c"]
            pack["channels_count"] = conn.execute(
                "SELECT COUNT(*) c FROM pack_channels WHERE pack_id=?", (pack["id"],)
            ).fetchone()["c"]
            packs.append(pack)
        return packs


def has_user_added_pack(user_id: int, pack_id: int) -> bool:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM user_packs WHERE user_id=? AND pack_id=?", (user_id, pack_id)
        ).fetchone()
        return row is not None


def record_user_pack(user_id: int, pack_id: int):
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_packs (user_id, pack_id, added_at) VALUES (?,?,?)",
            (user_id, pack_id, _now())
        )


def update_pack(pack_id: int, new_name: str, interests: list[str], channels: list[str]) -> bool:
    """Replaces the pack's name/interests/channels. Does NOT retroactively touch users
    who already connected the old version — they keep what they got at connection time."""
    try:
        with _get_conn() as conn:
            conn.execute("UPDATE packs SET name=? WHERE id=?", (new_name.strip(), pack_id))
            conn.execute("DELETE FROM pack_interests WHERE pack_id=?", (pack_id,))
            conn.execute("DELETE FROM pack_channels WHERE pack_id=?", (pack_id,))
            for interest in interests:
                conn.execute(
                    "INSERT INTO pack_interests (pack_id, interest) VALUES (?, ?)",
                    (pack_id, interest.strip().lower())
                )
            for channel in channels:
                ch = channel.strip()
                if not ch.startswith("@"):
                    ch = f"@{ch}"
                conn.execute(
                    "INSERT INTO pack_channels (pack_id, channel) VALUES (?, ?)",
                    (pack_id, ch.lower())
                )
        return True
    except sqlite3.IntegrityError:
        return False


def delete_pack(pack_id: int) -> bool:
    with _get_conn() as conn:
        cur = conn.execute("DELETE FROM packs WHERE id=?", (pack_id,))
        conn.execute("DELETE FROM pack_interests WHERE pack_id=?", (pack_id,))
        conn.execute("DELETE FROM pack_channels WHERE pack_id=?", (pack_id,))
        return cur.rowcount > 0


def get_user_pack_channels(user_id: int, pack_id: int) -> list[str]:
    """Channels this specific user received from this specific pack."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT channel FROM user_channels WHERE user_id=? AND from_pack_id=?",
            (user_id, pack_id)
        ).fetchall()
        return [r["channel"] for r in rows]


def remove_user_pack(user_id: int, pack_id: int):
    with _get_conn() as conn:
        conn.execute("DELETE FROM user_packs WHERE user_id=? AND pack_id=?", (user_id, pack_id))


# ─── One-off full-channel scans ────────────────────────────────────────────────

def create_scan_job(user_id: int, channel: str, interest: str, message_count: int,
                     estimated_tokens: int, usd_price: float, ton_price: float, method: str = "ton") -> int:
    with _get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO scan_jobs
                (user_id, channel, interest, message_count, estimated_tokens, usd_price, ton_price, method, status, created_at)
            VALUES (?,?,?,?,?,?,?,?, 'pending_payment', ?)
        """, (user_id, channel.lower(), interest, message_count, estimated_tokens, usd_price, ton_price, method, _now()))
        return cur.lastrowid


def attach_scan_receipt(job_id: int, receipt_file_id: str | None, receipt_text: str | None):
    with _get_conn() as conn:
        conn.execute(
            "UPDATE scan_jobs SET receipt_file_id=?, receipt_text=?, status='awaiting_approval' WHERE id=?",
            (receipt_file_id, receipt_text, job_id)
        )


def get_scan_job(job_id: int) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM scan_jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None


def set_scan_job_status(job_id: int, status: str):
    with _get_conn() as conn:
        conn.execute("UPDATE scan_jobs SET status=? WHERE id=?", (status, job_id))


def finish_scan_job(job_id: int, matches_found: int):
    with _get_conn() as conn:
        conn.execute(
            "UPDATE scan_jobs SET status='done', matches_found=?, completed_at=? WHERE id=?",
            (matches_found, _now(), job_id)
        )


# ─── Diagnostics ────────────────────────────────────────────────────────────────

def get_user_diagnostics(user_id: int) -> dict:
    """Everything needed to debug 'why doesn't this user get notifications' from /admin."""
    with _get_conn() as conn:
        user_row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        user = dict(user_row) if user_row else None
        if not user:
            return {"user": None, "channels": [], "interests": [], "sent_count": 0}

        channel_rows = conn.execute(
            "SELECT channel, account_idx, from_pack_id FROM user_channels WHERE user_id=? ORDER BY added_at",
            (user_id,)
        ).fetchall()
        channels = []
        for c in channel_rows:
            ch = c["channel"]
            mapped = conn.execute(
                "SELECT account_idx FROM channel_accounts WHERE channel=?", (ch,)
            ).fetchone()
            processed_count = conn.execute(
                "SELECT COUNT(*) c FROM processed_messages WHERE channel=?", (ch,)
            ).fetchone()["c"]
            channels.append({
                "channel": ch,
                "assigned_account": c["account_idx"],
                "mapped_account": mapped["account_idx"] if mapped else None,
                "from_pack_id": c["from_pack_id"],
                "processed_count": processed_count,
            })

        interest_rows = conn.execute(
            "SELECT interest, weight FROM interests WHERE user_id=? ORDER BY weight DESC",
            (user_id,)
        ).fetchall()
        interests = [dict(r) for r in interest_rows]

        sent_count = conn.execute(
            "SELECT COUNT(*) c FROM sent_notifications WHERE user_id=?", (user_id,)
        ).fetchone()["c"]

        return {"user": user, "channels": channels, "interests": interests, "sent_count": sent_count}


# ─── Admin DM log ─────────────────────────────────────────────────────────────

def log_dm(user_id: int, message: str, sent_by: str = "admin"):
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO dm_log (user_id, message, sent_at, sent_by) VALUES (?,?,?,?)",
            (user_id, message[:500], _now(), sent_by)
        )


def get_dm_log(limit: int = 50) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM dm_log ORDER BY sent_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_users_needing_nudge() -> list[dict]:
    """
    Staged nudge schedule for users with 0 channels:
    - Day 3: first nudge (registered exactly 3 days ago, no prior auto DM ever)
    - Day 7: second nudge (no auto DM in last 6 days)
    - Day 14: third nudge (no auto DM in last 9 days)
    - Day 14+: every 4 days (no auto DM in last 4 days)
    """
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT u.user_id, u.first_name, u.username, u.joined_at,
                   (SELECT COUNT(*) FROM user_channels uc WHERE uc.user_id = u.user_id) AS ch_count,
                   (SELECT COUNT(*) FROM interests i WHERE i.user_id = u.user_id) AS in_count,
                   (SELECT MAX(dl.sent_at) FROM dm_log dl
                    WHERE dl.user_id = u.user_id AND dl.sent_by = 'auto') AS last_auto_dm,
                   CAST((julianday('now') - julianday(u.joined_at)) AS INTEGER) AS days_since_join
            FROM users u
            WHERE u.is_banned = 0
              AND (u.bot_blocked = 0 OR u.bot_blocked IS NULL)
              AND (SELECT COUNT(*) FROM user_channels uc WHERE uc.user_id = u.user_id) = 0
              AND CAST((julianday('now') - julianday(u.joined_at)) AS INTEGER) >= 3
        """).fetchall()

        result = []
        for r in rows:
            row = dict(r)
            days = row["days_since_join"]
            last_dm = row["last_auto_dm"]

            if last_dm is None:
                # Никогда не получал авто-DM — шлём всем, кто >=3 дней
                result.append(row)
                continue

            from datetime import datetime as dt, timezone as tz
            last_dt = dt.fromisoformat(last_dm)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=tz.utc)
            days_since_last = (dt.now(tz.utc) - last_dt).days

            if days <= 7 and days_since_last >= 4:
                result.append(row)   # между 3 и 7 днями — интервал 4 дня
            elif days <= 14 and days_since_last >= 7:
                result.append(row)   # между 7 и 14 днями — интервал 7 дней
            elif days > 14 and days_since_last >= 4:
                result.append(row)   # после 14 дней — каждые 4 дня

        return result


def get_users_by_channel_count(channel_count: int) -> list[dict]:
    """Users who have exactly `channel_count` channels, excluding banned/blocked."""
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT u.user_id, u.first_name, u.username,
                   (SELECT COUNT(*) FROM user_channels uc WHERE uc.user_id = u.user_id) AS ch_count
            FROM users u
            WHERE u.is_banned = 0
              AND (u.bot_blocked = 0 OR u.bot_blocked IS NULL)
              AND (SELECT COUNT(*) FROM user_channels uc WHERE uc.user_id = u.user_id) = ?
            ORDER BY u.joined_at
        """, (channel_count,)).fetchall()
        return [dict(r) for r in rows]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
