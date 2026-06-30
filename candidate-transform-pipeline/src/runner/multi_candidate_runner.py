"""
MultiCandidateRunner — runs the full pipeline over a set of fragments and
produces one CanonicalCandidate per identity-resolved cluster.

The identity resolution step first clusters all fragments globally.
Then, for each cluster, a focused pipeline run is executed to produce
a single merged CanonicalCandidate.
"""

from typing import List, Tuple

import typer

from src.config.config_loader import AppConfig
from src.models.candidate_fragment import CandidateFragment
from src.models.canonical_candidate import CanonicalCandidate
from src.models.processing_context import ProcessingContext
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run_multi_candidate_pipeline(
    fragments: List[CandidateFragment],
    config: AppConfig,
) -> Tuple[List[CanonicalCandidate], List[str], List[str]]:
    """
    Run the full transformation pipeline over all fragments.

    Strategy:
      1. Run identity resolution on ALL fragments together to form clusters.
      2. For each cluster, run the full pipeline (normalizer → merge →
         evidence → builder → validator) on the cluster's fragments only.
      3. Collect one CanonicalCandidate per cluster.

    Args:
        fragments: All CandidateFragment objects loaded from all sources.
        config:    Loaded AppConfig.

    Returns:
        Tuple of (candidates, all_warnings, all_errors).
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

    # ── Step 1: Global identity normalization + resolution ──────────────────
    typer.echo("\n  Running Pipeline...")
    typer.echo("")

    global_ctx = ProcessingContext(candidate_fragments=fragments)

    # Normalize identities across all fragments first.
    norm = IdentityNormalizer()
    global_ctx = norm.execute(global_ctx)

    # Resolve into clusters across all sources.
    resolver = IdentityResolutionService()
    global_ctx = resolver.execute(global_ctx)

    resolution = global_ctx.identity_resolution_result or {}
    clusters = resolution.get("clusters", [])

    typer.echo("  ✓ Identity Resolution Complete")

    if not clusters:
        # No clusters found — treat all as one group.
        clusters = [
            {
                "cluster_id": "cluster_0",
                "fragment_indices": list(range(len(global_ctx.normalized_fragments))),
                "sources": [f.source for f in global_ctx.normalized_fragments],
                "score": 1.0,
            }
        ]

    # ── Step 2: Per-cluster pipeline runs ───────────────────────────────────
    candidates: List[CanonicalCandidate] = []

    for cluster in clusters:
        indices: List[int] = cluster["fragment_indices"]
        cluster_id: str = cluster["cluster_id"]

        # Pick the normalized fragments that belong to this cluster.
        cluster_frags = [global_ctx.normalized_fragments[i] for i in indices]

        # Build a fresh context for this cluster (already normalized).
        ctx = ProcessingContext(
            candidate_fragments=cluster_frags,
            normalized_fragments=cluster_frags,
            identity_resolution_result={
                "clusters": [cluster],
                "total_fragments": len(cluster_frags),
            },
        )

        # Run the per-cluster stages (skip identity steps — already done).
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
            # Override the cluster ID to match the global resolution.
            cand = ctx.canonical_candidate.model_copy(
                update={"candidate_id": cluster_id}
            )
            candidates.append(cand)
        else:
            logger.warning(
                "MultiCandidateRunner: cluster '%s' produced no candidate.", cluster_id
            )

    typer.echo("  ✓ Normalization Complete")
    typer.echo("  ✓ Merge Complete")
    typer.echo("  ✓ Confidence Calculated")
    typer.echo(f"  ✓ Generated {len(candidates)} Canonical Candidate(s)")

    return candidates, all_warnings, all_errors
