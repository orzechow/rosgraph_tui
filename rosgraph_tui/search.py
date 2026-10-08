"""Fuzzy filtering of entity names, backed by rapidfuzz (C++)."""

from __future__ import annotations

from collections.abc import Sequence

from rapidfuzz import fuzz, process

DEFAULT_CUTOFF = 50.0


def fuzzy_rank(names: Sequence[str], query: str, cutoff: float = DEFAULT_CUTOFF) -> list[tuple[str, float]]:
    """Return ``(name, score)`` for names scoring strictly above ``cutoff``.

    Best match first, ties by name.  An empty query returns every name with a
    perfect score, in the given order (callers pass sorted names).  Matching
    is case-insensitive and uses ``partial_ratio`` so a short query matches
    anywhere inside a long topic name.
    """
    if not query:
        return [(name, 100.0) for name in names]
    hits = process.extract(
        query,
        names,
        scorer=fuzz.partial_ratio,
        processor=str.lower,
        score_cutoff=cutoff,
        limit=None,
    )
    ranked = [(name, score) for name, score, _index in hits if score > cutoff]
    ranked.sort(key=lambda hit: (-hit[1], hit[0]))
    return ranked


def fuzzy_filter(names: Sequence[str], query: str, cutoff: float = DEFAULT_CUTOFF) -> list[str]:
    """Like :func:`fuzzy_rank` but returns only the names."""
    return [name for name, _score in fuzzy_rank(names, query, cutoff)]
