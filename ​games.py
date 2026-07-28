"""Marvel heroes, villains, slot machine, and casino roll logic."""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum


class EventType(Enum):
    HERO    = "hero"
    VILLAIN = "villain"
    LUCKY   = "lucky"


@dataclass(frozen=True)
class GameEvent:
    kind:  EventType
    name:  str
    emoji: str
    value: float
    # heroes  → win multiplier (e.g. 3.0 → получить ставку × 3)
    # villains → loss fraction  (e.g. 0.50 → потерять 50 % ставки, 1.0 → потерять 100 %)
    # lucky   → win multiplier  (×50)


# ── Heroes — 4 множителя: ×1.5 / ×3 / ×5 / ×10 ───────────────────────────────
HEROES: list[GameEvent] = [
    # ×1.5 — вес 12 каждый
    GameEvent(EventType.HERO, "Соколиный глаз",   "🏹",  1.5),
    GameEvent(EventType.HERO, "Человек-паук",     "🕷",  1.5),
    GameEvent(EventType.HERO, "Чёрная вдова",     "🖤",  1.5),
    GameEvent(EventType.HERO, "Сокол",            "🪽",  1.5),
    # ×3 — вес 8 каждый
    GameEvent(EventType.HERO, "Человек-муравей",  "🐜",  3.0),
    GameEvent(EventType.HERO, "Капитан Америка",  "🛡",  3.0),
    GameEvent(EventType.HERO, "Зимний солдат",    "❄️",  3.0),
    GameEvent(EventType.HERO, "Тор",              "⚡",  3.0),
    # ×5 — вес 4 каждый
    GameEvent(EventType.HERO, "Ракета",           "🦝",  5.0),
    GameEvent(EventType.HERO, "Грут",             "🌳",  5.0),
    GameEvent(EventType.HERO, "Капитан Марвел",   "🦸",  5.0),
    GameEvent(EventType.HERO, "Доктор Стрэндж",   "🧙",  5.0),
    # ×10 — вес 1 каждый
    GameEvent(EventType.HERO, "Халк",             "💚", 10.0),
    GameEvent(EventType.HERO, "Железный человек", "🔴", 10.0),
    GameEvent(EventType.HERO, "Алая Ведьма",      "🔮", 10.0),
    GameEvent(EventType.HERO, "Танос",            "💜", 10.0),
]
_HERO_WEIGHTS: list[float] = [
    12.0, 12.0, 12.0, 12.0,  # ×1.5
     8.0,  8.0,  8.0,  8.0,  # ×3
     4.0,  4.0,  4.0,  4.0,  # ×5
     1.0,  1.0,  1.0,  1.0,  # ×10
]


# ── Villains — только 50 % или 100 % потери ───────────────────────────────────
VILLAINS: list[GameEvent] = [
    GameEvent(EventType.VILLAIN, "Таскмастер",    "🎭", 0.50),
    GameEvent(EventType.VILLAIN, "Красный Череп", "💀", 0.50),
    GameEvent(EventType.VILLAIN, "Альтрон",       "⚙️", 0.50),
    GameEvent(EventType.VILLAIN, "Абомин",        "👹", 1.00),
    GameEvent(EventType.VILLAIN, "Локи",          "🐍", 1.00),
]
_VILLAIN_WEIGHTS: list[float] = [7.0, 7.0, 7.0, 4.5, 4.5]


# ── Lucky Day — шанс 0.001 %, выигрыш ×50 ────────────────────────────────────
LUCKY_DAY = GameEvent(EventType.LUCKY, "Счастливый день", "🌟", 50.0)


def roll_event(vip: bool = False) -> GameEvent:
    """
    Бросок для команды «марвел»:
       0.001 %  → Счастливый день (×50)
    Обычный: ~50 % герой / ~50 % злодей
    VIP:     ~65 % герой / ~35 % злодей
    """
    r = random.random()
    if r < 0.00001:           # 0.001 % Lucky Day
        return LUCKY_DAY
    hero_threshold = 0.65001 if vip else 0.50001
    if r < hero_threshold:
        return random.choices(HEROES, weights=_HERO_WEIGHTS, k=1)[0]
    return random.choices(VILLAINS, weights=_VILLAIN_WEIGHTS, k=1)[0]


# ── Slot machine — для команды «джекпот» (Telegram send_dice 🎰) ──────────────
# Telegram dice 🎰: значения 1–64.
# Точно известные комбинации:
#   value = 1  → 🍋🍋🍋
#   value = 64 → 7️⃣7️⃣7️⃣
# Для остальных значений символы не отображаются, чтобы не показывать
# комбинации, которые не соответствуют анимации Telegram.

def decode_slots(value: int) -> str | None:
    """
    Вернуть строку с символами барабанов для известных комбинаций Telegram 🎰,
    или None для всех остальных значений.
    """
    if value == 64:
        return "7️⃣  7️⃣  7️⃣"
    if value == 1:
        return "🍋  🍋  🍋"
    return None
