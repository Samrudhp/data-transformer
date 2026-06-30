"""
ProjectionService — applies runtime field projection to the CanonicalCandidate.

Projection is entirely runtime-driven by a ProjectionRequest.
The CanonicalCandidate is never modified.
"""

from typing import Any, Dict, List

from src.models.canonical_candidate import CanonicalCandidate
from src.models.projection_request import ProjectionRequest
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Top-level keys exposed by CanonicalCandidate that the wizard can reference.
_TOP_LEVEL_FIELDS = [
    "candidate_id",
    "personal_info",
    "contact",
    "education",
    "experience",
    "projects",
    "skills",
    "links",
    "confidence",
    "provenance",
]

# Human-readable labels for the wizard display.
FIELD_DISPLAY_NAMES: Dict[str, str] = {
    "candidate_id": "Candidate ID",
    "personal_info": "Personal Info",
    "contact": "Contact Details",
    "education": "Education",
    "experience": "Experience",
    "projects": "Projects",
    "skills": "Skills",
    "links": "Links",
    "confidence": "Confidence",
    "provenance": "Provenance",
}


class ProjectionService:
    """
    Applies a ProjectionRequest to a CanonicalCandidate to produce the
    final output dictionary.

    The CanonicalCandidate is serialised to a dict first; all operations
    are performed on that dict — the original model is never mutated.
    """

    def project(
        self,
        candidate: CanonicalCandidate,
        request: ProjectionRequest,
    ) -> Dict[str, Any]:
        """
        Apply the full projection pipeline and return the output dict.

        Steps:
          1. Serialise candidate to dict.
          2. Filter to included fields (or pass all if include is empty).
          3. Apply missing-value policy for any requested-but-absent fields.
          4. Apply field renames.

        Args:
            candidate: The fully resolved CanonicalCandidate (read-only).
            request: Runtime projection configuration.

        Returns:
            Final output dictionary.
        """
        # Serialise to plain dict (Pydantic v2 style).
        full_dict = candidate.model_dump(mode="python")

        if request.include:
            result = self.include_fields(full_dict, request.include)
            result = self.apply_missing_policy(
                result, request.include, request.missing_policy
            )
        else:
            # No include list → pass everything through.
            result = dict(full_dict)

        if request.rename:
            result = self.rename_fields(result, request.rename)

        logger.info(
            "ProjectionService: projected %d field(s).", len(result)
        )
        return result

    def include_fields(
        self,
        candidate_dict: Dict[str, Any],
        include: List[str],
    ) -> Dict[str, Any]:
        """
        Return only the keys listed in ``include``.

        Supports both top-level keys (``"skills"``) and dotted sub-paths
        (``"personal_info.full_name"``).

        Args:
            candidate_dict: Full serialised candidate dict.
            include: List of field path strings to keep.

        Returns:
            Filtered dictionary.
        """
        result: Dict[str, Any] = {}
        for path in include:
            parts = path.split(".", 1)
            top = parts[0]
            if top not in candidate_dict:
                continue  # missing — handled by apply_missing_policy later
            if len(parts) == 1:
                result[top] = candidate_dict[top]
            else:
                # Nested path: e.g. "personal_info.full_name"
                sub_key = parts[1]
                parent = candidate_dict[top]
                if isinstance(parent, dict) and sub_key in parent:
                    # Store as flat key with dot notation.
                    result[path] = parent[sub_key]
                elif isinstance(parent, dict):
                    pass  # missing sub-key — handled downstream
                else:
                    result[top] = parent
        return result

    def rename_fields(
        self,
        candidate_dict: Dict[str, Any],
        rename: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Rename keys in the output dictionary.

        Args:
            candidate_dict: Current output dict.
            rename: Mapping of current key → desired output key.

        Returns:
            Dictionary with renamed keys.
        """
        result: Dict[str, Any] = {}
        for key, value in candidate_dict.items():
            new_key = rename.get(key, key)
            result[new_key] = value
        return result

    def apply_missing_policy(
        self,
        candidate_dict: Dict[str, Any],
        requested_fields: List[str],
        policy: str,
    ) -> Dict[str, Any]:
        """
        Handle fields that were requested but are absent from the output.

        Args:
            candidate_dict: Current projection output dict.
            requested_fields: Field paths the user requested.
            policy: ``"omit"`` | ``"null"`` | ``"error"``

        Returns:
            Dict with missing fields handled per policy.

        Raises:
            KeyError: When ``policy == "error"`` and a field is missing.
        """
        result = dict(candidate_dict)
        for path in requested_fields:
            # Check both plain key and dotted key forms.
            present = path in result or path.split(".", 1)[0] in result
            if not present:
                if policy == "omit":
                    pass  # do nothing — field simply absent
                elif policy == "null":
                    result[path] = None
                elif policy == "error":
                    raise KeyError(
                        f"Projection error: requested field '{path}' is missing "
                        "from the canonical candidate."
                    )
        return result
