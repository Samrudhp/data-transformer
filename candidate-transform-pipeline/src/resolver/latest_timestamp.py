"""
LatestTimestampStrategy — selects the most recently produced value.

Requires each value entry to include an optional ``"timestamp"`` key in
ISO 8601 format. Falls back to first non-empty value when timestamps
are absent or equal.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.resolver.strategy import MergeStrategy
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LatestTimestampStrategy(MergeStrategy):
    """
    Merge strategy that selects the field value from the entry with the
    most recent ``"timestamp"``.

    Falls back gracefully:
      1. Entries with a parseable timestamp are compared directly.
      2. Entries without a timestamp are ranked lower than those with one.
      3. If no timestamps are present, returns the first non-empty value.
    """

    def merge(
        self,
        field_name: str,
        values: List[Dict[str, Any]],
    ) -> Any:
        """
        Return the value associated with the latest timestamp.

        Args:
            field_name: The canonical field name (used for logging).
            values: List of dicts with ``"value"``, ``"source"``, and
                    optional ``"timestamp"`` keys.

        Returns:
            The value from the most recent source record, or ``None`` if
            all values are empty.
        """
        if not values:
            return None

        best_value: Any = None
        best_ts: Optional[datetime] = None
        has_any_ts = False

        for entry in values:
            val = entry.get("value")
            if val is None or (isinstance(val, str) and val.strip() == ""):
                continue

            ts_raw = entry.get("timestamp")
            ts: Optional[datetime] = None
            if ts_raw:
                ts = self._parse_ts(ts_raw)
                if ts:
                    has_any_ts = True

            if best_value is None:
                # First non-empty entry — use as initial best.
                best_value = val
                best_ts = ts
                continue

            if ts is not None and (best_ts is None or ts > best_ts):
                best_value = val
                best_ts = ts

        if not has_any_ts:
            # No timestamps at all: return first non-empty value.
            for entry in values:
                val = entry.get("value")
                if val is not None and not (isinstance(val, str) and val.strip() == ""):
                    logger.debug(
                        "LatestTimestamp field='%s': no timestamps, using first value.",
                        field_name,
                    )
                    return val
            return None

        logger.debug(
            "LatestTimestamp field='%s' best_ts=%s value=%s",
            field_name,
            best_ts.isoformat() if best_ts else "none",
            repr(best_value),
        )
        return best_value

    @staticmethod
    def _parse_ts(value: Any) -> Optional[datetime]:
        """
        Attempt to parse a timestamp string into a datetime object.

        Returns ``None`` if parsing fails.
        """
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            return None
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y-%m",
        ):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None
