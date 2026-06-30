"""
ResumeAdapter — extracts candidate data from PDF resumes using pdfplumber.

Uses deterministic regex-based section parsing. No OCR, no LLM, no spaCy.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber

from src.adapters.base_adapter import BaseAdapter
from src.models.candidate_fragment import CandidateFragment
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?\d[\d\s\-().]{7,}\d)"
)
_URL_RE = re.compile(r"https?://[^\s]+")
_GITHUB_RE = re.compile(r"github\.com/([A-Za-z0-9\-]+)", re.IGNORECASE)
_LINKEDIN_RE = re.compile(r"linkedin\.com/in/([A-Za-z0-9\-]+)", re.IGNORECASE)

# Section header keywords (case-insensitive).
_SECTION_HEADERS = [
    "education",
    "experience",
    "work experience",
    "professional experience",
    "projects",
    "skills",
    "technical skills",
    "summary",
    "objective",
    "certifications",
    "awards",
    "publications",
    "languages",
]
_HEADER_RE = re.compile(
    r"^(?:" + "|".join(re.escape(h) for h in _SECTION_HEADERS) + r")\s*[:\-]?\s*$",
    re.IGNORECASE,
)


class ResumeAdapter(BaseAdapter):
    """
    Adapter for ingesting candidate data from PDF resumes.

    Uses pdfplumber for text extraction and deterministic regex patterns
    to identify candidate fields. No ML or NLP dependencies.
    """

    def __init__(self, file_path: Path) -> None:
        """
        Args:
            file_path: Path to the PDF resume file.
        """
        self.file_path = Path(file_path)

    # ------------------------------------------------------------------
    # Public adapter methods
    # ------------------------------------------------------------------

    def load(self) -> str:
        """
        Open the PDF and extract all text via pdfplumber.

        Returns:
            Full extracted text from all pages, joined by newlines.

        Raises:
            FileNotFoundError: If the PDF does not exist.
            ValueError: If no text could be extracted.
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"Resume PDF not found: {self.file_path}")

        pages: List[str] = []
        with pdfplumber.open(self.file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)

        if not pages:
            raise ValueError(f"Could not extract text from PDF: {self.file_path}")

        full_text = "\n".join(pages)
        logger.info(
            "ResumeAdapter: extracted %d chars from %s.", len(full_text), self.file_path
        )
        return full_text

    def parse(self, raw_data: str) -> Dict[str, Any]:
        """
        Parse extracted PDF text into structured resume sections.

        Args:
            raw_data: Raw text returned by ``load()``.

        Returns:
            Dictionary with keys: ``full_name``, ``email``, ``phone``,
            ``github``, ``linkedin``, ``skills``, ``education_raw``,
            ``experience_raw``, ``projects_raw``, ``summary_raw``.
        """
        lines = [line.strip() for line in raw_data.splitlines()]
        non_empty = [l for l in lines if l]

        result: Dict[str, Any] = {
            "full_name": self._extract_name(non_empty),
            "email": self._extract_email(raw_data),
            "phone": self._extract_phone(raw_data),
            "github": self._extract_github(raw_data),
            "linkedin": self._extract_linkedin(raw_data),
            "skills": self._extract_skills_section(lines),
            "education_raw": self._extract_section(lines, {"education"}),
            "experience_raw": self._extract_section(
                lines, {"experience", "work experience", "professional experience"}
            ),
            "projects_raw": self._extract_section(lines, {"projects"}),
            "summary_raw": self._extract_section(lines, {"summary", "objective"}),
        }
        return result

    def to_candidate_fragment(
        self, parsed_data: Dict[str, Any]
    ) -> List[CandidateFragment]:
        """
        Convert the parsed resume dict into a single CandidateFragment.

        Args:
            parsed_data: Structured dict returned by ``parse()``.

        Returns:
            A one-element list containing the CandidateFragment.
        """
        fragment = CandidateFragment(
            source="resume",
            extracted_fields=parsed_data,
            metadata={"file": str(self.file_path)},
            raw_input_reference=str(self.file_path),
        )
        logger.info("ResumeAdapter: produced 1 fragment from %s.", self.file_path)
        return [fragment]

    # ------------------------------------------------------------------
    # Private extraction helpers
    # ------------------------------------------------------------------

    def _extract_name(self, lines: List[str]) -> Optional[str]:
        """
        Heuristically extract the candidate name from the first non-empty lines.

        Strategy: the name is usually on one of the first three content lines,
        contains at least two words, and does not look like a section header,
        contact info, or URL.
        """
        for line in lines[:5]:
            if _EMAIL_RE.search(line):
                continue
            if _PHONE_RE.search(line):
                continue
            if _URL_RE.search(line):
                continue
            if _HEADER_RE.match(line):
                continue
            words = line.split()
            if 2 <= len(words) <= 5 and all(
                w[0].isupper() or w[0] == "." for w in words if w
            ):
                return line
        return None

    def _extract_email(self, text: str) -> Optional[str]:
        """Return the first email address found in the text."""
        match = _EMAIL_RE.search(text)
        return match.group(0).lower() if match else None

    def _extract_phone(self, text: str) -> Optional[str]:
        """Return the first phone number found in the text."""
        match = _PHONE_RE.search(text)
        return match.group(0).strip() if match else None

    def _extract_github(self, text: str) -> Optional[str]:
        """Return the full GitHub profile URL if present."""
        match = _GITHUB_RE.search(text)
        if match:
            return f"https://github.com/{match.group(1)}"
        return None

    def _extract_linkedin(self, text: str) -> Optional[str]:
        """Return the full LinkedIn profile URL if present."""
        match = _LINKEDIN_RE.search(text)
        if match:
            return f"https://www.linkedin.com/in/{match.group(1)}"
        return None

    def _extract_section(
        self, lines: List[str], header_variants: set
    ) -> List[str]:
        """
        Extract all lines belonging to a named section.

        Args:
            lines: All lines from the document.
            header_variants: Set of lowercase section header names to match.

        Returns:
            List of content lines found within the section.
        """
        content: List[str] = []
        in_section = False

        for line in lines:
            lower = line.lower().strip().rstrip(":").rstrip("-").strip()
            if lower in header_variants:
                in_section = True
                continue
            if in_section:
                # Stop at the next recognised section header.
                if _HEADER_RE.match(line) and lower not in header_variants:
                    break
                if line:
                    content.append(line)

        return content

    def _extract_skills_section(self, lines: List[str]) -> List[str]:
        """
        Extract skill tokens from the Skills section.

        Handles both comma-separated and bullet-separated formats.

        Returns:
            Deduplicated list of skill strings.
        """
        raw_lines = self._extract_section(
            lines, {"skills", "technical skills", "core competencies"}
        )
        skills: List[str] = []
        for line in raw_lines:
            # Split on common delimiters.
            parts = re.split(r"[,|•·\t]+", line)
            for part in parts:
                skill = part.strip().strip("–-").strip()
                if skill and len(skill) < 60:
                    skills.append(skill)
        # Deduplicate while preserving order.
        seen: set = set()
        unique: List[str] = []
        for s in skills:
            if s.lower() not in seen:
                seen.add(s.lower())
                unique.append(s)
        return unique
