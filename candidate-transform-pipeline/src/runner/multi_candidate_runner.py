"""
MultiCandidateRunner — runs the full pipeline over a set of fragments and
produces one CanonicalCandidate per identity-resolved cluster.

Returns candidates, warnings, errors, and identity-resolution metadata
so the caller (main.py) can drive all console output.
"""

from typing import Dict, Any, List, Tuple

from src.config.config_loader import AppConfig
from src.models.candidate_fragment import CandidateFragment
from src.models.canonical_candidate import CanonicalCandidate
from src.models.processing_context import ProcessingContext
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run_multi_candidate_pipeline(
    fragments: List[CandidateFragment],
    config: AppConfig,
) -> Tuple[List[CanonicalCandidate], List[str], List[str], Dict[str, Any]]:
    """
    Run the full transformation pipeline over all fragments.

    Strategy:
      1. Global identity normalisation + resolution across all fragments.
      2. Per-cluster focused pipeline (normalise → merge → evidence →
         builder → validate).
      3. Return one CanonicalCandidate per cluster.

    Args:
        fragments: All CandidateFragment objects from every source.
        config:    Loaded AppConfig.

    Returns:
        (candidates, all_warnings, all_errors, metadata)
        metadata keys: total_fragments, num_clusters
    """
    from src.confidence.evidence_engine import EvidenceEngine
    from src.identity.identity_normalizer import IdentityNormalizer
    from src.identity.identity_resolution import IdentityResolutionService
    from src.normalization.canonical_normalizer import CanonicalNormalizer
    from src.pipeline.canonical_builder import CanonicalCandidateBuilder
    from src.pipeline.orchestrator import PipelineOrchestrator
    from src.resolver.latest_timestamp import LatestTimestampStrategy
    from src.resolver.majority_vote import MajorityVoteStrategy
    from src.resolver.merge_engine import MergeEngine
    from src.resolver.weighted_priority import WeightedPriorityStrategy
    from src.validation.schema_validator import SchemaValidator

    strategy_name = config.resolver.merge_strategy
    priorities = config.resolver.source_priorities

    if strategy_name == "majority_vote":
        strategy = MajorityVoteStrategy()
    elif strategy_name == "latest_timestamp":
        strategy = LatestTimestampStrategy()
    else:
        strategy = WeightedPriorityStrategy(source_weights=priorities)

    all_warnings: List[str] = []
    all_errors: List[str] = []

    # ── Step 1: Global identity normalisation + resolution ───────────────────
    global_ctx = ProcessingContext(candidate_fragments=fragments)

    norm = IdentityNormalizer()
    global_ctx = norm.execute(global_ctx)

    resolver = IdentityResolutionService()
    global_ctx = resolver.execute(global_ctx)

    resolution = global_ctx.identity_resolution_result or {}
    clusters = resolution.get("clusters", [])

    if not clusters:
        clusters = [
            {
                "cluster_id": "cluster_0",
                "fragment_indices": list(range(len(global_ctx.normalized_fragments))),
                "sources": [f.source for f in global_ctx.normalized_fragments],
                "score": 1.0,
            }
        ]

    total_fragments = len(global_ctx.normalized_fragments)
    num_clusters = len(clusters)

    # ── Step 2: Per-cluster pipeline runs ────────────────────────────────────
    candidates: List[CanonicalCandidate] = []

    for cluster in clusters:
        indices: List[int] = cluster["fragment_indices"]
        cluster_id: str = cluster["cluster_id"]

        cluster_frags = [global_ctx.normalized_fragments[i] for i in indices]

        ctx = ProcessingContext(
            candidate_fragments=cluster_frags,
            normalized_fragments=cluster_frags,
            identity_resolution_result={
                "clusters": [cluster],
                "total_fragments": len(cluster_frags),
            },
        )

        per_cluster_stages = [
            CanonicalNormalizer(),
            MergeEngine(strategy=strategy),
            EvidenceEngine(config=config.confidence),
            CanonicalCandidateBuilder(),
            EvidenceEngine(config=config.confidence),
            SchemaValidator(),
        ]

        orchestrator = PipelineOrchestrator(stages=per_cluster_stages)
        ctx = orchestrator.run(ctx)

        all_warnings.extend(ctx.warnings)
        all_errors.extend(ctx.errors)

        if ctx.canonical_candidate is not None:
            cand = ctx.canonical_candidate.model_copy(
                update={"candidate_id": cluster_id}
            )
            candidates.append(cand)
        else:
            logger.warning(
                "MultiCandidateRunner: cluster '%s' produced no candidate.", cluster_id
            )

    meta: Dict[str, Any] = {
        "total_fragments": total_fragments,
        "num_clusters": num_clusters,
    }

    return candidates, all_warnings, all_errors, meta
