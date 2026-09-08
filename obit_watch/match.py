"""Name-variant matching and excerpt extraction."""

from __future__ import annotations

import re
from typing import List, Optional, Sequence

CONTEXT_WORDS = (
    "obituary",
    "obituaries",
    "funeral",
    "died",
    "death",
    "passing",
    "passed",
    "services",
    "memorial",
    "cremation",
    "interment",
    "survived",
    "beloved",
)


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _name_pattern(name: str) -> re.Pattern:
    """Case-insensitive pattern allowing flexible whitespace between tokens."""
    parts = [re.escape(p) for p in name.split() if p]
    if not parts:
        return re.compile(r"(?!)")  # never matches
    return re.compile(r"\b" + r"\s+".join(parts) + r"\b", re.IGNORECASE)


def find_match(
    text: str,
    names: Sequence[str],
    *,
    prefer_context: bool = True,
) -> Optional[str]:
    """
    Return a ≤200-char excerpt if any name variant appears in text.
    Prefer matches near CONTEXT_WORDS when prefer_context is True.
    """
    if not text or not names:
        return None

    flat = normalize_ws(text)
    lower = flat.lower()

    candidates: List[tuple] = []  # (score, start, end, name)

    for name in names:
        name = name.strip()
        if not name:
            continue
        pat = _name_pattern(name)
        for m in pat.finditer(flat):
            start, end = m.start(), m.end()
            win_start = max(0, start - 80)
            win_end = min(len(flat), end + 80)
            window = lower[win_start:win_end]
            score = 0
            for w in CONTEXT_WORDS:
                if w in window:
                    score += 2
            score += min(3, len(name.split()))
            candidates.append((score, start, end, name))

    if not candidates:
        return None

    if prefer_context:
        candidates.sort(key=lambda c: (-c[0], c[1]))
    else:
        candidates.sort(key=lambda c: c[1])

    _, start, end, _ = candidates[0]
    excerpt_radius = 90
    ex_start = max(0, start - excerpt_radius)
    ex_end = min(len(flat), end + excerpt_radius)
    excerpt = flat[ex_start:ex_end]
    if ex_start > 0:
        excerpt = "…" + excerpt
    if ex_end < len(flat):
        excerpt = excerpt + "…"
    excerpt = normalize_ws(excerpt)
    if len(excerpt) > 200:
        excerpt = excerpt[:197] + "…"
    return excerpt


def plausible_hit(text: str, names: Sequence[str]) -> Optional[str]:
    """Public helper: return excerpt or None."""
    return find_match(text, names, prefer_context=True)
