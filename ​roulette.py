"""Roulette — герой сумма число (одна ставка = одна игра)."""
from __future__ import annotations

import random

# ── Герои рулетки и их выплата ────────────────────────────────────────────────
# Ключи: как пишет игрок (нижний регистр)
HEROES: dict[str, tuple[str, str, int]] = {
    "паук":          ("Человек-паук", "🕷",  2),  # ×2
    "человек-паук":  ("Человек-паук", "🕷",  2),  # алиас
    "тор":           ("Тор",          "⚡",  3),  # ×3
    "танос":         ("Танос",        "💀",  4),  # ×4
}

ROULETTE_POOL      = 12   # числа 1–12
ROULETTE_WIN_COUNT = 4    # сколько чисел выигрывают при прокрутке


def spin_wheel() -> list[int]:
    """Случайно выбрать ROULETTE_WIN_COUNT выигрышных чисел из 1..ROULETTE_POOL."""
    return sorted(random.sample(range(1, ROULETTE_POOL + 1), ROULETTE_WIN_COUNT))
