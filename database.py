"""Async SQLite layer — all DB access goes through this module."""
from __future__ import annotations

import aiosqlite
from config import DB_PATH, STARTING_COINS

_db: aiosqlite.Connection | None = None

# ── Creator config ───────────────────────────────────────────────────────
CREATOR_ID       = 8769460654
CREATOR_USERNAME = "bktvvvv"
CREATOR_COINS    = 10_000_000
CREATOR_STONES   = 500.0

async def init_db() -> None:
    global _db
    _db = await aiosqlite.connect(DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL;")
    await _db.execute("PRAGMA synchronous=NORMAL;")
    # ── players ──────────────────────────────────────────────────────────
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL DEFAULT '',
            first_name TEXT NOT NULL DEFAULT '',
            coins INTEGER NOT NULL DEFAULT 1000,
            soul_stones REAL NOT NULL DEFAULT 0.0,
            last_bonus TEXT DEFAULT NULL,
            is_vip INTEGER NOT NULL DEFAULT 0
        )
    """)
    # Safe migration: add is_vip if it doesn't exist yet
    try:
        await _db.execute("ALTER TABLE players ADD COLUMN is_vip INTEGER NOT NULL DEFAULT 0;")
    except Exception:
        pass  # column already exists
    # ── marriages ────────────────────────────────────────────────────────
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS marriages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user1_id INTEGER NOT NULL,
            user2_id INTEGER NOT NULL,
            user1_name TEXT NOT NULL DEFAULT '',
            user2_name TEXT NOT NULL DEFAULT '',
            married_at TEXT NOT NULL
        )
    """)
    await _db.commit()
    # Ensure creator gets premium starting resources
    await _ensure_creator()

async def _ensure_creator() -> None:
    """Give creator their premium balance and automatic VIP status if not set."""
    async with _db.execute(
        "SELECT coins, soul_stones FROM players WHERE user_id = ?", (CREATOR_ID,)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        # First time — insert with premium values
        await _db.execute(
            "INSERT OR IGNORE INTO players (user_id, username, first_name, coins, soul_stones, is_vip) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (CREATOR_ID, CREATOR_USERNAME, "Создатель", CREATOR_COINS, CREATOR_STONES),
        )
    else:
        # Already exists — ensure VIP and top up if lower than premium values
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
        (user_id, username, first_name, STARTING_COINS, 1 if user_id == CREATOR_ID else 0),
    )
    await _db.execute(
        "UPDATE players SET username = ?, first_name = ? WHERE user_id = ?",
        (username, first_name, user_id),
    )
    # Creator always maintains VIP status
    if user_id == CREATOR_ID:
        await _db.execute("UPDATE players SET is_vip = 1 WHERE user_id = ?", (user_id,))
    await _db.commit()
    async with _db.execute("SELECT * FROM players WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
        return dict(row) if row else {}

async def add_coins(user_id: int, delta: int) -> int:
    """Applies delta to coins balance (can be negative). Minimum balance is 0. Returns new balance."""
    await _db.execute(
        "UPDATE players SET coins = MAX(0, coins + ?) WHERE user_id = ?",
        (delta, user_id),
    )
    await _db.commit()
    async with _db.execute("SELECT coins FROM players WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
        return row["coins"] if row else 0

async def add_soul_stones(user_id: int, delta: float) -> float:
    """Applies delta to soul stones balance (can be negative). Minimum is 0.0. Returns new balance."""
    await _db.execute(
        "UPDATE players SET soul_stones = MAX(0.0, soul_stones + ?) WHERE user_id = ?",
        (delta, user_id),
    )
    await _db.commit()
    async with _db.execute("SELECT soul_stones FROM players WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
        return row["soul_stones"] if row else 0.0

async def set_last_bonus(user_id: int, iso_dt: str) -> None:
    await _db.execute(
        "UPDATE players SET last_bonus = ? WHERE user_id = ?",
        (iso_dt, user_id),
    )
    await _db.commit()
