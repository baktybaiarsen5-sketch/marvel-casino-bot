import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# ── Database ─────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH: str = str(DATA_DIR / "casino.db")

# ── Economy ───────────────────────────────────────────────────────────────────
STARTING_COINS: int = 1_000

# Exchange rate: EXCHANGE_STONES soul stones → EXCHANGE_COINS coins
EXCHANGE_STONES: int = 20
EXCHANGE_COINS: int  = 1_000_000

# ── Bonus ─────────────────────────────────────────────────────────────────────
BONUS_COOLDOWN_HOURS: int = 24

# (weight, coins, soul_stones, display_label)
BONUS_VARIANTS: list[tuple[int, int, float, str]] = [
    (45, 10_000,     0.05, "💰 +10 000 монет\n🟣 +0.05 Камня Души"),
    (35, 15_000,     0.0,  "💰 +15 000 монет"),
    (15, 25_000,     0.10, "💰 +25 000 монет\n🟣 +0.10 Камня Души"),
    (4,  500_000,    0.20, "🍀 <b>СЧАСТЛИВЫЙ ДЕНЬ!</b>\n\n💰 +500 000 монет\n🟣 +0.20 Камня Души"),
    (1,  1_000_000,  1.0,  "💥 <b>ДЖЕКПОТ!</b>\n\n💰 +1 000 000 монет\n🟣 +1 Камень Души"),
]

# ── Shop packs: (stars, soul_stones, label) ───────────────────────────────────
SHOP_PACKS: list[tuple[int, int, str]] = [
    (25,  20,  "🟣 20 Камней Души"),
    (50,  40,  "🟣 40 Камней Души"),
    (70,  60,  "🟣 60 Камней Души"),
    (90,  80,  "🟣 80 Камней Души"),
    (100, 100, "🟣 100 Камней Души"),
]


def fmt_stones(v: float) -> str:
    """Format soul-stone value: whole numbers as int, fractions with up to 2 dp."""
    if v == int(v):
        return str(int(v))
    return f"{v:.2f}".rstrip("0")
