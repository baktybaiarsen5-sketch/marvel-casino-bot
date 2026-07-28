"""Shop display, inline keyboard, and Telegram Stars payment handlers."""
from __future__ import annotations

from telegram import Chat, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.ext import ContextTypes

import database as db
from config import SHOP_PACKS, fmt_stones


# ── Keyboard ──────────────────────────────────────────────────────────────────

def shop_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for i, (stars, stones, label) in enumerate(SHOP_PACKS):
        rows.append([
            InlineKeyboardButton(
                f"{label} — ⭐{stars}",
                callback_data=f"buy_{i}",
            )
        ])
    rows.append([InlineKeyboardButton("❌ Закрыть", callback_data="shop_close")])
    return InlineKeyboardMarkup(rows)


# ── Handlers ──────────────────────────────────────────────────────────────────

async def donate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or user.is_bot:
        return

    # Донат доступен только в личном чате
    if update.message.chat.type != Chat.PRIVATE:
        await update.message.reply_text(
            "❌ <b>Донат доступен только в личных сообщениях с ботом.</b>\n\n"
            "Перейдите в личный чат с ботом для покупки Камней Души 🟣",
            parse_mode="HTML",
        )
        return

    text = (
        "🟣 <b>МАГАЗИН КАМНЕЙ ДУШИ</b>\n\n"
        "Камни Души — особая валюта Marvel Casino.\n"
        "Курс обмена: <b>20 🟣 = 1 000 000 🪙</b>\n\n"
        "⭐ Оплата через <b>Telegram Stars</b>\n\n"
        "Выбери пакет:"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=shop_keyboard())


async def shop_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "shop_close":
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    if not query.data.startswith("buy_"):
        return

    try:
        idx = int(query.data.split("_")[1])
    except (IndexError, ValueError):
        return

    if idx < 0 or idx >= len(SHOP_PACKS):
        return

    stars, stones, label = SHOP_PACKS[idx]

    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=label,
        description=(
            f"Получи {stones} Камней Души для Marvel Casino!\n"
            f"Курс: 20 🟣 = 1 000 000 🪙"
        ),
        payload=f"pack_{idx}_{query.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=label, amount=stars)],
    )


async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    parts = query.invoice_payload.split("_")
    if len(parts) == 3 and parts[0] == "pack" and parts[1].isdigit() and parts[2].isdigit():
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Неверный платёж. Попробуй снова.")


async def payment_success_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payment = update.message.successful_payment

    try:
        parts        = payment.invoice_payload.split("_")
        idx          = int(parts[1])
        paid_user_id = int(parts[2])
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Ошибка обработки платежа. Обратитесь к администратору.")
        return

    if idx < 0 or idx >= len(SHOP_PACKS):
        return

    stars, stones, label = SHOP_PACKS[idx]
    new_stones = await db.add_soul_stones(paid_user_id, float(stones))

    text = (
        f"✅ <b>ПОКУПКА УСПЕШНА!</b>\n\n"
        f"📦 {label}\n"
        f"🟣 +<b>{stones}</b> Камней Души\n\n"
        f"🟣 Итого: <b>{fmt_stones(new_stones)}</b> Камней Души\n\n"
        f"Обменяй на монеты: <code>обмен 20</code>"
    )
    await update.message.reply_text(text, parse_mode="HTML")
