"""
MergeEngine — applies a configured MergeStrategy to all candidate fields.

Iterates over every canonical field name found across all normalised
fragments, passes the multi-source value list to the active strategy,
and writes the winning value plus full provenance into
``context.merge_decisions``.
"""

import time
from typing import Any, Dict, List

from src.models.processing_context import ProcessingContext
from src.pipeline.stage import Stage
from src.resolver.strategy import MergeStrategy
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Fields that should be collected as lists (union across sources) rather
# than selected as a single winner.
_LIST_FIELDS = {"skills", "education", "experience", "projects"}


class MergeEngine(Stage):
    """
    Pipeline stage that drives field-level merging across normalised
    candidate fragments.

    The engine:
      1. Collects all unique field names from every fragment.
      2. For each scalar field, passes all source values to the strategy.
      3. For list fields (skills, education, experience, projects), unions
         all values from all sources and deduplicates.
      4. Records a merge decision entry for every field, including the
         rejected values for provenance tracking.

    Results are stored in ``context.merge_decisions``.
    """

    def __init__(self, strategy: MergeStrategy) -> None:
        """
        Args:
            strategy: The merge strategy to apply to scalar fields.
        """
        self.strategy = strategy

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Apply the configured merge strategy across all normalised fragments.

        Args:
            context: Shared pipeline context with ``normalized_fragments``.

        Returns:
            Updated context with ``merge_decisions`` populated.
        """
        start = time.time()
        fragments = context.normalized_fragments
        strategy_name = self.strategy.__class__.__name__

        logger.info(
            "MergeEngine [%s]: merging %d fragment(s).",
            strategy_name,
            len(fragments),
        )

        if not fragments:
            logger.warning("MergeEngine: no fragments to merge.")
            return context

        # Collect all field names present across all fragments.
        all_fields: set = set()
        for frag in fragments:
            all_fields.update(frag.extracted_fields.keys())

        decisions: List[Dict[str, Any]] = []

        for field in sorted(all_fields):
            # Build the value list for this field.
            value_entries: List[Dict[str, Any]] = []
            for frag in fragments:
                val = frag.extracted_fields.get(field)
                if val is not None:
                    value_entries.append(
                        {
                            "source": frag.source,
                            "value": val,
                            "timestamp": frag.metadata.get("timestamp"),
                        }
                    )

            if not value_entries:
                continue

            if field in _LIST_FIELDS:
                winning_value = self._merge_list_field(field, value_entries)
                strategy_used = "list_union"
            else:
                try:
                    winning_value = self.strategy.merge(field, value_entries)
                    strategy_used = strategy_name
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "MergeEngine: strategy failed for field='%s': %s. Falling back to first value.",
                        field,
                        exc,
                    )
                    winning_value = value_entries[0]["value"]
                    strategy_used = "fallback_first"

            rejected = [
                e for e in value_entries
                if str(e.get("value")) != str(winning_value)
            ]

            decisions.append(
                {
                    "field": field,
                    "winning_value": winning_value,
                    "strategy": strategy_used,
                    "candidates": value_entries,
                    "rejected": rejected,
                }
            )

        context.merge_decisions = decisions
        elapsed = time.time() - start
        logger.info(
            "MergeEngine [%s]: completed — %d field decision(s) in %.3fs.",
            strategy_name,
            len(decisions),
            elapsed,
        )
        return context

    @staticmethod
    def _merge_list_field(
        field: str, value_entries: List[Dict[str, Any]]
    ) -> List[Any]:
        """
        Union all list values from every source and deduplicate.

        For list-typed fields (skills, education, experience, projects),
        we collect everything and remove exact duplicates while preserving
        insertion order.
        """
        seen: set = set()
        merged: List[Any] = []

        for entry in value_entries:
            val = entry.get("value")
            items = val if isinstance(val, list) else [val]
            for item in items:
                if item is None:
                    continue
                key = str(item).lower().strip() if isinstance(item, str) else str(item)
                if key not in seen:
                    seen.add(key)
                    merged.append(item)

        logger.debug("MergeEngine list_union field='%s' count=%d", field, len(merged))
        return merged
