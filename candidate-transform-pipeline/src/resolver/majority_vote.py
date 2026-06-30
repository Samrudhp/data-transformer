"""
MajorityVoteStrategy — selects the most frequently occurring value across sources.
"""

from collections import Counter
from typing import Any, Dict, List, Optional

from src.resolver.strategy import MergeStrategy
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MajorityVoteStrategy(MergeStrategy):
    """
    Merge strategy that selects the value with the highest vote count
    across all contributing sources.

    Comparison is performed on the lowercase string representation of each
    value, preserving the original casing in the returned value.
    When there is a tie in vote count, the candidate that appears first
    in the ``values`` list is returned (stable / deterministic).
    """

    def merge(
        self,
        field_name: str,
        values: List[Dict[str, Any]],
    ) -> Any:
        """
        Return the majority-voted value.

        Args:
            field_name: The canonical field name (used for logging).
            values: List of dicts with ``"value"`` and ``"source"`` keys.

        Returns:
            The most frequently occurring non-empty value, or ``None`` if
            all values are empty.
        """
        if not values:
            return None

        # Build a list of (normalised_key, original_value) for non-empty entries.
        candidates: List[Any] = []
        for entry in values:
            val = entry.get("value")
            if val is None or (isinstance(val, str) and val.strip() == ""):
                continue
            candidates.append(val)

        if not candidates:
            return None

        # Count votes using the lowercase string representation.
        vote_counts: Counter = Counter()
        first_seen: Dict[str, Any] = {}
        for val in candidates:
            key = str(val).lower().strip()
            vote_counts[key] += 1
            if key not in first_seen:
                first_seen[key] = val

        winner_key = vote_counts.most_common(1)[0][0]
        winner = first_seen[winner_key]

        logger.debug(
            "MajorityVote field='%s' winner='%s' votes=%d/%d",
            field_name,
            winner_key,
            vote_counts[winner_key],
            len(candidates),
        )
        return winner
