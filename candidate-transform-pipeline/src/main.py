"""
CLI entrypoint for the candidate transformation pipeline.

Commands
--------
run       — Full pipeline (interactive dataset selection + projection wizard).
inspect   — Display the canonical candidate schema.
test      — Run all curated test cases in test_cases/ (no user input needed).
validate  — Validate a candidate JSON file against the output schema.
version   — Print the current pipeline version.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

import typer

from src.config.config_loader import ConfigLoader
from src.models.canonical_candidate import CanonicalCandidate
from src.utils import cli_display
from src.utils.constants import PIPELINE_VERSION
from src.utils.logger import get_logger

logger = get_logger(__name__)

app = typer.Typer(
    name="candidate-pipeline",
    help="Enterprise candidate data transformation pipeline.",
    add_completion=False,
)

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

_INPUT_DIR    = Path("input")
_DEFAULT_CSV  = _INPUT_DIR / "recruiter.csv"
_DEFAULT_ATS  = _INPUT_DIR / "ats.json"
_DEFAULT_RESUMES = _INPUT_DIR / "resumes"
_DEFAULT_GITHUB  = _INPUT_DIR / "github"
_CONFIG_DIR   = Path("configs")
_OUTPUT_DIR   = Path("output")


# ---------------------------------------------------------------------------
# Source selection helpers
# ---------------------------------------------------------------------------


def _select_sources() -> Dict[str, Optional[Path]]:
    """
    Decide which input files to use.

    If input/ exists:
        - Show bundled dataset preview.
        - ENTER → use bundled; C → custom wizard.
    Otherwise:
        - Go straight to custom wizard.
    """
    if _INPUT_DIR.exists():
        cli_display.bundled_dataset_preview(
            _DEFAULT_CSV, _DEFAULT_ATS, _DEFAULT_RESUMES, _DEFAULT_GITHUB
        )
        typer.echo("")
        typer.echo("  Press ENTER to continue with this dataset.")
        typer.echo("  Type  C  to use your own input files.")
        typer.echo("")
        choice = typer.prompt("  >", default="").strip().upper()
        if choice != "C":
            return {
                "csv": _DEFAULT_CSV,
                "ats": _DEFAULT_ATS,
                "resumes_dir": _DEFAULT_RESUMES,
                "github_dir": _DEFAULT_GITHUB,
            }

    return _custom_input_wizard()


def _custom_input_wizard() -> Dict[str, Optional[Path]]:
    """Interactively collect custom source paths with retry on invalid input."""
    typer.echo("")
    typer.echo("  Custom Dataset — provide paths to your input files.")
    typer.echo("  Press ENTER to skip a source.")
    typer.echo("")

    return {
        "csv":        _ask_file("Recruiter CSV path"),
        "ats":        _ask_file("ATS JSON path"),
        "resumes_dir": _ask_dir("Resume folder path (contains .pdf files)"),
        "github_dir":  _ask_dir("GitHub folder path (contains .json files)"),
    }


def _ask_file(label: str) -> Optional[Path]:
    while True:
        raw = typer.prompt(f"  {label}", default="").strip()
        if not raw:
            return None
        p = Path(raw)
        if p.is_file():
            return p
        typer.echo(f"  [!] Not found: {raw}  — try again, or press ENTER to skip.")


def _ask_dir(label: str) -> Optional[Path]:
    while True:
        raw = typer.prompt(f"  {label}", default="").strip()
        if not raw:
            return None
        p = Path(raw)
        if p.is_dir():
            return p
        typer.echo(f"  [!] Not found: {raw}  — try again, or press ENTER to skip.")


# ---------------------------------------------------------------------------
# Projection target selection
# ---------------------------------------------------------------------------


def _select_projection_targets(
    candidates: List[CanonicalCandidate],
) -> List[CanonicalCandidate]:
    """Ask whether to project all candidates or one specific candidate."""
    count = len(candidates)
    if count == 1:
        return candidates

    typer.echo("")
    typer.echo("  Apply Projection To:")
    typer.echo("  1. All Candidates")
    typer.echo("  2. Select One Candidate")
    typer.echo("")
    choice = typer.prompt("  >", default="1").strip()

    if choice != "2":
        return candidates

    typer.echo("")
    for i, c in enumerate(candidates, start=1):
        name = c.personal_info.full_name or c.candidate_id
        typer.echo(f"  {i:>2}.  {name}")
    typer.echo("")

    raw = typer.prompt("  Select candidate number", default="1").strip()
    try:
        idx = int(raw) - 1
        if 0 <= idx < count:
            return [candidates[idx]]
    except ValueError:
        pass

    typer.echo("  [!] Invalid selection — applying to all candidates.")
    return candidates


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------


def _write_outputs(
    projected_list: List[dict],
    output_dir: Path,
    dry_run: bool,
) -> List[str]:
    """Write projected dicts to individual JSON files. Returns filenames written."""
    if dry_run:
        typer.echo("\n  → Dry-run mode: output not written to disk.")
        if projected_list:
            preview = json.dumps(projected_list[0], indent=2, default=str)
            typer.echo(preview[:1000] + ("…" if len(preview) > 1000 else ""))
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    filenames: List[str] = []
    for i, proj in enumerate(projected_list, start=1):
        fname = f"candidate_{i:03d}.json"
        (output_dir / fname).write_text(
            json.dumps(proj, indent=2, default=str), encoding="utf-8"
        )
        filenames.append(fname)
    return filenames


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@app.command()
def run(
    config_dir: Path = typer.Option(
        _CONFIG_DIR, "--config-dir", "-c",
        help="Directory containing pipeline YAML configs.",
    ),
    output_dir: Path = typer.Option(
        _OUTPUT_DIR, "--output-dir", "-o",
        help="Directory where candidate JSON files are written.",
    ),
    dry_run: Optional[bool] = typer.Option(
        None, "--dry-run", flag_value=True,
        help="Process data without writing output to disk.",
    ),
    no_wizard: Optional[bool] = typer.Option(
        None, "--no-wizard", flag_value=True,
        help="Skip projection wizard and output all fields.",
    ),
) -> None:
    """
    Run the complete candidate transformation pipeline.

    Presents an interactive source-selection step, then runs identity
    resolution, merge, and confidence scoring across all candidates.
    Launches the Projection Wizard for runtime field selection.
    """
    from src.projection.projection_service import ProjectionService
    from src.runner.dataset_loader import load_dataset
    from src.runner.multi_candidate_runner import run_multi_candidate_pipeline

    start_total = time.time()

    # ── 1. Banner ────────────────────────────────────────────────────────────
    cli_display.banner()

    # ── 2. Source selection ──────────────────────────────────────────────────
    paths = _select_sources()

    csv_path    = paths.get("csv")        or Path("/dev/null/nonexistent_csv")
    ats_path    = paths.get("ats")        or Path("/dev/null/nonexistent_ats")
    resumes_dir = paths.get("resumes_dir") or Path("/dev/null/nonexistent_resumes")
    github_dir  = paths.get("github_dir") or Path("/dev/null/nonexistent_github")

    # ── 3. Config ────────────────────────────────────────────────────────────
    try:
        config = ConfigLoader(config_dir).load()
    except Exception as exc:
        typer.echo(f"\n  [ERROR] Failed to load config: {exc}", err=True)
        raise typer.Exit(code=1)

    # ── 4. Load fragments ────────────────────────────────────────────────────
    summary = load_dataset(
        csv_path=csv_path,
        ats_path=ats_path,
        resumes_dir=resumes_dir,
        github_dir=github_dir,
    )
    fragments = summary.fragments

    cli_display.dataset_summary(
        summary.csv_count,
        summary.ats_count,
        summary.resume_count,
        summary.github_count,
    )

    if not fragments:
        typer.echo("\n  [ERROR] No candidate fragments loaded. Aborting.", err=True)
        raise typer.Exit(code=1)

    # ── 5. Pipeline ──────────────────────────────────────────────────────────
    cli_display.pipeline_heading()

    candidates, warnings, errors, meta = run_multi_candidate_pipeline(
        fragments, config
    )

    total_frags  = meta["total_fragments"]
    num_clusters = meta["num_clusters"]

    # Step completion output
    cli_display.step_done("Identity Resolution")
    cli_display.step_done("Normalization")
    cli_display.step_done("Merge Policy")
    cli_display.step_done("Confidence Scoring")
    cli_display.step_done(
        "Canonical Profiles",
        f"{len(candidates)} candidate(s) generated",
    )

    # ── 6. IR summary ────────────────────────────────────────────────────────
    cli_display.ir_summary(total_frags, num_clusters)

    if not candidates:
        typer.echo("\n  [ERROR] Pipeline produced no canonical candidates.", err=True)
        if errors:
            for e in errors[:5]:
                typer.echo(f"    • {e}", err=True)
        raise typer.Exit(code=1)

    if warnings:
        typer.echo(f"\n  ⚠   {len(warnings)} processing warning(s).")

    # ── 7. Projection target ─────────────────────────────────────────────────
    typer.echo("")
    cli_display.step_waiting("Projection", "select candidates to project")
    target_candidates = _select_projection_targets(candidates)

    # ── 8. Projection wizard ─────────────────────────────────────────────────
    if no_wizard:
        from src.models.projection_request import ProjectionRequest
        request = ProjectionRequest()
    else:
        typer.echo("\n  → Launching Projection Wizard...\n")
        from src.projection.wizard import run_wizard
        request = run_wizard()

    # ── 9. Apply projection ──────────────────────────────────────────────────
    from jsonschema import ValidationError
    from src.validation.schema_validator import SchemaValidator

    svc = ProjectionService()
    schema_validator = SchemaValidator()
    projected_list: List[dict] = []

    for cand in target_candidates:
        try:
            projected = svc.project(cand, request)
        except KeyError as exc:
            typer.echo(
                f"  [ERROR] Projection failed for {cand.candidate_id}: {exc}", err=True
            )
            continue
        try:
            schema_validator.validate(projected)
        except ValidationError as exc:
            typer.echo(f"  ⚠  Schema warning for {cand.candidate_id}: {exc.message}")
        projected_list.append(projected)

    if not projected_list:
        typer.echo("\n  [ERROR] No candidates survived projection.", err=True)
        raise typer.Exit(code=1)

    # ── 10. Write output ─────────────────────────────────────────────────────
    filenames = _write_outputs(projected_list, output_dir, bool(dry_run))

    elapsed = time.time() - start_total
    cli_display.step_done("Pipeline", f"completed in {elapsed:.2f}s")

    if not dry_run:
        cli_display.output_summary(len(projected_list), output_dir, filenames)


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


@app.command()
def inspect() -> None:
    """Display the canonical candidate schema grouped by category."""
    cli_display.banner()
    cli_display.inspect_schema()


# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------


@app.command()
def test(
    test_cases_dir: Path = typer.Option(
        Path("test_cases"), "--dir",
        help="Directory containing curated test case inputs.",
    ),
    config_dir: Path = typer.Option(
        Path("configs"), "--config-dir",
        help="Configuration directory.",
    ),
) -> None:
    """
    Run all curated end-to-end test cases and print PASS/FAIL results.

    Uses only data in test_cases/ — never touches the default input/ folder.
    Never pauses for user input.
    """
    cli_display.banner()
    from src.tests.test_runner import run_all_test_cases
    run_all_test_cases(test_cases_dir=test_cases_dir, config_dir=config_dir)


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


@app.command()
def validate(
    input_file: Path = typer.Argument(
        ..., help="Path to a candidate JSON file to validate.",
    ),
) -> None:
    """Validate a candidate JSON output file against the schema."""
    from jsonschema import ValidationError
    from src.validation.schema_validator import SchemaValidator

    if not input_file.exists():
        typer.echo(f"  [ERROR] File not found: {input_file}", err=True)
        raise typer.Exit(code=1)

    try:
        with input_file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        typer.echo(f"  [ERROR] Invalid JSON: {exc}", err=True)
        raise typer.Exit(code=1)

    try:
        SchemaValidator().validate(data)
        typer.echo(f"  ✓  {input_file.name} — VALID")
    except ValidationError as exc:
        typer.echo(f"  ✗  {input_file.name} — INVALID: {exc.message}", err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


@app.command()
def version() -> None:
    """Print the pipeline version."""
    typer.echo(f"candidate-transform-pipeline v{PIPELINE_VERSION}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
