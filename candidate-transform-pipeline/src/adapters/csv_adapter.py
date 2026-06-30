"""
CSVAdapter — loads candidate data from CSV files using pandas.

Each row in the CSV is treated as one CandidateFragment.
"""

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from src.adapters.base_adapter import BaseAdapter
from src.models.candidate_fragment import CandidateFragment
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Mapping from CSV column names to canonical extracted_fields keys.
# Extend this mapping to support additional column name variants.
_CSV_FIELD_MAP: Dict[str, str] = {
    "full_name": "full_name",
    "name": "full_name",
    "first_name": "first_name",
    "last_name": "last_name",
    "email": "email",
    "email_address": "email",
    "phone": "phone",
    "phone_number": "phone",
    "skills": "skills",
    "education": "education",
    "experience": "experience",
    "github": "github",
    "github_url": "github",
    "linkedin": "linkedin",
    "linkedin_url": "linkedin",
    "city": "city",
    "location": "city",
    "country": "country",
    "title": "current_title",
    "current_title": "current_title",
    "company": "current_company",
    "current_company": "current_company",
    "summary": "summary",
}


class CSVAdapter(BaseAdapter):
    """
    Adapter for ingesting candidate records from CSV files.

    Each row in the CSV corresponds to one CandidateFragment.
    Column names are normalised via ``_CSV_FIELD_MAP`` before being
    stored in ``extracted_fields``.
    """

    def __init__(self, file_path: Path) -> None:
        """
        Args:
            file_path: Path to the CSV source file.
        """
        self.file_path = Path(file_path)

    def load(self) -> pd.DataFrame:
        """
        Read the CSV file into a pandas DataFrame.

        Returns:
            DataFrame containing all rows from the CSV.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the CSV is empty.
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.file_path}")

        df = pd.read_csv(self.file_path, dtype=str, keep_default_na=False)
        if df.empty:
            raise ValueError(f"CSV file is empty: {self.file_path}")

        logger.info("CSVAdapter: loaded %d rows from %s.", len(df), self.file_path)
        return df

    def parse(self, raw_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Normalise column names and convert each DataFrame row to a dict.

        Args:
            raw_data: DataFrame returned by ``load()``.

        Returns:
            List of row dictionaries with canonicalised field keys.
        """
        rows: List[Dict[str, Any]] = []
        for _, row in raw_data.iterrows():
            record: Dict[str, Any] = {}
            for col, value in row.items():
                key = str(col).strip().lower().replace(" ", "_")
                canonical_key = _CSV_FIELD_MAP.get(key, key)
                # Treat empty strings as None for clean downstream handling.
                record[canonical_key] = None if value == "" else value
            rows.append(record)
        return rows

    def to_candidate_fragment(
        self, parsed_data: List[Dict[str, Any]]
    ) -> List[CandidateFragment]:
        """
        Convert parsed CSV rows into CandidateFragment objects.

        Skills are split on commas if supplied as a delimited string.

        Args:
            parsed_data: List of row dicts from ``parse()``.

        Returns:
            List of CandidateFragment instances.
        """
        fragments: List[CandidateFragment] = []
        for idx, row in enumerate(parsed_data):
            fields = dict(row)

            # Split comma-separated skills into a list.
            raw_skills = fields.get("skills")
            if isinstance(raw_skills, str):
                fields["skills"] = [s.strip() for s in raw_skills.split(",") if s.strip()]

            fragment = CandidateFragment(
                source="csv",
                extracted_fields=fields,
                metadata={"row_index": idx, "file": str(self.file_path)},
                raw_input_reference=str(self.file_path),
            )
            fragments.append(fragment)

        logger.info("CSVAdapter: produced %d fragment(s).", len(fragments))
        return fragments
