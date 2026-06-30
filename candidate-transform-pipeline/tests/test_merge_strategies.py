"""
Tests for merge strategy implementations.
"""

import pytest
from src.resolver.weighted_priority import WeightedPriorityStrategy
from src.resolver.majority_vote import MajorityVoteStrategy
from src.resolver.latest_timestamp import LatestTimestampStrategy


class TestWeightedPriorityStrategy:
    def setup_method(self):
        self.strategy = WeightedPriorityStrategy(
            source_weights={"ats": 1.0, "resume": 0.8, "csv": 0.6, "github": 0.4}
        )

    def test_highest_weight_wins(self):
        values = [
            {"source": "csv", "value": "CSV Title"},
            {"source": "ats", "value": "ATS Title"},
        ]
        assert self.strategy.merge("current_title", values) == "ATS Title"

    def test_empty_values_returns_none(self):
        assert self.strategy.merge("field", []) is None

    def test_none_values_skipped(self):
        values = [
            {"source": "ats", "value": None},
            {"source": "csv", "value": "CSV Value"},
        ]
        assert self.strategy.merge("field", values) == "CSV Value"

    def test_unknown_source_gets_zero_weight(self):
        values = [
            {"source": "unknown", "value": "Unknown"},
            {"source": "csv", "value": "CSV Value"},
        ]
        assert self.strategy.merge("field", values) == "CSV Value"

    def test_all_empty_returns_none(self):
        values = [
            {"source": "ats", "value": None},
            {"source": "csv", "value": ""},
        ]
        assert self.strategy.merge("field", values) is None


class TestMajorityVoteStrategy:
    def setup_method(self):
        self.strategy = MajorityVoteStrategy()

    def test_majority_wins(self):
        values = [
            {"source": "ats", "value": "Python"},
            {"source": "csv", "value": "Python"},
            {"source": "github", "value": "JavaScript"},
        ]
        assert self.strategy.merge("language", values) == "Python"

    def test_single_value(self):
        values = [{"source": "csv", "value": "React"}]
        assert self.strategy.merge("skill", values) == "React"

    def test_empty_returns_none(self):
        assert self.strategy.merge("field", []) is None

    def test_case_insensitive_comparison(self):
        values = [
            {"source": "ats", "value": "PYTHON"},
            {"source": "csv", "value": "python"},
            {"source": "github", "value": "JavaScript"},
        ]
        result = self.strategy.merge("field", values)
        assert result.lower() == "python"

    def test_tie_returns_first_occurrence(self):
        values = [
            {"source": "ats", "value": "A"},
            {"source": "csv", "value": "B"},
        ]
        # Both have 1 vote; first occurrence wins
        assert self.strategy.merge("field", values) == "A"


class TestLatestTimestampStrategy:
    def setup_method(self):
        self.strategy = LatestTimestampStrategy()

    def test_latest_timestamp_wins(self):
        values = [
            {"source": "csv", "value": "Old Value", "timestamp": "2022-01-01"},
            {"source": "ats", "value": "New Value", "timestamp": "2024-06-15"},
        ]
        assert self.strategy.merge("field", values) == "New Value"

    def test_no_timestamps_returns_first(self):
        values = [
            {"source": "csv", "value": "First"},
            {"source": "ats", "value": "Second"},
        ]
        assert self.strategy.merge("field", values) == "First"

    def test_empty_returns_none(self):
        assert self.strategy.merge("field", []) is None

    def test_partial_timestamps(self):
        """Entry with timestamp beats entry without."""
        values = [
            {"source": "csv", "value": "No TS"},
            {"source": "ats", "value": "Has TS", "timestamp": "2024-01-01"},
        ]
        assert self.strategy.merge("field", values) == "Has TS"
