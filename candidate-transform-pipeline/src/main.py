"""
CLI entrypoint for the candidate transformation pipeline.

Commands
--------
run       — Execute the complete pipeline end-to-end.
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
# Helpers
# ---------------------------------------------------------------------------


def _build_pipeline_from_config(config: AppConfig):  # type: ignore[return]
    """
    Instantiate and return the ordered list of pipeline Stage objects
    based on the loaded configuration.
    """
    from src.confidence.evidence_engine import EvidenceEngine
    from src.identity.identity_normalizer import IdentityNormalizer
    from src.identity.identity_resolution import IdentityResolutionService
    from src.normalization.canonical_normalizer import CanonicalNormalizer
    from src.pipeline.canonical_builder import CanonicalCandidateBuilder
    from src.resolver.latest_timestamp import LatestTimestampStrategy
    from src.resolver.majority_vote import MajorityVoteStrategy
    from src.resolver.merge_engine import MergeEngine
    from src.resolver.weighted_priority import WeightedPriorityStrategy
    from src.validation.schema_validator import SchemaValidator

    strategy_name = config.resolver.merge_strategy
    priorities = config.resolver.source_priorities

    if strategy_name == "majority_vote":
        strategy = MajorityVoteStrategy()
    elif strategy_name == "latest_timestamp":
        strategy = LatestTimestampStrategy()
    else:
        strategy = WeightedPriorityStrategy(source_weights=priorities)

    return [
        IdentityNormalizer(),
        IdentityResolutionService(),
        CanonicalNormalizer(),
        MergeEngine(strategy=strategy),
        EvidenceEngine(config=config.confidence),
        CanonicalCandidateBuilder(),
        EvidenceEngine(config=config.confidence),  # second pass after builder
        SchemaValidator(),
    ]


def _load_fragments(sources: List[str], config_dir: Path) -> List:
    """
    Parse ``--source`` arguments and load CandidateFragments from each source.

    Format: ``<type>:<path>``  e.g. ``csv:data/candidates.csv``
    """
    from src.adapters.ats_adapter import ATSAdapter
    from src.adapters.csv_adapter import CSVAdapter
    from src.adapters.github_adapter import GitHubAdapter
    from src.adapters.resume_adapter import ResumeAdapter

    fragments = []
    for source_spec in sources:
        if ":" not in source_spec:
            typer.echo(
                f"[!] Invalid source format '{source_spec}'. "
                "Expected <type>:<path>. Skipping.",
                err=True,
            )
            continue

        src_type, src_path = source_spec.split(":", 1)
        src_type = src_type.strip().lower()
        src_path = src_path.strip()

        try:
            if src_type == "csv":
                adapter = CSVAdapter(Path(src_path))
                raw = adapter.load()
                parsed = adapter.parse(raw)
                fragments.extend(adapter.to_candidate_fragment(parsed))

            elif src_type == "ats":
                adapter = ATSAdapter({"file_path": src_path})
                raw = adapter.load()
                parsed = adapter.parse(raw)
                fragments.extend(adapter.to_candidate_fragment(parsed))

            elif src_type == "resume":
                adapter = ResumeAdapter(Path(src_path))
                raw = adapter.load()
                parsed = adapter.parse(raw)
                fragments.extend(adapter.to_candidate_fragment(parsed))

            elif src_type == "github":
                adapter = GitHubAdapter(username=src_path)
                raw = adapter.load()
                parsed = adapter.parse(raw)
                fragments.extend(adapter.to_candidate_fragment(parsed))

            else:
                typer.echo(
                    f"[!] Unknown source type '{src_type}'. "
                    "Supported: csv, ats, resume, github.",
                    err=True,
                )

        except FileNotFoundError as exc:
            typer.echo(f"[!] Source not found: {exc}", err=True)
        except ValueError as exc:
            typer.echo(f"[!] Source error: {exc}", err=True)

    return fragments


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@app.command()
def run(
    sources: List[str] = typer.Option(
        ...,
        "--source",
        "-s",
        help=(
            "One or more source inputs. Format: <type>:<path>. "
            "Example: --source csv:data/candidates.csv "
            "--source resume:resumes/cv.pdf"
        ),
    ),
    config_dir: Path = typer.Option(
        Path("configs"),
        "--config-dir",
        "-c",
        help="Directory containing pipeline.yaml, resolver.yaml, confidence.yaml.",
    ),
    output_dir: Path = typer.Option(
        Path("output"),
        "--output-dir",
        "-o",
        help="Directory where the final JSON output will be written.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run the pipeline without writing output to disk.",
    ),
    no_wizard: bool = typer.Option(
        False,
        "--no-wizard",
        help="Skip the interactive projection wizard (output all fields).",
    ),
) -> None:
    """
    Run the complete candidate transformation pipeline.

    Loads source data, executes all pipeline stages, launches an interactive
    projection wizard, validates the output, and writes the final JSON.
    """
    from src.pipeline.orchestrator import PipelineOrchestrator
    from src.projection.projection_service import ProjectionService

    start_total = time.time()
    typer.echo("\n" + "=" * 60)
    typer.echo("  Candidate Transformation Pipeline")
    typer.echo("=" * 60)

    # 1. Load configuration.
    typer.echo(f"\n→ Loading configuration from: {config_dir}")
    try:
        config = ConfigLoader(config_dir).load()
    except Exception as exc:
        typer.echo(f"[ERROR] Failed to load config: {exc}", err=True)
        raise typer.Exit(code=1)

    # 2. Load fragments from sources.
    typer.echo(f"→ Loading sources: {sources}")
    fragments = _load_fragments(sources, config_dir)
    if not fragments:
        typer.echo("[ERROR] No candidate fragments loaded. Aborting.", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"  Loaded {len(fragments)} fragment(s).")

    # 3. Build context.
    context = ProcessingContext(candidate_fragments=fragments)

    # 4. Build and run the pipeline.
    typer.echo("→ Running pipeline stages...")
    stages = _build_pipeline_from_config(config)
    orchestrator = PipelineOrchestrator(stages=stages)
    context = orchestrator.run(context)

    if context.canonical_candidate is None:
        typer.echo("[ERROR] Pipeline did not produce a canonical candidate.", err=True)
        if context.errors:
            for err in context.errors:
                typer.echo(f"  • {err}", err=True)
        raise typer.Exit(code=1)

    candidate = context.canonical_candidate
    typer.echo(f"  Pipeline complete. candidate_id={candidate.candidate_id}")

    if context.warnings:
        typer.echo(f"  Warnings ({len(context.warnings)}):")
        for w in context.warnings:
            typer.echo(f"    ⚠ {w}")

    # 5. Interactive Projection Wizard (or pass-through).
    from src.projection.wizard import run_wizard

    if no_wizard:
        from src.models.projection_request import ProjectionRequest
        request = ProjectionRequest()  # Include all fields.
    else:
        typer.echo("\n→ Launching Interactive Projection Wizard...")
        request = run_wizard()

    # 6. Apply projection.
    svc = ProjectionService()
    try:
        projected = svc.project(candidate, request)
    except KeyError as exc:
        typer.echo(f"[ERROR] Projection failed: {exc}", err=True)
        raise typer.Exit(code=1)

    # 7. Validate output schema.
    from src.validation.schema_validator import SchemaValidator
    from jsonschema import ValidationError

    schema_validator = SchemaValidator()
    try:
        schema_validator.validate(projected)
        typer.echo("  Schema validation: PASSED ✓")
    except ValidationError as exc:
        typer.echo(f"  Schema validation: FAILED — {exc.message}", err=True)
        context.errors.append(str(exc.message))

    # 8. Write output.
    output_payload = json.dumps(projected, indent=2, default=str)

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_file = output_dir / f"{candidate.candidate_id}.json"
        out_file.write_text(output_payload, encoding="utf-8")
        typer.echo(f"\n→ Output written to: {out_file}")
    else:
        typer.echo("\n→ Dry-run mode: output not written to disk.")
        typer.echo("\n" + output_payload[:1200] + ("…" if len(output_payload) > 1200 else ""))

    elapsed = time.time() - start_total
    typer.echo(f"\n✓ Pipeline completed in {elapsed:.2f}s")
    typer.echo("=" * 60 + "\n")


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
    """Run all curated end-to-end test cases and print PASS/FAIL results."""
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
