"""Daily bonus handler — one claim per 24 hours."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ContextTypes

import database as db
from config import BONUS_VARIANTS, BONUS_COOLDOWN_HOURS, fmt_stones


async def bonus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return

    player = await db.get_or_create_player(
        user.id, user.username or "", user.first_name
    )
    now = datetime.now(timezone.utc)

    # ── Cooldown check ────────────────────────────────────────────────────────
    if player["last_bonus"]:
        try:
            last = datetime.fromisoformat(player["last_bonus"])
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            diff = now - last
            if diff < timedelta(hours=BONUS_COOLDOWN_HOURS):
                remaining      = timedelta(hours=BONUS_COOLDOWN_HOURS) - diff
                total_secs     = int(remaining.total_seconds())
                hours, rem     = divmod(total_secs, 3600)
                minutes        = rem // 60
                await update.message.reply_text(
                    f"⏳ <b>Бонус уже получен!</b>\n\n"
                    f"⏰ Следующий бонус через: <b>{hours} ч {minutes} мин</b>",
                    parse_mode="HTML",
                )
                return
        except ValueError:
            pass  # Corrupted date — allow claim

    # ── Roll bonus ────────────────────────────────────────────────────────────
    weights = [v[0] for v in BONUS_VARIANTS]
    _, coins, stones, label = random.choices(BONUS_VARIANTS, weights=weights, k=1)[0]

    new_coins  = await db.add_coins(user.id, coins)
    new_stones = await db.add_soul_stones(user.id, stones)
    await db.set_last_bonus(user.id, now.isoformat())

    text = (
        f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС</b>\n\n"
        f"{label}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"🪙 Монеты: <b>{new_coins:,}</b>\n"
        f"🟣 Камни Души: <b>{fmt_stones(new_stones)}</b>\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"⏰ Следующий бонус через: <b>24 ч 0 мин</b>"
    )
    await update.message.reply_text(text, parse_mode="HTML")
