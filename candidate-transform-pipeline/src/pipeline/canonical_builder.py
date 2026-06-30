"""
CanonicalCandidateBuilder — constructs the final CanonicalCandidate from merge decisions.

Reads ``context.merge_decisions`` and assembles a fully populated
CanonicalCandidate, preserving provenance records for every field.
"""

import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.models.canonical_candidate import (
    CanonicalCandidate,
    ContactInfo,
    Education,
    Experience,
    Links,
    PersonalInfo,
    Project,
)
from src.models.processing_context import ProcessingContext
from src.models.provenance import Provenance
from src.pipeline.stage import Stage
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _get(decisions_map: Dict[str, Any], field: str, default: Any = None) -> Any:
    """Return the winning value for a field from the decisions map."""
    entry = decisions_map.get(field)
    if entry is None:
        return default
    return entry.get("winning_value", default)


def _build_provenance(
    field: str,
    decision: Dict[str, Any],
    stage: str = "CanonicalCandidateBuilder",
) -> List[Provenance]:
    """
    Build Provenance records for every source that contributed to a field.
    """
    records: List[Provenance] = []
    winning_value = decision.get("winning_value")
    for entry in decision.get("candidates", []):
        records.append(
            Provenance(
                source=entry.get("source", "unknown"),
                original_value=entry.get("value"),
                transformed_value=winning_value,
                pipeline_stage=stage,
                timestamp=datetime.utcnow(),
            )
        )
    return records


class CanonicalCandidateBuilder(Stage):
    """
    Pipeline stage that assembles the CanonicalCandidate from merge decisions.

    Responsibilities:
      - Maps merge_decisions to the typed CanonicalCandidate model fields.
      - Builds structured Education, Experience, Project, and Links objects.
      - Records field-level provenance including rejected values.
      - Assigns a unique candidate_id.
      - Never discards rejected values — they are stored in provenance.
    """

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Build the CanonicalCandidate from ``context.merge_decisions``.

        Args:
            context: Shared pipeline context with merge decisions populated.

        Returns:
            Updated context with ``canonical_candidate`` set.
        """
        start = time.time()
        logger.info("CanonicalCandidateBuilder: assembling candidate.")

        # Index decisions by field name for O(1) lookup.
        dm: Dict[str, Dict[str, Any]] = {
            d["field"]: d for d in context.merge_decisions
        }

        provenance: List[Provenance] = []

        # ---- Personal info ----
        full_name = _get(dm, "full_name")
        first_name = _get(dm, "first_name")
        last_name = _get(dm, "last_name")

        # Derive first/last from full_name if missing.
        if full_name and not first_name and not last_name:
            parts = str(full_name).split()
            first_name = parts[0] if parts else None
            last_name = parts[-1] if len(parts) > 1 else None

        personal_info = PersonalInfo(
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            date_of_birth=_get(dm, "date_of_birth"),
            gender=_get(dm, "gender"),
            nationality=_get(dm, "nationality"),
        )

        for field in ("full_name", "first_name", "last_name"):
            if field in dm:
                provenance.extend(_build_provenance(field, dm[field]))

        # ---- Contact info ----
        contact = ContactInfo(
            email=_get(dm, "email"),
            phone=_get(dm, "phone"),
            address=_get(dm, "address"),
            city=_get(dm, "city"),
            state=_get(dm, "state"),
            country=_get(dm, "country"),
            postal_code=_get(dm, "postal_code"),
        )

        for field in ("email", "phone", "city", "country"):
            if field in dm:
                provenance.extend(_build_provenance(field, dm[field]))

        # ---- Education ----
        raw_education = _get(dm, "education", [])
        education: List[Education] = []
        if isinstance(raw_education, list):
            for entry in raw_education:
                if isinstance(entry, dict):
                    education.append(
                        Education(
                            institution=entry.get("institution"),
                            degree=entry.get("degree"),
                            field_of_study=entry.get("field_of_study") or entry.get("major"),
                            start_date=entry.get("start_date"),
                            end_date=entry.get("end_date"),
                            gpa=_safe_float(entry.get("gpa")),
                        )
                    )
        if "education" in dm:
            provenance.extend(_build_provenance("education", dm["education"]))

        # ---- Experience ----
        raw_experience = _get(dm, "experience", [])
        experience: List[Experience] = []
        if isinstance(raw_experience, list):
            for entry in raw_experience:
                if isinstance(entry, dict):
                    end_date = entry.get("end_date", "")
                    is_current = str(end_date).lower() in ("", "present", "current", "now")
                    experience.append(
                        Experience(
                            company=entry.get("company") or entry.get("employer"),
                            title=entry.get("title") or entry.get("job_title"),
                            location=entry.get("location"),
                            start_date=entry.get("start_date"),
                            end_date=None if is_current else end_date or None,
                            description=entry.get("description"),
                            is_current=is_current,
                        )
                    )
        if "experience" in dm:
            provenance.extend(_build_provenance("experience", dm["experience"]))

        # ---- Projects ----
        raw_projects = _get(dm, "projects", [])
        projects: List[Project] = []
        if isinstance(raw_projects, list):
            for entry in raw_projects:
                if isinstance(entry, dict):
                    techs = entry.get("technologies", [])
                    if isinstance(techs, str):
                        techs = [t.strip() for t in techs.split(",") if t.strip()]
                    projects.append(
                        Project(
                            name=entry.get("name"),
                            description=entry.get("description"),
                            url=entry.get("url"),
                            technologies=techs,
                            start_date=entry.get("start_date"),
                            end_date=entry.get("end_date"),
                        )
                    )

        # ---- Skills ----
        raw_skills = _get(dm, "skills", [])
        if isinstance(raw_skills, str):
            raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
        skills: List[str] = list(raw_skills) if isinstance(raw_skills, list) else []

        if "skills" in dm:
            provenance.extend(_build_provenance("skills", dm["skills"]))

        # ---- Links ----
        links = Links(
            linkedin=_get(dm, "linkedin"),
            github=_get(dm, "github"),
            portfolio=_get(dm, "portfolio"),
        )

        for field in ("linkedin", "github", "portfolio"):
            if field in dm:
                provenance.extend(_build_provenance(field, dm[field]))

        # ---- Candidate ID ----
        # Use the resolved cluster ID if available, else generate a UUID.
        candidate_id = _derive_candidate_id(context)

        candidate = CanonicalCandidate(
            candidate_id=candidate_id,
            personal_info=personal_info,
            contact=contact,
            education=education,
            experience=experience,
            projects=projects,
            skills=skills,
            links=links,
            confidence=None,  # EvidenceEngine populates this.
            provenance=provenance,
        )

        context.canonical_candidate = candidate
        elapsed = time.time() - start
        logger.info(
            "CanonicalCandidateBuilder: completed in %.3fs. candidate_id=%s",
            elapsed,
            candidate_id,
        )
        return context


def _safe_float(value: Any) -> Optional[float]:
    """Safely convert a value to float; return None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _derive_candidate_id(context: ProcessingContext) -> str:
    """
    Derive a stable candidate ID from the identity resolution result,
    or generate a new UUID if no cluster ID is available.
    """
    result = context.identity_resolution_result
    if result and result.get("clusters"):
        first_cluster = result["clusters"][0]
        return first_cluster.get("cluster_id", str(uuid.uuid4()))
    # Stable ID from email if present in fragments.
    for frag in context.normalized_fragments:
        email = frag.extracted_fields.get("email")
        if email:
            safe = str(email).replace("@", "_at_").replace(".", "_")
            return f"candidate_{safe}"
    return f"candidate_{uuid.uuid4().hex[:8]}"
