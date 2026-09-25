"""Fuzzy filtering of entity names, backed by rapidfuzz (C++)."""

from __future__ import annotations

from collections.abc import Sequence

from rapidfuzz import fuzz, process

DEFAULT_CUTOFF = 50.0


def fuzzy_filter(names: Sequence[str], query: str, cutoff: float = DEFAULT_CUTOFF) -> list[str]:
    """Return the names matching ``query``, best match first, ties by name.

    An empty query returns ``names`` unchanged (they are expected to be sorted
    already).  Matching is case-insensitive and uses ``partial_ratio`` so a
    short query matches anywhere inside a long topic name.
    """
    if not query:
        return list(names)
    hits = process.extract(
        query,
        names,
        scorer=fuzz.partial_ratio,
        processor=str.lower,
        score_cutoff=cutoff,
        limit=None,
    )
    hits.sort(key=lambda hit: (-hit[1], hit[0]))
    return [name for name, _score, _index in hits]
