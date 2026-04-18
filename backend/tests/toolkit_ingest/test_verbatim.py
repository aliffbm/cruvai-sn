"""Verbatim-content check — enforces the 15-word rule from the rewrite workflow.

For every cruvai-authored version that has `derived_from_version_id` set, no
contiguous 15-word span from the original may appear verbatim in the rewrite.

The check function here is standalone so it can be invoked from CI without
a DB — the calling code feeds (original, rewrite) pairs loaded via SQLAlchemy.
"""

from __future__ import annotations

import re


_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def longest_verbatim_span(original: str, rewrite: str) -> int:
    """Return the length (in words) of the longest contiguous verbatim span
    from `original` that appears in `rewrite`. Case-insensitive, ignoring
    punctuation/whitespace differences.
    """

    o = [w.lower() for w in _WORD_RE.findall(original)]
    r = [w.lower() for w in _WORD_RE.findall(rewrite)]
    if not o or not r:
        return 0
    # Build set of shingles of the rewrite for O(n*w) check
    max_found = 0
    r_len = len(r)
    # Sliding window: try each position in original, grow while it matches any position in rewrite
    # For efficiency, index rewrite positions by starting word
    index: dict[str, list[int]] = {}
    for j, w in enumerate(r):
        index.setdefault(w, []).append(j)
    for i, w in enumerate(o):
        for j in index.get(w, []):
            k = 0
            while i + k < len(o) and j + k < r_len and o[i + k] == r[j + k]:
                k += 1
            if k > max_found:
                max_found = k
    return max_found


def assert_verbatim_ok(original: str, rewrite: str, *, max_words: int = 14) -> None:
    """Raise AssertionError if any span > max_words is copied verbatim."""
    span = longest_verbatim_span(original, rewrite)
    if span > max_words:
        raise AssertionError(
            f"Rewrite contains a {span}-word verbatim span from original "
            f"(max allowed: {max_words})."
        )


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_longest_verbatim_span_identifies_copy():
    original = "This entire paragraph is copied verbatim from the original source code"
    rewrite = "Before anything: this entire paragraph is copied verbatim from the original source code — oops"
    assert longest_verbatim_span(original, rewrite) >= 11


def test_longest_verbatim_span_ignores_small_overlap():
    original = "the quick brown fox jumps over the lazy dog"
    rewrite = "A cat sat on the mat quietly while watching"
    # Only "the" + "the" overlap; span should be 1
    assert longest_verbatim_span(original, rewrite) == 1


def test_assert_verbatim_ok_raises_on_long_span():
    original = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi"
    rewrite = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi and more"
    try:
        assert_verbatim_ok(original, rewrite, max_words=14)
    except AssertionError:
        return
    raise AssertionError("Expected verbatim check to fail")


def test_assert_verbatim_ok_passes_on_rewrite():
    original = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi"
    rewrite = "A Cruvai-grade treatment of the same methodology in fresh words and ServiceNow-flavored examples"
    assert_verbatim_ok(original, rewrite, max_words=14)
