"""
Provenance model — tracks the origin and transformation history of a field value.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    """
    Records where a value came from and how it was transformed.

    Attributes:
        source: The adapter or system that originally supplied this value.
        original_value: The raw value as extracted from the source.
        transformed_value: The value after normalization or transformation.
        pipeline_stage: The stage name at which the transformation occurred.
        timestamp: UTC timestamp when the provenance record was created.
    """

    source: str = Field(..., description="Originating source identifier (e.g. 'csv', 'ats').")
    original_value: Any = Field(..., description="Raw value extracted from the source.")
    transformed_value: Any = Field(
        None, description="Value after pipeline normalization."
    )
    pipeline_stage: str = Field(
        ..., description="Name of the pipeline stage that produced this record."
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when this provenance entry was recorded.",
    )
