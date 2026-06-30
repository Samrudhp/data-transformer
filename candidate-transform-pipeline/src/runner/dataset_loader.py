"""
DatasetLoader — discovers and loads all candidate fragments from an input directory.

Supports the default input/ folder structure:
    input/
        recruiter.csv       — recruiter spreadsheet (multiple rows)
        ats.json            — ATS export (array of candidates)
        resumes/            — folder of PDF resume files
        github/             — folder of GitHub mock JSON files
"""

from pathlib import Path
from typing import List, NamedTuple

import typer

from src.models.candidate_fragment import CandidateFragment
from src.utils.logger import get_logger

logger = get_logger(__name__)

_DOT = "."
_SEP = " "


class DatasetSummary(NamedTuple):
    csv_count: int
    ats_count: int
    resume_count: int
    github_count: int
    fragments: List[CandidateFragment]


def load_dataset(
    csv_path: Path,
    ats_path: Path,
    resumes_dir: Path,
    github_dir: Path,
    *,
    silent: bool = False,
) -> DatasetSummary:
    """
    Load all candidate fragments from the four source types.

    Args:
        csv_path:    Path to the recruiter CSV file.
        ats_path:    Path to the ATS JSON file.
        resumes_dir: Directory containing PDF resume files.
        github_dir:  Directory containing GitHub mock JSON files.
        silent:      Suppress echo output when True.

    Returns:
        DatasetSummary with fragment list and per-source counts.
    """
    from src.adapters.ats_adapter import ATSAdapter
    from src.adapters.csv_adapter import CSVAdapter
    from src.adapters.github_adapter import GitHubAdapter
    from src.adapters.resume_adapter import ResumeAdapter

    all_fragments: List[CandidateFragment] = []

    # ── Recruiter CSV ───────────────────────────────────────────────────────
    csv_count = 0
    if csv_path.exists():
        try:
            adapter = CSVAdapter(csv_path)
            raw = adapter.load()
            parsed = adapter.parse(raw)
            frags = adapter.to_candidate_fragment(parsed)
            all_fragments.extend(frags)
            csv_count = len(frags)
        except Exception as exc:
            logger.warning("DatasetLoader: CSV load error — %s", exc)
    else:
        logger.warning("DatasetLoader: CSV not found at %s — skipping.", csv_path)

    # ── ATS JSON ────────────────────────────────────────────────────────────
    ats_count = 0
    if ats_path.exists():
        try:
            adapter = ATSAdapter({"file_path": str(ats_path)})
            raw = adapter.load()
            parsed = adapter.parse(raw)
            frags = adapter.to_candidate_fragment(parsed)
            all_fragments.extend(frags)
            ats_count = len(frags)
        except Exception as exc:
            logger.warning("DatasetLoader: ATS load error — %s", exc)
    else:
        logger.warning("DatasetLoader: ATS not found at %s — skipping.", ats_path)

    # ── Resume PDFs ─────────────────────────────────────────────────────────
    resume_count = 0
    resume_files: List[Path] = []
    if resumes_dir.exists() and resumes_dir.is_dir():
        resume_files = sorted(resumes_dir.glob("*.pdf"))
        for pdf_path in resume_files:
            try:
                adapter = ResumeAdapter(pdf_path)
                raw = adapter.load()
                parsed = adapter.parse(raw)
                frags = adapter.to_candidate_fragment(parsed)
                all_fragments.extend(frags)
                resume_count += len(frags)
            except Exception as exc:
                logger.warning("DatasetLoader: resume '%s' error — %s", pdf_path.name, exc)
    else:
        logger.warning("DatasetLoader: resumes dir not found at %s — skipping.", resumes_dir)

    # ── GitHub JSON ─────────────────────────────────────────────────────────
    github_count = 0
    github_files: List[Path] = []
    if github_dir.exists() and github_dir.is_dir():
        github_files = sorted(github_dir.glob("*.json"))
        for gh_path in github_files:
            try:
                adapter = GitHubAdapter(username=str(gh_path))
                raw = adapter.load()
                parsed = adapter.parse(raw)
                frags = adapter.to_candidate_fragment(parsed)
                all_fragments.extend(frags)
                github_count += len(frags)
            except Exception as exc:
                logger.warning(
                    "DatasetLoader: github '%s' error — %s", gh_path.name, exc
                )
    else:
        logger.warning(
            "DatasetLoader: github dir not found at %s — skipping.", github_dir
        )

    if not silent:
        _print_load_summary(csv_count, ats_count, resume_count, github_count)

    return DatasetSummary(
        csv_count=csv_count,
        ats_count=ats_count,
        resume_count=resume_count,
        github_count=github_count,
        fragments=all_fragments,
    )


def _print_load_summary(
    csv_count: int, ats_count: int, resume_count: int, github_count: int
) -> None:
    """Print a formatted dataset ingestion summary table."""
    width = 44
    typer.echo("\n" + "=" * width)
    typer.echo("  Loading Default Input Dataset...")
    typer.echo("=" * width)
    typer.echo(_row("Recruiter CSV", csv_count, "Candidates"))
    typer.echo(_row("ATS JSON", ats_count, "Candidates"))
    typer.echo(_row("Resume PDFs", resume_count, "Files"))
    typer.echo(_row("GitHub Profiles", github_count, "Profiles"))
    typer.echo("=" * width)


def _row(label: str, count: int, unit: str) -> str:
    """Format one summary row with dot-fill alignment."""
    right = f"{count} {unit}"
    max_width = 40
    dots = max_width - len(label) - len(right)
    if dots < 1:
        dots = 1
    return f"  {label} {'.' * dots} {right}"
