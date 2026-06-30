"""
ATSAdapter — loads candidate data from an ATS JSON export file.

Maps ATS-specific field names to canonical extracted_fields keys.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from src.adapters.base_adapter import BaseAdapter
from src.models.candidate_fragment import CandidateFragment
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Mapping from ATS field names → canonical fragment field keys.
# Extend this dict to support additional ATS vendors.
_ATS_FIELD_MAP: Dict[str, str] = {
    # Identity
    "candidateName": "full_name",
    "firstName": "first_name",
    "lastName": "last_name",
    "fullName": "full_name",
    # Contact
    "emailAddress": "email",
    "email": "email",
    "mobilePhone": "phone",
    "phoneNumber": "phone",
    "phone": "phone",
    # Location
    "city": "city",
    "location": "city",
    "country": "country",
    # Professional
    "currentTitle": "current_title",
    "jobTitle": "current_title",
    "currentCompany": "current_company",
    "employer": "current_company",
    "skills": "skills",
    "technicalSkills": "skills",
    # Education / Experience
    "educationHistory": "education",
    "education": "education",
    "workHistory": "experience",
    "experience": "experience",
    # Links
    "githubUrl": "github",
    "github": "github",
    "linkedinUrl": "linkedin",
    "linkedin": "linkedin",
    # Meta
    "summary": "summary",
    "candidateId": "ats_candidate_id",
    "applicationDate": "application_date",
    "source": "ats_source_channel",
}


class ATSAdapter(BaseAdapter):
    """
    Adapter for ingesting candidate records from ATS JSON export files.

    The ATS JSON may contain a single candidate object or an array
    of candidate objects under a top-level ``"candidates"`` key.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Args:
            config: Must contain ``"file_path"`` key pointing to the ATS JSON file.
                    Optional ``"encoding"`` key (default ``"utf-8"``).
        """
        self.config = config
        self.file_path = Path(config["file_path"])
        self.encoding: str = config.get("encoding", "utf-8")

    def load(self) -> Any:
        """
        Read and JSON-decode the ATS export file.

        Returns:
            Parsed JSON structure (list or dict).

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file contains invalid JSON.
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"ATS file not found: {self.file_path}")

        with self.file_path.open("r", encoding=self.encoding) as fh:
            try:
                data = json.load(fh)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Malformed ATS JSON in {self.file_path}: {exc}"
                ) from exc

        logger.info("ATSAdapter: loaded ATS data from %s.", self.file_path)
        return data

    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        """
        Normalise the raw ATS payload into a list of candidate record dicts.

        Supports:
          - A plain dict (single candidate).
          - A list of dicts.
          - A dict with a ``"candidates"`` key containing a list.

        Args:
            raw_data: Parsed JSON from ``load()``.

        Returns:
            List of raw ATS candidate record dicts.
        """
        if isinstance(raw_data, list):
            records = raw_data
        elif isinstance(raw_data, dict):
            records = raw_data.get("candidates", [raw_data])
        else:
            logger.warning("ATSAdapter: unexpected payload type %s.", type(raw_data))
            records = []

        logger.info("ATSAdapter: parsed %d ATS record(s).", len(records))
        return records  # type: ignore[return-value]

    def to_candidate_fragment(
        self, parsed_data: List[Dict[str, Any]]
    ) -> List[CandidateFragment]:
        """
        Map ATS field names to canonical keys and produce CandidateFragment objects.

        Args:
            parsed_data: List of raw ATS record dicts from ``parse()``.

        Returns:
            List of CandidateFragment instances.
        """
        fragments: List[CandidateFragment] = []
        for record in parsed_data:
            fields: Dict[str, Any] = {}
            for ats_key, value in record.items():
                canonical_key = _ATS_FIELD_MAP.get(ats_key, ats_key)
                fields[canonical_key] = value

            # Normalise skills if supplied as a comma-separated string.
            raw_skills = fields.get("skills")
            if isinstance(raw_skills, str):
                fields["skills"] = [s.strip() for s in raw_skills.split(",") if s.strip()]

            ats_id = fields.get("ats_candidate_id", "unknown")
            fragment = CandidateFragment(
                source="ats",
                extracted_fields=fields,
                metadata={"ats_candidate_id": ats_id, "file": str(self.file_path)},
                raw_input_reference=str(self.file_path),
            )
            fragments.append(fragment)

        logger.info("ATSAdapter: produced %d fragment(s).", len(fragments))
        return fragments
