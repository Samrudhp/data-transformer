"""
GitHubAdapter — loads candidate data from a mock GitHub JSON file.

No live API calls are made. The adapter reads a local JSON file that
mirrors the GitHub REST API response format.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.adapters.base_adapter import BaseAdapter
from src.models.candidate_fragment import CandidateFragment
from src.utils.logger import get_logger

logger = get_logger(__name__)


class GitHubAdapter(BaseAdapter):
    """
    Adapter for ingesting candidate data from a mock GitHub JSON file.

    The JSON file should mirror the GitHub API profile response, optionally
    augmented with a ``"repositories"`` list and ``"languages"`` mapping.

    No internet connectivity is required.
    """

    def __init__(self, username: str, api_token: Optional[str] = None) -> None:
        """
        Args:
            username: GitHub username — used to locate the mock JSON file at
                      ``test_cases/<username>_github.json`` relative to the
                      project root, or as a file path directly if it resolves
                      to an existing file.
            api_token: Ignored in mock mode; retained for interface compatibility.
        """
        self.username = username
        self.api_token = api_token
        # Resolve the mock file path.
        candidate_path = Path(username)
        if candidate_path.exists() and candidate_path.suffix == ".json":
            self.file_path: Optional[Path] = candidate_path
        else:
            self.file_path = None

    def load(self) -> Dict[str, Any]:
        """
        Read the mock GitHub JSON file from disk.

        Returns:
            Parsed JSON dict representing the GitHub profile.

        Raises:
            FileNotFoundError: If no mock file can be located.
            ValueError: If the file contains invalid JSON.
        """
        if self.file_path is None or not self.file_path.exists():
            raise FileNotFoundError(
                f"GitHub mock file not found for username='{self.username}'. "
                "Pass the full path as the ``username`` argument."
            )
        with self.file_path.open("r", encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON in GitHub mock file {self.file_path}: {exc}"
                ) from exc

        logger.info("GitHubAdapter: loaded mock data from %s.", self.file_path)
        return data  # type: ignore[return-value]

    def parse(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map GitHub API fields to canonical fragment field names.

        Args:
            raw_data: Raw GitHub profile dict from ``load()``.

        Returns:
            Normalised dict with canonical field keys.
        """
        login: str = raw_data.get("login", self.username)
        name: Optional[str] = raw_data.get("name")
        bio: Optional[str] = raw_data.get("bio")
        location: Optional[str] = raw_data.get("location")
        email: Optional[str] = raw_data.get("email")
        blog: Optional[str] = raw_data.get("blog")
        github_url = f"https://github.com/{login}"

        # Aggregate languages from the optional ``repositories`` list.
        languages: List[str] = []
        for repo in raw_data.get("repositories", []):
            lang = repo.get("language")
            if lang and lang not in languages:
                languages.append(lang)

        # Support a flat ``languages`` mapping too (e.g. {Python: 12345}).
        for lang in raw_data.get("languages", {}).keys():
            if lang and lang not in languages:
                languages.append(lang)

        parsed: Dict[str, Any] = {
            "github_username": login,
            "github": github_url,
            "full_name": name,
            "email": email,
            "city": location,
            "summary": bio,
            "portfolio": blog if blog else None,
            "skills": languages,  # Programming languages as inferred skills.
        }
        return parsed

    def to_candidate_fragment(
        self, parsed_data: Dict[str, Any]
    ) -> List[CandidateFragment]:
        """
        Convert parsed GitHub data into a single CandidateFragment.

        Args:
            parsed_data: Normalised dict from ``parse()``.

        Returns:
            A one-element list containing the CandidateFragment.
        """
        fragment = CandidateFragment(
            source="github",
            extracted_fields=parsed_data,
            metadata={
                "github_username": self.username,
                "file": str(self.file_path),
            },
            raw_input_reference=str(self.file_path),
        )
        logger.info(
            "GitHubAdapter: produced 1 fragment for username '%s'.", self.username
        )
        return [fragment]
