"""
CandidateFragment model — partial candidate information extracted from a single source.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class CandidateFragment(BaseModel):
    """
    Represents a partial candidate record as extracted from one upstream source.

    A fragment is the raw, unmerged output produced by a source adapter.
    Multiple fragments from different sources are later resolved and merged
    into a single CanonicalCandidate.

    Attributes:
        source: Identifier of the adapter/source that produced this fragment
                (e.g. 'csv', 'ats', 'resume', 'github').
        extracted_fields: Key-value mapping of field names to extracted values.
        metadata: Optional adapter-level metadata (e.g. file path, fetch time).
        raw_input_reference: Opaque reference to the original raw input artifact
                             (file path, URL, ATS record ID, etc.).
    """

    source: str = Field(..., description="Source adapter identifier.")
    extracted_fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Flat key-value map of extracted candidate fields.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Adapter-level metadata associated with the extraction.",
    )
    raw_input_reference: Optional[str] = Field(
        None,
        description="Reference to the original raw input artifact (path, URL, ID).",
    )
