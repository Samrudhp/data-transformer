"""
ProcessingContext — the central mutable state object threaded through every pipeline stage.

Each stage receives the same context instance, reads what it needs,
and writes its results back into it. This allows the orchestrator to
maintain a single, coherent view of the pipeline's progress.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.models.candidate_fragment import CandidateFragment
from src.models.canonical_candidate import CanonicalCandidate


class ProcessingContext(BaseModel):
    """
    Shared pipeline state passed through and mutated by every stage.

    Attributes:
        candidate_fragments: Raw fragments collected from all source adapters.
        normalized_fragments: Fragments after identity normalization.
        identity_resolution_result: Output of the identity resolution stage
                                    (e.g. resolved candidate ID or cluster).
        merge_decisions: Field-level merge decisions produced by the merge engine.
        evidence: Evidence records collected by the evidence scoring engine.
        warnings: Non-fatal issues accumulated during processing.
        errors: Fatal or stage-level errors encountered during processing.
        execution_logs: Ordered log of stage execution events.
        canonical_candidate: The fully constructed canonical candidate, available
                             after the canonical builder stage completes.
    """

    # --- Input ---
    candidate_fragments: List[CandidateFragment] = Field(
        default_factory=list,
        description="Raw fragments from all source adapters.",
    )

    # --- Stage outputs ---
    normalized_fragments: List[CandidateFragment] = Field(
        default_factory=list,
        description="Fragments after identity normalization.",
    )
    identity_resolution_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Result payload from the identity resolution stage.",
    )
    merge_decisions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Per-field merge decisions from the merge policy engine.",
    )
    evidence: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Evidence records scored by the evidence engine.",
    )

    # --- Diagnostics ---
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal warnings accumulated across all stages.",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Errors encountered during pipeline execution.",
    )
    execution_logs: List[str] = Field(
        default_factory=list,
        description="Ordered trace of stage execution events.",
    )

    # --- Final output ---
    canonical_candidate: Optional[CanonicalCandidate] = Field(
        None,
        description="The fully merged and normalized candidate produced by the builder stage.",
    )

    model_config = {"arbitrary_types_allowed": True}
