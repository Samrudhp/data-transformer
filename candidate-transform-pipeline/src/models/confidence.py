"""
Confidence model — represents the computed confidence for a candidate field or record.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Confidence(BaseModel):
    """
    Encapsulates confidence metadata for a candidate field or section.

    Attributes:
        value: The final aggregated confidence score in range [0.0, 1.0].
        confidence_scores: Per-source or per-field breakdown of individual scores.
        supporting_sources: List of source identifiers that contributed to this score.
        reasons: Human-readable explanations for the assigned confidence level.
    """

    value: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Aggregated confidence score between 0.0 and 1.0.",
    )
    confidence_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Mapping of source/field name to individual confidence score.",
    )
    supporting_sources: List[str] = Field(
        default_factory=list,
        description="Source identifiers that contributed evidence for this score.",
    )
    reasons: List[str] = Field(
        default_factory=list,
        description="Explanatory reasons for the assigned confidence value.",
    )
