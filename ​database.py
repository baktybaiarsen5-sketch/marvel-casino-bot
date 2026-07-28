"""Async SQLite layer — all DB access goes through this module."""
from __future__ import annotations

import aiosqlite
from config import DB_PATH, STARTING_COINS

_db: aiosqlite.Connection | None = None

# ── Creator config ────────────────────────────────────────────────────────────
CREATOR_ID       = 8769460654
CREATOR_USERNAME = "bktvvvv"
CREATOR_COINS    = 10_000_000
CREATOR_STONES   = 500.0


async def init_db() -> None:
    global _db
    _db = await aiosqlite.connect(DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA synchronous=NORMAL")

    # ── players ───────────────────────────────────────────────────────────────
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT    NOT NULL DEFAULT '',
            first_name  TEXT    NOT NULL DEFAULT '',
            coins       INTEGER NOT NULL DEFAULT 1000,
            soul_stones REAL    NOT NULL DEFAULT 0.0,
            last_bonus  TEXT             DEFAULT NULL,
            is_vip      INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Safe migration: add is_vip if it doesn't exist yet
    try:
        await _db.execute("ALTER TABLE players ADD COLUMN is_vip INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass  # column already exists

    # ── marriages ─────────────────────────────────────────────────────────────
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS marriages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id     INTEGER NOT NULL,
            user1_id    INTEGER NOT NULL,
            user2_id    INTEGER NOT NULL,
            user1_name  TEXT    NOT NULL DEFAULT '',
            user2_name  TEXT    NOT NULL DEFAULT '',
            married_at  TEXT    NOT NULL
        )
    """)

    await _db.commit()

    # Ensure creator has premium starting resources
    await _ensure_creator()


async def _ensure_creator() -> None:
    """Give the creator their premium balance and auto-VIP if not already set."""
    async with _db.execute(
        "SELECT coins, soul_stones FROM players WHERE user_id = ?", (CREATOR_ID,)
    ) as cur:
        row = await cur.fetchone()

    if row is None:
        # First time — insert with premium values
        await _db.execute(
            "INSERT OR IGNORE INTO players (user_id, username, first_name, coins, soul_stones, is_vip) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (CREATOR_ID, CREATOR_USERNAME, "Creator", CREATOR_COINS, CREATOR_STONES),
        )
    else:
        # Already exists — ensure VIP and boost if below premium values
        updates = ["is_vip = 1"]
        if row["coins"] < CREATOR_COINS:
            updates.append(f"coins = {CREATOR_COINS}")
        if row["soul_stones"] < CREATOR_STONES:
            updates.append(f"soul_stones = {CREATOR_STONES}")
        if updates:
            await _db.execute(
                f"UPDATE players SET {', '.join(updates)} WHERE user_id = ?",
                (CREATOR_ID,),
            )

    await _db.commit()


async def close_db() -> None:
    global _db
    if _db:
        await _db.close()
        _db = None


async def get_or_create_player(user_id: int, username: str, first_name: str) -> dict:
    await _db.execute(
        "INSERT OR IGNORE INTO players (user_id, username, first_name, coins, is_vip) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, first_name, STARTING_COINS,
         1 if user_id == CREATOR_ID else 0),
    )
    await _db.execute(
        "UPDATE players SET username = ?, first_name = ? WHERE user_id = ?",
        (username, first_name, user_id),
    )
    # Creator always keeps VIP
    if user_id == CREATOR_ID:
        await _db.execute("UPDATE players SET is_vip = 1 WHERE user_id = ?", (user_id,))
    await _db.commit()
    async with _db.execute("SELECT * FROM players WHERE user_id = ?", (user_id,)) as cur:
        return dict(await cur.fetchone())


async def add_coins(user_id: int, delta: int) -> int:
    """Apply a coins delta (can be negative). Balance floor is 0. Returns new balance."""
    await _db.execute(
        "UPDATE players SET coins = MAX(0, coins + ?) WHERE user_id = ?",
        (delta, user_id),
    )
    await _db.commit()
    async with _db.execute("SELECT coins FROM players WHERE user_id = ?", (user_id,)) as cur:
        return (await cur.fetchone())["coins"]


async def add_soul_stones(user_id: int, delta: float) -> float:
    """Apply a soul-stones delta (can be negative). Floor is 0. Returns new balance."""
    await _db.execute(
        "UPDATE players SET soul_stones = MAX(0.0, soul_stones + ?) WHERE user_id = ?",
        (delta, user_id),
    )
    await _db.commit()
    async with _db.execute("SELECT soul_stones FROM players WHERE user_id = ?", (user_id,)) as cur:
        return (await cur.fetchone())["soul_stones"]


async def set_last_bonus(user_id: int, iso_dt: str) -> None:
    await _db.execute(
        "UPDATE players SET last_bonus = ? WHERE user_id = ?",
        (iso_dt, user_id),
    )
    await _db.commit()


async def set_vip(user_id: int, value: int) -> None:
    await _db.execute("UPDATE players SET is_vip = ? WHERE user_id = ?", (value, user_id))
    await _db.commit()


async def get_top_players(limit: int = 30) -> list[dict]:
    async with _db.execute(
        "SELECT user_id, username, first_name, coins, is_vip FROM players "
        "ORDER BY coins DESC LIMIT ?",
        (limit,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def get_player_by_username(username: str) -> dict | None:
    """Find a player by Telegram username (case-insensitive, without @)."""
    clean = username.lstrip("@")
    async with _db.execute(
        "SELECT * FROM players WHERE lower(username) = lower(?)", (clean,)
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def reset_all_balances() -> int:
    """Reset ALL players to STARTING_COINS and 0 soul stones. Returns number of rows updated."""
    await _db.execute(
        "UPDATE players SET coins = ?, soul_stones = 0.0", (STARTING_COINS,)
    )
    await _db.commit()
    # Re-apply creator premium
    await _ensure_creator()
    async with _db.execute("SELECT changes()") as cur:
        return (await cur.fetchone())[0]


# ── Marriage ──────────────────────────────────────────────────────────────────

async def create_marriage(chat_id: int, u1_id: int, u1_name: str,
                           u2_id: int, u2_name: str, married_at: str) -> int:
    cur = await _db.execute(
        "INSERT INTO marriages (chat_id, user1_id, user2_id, user1_name, user2_name, married_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, u1_id, u2_id, u1_name, u2_name, married_at),
    )
    await _db.commit()
    return cur.lastrowid


async def get_marriage(user_id: int) -> dict | None:
    """Return the marriage row for a user (any chat), or None."""
    async with _db.execute(
        "SELECT * FROM marriages WHERE user1_id = ? OR user2_id = ? LIMIT 1",
        (user_id, user_id),
    ) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_chat_marriages(chat_id: int) -> list[dict]:
    """Return all marriages in a specific chat, newest last."""
    async with _db.execute(
        "SELECT * FROM marriages WHERE chat_id = ? ORDER BY married_at ASC",
        (chat_id,),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def delete_marriage(user_id: int) -> None:
    await _db.execute(
        "DELETE FROM marriages WHERE user1_id = ? OR user2_id = ?",
        (user_id, user_id),
    )
    await _db.commit()
