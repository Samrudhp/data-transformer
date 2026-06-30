"""
CLI entrypoint for the candidate transformation pipeline.

Commands
--------
run       — Execute the complete pipeline end-to-end (interactive source selection).
inspect   — Display all available canonical candidate fields.
test      — Run all curated test cases in test_cases/.
validate  — Validate a candidate JSON file against the output schema.
version   — Print the current pipeline version.
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Optional

import typer

from src.config.config_loader import AppConfig, ConfigLoader
from src.models.canonical_candidate import CanonicalCandidate
from src.models.processing_context import ProcessingContext
from src.utils.constants import PIPELINE_VERSION
from src.utils.logger import get_logger

logger = get_logger(__name__)

app = typer.Typer(
    name="candidate-pipeline",
    help="Enterprise candidate data transformation pipeline.",
    add_completion=False,
)

# ---------------------------------------------------------------------------
# Default input directory layout
# ---------------------------------------------------------------------------

_DEFAULT_INPUT_DIR = Path("input")
_DEFAULT_CSV = _DEFAULT_INPUT_DIR / "recruiter.csv"
_DEFAULT_ATS = _DEFAULT_INPUT_DIR / "ats.json"
_DEFAULT_RESUMES = _DEFAULT_INPUT_DIR / "resumes"
_DEFAULT_GITHUB = _DEFAULT_INPUT_DIR / "github"
_DEFAULT_CONFIG_DIR = Path("configs")
_DEFAULT_OUTPUT_DIR = Path("output")


# ---------------------------------------------------------------------------
# Interactive source selection
# ---------------------------------------------------------------------------


def _prompt_source_selection() -> dict:
    """
    Display the Input Source Selection menu and return resolved paths.

    Returns a dict with keys: csv, ats, resumes_dir, github_dir.
    """
    typer.echo("\n" + "=" * 41)
    typer.echo("  Input Source Selection")
    typer.echo("=" * 41)
    typer.echo("  1. Use bundled demo dataset  (Recommended)")
    typer.echo("  2. Use my own input files")
    typer.echo("")

    choice = typer.prompt("  Your choice", default="1").strip()

    if choice == "2":
        return _prompt_custom_paths()

    # Default: mode 1
    return {
        "csv": _DEFAULT_CSV,
        "ats": _DEFAULT_ATS,
        "resumes_dir": _DEFAULT_RESUMES,
        "github_dir": _DEFAULT_GITHUB,
    }


def _prompt_custom_paths() -> dict:
    """Interactively collect and validate custom source file paths."""
    typer.echo("")
    typer.echo("  Please provide paths to your input files.")
    typer.echo("  Press Enter to skip a source (at least one is required).")
    typer.echo("")

    def _ask_file(label: str, default: str = "") -> Optional[Path]:
        raw = typer.prompt(f"  {label}", default=default).strip()
        if not raw:
            return None
        p = Path(raw)
        if not p.exists():
            typer.echo(f"  [!] Path not found: {p} — skipping this source.")
            return None
        return p

    def _ask_dir(label: str, default: str = "") -> Optional[Path]:
        raw = typer.prompt(f"  {label}", default=default).strip()
        if not raw:
            return None
        p = Path(raw)
        if not p.is_dir():
            typer.echo(f"  [!] Directory not found: {p} — skipping this source.")
            return None
        return p

    csv_path = _ask_file("Recruiter CSV path")
    ats_path = _ask_file("ATS JSON path")
    resumes_dir = _ask_dir("Resume folder path (contains .pdf files)")
    github_dir = _ask_dir("GitHub folder path (contains .json files)")

    return {
        "csv": csv_path,
        "ats": ats_path,
        "resumes_dir": resumes_dir,
        "github_dir": github_dir,
    }


# ---------------------------------------------------------------------------
# Post-pipeline projection selection
# ---------------------------------------------------------------------------


def _prompt_projection_target(
    candidates: List[CanonicalCandidate],
) -> List[CanonicalCandidate]:
    """
    Ask the user whether to project all candidates or select one.

    Returns the list of candidates to apply projection to.
    """
    count = len(candidates)
    typer.echo("\n" + "=" * 41)
    typer.echo("  Pipeline Complete")
    typer.echo(f"  Generated {count} Canonical Candidate(s)")
    typer.echo("=" * 41)

    if count == 1:
        return candidates

    typer.echo("")
    typer.echo("  Apply Projection To:")
    typer.echo("  1. All Candidates")
    typer.echo("  2. Select One Candidate")
    typer.echo("")
    choice = typer.prompt("  Your choice", default="1").strip()

    if choice != "2":
        return candidates

    # Show candidate list.
    typer.echo("")
    for i, c in enumerate(candidates, start=1):
        name = c.personal_info.full_name or c.candidate_id
        typer.echo(f"  {i}. {name}")
    typer.echo("")

    raw = typer.prompt("  Select candidate number", default="1").strip()
    try:
        idx = int(raw) - 1
        if 0 <= idx < count:
            return [candidates[idx]]
        typer.echo("  [!] Invalid number — defaulting to all candidates.")
    except ValueError:
        typer.echo("  [!] Invalid input — defaulting to all candidates.")

    return candidates


# ---------------------------------------------------------------------------
# Output writer
# ---------------------------------------------------------------------------


def _write_outputs(
    projected_list: List[dict],
    candidates: List[CanonicalCandidate],
    output_dir: Path,
    dry_run: bool,
) -> None:
    """Write projected candidate dicts to output JSON files."""
    if dry_run:
        typer.echo("\n  → Dry-run mode: output not written to disk.")
        for proj in projected_list[:1]:
            preview = json.dumps(proj, indent=2, default=str)
            typer.echo(preview[:1200] + ("…" if len(preview) > 1200 else ""))
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    for i, (proj, cand) in enumerate(zip(projected_list, candidates), start=1):
        filename = f"candidate_{i:03d}.json"
        out_file = output_dir / filename
        out_file.write_text(
            json.dumps(proj, indent=2, default=str), encoding="utf-8"
        )
    typer.echo(f"\n  → {len(projected_list)} file(s) written to: {output_dir}/")


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@app.command()
def run(
    config_dir: Path = typer.Option(
        _DEFAULT_CONFIG_DIR,
        "--config-dir",
        "-c",
        help="Directory containing pipeline.yaml, resolver.yaml, confidence.yaml.",
    ),
    output_dir: Path = typer.Option(
        _DEFAULT_OUTPUT_DIR,
        "--output-dir",
        "-o",
        help="Directory where the final JSON output files will be written.",
    ),
    dry_run: Optional[bool] = typer.Option(
        None,
        "--dry-run",
        flag_value=True,
        help="Run the pipeline without writing output to disk.",
    ),
    no_wizard: Optional[bool] = typer.Option(
        None,
        "--no-wizard",
        flag_value=True,
        help="Skip the interactive projection wizard (output all fields).",
    ),
) -> None:
    """
    Run the complete candidate transformation pipeline.

    Interactively asks whether to use the bundled demo dataset or custom
    input files. Runs identity resolution, merge, and confidence scoring
    across all candidates. Launches the Projection Wizard.
    """
    from src.projection.projection_service import ProjectionService
    from src.runner.dataset_loader import load_dataset
    from src.runner.multi_candidate_runner import run_multi_candidate_pipeline

    start_total = time.time()

    # ── 1. Source selection ──────────────────────────────────────────────────
    paths = _prompt_source_selection()

    csv_path = paths.get("csv") or Path("/nonexistent_csv")
    ats_path = paths.get("ats") or Path("/nonexistent_ats")
    resumes_dir = paths.get("resumes_dir") or Path("/nonexistent_resumes")
    github_dir = paths.get("github_dir") or Path("/nonexistent_github")

    # ── 2. Load configuration ────────────────────────────────────────────────
    try:
        config = ConfigLoader(config_dir).load()
    except Exception as exc:
        typer.echo(f"\n  [ERROR] Failed to load config: {exc}", err=True)
        raise typer.Exit(code=1)

    # ── 3. Load fragments ────────────────────────────────────────────────────
    summary = load_dataset(
        csv_path=csv_path,
        ats_path=ats_path,
        resumes_dir=resumes_dir,
        github_dir=github_dir,
    )
    fragments = summary.fragments

    if not fragments:
        typer.echo("\n  [ERROR] No candidate fragments loaded. Aborting.", err=True)
        raise typer.Exit(code=1)

    # ── 4. Multi-candidate pipeline run ──────────────────────────────────────
    candidates, warnings, errors = run_multi_candidate_pipeline(fragments, config)

    if not candidates:
        typer.echo("\n  [ERROR] Pipeline produced no canonical candidates.", err=True)
        if errors:
            for e in errors[:5]:
                typer.echo(f"    • {e}", err=True)
        raise typer.Exit(code=1)

    if warnings:
        typer.echo(f"\n  ⚠  {len(warnings)} warning(s) during processing.")

    # ── 5. Projection target selection ───────────────────────────────────────
    target_candidates = _prompt_projection_target(candidates)

    # ── 6. Projection wizard ─────────────────────────────────────────────────
    if no_wizard:
        from src.models.projection_request import ProjectionRequest
        request = ProjectionRequest()
    else:
        typer.echo("\n  → Launching Projection Wizard...")
        from src.projection.wizard import run_wizard
        request = run_wizard()

    # ── 7. Apply projection ──────────────────────────────────────────────────
    from src.validation.schema_validator import SchemaValidator
    from jsonschema import ValidationError

    svc = ProjectionService()
    schema_validator = SchemaValidator()
    projected_list = []

    for cand in target_candidates:
        try:
            projected = svc.project(cand, request)
        except KeyError as exc:
            typer.echo(f"  [ERROR] Projection failed for {cand.candidate_id}: {exc}", err=True)
            continue

        # Schema validation per candidate.
        try:
            schema_validator.validate(projected)
        except ValidationError as exc:
            typer.echo(
                f"  ⚠  Schema warning for {cand.candidate_id}: {exc.message}"
            )

        projected_list.append(projected)

    if not projected_list:
        typer.echo("\n  [ERROR] No candidates survived projection.", err=True)
        raise typer.Exit(code=1)

    # ── 8. Write outputs ─────────────────────────────────────────────────────
    _write_outputs(projected_list, target_candidates, output_dir, dry_run)

    elapsed = time.time() - start_total
    typer.echo(f"\n  ✓ Pipeline completed in {elapsed:.2f}s")
    typer.echo("=" * 41 + "\n")


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


@app.command()
def inspect() -> None:
    """Display all available canonical candidate fields."""
    from src.models.canonical_candidate import (
        CanonicalCandidate,
        ContactInfo,
        Education,
        Experience,
        Links,
        PersonalInfo,
        Project,
    )
    from src.projection.projection_service import FIELD_DISPLAY_NAMES, _TOP_LEVEL_FIELDS

    typer.echo("\n" + "=" * 60)
    typer.echo("  Canonical Candidate Fields")
    typer.echo("=" * 60)

    section_models = {
        "personal_info": PersonalInfo,
        "contact": ContactInfo,
        "education": Education,
        "experience": Experience,
        "projects": Project,
        "links": Links,
    }

    for field in _TOP_LEVEL_FIELDS:
        label = FIELD_DISPLAY_NAMES.get(field, field)
        typer.echo(f"\n  {label}  ({field})")
        if field in section_models:
            model = section_models[field]
            for sub_field, info in model.model_fields.items():
                annotation = str(info.annotation).replace("typing.", "")
                typer.echo(f"    ├── {sub_field}: {annotation}")
        elif field == "skills":
            typer.echo("    ├── List[str]")
        elif field == "confidence":
            typer.echo("    ├── value: float")
            typer.echo("    ├── confidence_scores: Dict[str, float]")
            typer.echo("    ├── supporting_sources: List[str]")
            typer.echo("    └── reasons: List[str]")

    typer.echo("\n" + "=" * 60 + "\n")


# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------


@app.command()
def test(
    test_cases_dir: Path = typer.Option(
        Path("test_cases"),
        "--dir",
        help="Directory containing curated test case inputs.",
    ),
    config_dir: Path = typer.Option(
        Path("configs"),
        "--config-dir",
        help="Configuration directory.",
    ),
) -> None:
    """
    Run all curated end-to-end test cases and print PASS/FAIL results.

    Uses only the data in test_cases/ — never touches the default input/ folder.
    """
    from src.tests.test_runner import run_all_test_cases

    run_all_test_cases(test_cases_dir=test_cases_dir, config_dir=config_dir)


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


@app.command()
def validate(
    input_file: Path = typer.Argument(
        ...,
        help="Path to a candidate JSON file to validate against the output schema.",
    ),
) -> None:
    """Validate a candidate JSON file against the output schema."""
    from jsonschema import ValidationError

    from src.validation.schema_validator import SchemaValidator

    if not input_file.exists():
        typer.echo(f"[ERROR] File not found: {input_file}", err=True)
        raise typer.Exit(code=1)

    try:
        with input_file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        typer.echo(f"[ERROR] Invalid JSON: {exc}", err=True)
        raise typer.Exit(code=1)

    validator = SchemaValidator()
    try:
        validator.validate(data)
        typer.echo(f"✓ {input_file.name} — VALID")
    except ValidationError as exc:
        typer.echo(f"✗ {input_file.name} — INVALID: {exc.message}", err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


@app.command()
def version() -> None:
    """Print the current pipeline version and exit."""
    typer.echo(f"candidate-transform-pipeline v{PIPELINE_VERSION}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
