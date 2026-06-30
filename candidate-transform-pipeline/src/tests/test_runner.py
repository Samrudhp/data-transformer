"""
Test runner for ``python main.py test``.

Discovers test cases under ``test_cases/``, executes the pipeline for each,
compares key fields against expected fixtures, and prints a detailed
PASS/FAIL report.
"""

import json
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import typer

from src.config.config_loader import ConfigLoader
from src.models.processing_context import ProcessingContext
from src.utils.logger import get_logger

logger = get_logger(__name__)

_SEPARATOR = "─" * 66
_DOUBLE = "=" * 66


# ---------------------------------------------------------------------------
# Test case discovery
# ---------------------------------------------------------------------------


def _discover_test_cases(test_cases_dir: Path) -> List[Path]:
    """
    Return sorted subdirectory paths that contain an ``expected/`` folder.
    """
    cases: List[Path] = []
    if not test_cases_dir.exists():
        return cases
    for child in sorted(test_cases_dir.iterdir()):
        if child.is_dir() and (child / "expected").exists():
            cases.append(child)
    return cases


def _load_expected(case_dir: Path) -> Dict[str, Any]:
    """Load ``expected/output.json`` from the test case directory."""
    expected_file = case_dir / "expected" / "output.json"
    if not expected_file.exists():
        return {}
    with expected_file.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_scenario_meta(case_dir: Path) -> Dict[str, str]:
    """Load ``meta.json`` if present (scenario description, expected behaviour)."""
    meta_file = case_dir / "meta.json"
    if meta_file.exists():
        with meta_file.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    # Derive minimal meta from directory name.
    name = case_dir.name.replace("_", " ").replace("-", " ").title()
    return {"scenario": name, "expected_behaviour": "Pipeline completes without fatal errors."}


# ---------------------------------------------------------------------------
# Pipeline runner for a single test case
# ---------------------------------------------------------------------------


def _run_test_case(
    case_dir: Path, config_dir: Path
) -> Tuple[Optional[Dict[str, Any]], List[str], List[str]]:
    """
    Run the pipeline for one test case.

    Returns:
        (projected_output, warnings, errors)
    """
    from src.adapters.ats_adapter import ATSAdapter
    from src.adapters.csv_adapter import CSVAdapter
    from src.adapters.github_adapter import GitHubAdapter
    from src.adapters.resume_adapter import ResumeAdapter
    from src.confidence.evidence_engine import EvidenceEngine
    from src.identity.identity_normalizer import IdentityNormalizer
    from src.identity.identity_resolution import IdentityResolutionService
    from src.models.projection_request import ProjectionRequest
    from src.normalization.canonical_normalizer import CanonicalNormalizer
    from src.pipeline.canonical_builder import CanonicalCandidateBuilder
    from src.pipeline.orchestrator import PipelineOrchestrator
    from src.projection.projection_service import ProjectionService
    from src.resolver.merge_engine import MergeEngine
    from src.resolver.weighted_priority import WeightedPriorityStrategy
    from src.validation.schema_validator import SchemaValidator

    config = ConfigLoader(config_dir).load()
    inputs_dir = case_dir / "inputs"

    fragments: list = []

    # CSV
    for csv_file in sorted(inputs_dir.glob("*.csv")):
        try:
            adapter = CSVAdapter(csv_file)
            raw = adapter.load()
            parsed = adapter.parse(raw)
            fragments.extend(adapter.to_candidate_fragment(parsed))
        except Exception:
            pass

    # ATS JSON
    for ats_file in sorted(inputs_dir.glob("*ats*.json")):
        try:
            adapter = ATSAdapter({"file_path": str(ats_file)})
            raw = adapter.load()
            parsed = adapter.parse(raw)
            fragments.extend(adapter.to_candidate_fragment(parsed))
        except Exception:
            pass

    # Resume PDF
    for pdf_file in sorted(inputs_dir.glob("*.pdf")):
        try:
            adapter = ResumeAdapter(pdf_file)
            raw = adapter.load()
            parsed = adapter.parse(raw)
            fragments.extend(adapter.to_candidate_fragment(parsed))
        except Exception:
            pass

    # GitHub JSON
    for gh_file in sorted(inputs_dir.glob("*github*.json")):
        try:
            adapter = GitHubAdapter(username=str(gh_file))
            raw = adapter.load()
            parsed = adapter.parse(raw)
            fragments.extend(adapter.to_candidate_fragment(parsed))
        except Exception:
            pass

    if not fragments:
        return None, [], ["No fragments could be loaded from inputs/."]

    strategy = WeightedPriorityStrategy(source_weights=config.resolver.source_priorities)
    stages = [
        IdentityNormalizer(),
        IdentityResolutionService(),
        CanonicalNormalizer(),
        MergeEngine(strategy=strategy),
        EvidenceEngine(config=config.confidence),
        CanonicalCandidateBuilder(),
        EvidenceEngine(config=config.confidence),
        SchemaValidator(),
    ]

    ctx = ProcessingContext(candidate_fragments=fragments)
    orchestrator = PipelineOrchestrator(stages=stages)
    ctx = orchestrator.run(ctx)

    if ctx.canonical_candidate is None:
        return None, ctx.warnings, ctx.errors

    svc = ProjectionService()
    output = svc.project(ctx.canonical_candidate, ProjectionRequest())
    return output, ctx.warnings, ctx.errors


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def _compare(
    actual: Optional[Dict[str, Any]],
    expected: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Compare actual output against expected fixture.

    Checks top-level keys specified in expected.
    Returns (all_pass, list_of_failure_messages).
    """
    if not expected:
        # No expected fixture — just check pipeline produced output.
        passed = actual is not None
        return passed, [] if passed else ["Pipeline produced no output."]

    failures: List[str] = []
    if actual is None:
        return False, ["Pipeline produced no output."]

    for key, exp_val in expected.items():
        act_val = actual.get(key)
        if isinstance(exp_val, dict) and isinstance(act_val, dict):
            for sub_key, sub_exp in exp_val.items():
                sub_act = act_val.get(sub_key)
                if str(sub_act).lower() != str(sub_exp).lower():
                    failures.append(
                        f"  {key}.{sub_key}: expected='{sub_exp}' actual='{sub_act}'"
                    )
        elif isinstance(exp_val, list):
            # For lists (skills, education), check at least the items exist.
            if not isinstance(act_val, list):
                failures.append(f"  {key}: expected list, got {type(act_val).__name__}")
            else:
                for item in exp_val:
                    found = any(
                        str(item).lower() in str(a).lower() for a in act_val
                    )
                    if not found:
                        failures.append(
                            f"  {key}: expected item '{item}' not found in {act_val[:3]}…"
                        )
        elif act_val is None and exp_val is not None:
            failures.append(f"  {key}: expected='{exp_val}' actual=None")
        elif str(act_val).lower() != str(exp_val).lower():
            failures.append(
                f"  {key}: expected='{exp_val}' actual='{act_val}'"
            )

    return len(failures) == 0, failures


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------


def run_all_test_cases(test_cases_dir: Path, config_dir: Path) -> None:
    """
    Discover and run all test cases, printing a detailed PASS/FAIL report.
    """
    typer.echo("\n" + _DOUBLE)
    typer.echo("  Candidate Pipeline Test Suite")
    typer.echo(_DOUBLE)

    cases = _discover_test_cases(test_cases_dir)
    if not cases:
        typer.echo(
            f"\n  [!] No test cases found in '{test_cases_dir}'.\n"
            "      Each test case needs: inputs/ and expected/ subdirectories.\n"
        )
        return

    passed_count = 0
    failed_count = 0
    results: List[Dict[str, Any]] = []

    for case_dir in cases:
        meta = _load_scenario_meta(case_dir)
        expected = _load_expected(case_dir)

        typer.echo(f"\n{_SEPARATOR}")
        typer.echo(f"  {case_dir.name}")
        typer.echo(f"  Scenario : {meta.get('scenario', case_dir.name)}")
        typer.echo(f"  Expected : {meta.get('expected_behaviour', 'Pipeline completes.')}")

        try:
            actual, warnings, errors = _run_test_case(case_dir, config_dir)
        except Exception as exc:
            actual, warnings, errors = None, [], [f"Exception: {exc}"]
            logger.debug(traceback.format_exc())

        passed, failures = _compare(actual, expected)

        typer.echo(f"  Actual   : {'Output produced' if actual else 'No output'}")
        if warnings:
            for w in warnings[:3]:
                typer.echo(f"  ⚠ Warning: {w}")
        if errors:
            for e in errors[:3]:
                typer.echo(f"  ✗ Error  : {e}")
        if failures:
            for f in failures[:5]:
                typer.echo(f"  ✗ Mismatch: {f}")

        status = "PASS ✓" if passed else "FAIL ✗"
        typer.echo(f"\n  Result   : {status}")

        if passed:
            passed_count += 1
        else:
            failed_count += 1

        results.append(
            {
                "name": case_dir.name,
                "passed": passed,
                "errors": errors,
                "failures": failures,
            }
        )

    # Final summary
    total = passed_count + failed_count
    typer.echo("\n" + _DOUBLE)
    typer.echo(f"  {passed_count} / {total} Tests Passed")
    typer.echo(_DOUBLE + "\n")

    if failed_count > 0:
        raise typer.Exit(code=1)
