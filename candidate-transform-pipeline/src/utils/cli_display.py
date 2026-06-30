"""
cli_display — centralised presentation layer.

All console output (banners, summaries, progress, schema) is defined
here. Zero business logic. Import and call from main.py only.
"""

from pathlib import Path
from typing import Dict, List, Optional

import typer

from src.utils.constants import PIPELINE_VERSION

_W = 70
SEP = "=" * _W
LINE = "─" * _W


# ── Banner ────────────────────────────────────────────────────────

def banner(verbose: bool = False) -> None:
    """Startup banner — call once per command invocation."""
    mode = "Verbose" if verbose else "Normal"
    typer.echo(SEP)
    typer.echo(_c("Candidate Data Transformation Pipeline"))
    typer.echo(_c("Eightfold AI Assignment"))
    typer.echo(SEP)
    typer.echo(f"Version        : {PIPELINE_VERSION}")
    typer.echo(f"Architecture   : Enterprise Modular ETL Pipeline")
    typer.echo(f"Execution Mode : {mode}")
    typer.echo(SEP)


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

    typer.echo(SEP)
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


# ── Pipeline statistics ───────────────────────────────────────────

def pipeline_statistics(
    fragments_loaded: int,
    canonical_candidates: int,
    identity_clusters: int,
    merge_decisions: int,
    overall_confidence: float,
    warnings: int,
    errors: int,
    execution_time_ms: int,
) -> None:
    """Display the final pipeline execution statistics."""
    typer.echo(f"\n{SEP}")
    typer.echo("  Pipeline Statistics")
    typer.echo(LINE)
    typer.echo(_dot("  Fragments Loaded",            str(fragments_loaded)))
    typer.echo(_dot("  Canonical Candidates",       str(canonical_candidates)))
    typer.echo(_dot("  Identity Clusters",          str(identity_clusters)))
    typer.echo(_dot("  Merge Decisions",            str(merge_decisions)))
    typer.echo(_dot("  Overall Confidence",         f"{overall_confidence:.2f}"))
    typer.echo("")
    typer.echo("  Confidence Computed From")
    typer.echo("  ✓ Source Reliability")
    typer.echo("  ✓ Source Agreement")
    typer.echo("  ✓ Similarity Score")
    typer.echo("  ✓ Conflict Penalty")
    typer.echo("")
    typer.echo(_dot("  Warnings",                   str(warnings)))
    typer.echo(_dot("  Errors",                     str(errors)))
    typer.echo(_dot("  Execution Time",             f"{execution_time_ms} ms"))
    typer.echo(SEP)


# ── Output summary ────────────────────────────────────────────────

def output_summary(count: int, output_dir: Path, filenames: List[str], overall_confidence: float) -> None:
    typer.echo(f"\n{SEP}")
    typer.echo("  Pipeline Completed Successfully")
    typer.echo(LINE)
    typer.echo(f"  Canonical Candidates   {count}")
    typer.echo(f"  Overall Confidence     {overall_confidence:.2f}")
    typer.echo("")
    typer.echo("  Confidence Computed From")
    typer.echo("  ✓ Source Reliability")
    typer.echo("  ✓ Source Agreement")
    typer.echo("  ✓ Similarity Score")
    typer.echo("  ✓ Conflict Penalty")
    typer.echo("")
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
    ]),
    ("Contact", [
        ("email",       "Emails"),
        ("phone",       "Phones"),
    ]),
    ("Professional", [
        ("skills",          "Skills"),
        ("experience",      "Experience"),
        ("current_company", "Current Company"),
        ("projects",        "Projects"),
    ]),
    ("Links", [
        ("github",    "GitHub"),
        ("portfolio", "Portfolio"),
    ]),
    ("Metadata", [
        ("confidence",   "Confidence"),
        ("provenance",   "Provenance"),
    ]),
]


def inspect_schema() -> None:
    typer.echo(f"\n{SEP}")
    typer.echo("  Canonical Candidate Schema")
    typer.echo(SEP)
    counter = 1
    for group, fields in _SCHEMA:
        typer.echo(f"\n{group}")
        for key, label in fields:
            typer.echo(f"{counter:>2}. {label}")
            counter += 1
    typer.echo(SEP + "\n")


# ── Test runner helpers ───────────────────────────────────────────

def test_suite_header() -> None:
    typer.echo(f"\n{SEP}")
    typer.echo("  Candidate Pipeline Test Suite")
    typer.echo(SEP)


def test_case_result(
    name: str,
    scenario: str,
    expected: str,
    passed: bool,
    fragments_loaded: int,
    canonical_candidates: int,
    identity_clusters: int,
    merge_decisions: int,
    overall_confidence: float,
    schema_validation: str,
    execution_time_ms: int,
    failures: List[str],
    warnings: List[str],
    errors: List[str],
) -> None:
    short = name.replace("_", " — ", 1)
    status = "PASS ✓" if passed else "FAIL ✗"
    typer.echo(SEP)
    typer.echo(f"{short}")
    typer.echo(SEP)
    typer.echo("Scenario")
    typer.echo(f"{scenario}")
    typer.echo("")
    typer.echo("Expected Behaviour")
    typer.echo(f"{expected}")
    typer.echo("")
    typer.echo("Actual Result")
    typer.echo(f"✓ Fragments Loaded          : {fragments_loaded}")
    typer.echo(f"✓ Canonical Candidates      : {canonical_candidates}")
    typer.echo(f"✓ Identity Clusters         : {identity_clusters}")
    typer.echo(f"✓ Merge Decisions           : {merge_decisions}")
    typer.echo(f"✓ Overall Confidence        : {overall_confidence:.2f}")
    typer.echo("  Confidence Computed From")
    typer.echo("  ✓ Source Reliability")
    typer.echo("  ✓ Source Agreement")
    typer.echo("  ✓ Similarity Score")
    typer.echo("  ✓ Conflict Penalty")
    typer.echo(f"✓ Schema Validation         : {schema_validation}")
    typer.echo(f"✓ Execution Time            : {execution_time_ms} ms")
    for w in warnings[:2]:
        typer.echo(f"  ⚠ Warning  : {w}")
    for e in errors[:2]:
        typer.echo(f"  ✗ Error    : {e}")
    for f in failures[:3]:
        typer.echo(f"  ✗ Mismatch : {f}")
    typer.echo("")
    typer.echo("Final Result")
    typer.echo(status)
    typer.echo("------------------------------------------------------------")


def test_suite_summary(
    total: int,
    passed: int,
    failed: int,
    canonical_candidates: int,
    avg_execution_time_ms: int,
) -> None:
    success_rate = int((passed / total) * 100) if total > 0 else 0
    typer.echo(f"\n{SEP}")
    typer.echo("Candidate Pipeline Test Summary")
    typer.echo(SEP)
    typer.echo(_dot("Tests Executed", str(total)))
    typer.echo(_dot("Passed",         str(passed)))
    typer.echo(_dot("Failed",         str(failed)))
    typer.echo(_dot("Success Rate",   f"{success_rate}%"))
    typer.echo(_dot("Canonical Candidates", str(canonical_candidates)))
    typer.echo(_dot("Average Execution Time", f"{avg_execution_time_ms} ms"))
    typer.echo(SEP)
    typer.echo("Overall Result")
    if failed == 0:
        typer.echo("✓ ALL TESTS PASSED")
    else:
        typer.echo("✗ SOME TESTS FAILED")
    typer.echo(SEP)


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
