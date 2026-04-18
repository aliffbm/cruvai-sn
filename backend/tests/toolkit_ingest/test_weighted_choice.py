"""Sanity checks for the weighted-random label picker used by GuidanceService."""

from __future__ import annotations

import random

from app.services.guidance_service import _weighted_choice


class _FakeLabel:
    def __init__(self, name: str, weight: int):
        self.name = name
        self.traffic_weight = weight

    def __repr__(self) -> str:
        return f"Label({self.name}, {self.traffic_weight})"


def test_weighted_choice_respects_weights():
    rows = [_FakeLabel("A", 70), _FakeLabel("B", 30)]
    counts = {"A": 0, "B": 0}
    random.seed(0)
    for _ in range(2000):
        picked = _weighted_choice(rows)
        counts[picked.name] += 1
    # Expect rough 70/30 split; allow ±10% drift with 2000 samples
    ratio = counts["A"] / 2000
    assert 0.6 < ratio < 0.8, f"Unexpected ratio: {ratio}, counts={counts}"


def test_weighted_choice_single_row():
    rows = [_FakeLabel("only", 100)]
    assert _weighted_choice(rows) is rows[0]


def test_weighted_choice_zero_weights_returns_first():
    rows = [_FakeLabel("A", 0), _FakeLabel("B", 0)]
    assert _weighted_choice(rows) is rows[0]


def test_weighted_choice_empty_returns_none():
    assert _weighted_choice([]) is None
