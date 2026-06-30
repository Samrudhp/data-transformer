"""
WeightedPriorityStrategy — selects the value from the highest-priority source.

Source priorities are loaded from resolver.yaml configuration.
"""

from typing import Any, Dict, List

from src.resolver.strategy import MergeStrategy
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WeightedPriorityStrategy(MergeStrategy):
    """
    Merge strategy that selects the field value from the source with the
    highest configured priority weight.

    When multiple sources share the same maximum weight (tie), the first
    occurrence in the ``values`` list is selected (deterministic).
    """

    def __init__(self, source_weights: Dict[str, float]) -> None:
        """
        Args:
            source_weights: Mapping of source identifier → numeric priority weight.
                            Higher weight = higher trust.
        """
        self.source_weights = source_weights

    def merge(
        self,
        field_name: str,
        values: List[Dict[str, Any]],
    ) -> Any:
        """
        Return the value from the highest-weighted source.

        Only entries with a non-None, non-empty value are considered.

        Args:
            field_name: The canonical field name (used for logging).
            values: List of dicts, each with ``"value"`` and ``"source"`` keys.

        Returns:
            The value from the highest-priority source, or ``None`` if all
            values are empty.
        """
        if not values:
            return None

        best_value: Any = None
        best_weight: float = -1.0

        for entry in values:
            val = entry.get("value")
            source = entry.get("source", "")
            weight = self.source_weights.get(source, 0.0)

            # Skip empty values; treat None and "" as absent.
            if val is None or (isinstance(val, str) and val.strip() == ""):
                continue

            if weight > best_weight:
                best_weight = weight
                best_value = val

        logger.debug(
            "WeightedPriority field='%s' winner_weight=%.2f value=%s",
            field_name,
            best_weight,
            repr(best_value),
        )
        return best_value
