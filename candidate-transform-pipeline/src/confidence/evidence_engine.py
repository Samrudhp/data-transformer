"""
EvidenceEngine — computes evidence-based confidence scores.

Scoring factors
---------------
1. Source reliability  — weight from confidence.yaml source_weights.
2. Agreement count     — bonus when multiple sources agree on the same value.
3. Conflict penalty    — deduction when sources disagree.
4. Coverage            — ratio of important fields populated vs total.

Final score is clamped to [0.0, 1.0].
"""

import time
from typing import Any, Dict, List

from src.config.config_loader import ConfidenceConfig
from src.models.confidence import Confidence
from src.models.processing_context import ProcessingContext
from src.pipeline.stage import Stage
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Fields considered "important" for coverage scoring.
_IMPORTANT_FIELDS = {
    "full_name",
    "email",
    "phone",
    "skills",
    "education",
    "experience",
}

_AGREEMENT_BONUS = 0.05   # per additional agreeing source beyond the first
_CONFLICT_PENALTY = 0.08  # per field where sources disagree


class EvidenceEngine(Stage):
    """
    Pipeline stage that computes evidence-based confidence scores for the
    merged candidate record.

    Reads source weights and field weights from a ``ConfidenceConfig``.
    Stores individual evidence records in ``context.evidence`` and sets
    the ``confidence`` attribute on the ``canonical_candidate`` if available.
    """

    def __init__(self, config: ConfidenceConfig) -> None:
        """
        Args:
            config: Parsed confidence.yaml configuration.
        """
        self.config = config

    def calculate(self, context: ProcessingContext) -> Confidence:
        """
        Compute a Confidence object from the current context state.

        Uses merge_decisions to measure agreement/conflict and
        source_weights for reliability scoring.

        Args:
            context: Shared pipeline context.

        Returns:
            A populated Confidence model instance.
        """
        decisions = context.merge_decisions
        source_weights = self.config.source_weights
        field_weights = self.config.field_weights

        per_source_scores: Dict[str, float] = {}
        supporting_sources: set = set()
        reasons: List[str] = []
        evidence_records: List[Dict[str, Any]] = []
        conflict_count = 0
        agreement_bonus_total = 0.0

        # --- Per-field analysis ---
        for decision in decisions:
            field: str = decision["field"]
            candidates: List[Dict[str, Any]] = decision.get("candidates", [])
            winning_value = decision.get("winning_value")

            if not candidates:
                continue

            # Collect sources that provided this field.
            field_sources = [e["source"] for e in candidates]
            agreeing_sources = [
                e["source"]
                for e in candidates
                if str(e.get("value", "")).lower() == str(winning_value or "").lower()
            ]

            for src in field_sources:
                if src not in per_source_scores:
                    per_source_scores[src] = source_weights.get(src, 0.5)
                supporting_sources.add(src)

            # Agreement bonus.
            if len(agreeing_sources) > 1:
                bonus = _AGREEMENT_BONUS * (len(agreeing_sources) - 1)
                agreement_bonus_total += bonus
                reasons.append(
                    f"field='{field}': {len(agreeing_sources)} sources agree → +{bonus:.2f}"
                )

            # Conflict detection.
            unique_vals = {str(e.get("value", "")).lower() for e in candidates}
            if len(unique_vals) > 1:
                conflict_count += 1

            evidence_records.append(
                {
                    "field": field,
                    "winning_value": winning_value,
                    "sources": field_sources,
                    "agreeing_sources": agreeing_sources,
                    "conflict": len(unique_vals) > 1,
                }
            )

        # --- Aggregate source reliability score ---
        if per_source_scores:
            reliability = sum(per_source_scores.values()) / len(per_source_scores)
        else:
            reliability = 0.5

        # --- Coverage score (important fields populated) ---
        all_field_names = {d["field"] for d in decisions}
        covered = _IMPORTANT_FIELDS & all_field_names
        coverage = len(covered) / len(_IMPORTANT_FIELDS) if _IMPORTANT_FIELDS else 1.0

        # --- Conflict penalty ---
        penalty = _CONFLICT_PENALTY * conflict_count
        if conflict_count:
            reasons.append(
                f"{conflict_count} field conflict(s) detected → -{penalty:.2f}"
            )

        # --- Final score ---
        raw_score = (
            reliability * 0.50
            + coverage * 0.30
            + agreement_bonus_total * 0.15
            - penalty * 0.05
        )
        final_score = max(0.0, min(1.0, raw_score))

        # Threshold warning.
        if final_score < self.config.minimum_confidence_threshold:
            reasons.append(
                f"Score {final_score:.2f} is below threshold "
                f"{self.config.minimum_confidence_threshold:.2f}."
            )

        reasons.insert(
            0,
            f"reliability={reliability:.2f}  coverage={coverage:.2f}  "
            f"conflicts={conflict_count}  sources={sorted(supporting_sources)}",
        )

        return Confidence(
            value=round(final_score, 4),
            confidence_scores={**per_source_scores, "coverage": round(coverage, 4)},
            supporting_sources=sorted(supporting_sources),
            reasons=reasons,
        ), evidence_records

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Run evidence scoring and store results in the context.

        Args:
            context: Shared pipeline context.

        Returns:
            Updated context with ``evidence`` populated and confidence
            attached to ``canonical_candidate`` if available.
        """
        start = time.time()
        logger.info("EvidenceEngine: calculating evidence scores.")

        confidence, records = self.calculate(context)
        context.evidence = records

        # Attach confidence to canonical_candidate if already built.
        if context.canonical_candidate is not None:
            context.canonical_candidate = context.canonical_candidate.model_copy(
                update={"confidence": confidence}
            )

        elapsed = time.time() - start
        logger.info(
            "EvidenceEngine: score=%.4f  sources=%s  elapsed=%.3fs",
            confidence.value,
            confidence.supporting_sources,
            elapsed,
        )

        if confidence.value < self.config.minimum_confidence_threshold:
            warning = (
                f"EvidenceEngine: confidence score {confidence.value:.4f} is below "
                f"threshold {self.config.minimum_confidence_threshold:.2f}."
            )
            logger.warning(warning)
            context.warnings.append(warning)

        return context
