"""
cli_display — centralised presentation layer.

All console output (banners, summaries, progress, schema) is defined
here. Zero business logic. Import and call from main.py only.
"""

from pathlib import Path
from typing import Dict, List, Optional

import typer

from src.utils.constants import PIPELINE_VERSION

_W = 62
SEP = "=" * _W
LINE = "─" * _W


# ── Banner ────────────────────────────────────────────────────────

def banner() -> None:
    """Startup banner — call once per command invocation."""
    typer.echo(f"\n{SEP}")
    typer.echo(_c("Candidate Data Transformation Pipeline"))
    typer.echo(_c("Eightfold AI Assignment"))
    typer.echo(SEP)
    typer.echo(f"  Version        : {PIPELINE_VERSION}")
    typer.echo(f"  Architecture   : Enterprise Modular ETL Pipeline")
    typer.echo(f"  Sources        :")
    typer.echo(f"    ✓  Recruiter CSV")
    typer.echo(f"    ✓  ATS JSON")
    typer.echo(f"    ✓  Resume PDF")
    typer.echo(f"    ✓  GitHub Mock")
    typer.echo(SEP + "\n")


# ── Bundled dataset preview (before loading) ──────────────────────

def bundled_dataset_preview(
    csv_path: Path,
    ats_path: Path,
    resumes_dir: Path,
    github_dir: Path,
) -> None:
    """Show which default-input files are present, before loading them."""
    resume_n = len(list(resumes_dir.glob("*.pdf"))) if resumes_dir.exists() else 0
    github_n = len(list(github_dir.glob("*.json"))) if github_dir.exists() else 0

    typer.echo(f"{SEP}")
    typer.echo("  Loading bundled demonstration dataset...")
    typer.echo(LINE)
    _src_row("recruiter.csv",                            csv_path.exists())
    _src_row("ats.json",                                 ats_path.exists())
    _src_row(f"Resume PDFs        ({resume_n} files)",   resume_n > 0)
    _src_row(f"GitHub Profiles    ({github_n} profiles)", github_n > 0)
    typer.echo(SEP)


# ── Dataset summary (after loading) ──────────────────────────────

def dataset_summary(
    csv_count: int,
    ats_count: int,
    resume_count: int,
    github_count: int,
) -> None:
    total = csv_count + ats_count + resume_count + github_count
    typer.echo(f"\n{SEP}")
    typer.echo("  Dataset Summary")
    typer.echo(LINE)
    typer.echo(_dot("  Recruiter CSV",       f"{csv_count} records"))
    typer.echo(_dot("  ATS JSON",            f"{ats_count} records"))
    typer.echo(_dot("  Resume PDFs",         f"{resume_count} files"))
    typer.echo(_dot("  GitHub Profiles",     f"{github_count} profiles"))
    typer.echo(f"  {LINE}")
    typer.echo(_dot("  Total Candidate Fragments", str(total)))
    typer.echo(SEP)


# ── Pipeline progress ─────────────────────────────────────────────

def pipeline_heading() -> None:
    typer.echo(f"\n{SEP}")
    typer.echo("  Running Pipeline")
    typer.echo(SEP)


def step_done(label: str, detail: str = "") -> None:
    suffix = f"  —  {detail}" if detail else ""
    typer.echo(f"  ✓  {label}{suffix}")


def step_waiting(label: str, detail: str = "") -> None:
    suffix = f"  —  {detail}" if detail else ""
    typer.echo(f"  ⋯  {label}{suffix}")


# ── Identity resolution summary ───────────────────────────────────

def ir_summary(total_fragments: int, num_clusters: int) -> None:
    merged = max(0, total_fragments - num_clusters)
    typer.echo(f"\n{SEP}")
    typer.echo("  Identity Resolution Complete")
    typer.echo(LINE)
    typer.echo(_dot("  Input Fragments",            str(total_fragments)))
    typer.echo(_dot("  Canonical Candidates",       str(num_clusters)))
    typer.echo(_dot("  Duplicate Fragments Merged", str(merged)))
    typer.echo(SEP)


# ── Output summary ────────────────────────────────────────────────

def output_summary(count: int, output_dir: Path, filenames: List[str]) -> None:
    typer.echo(f"\n{SEP}")
    typer.echo("  Pipeline Completed Successfully")
    typer.echo(LINE)
    typer.echo(f"  Canonical Candidates   {count}")
    typer.echo(f"  Output Folder          {output_dir}/")
    typer.echo("  Files Generated")
    for name in filenames[:10]:
        typer.echo(f"    {name}")
    if len(filenames) > 10:
        typer.echo(f"    ... and {len(filenames) - 10} more")
    typer.echo(SEP + "\n")


# ── Inspect schema ────────────────────────────────────────────────

_SCHEMA: List[tuple] = [
    ("Personal Information", [
        ("full_name",      "Full Name"),
        ("first_name",     "First Name"),
        ("last_name",      "Last Name"),
        ("date_of_birth",  "Date of Birth"),
        ("gender",         "Gender"),
        ("nationality",    "Nationality"),
    ]),
    ("Contact", [
        ("email",       "Email"),
        ("phone",       "Phone"),
        ("address",     "Address"),
        ("city",        "City"),
        ("state",       "State"),
        ("country",     "Country"),
        ("postal_code", "Postal Code"),
    ]),
    ("Professional", [
        ("current_title",   "Current Title"),
        ("current_company", "Current Company"),
        ("skills",          "Skills"),
        ("experience",      "Experience"),
        ("education",       "Education"),
        ("projects",        "Projects"),
    ]),
    ("Links", [
        ("linkedin",  "LinkedIn"),
        ("github",    "GitHub"),
        ("portfolio", "Portfolio"),
    ]),
    ("Metadata", [
        ("candidate_id", "Candidate ID"),
        ("confidence",   "Confidence Score"),
        ("provenance",   "Provenance Records"),
    ]),
]


def inspect_schema() -> None:
    typer.echo(f"\n{SEP}")
    typer.echo("  Canonical Candidate Schema")
    typer.echo(SEP)
    counter = 1
    for group, fields in _SCHEMA:
        typer.echo(f"\n  {group}")
        for key, label in fields:
            typer.echo(f"    {counter:>2}.  {label}  ({key})")
            counter += 1
    typer.echo(f"\n{SEP}\n")


# ── Test runner helpers ───────────────────────────────────────────

def test_suite_header() -> None:
    typer.echo(f"\n{SEP}")
    typer.echo("  Candidate Pipeline Test Suite")
    typer.echo(SEP)


def test_case_result(
    name: str,
    scenario: str,
    expected: str,
    actual: str,
    passed: bool,
    failures: List[str],
    warnings: List[str],
    errors: List[str],
) -> None:
    short = name.replace("_", " — ", 1)  # TC01_HappyPath → TC01 — HappyPath
    status = "PASS  ✓" if passed else "FAIL  ✗"
    typer.echo(f"\n  {short}")
    typer.echo(f"  {LINE}")
    typer.echo(f"  Scenario   : {scenario}")
    typer.echo(f"  Expected   : {expected}")
    typer.echo(f"  Actual     : {actual}")
    for w in warnings[:2]:
        typer.echo(f"  ⚠ Warning  : {w}")
    for e in errors[:2]:
        typer.echo(f"  ✗ Error    : {e}")
    for f in failures[:3]:
        typer.echo(f"  ✗ Mismatch : {f}")
    typer.echo(f"  Result     : {status}")


def test_suite_summary(total: int, passed: int, failed: int) -> None:
    overall = "PASS" if failed == 0 else "FAIL"
    typer.echo(f"\n{SEP}")
    typer.echo("  Summary")
    typer.echo(LINE)
    typer.echo(_dot("  Tests Executed", str(total)))
    typer.echo(_dot("  Passed",         str(passed)))
    typer.echo(_dot("  Failed",         str(failed)))
    typer.echo(_dot("  Overall Result", overall))
    typer.echo(SEP + "\n")


# ── Internal helpers ──────────────────────────────────────────────

def _c(text: str) -> str:
    """Centre text within banner width."""
    return text.center(_W)


def _src_row(label: str, ok: bool) -> None:
    mark = "✓" if ok else "✗"
    typer.echo(f"  {mark}  {label}")


def _dot(label: str, value: str) -> str:
    available = _W - len(label) - len(value) - 1
    dots = "." * max(1, available)
    return f"{label} {dots} {value}"
