"""
ProjectionRequest model — runtime-configurable output projection specification.

Users supply a ProjectionRequest to control which fields appear in the final
output, how they are renamed, and what happens when a requested field is absent.
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ProjectionRequest(BaseModel):
    """
    Describes the user's runtime field-projection preferences.

    Attributes:
        include: Explicit list of canonical field paths to include in output.
                 If empty, all fields are included (pass-through).
        rename: Optional mapping of canonical field name → desired output name.
        missing_policy: Behaviour when a requested field is absent on the candidate.
            - ``"omit"``  — silently drop the field from output.
            - ``"null"``  — include the field with a null value.
            - ``"error"`` — raise an error and halt projection.
    """

    include: List[str] = Field(
        default_factory=list,
        description="Canonical field paths to include. Empty list means include all.",
    )
    rename: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of canonical field name to desired output key name.",
    )
    missing_policy: Literal["omit", "null", "error"] = Field(
        default="omit",
        description="Policy applied when a requested field is missing on the candidate.",
    )
