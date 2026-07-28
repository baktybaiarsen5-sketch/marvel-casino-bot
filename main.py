"""Marvel Casino Bot — entry point and handler registration."""
from __future__ import annotations

import asyncio
import logging
import re
import time

from telegram import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

from config import BOT_TOKEN, EXCHANGE_STONES, EXCHANGE_COINS, fmt_stones
import database as db
from database import CREATOR_ID
from games import roll_event, decode_slots, EventType
from payments import (
    donate_handler,
    shop_callback_handler,
    precheckout_handler,
    payment_success_handler,
)
from bonus import bonus_handler
import roulette as rl
import marriage as mar
import interactions as iact

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

VIP_COST_STONES = 50  # стоимость VIP в Камнях Души


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cooldown — единый 15-секундный таймер на все игры, отдельно для каждого юзера
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_GAME_COOLDOWN_SEC: float = 15.0
_game_cooldowns: dict[int, float] = {}


def _remaining_cooldown(user_id: int) -> int:
    remaining = _GAME_COOLDOWN_SEC - (time.monotonic() - _game_cooldowns.get(user_id, 0.0))
    return max(0, int(remaining) + 1) if remaining > 0 else 0


def _set_cooldown(user_id: int) -> None:
    _game_cooldowns[user_id] = time.monotonic()


def _name(username: str | None, first_name: str | None) -> str:
    if username:
        return f"@{username}"
    return first_name or "Игрок"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Casino — "марвел <ставка>"
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def bet_handler(update: Update, context) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return

    secs = _remaining_cooldown(user.id)
    if secs:
        await update.message.reply_text(
            f"⏳ Подождите <b>{secs}</b> сек. перед следующей игрой!",
            parse_mode="HTML",
        )
        return

    try:
        amount = int(context.matches[0].group(1))
    except (IndexError, AttributeError, ValueError):
        return

    if amount <= 0:
        await update.message.reply_text("❌ Ставка должна быть больше нуля!")
        return

    player = await db.get_or_create_player(user.id, user.username or "", user.first_name)

    if player["coins"] < amount:
        await update.message.reply_text(
            f"❌ <b>Недостаточно монет!</b>\n\n"
            f"🪙 Ваш баланс: <b>{player['coins']:,}</b>",
            parse_mode="HTML",
        )
        return

    _set_cooldown(user.id)
    vip = bool(player.get("is_vip", 0))
    event = roll_event(vip=vip)

    if event.kind == EventType.LUCKY:
        win       = int(amount * event.value)
        profit    = win - amount
        new_coins = await db.add_coins(user.id, profit)
        text = (
            f"🌟 <b>СЧАСТЛИВЫЙ ДЕНЬ!!!</b> 🌟\n\n"
            f"✨ Невероятная удача! Все герои Marvel\n"
            f"   объединились ради тебя!\n\n"
            f"💸 Ставка: <b>{amount:,}</b>\n"
            f"🔥 Множитель: <b>×{int(event.value)}</b>\n"
            f"💰 Выигрыш: <b>+{win:,}</b>\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"🪙 Баланс: <b>{new_coins:,}</b>"
        )

    elif event.kind == EventType.VILLAIN:
        loss      = int(amount * event.value)
        profit    = -loss
        new_coins = await db.add_coins(user.id, profit)
        pct       = int(event.value * 100)
        text = (
            f"🎰 <b>MARVEL CASINO</b>\n\n"
            f"💸 Ставка: <b>{amount:,}</b>\n\n"
            f"😈 Появился злодей:\n\n"
            f"{event.emoji} <b>{event.name}</b>\n\n"
            f"💀 Забирает <b>{pct}%</b> ставки — <b>-{loss:,}</b>\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"🪙 Баланс: <b>{new_coins:,}</b>"
        )

    else:  # HERO
        win       = int(amount * event.value)
        profit    = win - amount
        new_coins = await db.add_coins(user.id, profit)
        mult      = int(event.value) if event.value == int(event.value) else event.value
        text = (
            f"🎰 <b>MARVEL CASINO</b>\n\n"
            f"💸 Ставка: <b>{amount:,}</b>\n\n"
            f"🎴 Вам выпал:\n\n"
            f"{event.emoji} <b>{event.name}</b>\n\n"
            f"🔥 Множитель <b>×{mult}</b>\n\n"
            f"💰 Вы выиграли <b>{win:,}</b> монет.\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"🪙 Баланс: <b>{new_coins:,}</b>"
        )

    await update.message.reply_text(text, parse_mode="HTML")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Jackpot — "джекпот <ставка>"  (Telegram 🎰 dice)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def jackpot_handler(update: Update, context) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return

    secs = _remaining_cooldown(user.id)
    if secs:
        await update.message.reply_text(
            f"⏳ Подождите <b>{secs}</b> сек. перед следующей игрой!",
            parse_mode="HTML",
        )
        return

    try:
        amount = int(context.matches[0].group(1))
    except (IndexError, AttributeError, ValueError):
        return

    if amount <= 0:
        await update.message.reply_text("❌ Ставка должна быть больше нуля!")
        return

    player = await db.get_or_create_player(user.id, user.username or "", user.first_name)

    if player["coins"] < amount:
        await update.message.reply_text(
            f"❌ <b>Недостаточно монет!</b>\n\n"
            f"🪙 Ваш баланс: <b>{player['coins']:,}</b>",
            parse_mode="HTML",
        )
        return

    _set_cooldown(user.id)

    dice_msg = await update.message.reply_dice(emoji="🎰")
    await asyncio.sleep(3)

    value      = dice_msg.dice.value
    slots_line = decode_slots(value)  # str или None

    if value == 64:   # 7️⃣7️⃣7️⃣
        win       = amount * 7
        profit    = win - amount
        new_coins = await db.add_coins(user.id, profit)
        text = (
            f"🎰 <b>ДЖЕКПОТ — 777!</b> 🎉\n\n"
            f"[ {slots_line} ]\n\n"
            f"🎉 Джекпот выигран!\n"
            f"💸 Ставка: <b>{amount:,}</b>\n"
            f"🔥 Множитель: <b>×7</b>\n"
            f"💰 Выигрыш: <b>+{win:,}</b> 🪙\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"🪙 Баланс: <b>{new_coins:,}</b>"
        )

    elif value == 1:  # 🍋🍋🍋
        win       = amount * 4
        profit    = win - amount
        new_coins = await db.add_coins(user.id, profit)
        text = (
            f"🎰 <b>ТРИ ЛИМОНА!</b> 🍋\n\n"
            f"[ {slots_line} ]\n\n"
            f"💸 Ставка: <b>{amount:,}</b>\n"
            f"🔥 Множитель: <b>×4</b>\n"
            f"💰 Выигрыш: <b>+{win:,}</b> 🪙\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"🪙 Баланс: <b>{new_coins:,}</b>"
        )

    else:
        new_coins = await db.add_coins(user.id, -amount)
        text = (
            f"🎰 <b>ДЖЕКПОТ</b>\n\n"
            f"❌ Не повезло!\n"
            f"Ставка потеряна: <b>{amount:,}</b> 🪙\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"🪙 Баланс: <b>{new_coins:,}</b>"
        )

    await update.message.reply_text(text, parse_mode="HTML")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Roulette — "рулетка" → инструкция; "герой сумма число" → одна ставка
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_ROULETTE_INFO = (
    "🎡 <b>РУЛЕТКА</b>\n\n"
    "Выберите героя:\n\n"
    "🕷 Человек-паук — выплата <b>×2</b>\n"
    "⚡ Тор — выплата <b>×3</b>\n"
    "💀 Танос — выплата <b>×4</b>\n\n"
    "Затем сделайте ставку в формате:\n\n"
    "<code>герой сумма число</code>\n\n"
    "Примеры:\n"
    "<code>танос 1000 7</code>\n"
    "<code>тор 5000 12</code>\n"
    "<code>человек-паук 3000 4</code>\n\n"
    "Число должно быть от <b>1</b> до <b>12</b>.\n"
    "Из 12 чисел выбираются 4 победных 🎯\n"
    "При совпадении — получите ставку × множитель!"
)


async def roulette_info_handler(update: Update, context) -> None:
    await update.message.reply_text(_ROULETTE_INFO, parse_mode="HTML")


async def roulette_bet_handler(update: Update, context) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return

    try:
        hero_raw = context.matches[0].group(1).lower()
        amount   = int(context.matches[0].group(2))
        number   = int(context.matches[0].group(3))
    except (IndexError, AttributeError, ValueError):
        return

    # Нормализуем "человек-паук" → "паук" для HEROES lookup
    hero_key = "паук" if hero_raw == "человек-паук" else hero_raw

    if hero_key not in rl.HEROES:
        return

    if number < 1 or number > rl.ROULETTE_POOL:
        await update.message.reply_text(
            f"❌ Число должно быть от 1 до {rl.ROULETTE_POOL}!"
        )
        return

    if amount <= 0:
        await update.message.reply_text("❌ Ставка должна быть больше нуля!")
        return

    secs = _remaining_cooldown(user.id)
    if secs:
        await update.message.reply_text(
            f"⏳ Подождите <b>{secs}</b> сек. перед следующей игрой!",
            parse_mode="HTML",
        )
        return

    hero_name, hero_emoji, hero_mult = rl.HEROES[hero_key]

    player = await db.get_or_create_player(user.id, user.username or "", user.first_name)
    if player["coins"] < amount:
        await update.message.reply_text(
            f"❌ <b>Недостаточно монет!</b>\n"
            f"🪙 Баланс: <b>{player['coins']:,}</b>",
            parse_mode="HTML",
        )
        return

    # Списываем ставку и фиксируем кулдаун
    await db.add_coins(user.id, -amount)
    _set_cooldown(user.id)

    await update.message.reply_text(
        f"🎡 <b>Рулетка запускается...</b>\n"
        f"{hero_emoji} <b>{hero_name}</b> — число <b>{number}</b> — ставка <b>{amount:,}</b> 🪙\n\n"
        f"⏳ Ожидайте 5 секунд...",
        parse_mode="HTML",
    )

    await asyncio.sleep(5)

    winning_numbers = rl.spin_wheel()
    won = number in winning_numbers

    if won:
        payout    = amount * hero_mult
        profit    = payout - amount
        new_coins = await db.add_coins(user.id, payout)
        result = (
            f"🎡 <b>РЕЗУЛЬТАТ РУЛЕТКИ</b>\n\n"
            f"{hero_emoji} <b>{hero_name}</b> (×{hero_mult})\n\n"
            f"🎯 Выигрышные числа: <b>{', '.join(str(n) for n in winning_numbers)}</b>\n\n"
            f"✅ Ваше число <b>{number}</b> — победило!\n\n"
            f"💰 Выплата: <b>+{payout:,}</b> 🪙\n"
            f"📈 Чистый выигрыш: <b>+{profit:,}</b> 🪙\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"🪙 Баланс: <b>{new_coins:,}</b>"
        )
    else:
        new_coins = (await db.get_or_create_player(user.id, user.username or "", user.first_name))["coins"]
        result = (
            f"🎡 <b>РЕЗУЛЬТАТ РУЛЕТКИ</b>\n\n"
            f"{hero_emoji} <b>{hero_name}</b> (×{hero_mult})\n\n"
            f"🎯 Выигрышные числа: <b>{', '.join(str(n) for n in winning_numbers)}</b>\n\n"
            f"❌ Ваше число <b>{number}</b> — не совпало.\n\n"
            f"💸 Потеряно: <b>{amount:,}</b> 🪙\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"🪙 Баланс: <b>{new_coins:,}</b>"
        )

    await context.bot.send_message(
        chat_id=update.message.chat_id, text=result, parse_mode="HTML"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VIP — "вип"
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def vip_handler(update: Update, context) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return

    player = await db.get_or_create_player(user.id, user.username or "", user.first_name)

    if player.get("is_vip"):
        await update.message.reply_text(
            "⭐ <b>Вы уже являетесь VIP-игроком!</b>\n\n"
            "🎯 Ваш шанс выигрыша в марвел повышен.",
            parse_mode="HTML",
        )
        return

    if player["soul_stones"] < VIP_COST_STONES:
        await update.message.reply_text(
            f"❌ <b>Недостаточно Камней Души!</b>\n\n"
            f"Стоимость VIP: <b>{VIP_COST_STONES} 🟣</b>\n"
            f"У вас: <b>{fmt_stones(player['soul_stones'])} 🟣</b>",
            parse_mode="HTML",
        )
        return

    await db.add_soul_stones(user.id, -float(VIP_COST_STONES))
    await db.set_vip(user.id, 1)

    player_after = await db.get_or_create_player(user.id, user.username or "", user.first_name)
    await update.message.reply_text(
        f"⭐ <b>VIP активирован!</b>\n\n"
        f"🟣 Списано: <b>{VIP_COST_STONES} Камней Души</b>\n\n"
        f"🎯 Теперь ваш шанс выигрыша в марвел выше!\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"🟣 Камни Души: <b>{fmt_stones(player_after['soul_stones'])}</b>",
        parse_mode="HTML",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Transfer — "+<сумма>" (ответ) или "+<сумма> @username" (только в группах)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def transfer_reply_handler(update: Update, context) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return
    if update.message.chat.type == Chat.PRIVATE:
        return

    reply = update.message.reply_to_message
    if reply is None or reply.from_user is None or reply.from_user.is_bot:
        return

    recipient_tg = reply.from_user
    if recipient_tg.id == user.id:
        await update.message.reply_text("❌ Нельзя переводить монеты самому себе.")
        return

    try:
        amount = int(context.matches[0].group(1))
    except (IndexError, AttributeError, ValueError):
        return

    if amount <= 0:
        await update.message.reply_text("❌ Сумма перевода должна быть больше нуля.")
        return

    sender = await db.get_or_create_player(user.id, user.username or "", user.first_name)

    if sender["coins"] < amount:
        await update.message.reply_text(
            f"❌ <b>Недостаточно монет!</b>\n🪙 Баланс: <b>{sender['coins']:,}</b>",
            parse_mode="HTML",
        )
        return

    await db.get_or_create_player(
        recipient_tg.id, recipient_tg.username or "", recipient_tg.first_name,
    )
    await db.add_coins(user.id, -amount)
    await db.add_coins(recipient_tg.id, amount)

    s_name = _name(user.username, user.first_name)
    r_name = _name(recipient_tg.username, recipient_tg.first_name)

    await update.message.reply_text(
        f"💸 {s_name} передал(а) {r_name} <b>{amount:,}</b> 🪙 монет Marvel!",
        parse_mode="HTML",
    )


async def transfer_username_handler(update: Update, context) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return
    if update.message.chat.type == Chat.PRIVATE:
        return

    try:
        amount   = int(context.matches[0].group(1))
        username = context.matches[0].group(2)
    except (IndexError, AttributeError, ValueError):
        return

    if amount <= 0:
        await update.message.reply_text("❌ Сумма перевода должна быть больше нуля.")
        return

    if username.lower() in (user.username or "").lower():
        await update.message.reply_text("❌ Нельзя переводить монеты самому себе.")
        return

    recipient = await db.get_player_by_username(username)
    if recipient is None:
        await update.message.reply_text(
            f"❌ Игрок <b>@{username}</b> не найден.\n"
            f"Он должен хотя бы раз написать боту.",
            parse_mode="HTML",
        )
        return

    if recipient["user_id"] == user.id:
        await update.message.reply_text("❌ Нельзя переводить монеты самому себе.")
        return

    sender = await db.get_or_create_player(user.id, user.username or "", user.first_name)

    if sender["coins"] < amount:
        await update.message.reply_text(
            f"❌ <b>Недостаточно монет!</b>\n🪙 Баланс: <b>{sender['coins']:,}</b>",
            parse_mode="HTML",
        )
        return

    await db.add_coins(user.id, -amount)
    await db.add_coins(recipient["user_id"], amount)

    s_name = _name(user.username, user.first_name)
    r_name = _name(recipient["username"], recipient["first_name"])

    await update.message.reply_text(
        f"💸 {s_name} передал(а) {r_name} <b>{amount:,}</b> 🪙 монет Marvel!",
        parse_mode="HTML",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Balance — "б"
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def balance_handler(update: Update, context) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return

    player = await db.get_or_create_player(user.id, user.username or "", user.first_name)
    vip_line = "\n⭐ <b>VIP-статус активен</b>" if player.get("is_vip") else ""
    text = (
        f"💰 <b>Ваш баланс</b>{vip_line}\n\n"
        f"🪙 Монеты: <b>{player['coins']:,}</b>\n\n"
        f"🟣 Камни Души: <b>{fmt_stones(player['soul_stones'])}</b>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Top 30 — "топ"
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_MEDALS: dict[int, str] = {1: "🥇", 2: "🥈", 3: "🥉"}

async def top_handler(update: Update, context) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return

    players = await db.get_top_players(30)
    if not players:
        await update.message.reply_text(
            "🏜️ Пока нет игроков!\nНапиши <code>марвел 100</code>, чтобы начать.",
            parse_mode="HTML",
        )
        return

    lines = ["🏆 <b>ТОП-30</b>\n"]
    for i, p in enumerate(players, 1):
        badge = _MEDALS.get(i, f"{i}.")
        name  = f"@{p['username']}" if p["username"] else (p["first_name"] or f"Игрок {p['user_id']}")
        vip   = " ⭐" if p.get("is_vip") else ""
        lines.append(f"{badge} {name[:30]}{vip} — <b>{p['coins']:,}</b>")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Exchange — "обмен <количество>"
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def exchange_handler(update: Update, context) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return

    try:
        amount = int(context.matches[0].group(1))
    except (IndexError, AttributeError, ValueError):
        await update.message.reply_text(
            "❌ Использование: <code>обмен &lt;количество камней&gt;</code>",
            parse_mode="HTML",
        )
        return

    if amount <= 0:
        await update.message.reply_text("❌ Количество должно быть больше нуля.")
        return

    player = await db.get_or_create_player(user.id, user.username or "", user.first_name)

    if player["soul_stones"] < amount:
        await update.message.reply_text(
            f"❌ <b>Недостаточно Камней Души!</b>\n\n"
            f"🟣 У тебя: <b>{fmt_stones(player['soul_stones'])}</b>",
            parse_mode="HTML",
        )
        return

    coins_gained = int((amount / EXCHANGE_STONES) * EXCHANGE_COINS)
    new_stones   = await db.add_soul_stones(user.id, -float(amount))
    new_coins    = await db.add_coins(user.id, coins_gained)

    text = (
        f"💱 <b>ОБМЕН ВЫПОЛНЕН</b>\n\n"
        f"🟣 -{amount} Камней Души\n"
        f"🪙 +{coins_gained:,} монет\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"🪙 Монеты: <b>{new_coins:,}</b>\n"
        f"🟣 Камни Души: <b>{fmt_stones(new_stones)}</b>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Marriage — брак / мой брак / браки
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def propose_marriage_handler(update: Update, context) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return

    if update.message.chat.type == Chat.PRIVATE:
        await update.message.reply_text("💍 Браки заключаются только в группах!")
        return

    reply = update.message.reply_to_message
    if reply is None or reply.from_user is None:
        await update.message.reply_text("❌ Ответьте на сообщение пользователя.")
        return

    target = reply.from_user
    if target.is_bot:
        await update.message.reply_text("❌ Нельзя предложить брак боту.")
        return

    if target.id == user.id:
        await update.message.reply_text("❌ Нельзя предложить брак самому себе.")
        return

    # Проверяем, нет ли уже брака у инициатора
    if await db.get_marriage(user.id):
        await update.message.reply_text("❌ Вы уже состоите в браке!")
        return

    # Проверяем, нет ли уже брака у цели
    if await db.get_marriage(target.id):
        await update.message.reply_text(
            f"❌ {_name(target.username, target.first_name)} уже состоит в браке!"
        )
        return

    # Проверяем, нет ли уже активного предложения от этого пользователя
    if mar.has_pending_proposal_from(user.id):
        await update.message.reply_text(
            "⏳ У вас уже есть активное предложение брака.\n"
            "Дождитесь ответа!"
        )
        return

    proposer_name = _name(user.username, user.first_name)
    target_name   = _name(target.username, target.first_name)

    mar.add_proposal(
        proposer_id=user.id, proposer_name=proposer_name,
        target_id=target.id, target_name=target_name,
        chat_id=update.message.chat_id,
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Принять",    callback_data=f"marry_yes:{user.id}:{target.id}"),
            InlineKeyboardButton("❌ Отказаться", callback_data=f"marry_no:{user.id}:{target.id}"),
        ]
    ])

    await update.message.reply_text(
        f"💍 {proposer_name} предлагает {target_name} вступить в брак!",
        reply_markup=keyboard,
    )


async def marriage_callback_handler(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data  # "marry_yes:uid1:uid2" or "marry_no:uid1:uid2"
    parts = data.split(":")
    if len(parts) != 3:
        return

    action, proposer_id_s, target_id_s = parts
    proposer_id = int(proposer_id_s)
    target_id   = int(target_id_s)

    responder = query.from_user
    if responder.id != target_id:
        await query.answer("Это предложение не для вас.", show_alert=True)
        return

    proposal = mar.get_proposal(proposer_id, target_id)
    if proposal is None:
        await query.edit_message_text("⌛ Предложение уже истекло или было отозвано.")
        return

    mar.remove_proposal(proposer_id, target_id)

    if action == "marry_no":
        await query.edit_message_text("❌ Предложение брака отклонено.")
        return

    # Принято — проверяем снова на браки (могли успеть пока ждали ответа)
    if await db.get_marriage(proposer_id):
        await query.edit_message_text("❌ Инициатор уже состоит в браке.")
        return
    if await db.get_marriage(target_id):
        await query.edit_message_text("❌ Вы уже состоите в браке.")
        return

    now = mar.now_iso()
    await db.create_marriage(
        chat_id=proposal["chat_id"],
        u1_id=proposer_id,   u1_name=proposal["proposer_name"],
        u2_id=target_id,     u2_name=proposal["target_name"],
        married_at=now,
    )

    await query.edit_message_text(
        f"💖 <b>Новый брак!</b>\n\n"
        f"{proposal['proposer_name']} ❤️ {proposal['target_name']}\n\n"
        f"Поздравляем с заключением брака! 🎉",
        parse_mode="HTML",
    )


async def my_marriage_handler(update: Update, context) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return

    m = await db.get_marriage(user.id)
    if m is None:
        await update.message.reply_text("💔 Вы пока не состоите в браке.")
        return

    secs = mar.seconds_since(m["married_at"])
    dur  = mar.format_duration(secs)

    await update.message.reply_text(
        f"💍 <b>Ваш брак</b>\n\n"
        f"❤️ {m['user1_name']} × {m['user2_name']}\n\n"
        f"🕒 Вместе уже:\n<b>{dur}</b>",
        parse_mode="HTML",
    )


async def all_marriages_handler(update: Update, context) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return

    if update.message.chat.type == Chat.PRIVATE:
        await update.message.reply_text("💍 Команда работает только в группах.")
        return

    marriages = await db.get_chat_marriages(update.message.chat_id)
    if not marriages:
        await update.message.reply_text("💔 В этом чате пока нет браков.")
        return

    lines = ["💍 <b>Браки этого чата</b>\n"]
    for i, m in enumerate(marriages, 1):
        secs = mar.seconds_since(m["married_at"])
        dur  = mar.format_duration(secs)
        lines.append(f"{i}. ❤️ {m['user1_name']} × {m['user2_name']}\nВместе: {dur}\n")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Interactions — обнять / поцеловать / ударить / …
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def interaction_handler(update: Update, context) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return

    try:
        action_word = context.matches[0].group(1).lower()
    except (IndexError, AttributeError):
        return

    reply = update.message.reply_to_message
    if reply is None or reply.from_user is None:
        await update.message.reply_text("❌ Ответьте на сообщение пользователя.")
        return

    target = reply.from_user
    if target.is_bot:
        await update.message.reply_text("❌ Нельзя применить это к боту.")
        return

    if target.id == user.id:
        await update.message.reply_text("❌ Нельзя применить это к самому себе.")
        return

    action_data = iact.ACTIONS.get(action_word)
    if action_data is None:
        return

    emoji, template = action_data
    a_name = _name(user.username, user.first_name)
    b_name = _name(target.username, target.first_name)
    text   = f"{emoji} " + template.format(a=a_name, b=b_name)

    await update.message.reply_text(text)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /start — короткое приветствие
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_START = (
    "🎰 <b>Добро пожаловать в Marvel Casino!</b>\n\n"
    "Испытай удачу вместе с героями Marvel.\n"
    "Ставь монеты — встречай героев и злодеев!\n\n"
    "🪙 Стартовый баланс: <b>1 000 монет</b>\n\n"
    "📖 Все команды: /help"
)

async def start_handler(update: Update, context) -> None:
    user = update.effective_user
    if user:
        await db.get_or_create_player(user.id, user.username or "", user.first_name)
    await update.message.reply_text(_START, parse_mode="HTML")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /help — полное меню команд
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_HELP = (
    "🎰 <b>MARVEL CASINO — КОМАНДЫ</b>\n\n"
    "━━━━━━━━━━━━━━\n"
    "🎲 <code>марвел &lt;ставка&gt;</code>\n"
    "    Ставка на героя Marvel (кулдаун 15 сек)\n\n"
    "🎰 <code>джекпот &lt;ставка&gt;</code>\n"
    "    Слот-машина: 777=×7  🍋🍋🍋=×4\n\n"
    "🎡 <code>рулетка</code> — инструкция\n"
    "    <code>герой сумма число</code> — ставка (1–12)\n"
    "    🕷 паук ×2  |  ⚡ тор ×3  |  💀 танос ×4\n\n"
    "💸 <b>Перевод монет</b> (только в группах):\n"
    "    <code>+&lt;сумма&gt;</code> — ответом на сообщение\n"
    "    <code>+&lt;сумма&gt; @username</code> — по имени\n\n"
    "━━━━━━━━━━━━━━\n"
    "💰 <code>б</code> — баланс\n"
    "🏆 <code>топ</code> — ТОП-30 игроков\n"
    "🎁 <code>бонус</code> — ежедневный бонус (24 ч)\n"
    "🟣 <code>донат</code> — купить Камни Души за ⭐ (только в лс)\n"
    "💱 <code>обмен &lt;кол-во&gt;</code> — 🟣 → 🪙\n"
    "⭐ <code>вип</code> — купить VIP за 50 🟣 (повышает шанс в марвел)\n\n"
    "━━━━━━━━━━━━━━\n"
    "💍 <b>Браки</b> (только в группах):\n"
    "    <code>брак</code> — предложить брак (ответом на сообщение)\n"
    "    <code>мой брак</code> — информация о вашем браке\n"
    "    <code>браки</code> — все браки чата\n\n"
    "━━━━━━━━━━━━━━\n"
    "🎭 <b>Взаимодействия</b> (ответом на сообщение):\n"
    "обнять · поцеловать · ударить · шлепнуть · убить\n"
    "пожать руку · дать пять · подарить · угостить\n"
    "рассмешить · защитить · пнуть · усыпить\n"
    "короновать · поздравить · отпраздновать\n\n"
    "━━━━━━━━━━━━━━\n"
    "💡 Курс: <b>20 🟣 = 1 000 000 🪙</b>\n"
    "🎯 Стартовый баланс: <b>1 000 монет</b>\n\n"
    "🌟 <i>Герои дают ×1.5/×3/×5/×10. Злодеи забирают\n"
    "50% или 100% ставки. Шанс 50/50. VIP — больше побед!</i>"
)

async def help_handler(update: Update, context) -> None:
    await update.message.reply_text(_HELP, parse_mode="HTML")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# App lifecycle
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _post_init(app: Application) -> None:
    await db.init_db()
    logger.info("✅ Database initialised at %s", db.DB_PATH)


async def _post_shutdown(app: Application) -> None:
    await db.close_db()
    logger.info("🔒 Database closed")


async def _error_handler(update: object, context) -> None:
    logger.error("Unhandled exception: %s", context.error, exc_info=context.error)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Entry point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set!")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    # /start  /help
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))

    # марвел <ставка>
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(r"^марвел\s+(\d+)", re.IGNORECASE)),
        bet_handler,
    ))

    # джекпот <ставка>
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(r"^джекпот\s+(\d+)", re.IGNORECASE)),
        jackpot_handler,
    ))

    # рулетка — инструкция
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(r"^рулетка$", re.IGNORECASE)),
        roulette_info_handler,
    ))

    # герой сумма число — ставка в рулетке
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(
            r"^(паук|тор|танос|человек-паук)\s+(\d+)\s+(\d+)$",
            re.IGNORECASE,
        )),
        roulette_bet_handler,
    ))

    # вип
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(r"^вип$", re.IGNORECASE)),
        vip_handler,
    ))

    # брак (предложение — только ответом)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(r"^брак$", re.IGNORECASE)),
        propose_marriage_handler,
    ))

    # мой брак
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(r"^мой брак$", re.IGNORECASE)),
        my_marriage_handler,
    ))

    # браки
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(r"^браки$", re.IGNORECASE)),
        all_marriages_handler,
    ))

    # Взаимодействия (обнять / поцеловать / …)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(iact.PATTERN, re.IGNORECASE)),
        interaction_handler,
    ))

    # Перевод ответом: +1000
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(r"^\+(\d+)\s*$")),
        transfer_reply_handler,
    ))

    # Перевод по username: +1000 @user
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(r"^\+(\d+)\s+@(\w+)\s*$")),
        transfer_username_handler,
    ))

    # б
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(r"^б$", re.IGNORECASE)),
        balance_handler,
    ))

    # топ
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(r"^топ$", re.IGNORECASE)),
        top_handler,
    ))

    # бонус
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(r"^бонус$", re.IGNORECASE)),
        bonus_handler,
    ))

    # донат
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(r"^донат$", re.IGNORECASE)),
        donate_handler,
    ))

    # обмен <количество>
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND
        & filters.Regex(re.compile(r"^обмен\s+(\d+)", re.IGNORECASE)),
        exchange_handler,
    ))

    # Callback: брак accept/reject
    app.add_handler(CallbackQueryHandler(
        marriage_callback_handler,
        pattern=re.compile(r"^marry_(yes|no):\d+:\d+$"),
    ))

    # Shop inline-keyboard callbacks
    app.add_handler(CallbackQueryHandler(
        shop_callback_handler,
        pattern=re.compile(r"^(buy_\d+|shop_close)$"),
    ))

    # Telegram Stars
    app.add_handler(PreCheckoutQueryHandler(precheckout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment_success_handler))

    app.add_error_handler(_error_handler)

    logger.info("🎰 Marvel Casino Bot starting…")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
