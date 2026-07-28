"""Marriage system — предложения брака, принятие, команды."""
from __future__ import annotations

from datetime import datetime, timezone


# ── Pending proposals (in-memory) ────────────────────────────────────────────
# key: f"{proposer_id}:{target_id}"
# value: dict with proposal metadata
_pending: dict[str, dict] = {}


def make_key(proposer_id: int, target_id: int) -> str:
    return f"{proposer_id}:{target_id}"


def add_proposal(proposer_id: int, proposer_name: str,
                 target_id: int, target_name: str, chat_id: int) -> None:
    key = make_key(proposer_id, target_id)
    _pending[key] = {
        "proposer_id":   proposer_id,
        "proposer_name": proposer_name,
        "target_id":     target_id,
        "target_name":   target_name,
        "chat_id":       chat_id,
    }


def get_proposal(proposer_id: int, target_id: int) -> dict | None:
    return _pending.get(make_key(proposer_id, target_id))


def remove_proposal(proposer_id: int, target_id: int) -> None:
    _pending.pop(make_key(proposer_id, target_id), None)


def has_pending_proposal_from(proposer_id: int) -> bool:
    """Check if this user already has a pending outgoing proposal."""
    return any(v["proposer_id"] == proposer_id for v in _pending.values())


# ── Duration formatter ────────────────────────────────────────────────────────

def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} сек."
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} мин."
    hours = minutes // 60
    minutes %= 60
    if hours < 24:
        parts = f"{hours} ч."
        if minutes:
            parts += f" {minutes} мин."
        return parts
    days = hours // 24
    hours %= 24
    if days < 30:
        parts = f"{days} дн."
        if hours:
            parts += f" {hours} ч."
        return parts
    months = days // 30
    days %= 30
    if months < 12:
        parts = f"{months} мес."
        if days:
            parts += f" {days} дн."
        return parts
    years = months // 12
    months %= 12
    parts = f"{years} г."
    if months:
        parts += f" {months} мес."
    return parts


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def seconds_since(iso_dt: str) -> int:
    dt = datetime.fromisoformat(iso_dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    return max(0, int(delta.total_seconds()))
