"""
Test runner for ``python main.py test``.

Discovers test cases under ``test_cases/``, executes the pipeline for each,
compares key fields against expected fixtures, and prints a detailed
PASS/FAIL report using cli_display for consistent styling.

Never asks for user input — runs all cases automatically.
"""

import json
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import typer

from src.config.config_loader import ConfigLoader
from src.models.processing_context import ProcessingContext
from src.utils import cli_display
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Test case discovery
# ---------------------------------------------------------------------------


def _discover_test_cases(test_cases_dir: Path) -> List[Path]:
    cases: List[Path] = []
    if not test_cases_dir.exists():
        return cases
    for child in sorted(test_cases_dir.iterdir()):
        if child.is_dir() and (child / "expected").exists():
            cases.append(child)
    return cases


def _load_expected(case_dir: Path) -> Dict[str, Any]:
    expected_file = case_dir / "expected" / "output.json"
    if not expected_file.exists():
        return {}
    with expected_file.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_scenario_meta(case_dir: Path) -> Dict[str, str]:
    meta_file = case_dir / "meta.json"
    if meta_file.exists():
        with meta_file.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    name = case_dir.name.replace("_", " ").replace("-", " ").title()
    return {
        "scenario": name,
        "expected_behaviour": "Pipeline completes without fatal errors.",
    }


# ---------------------------------------------------------------------------
# Single test case runner
# ---------------------------------------------------------------------------


def _run_test_case(
    case_dir: Path, config_dir: Path
) -> Tuple[Optional[Dict[str, Any]], List[str], List[str], Dict[str, Any]]:
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

    for csv_file in sorted(inputs_dir.glob("*.csv")):
        try:
            adapter = CSVAdapter(csv_file)
            fragments.extend(adapter.to_candidate_fragment(adapter.parse(adapter.load())))
        except Exception:
            pass

    for ats_file in sorted(inputs_dir.glob("*ats*.json")):
        try:
            adapter = ATSAdapter({"file_path": str(ats_file)})
            fragments.extend(adapter.to_candidate_fragment(adapter.parse(adapter.load())))
        except Exception:
            pass

    for pdf_file in sorted(inputs_dir.glob("*.pdf")):
        try:
            adapter = ResumeAdapter(pdf_file)
            fragments.extend(adapter.to_candidate_fragment(adapter.parse(adapter.load())))
        except Exception:
            pass

    for gh_file in sorted(inputs_dir.glob("*github*.json")):
        try:
            adapter = GitHubAdapter(username=str(gh_file))
            fragments.extend(adapter.to_candidate_fragment(adapter.parse(adapter.load())))
        except Exception:
            pass

    if not fragments:
        return None, [], ["No fragments could be loaded from inputs/."], {
            "fragments_loaded": 0,
            "canonical_candidates": 0,
            "identity_clusters": 0,
            "merge_decisions": 0,
            "overall_confidence": 0.0,
            "schema_validation": "FAILED",
            "execution_time_ms": 0,
        }

    strategy = WeightedPriorityStrategy(source_weights=config.resolver.source_priorities)
    stages = [
        IdentityNormalizer(),
        IdentityResolutionService(),
        CanonicalNormalizer(),
        MergeEngine(strategy=strategy),
        CanonicalCandidateBuilder(),
        EvidenceEngine(config=config.confidence),
        SchemaValidator(),
    ]

    ctx = ProcessingContext(candidate_fragments=fragments)
    
    start_time = time.time()
    ctx = PipelineOrchestrator(stages=stages).run(ctx)
    elapsed_ms = int((time.time() - start_time) * 1000)

    # Determine schema validation status
    schema_status = "PASSED"
    for err in ctx.errors:
        if "SchemaValidator" in err or "ValidationError" in err:
            schema_status = "FAILED"
            break
    if ctx.canonical_candidate is None:
        schema_status = "FAILED"

    stats = {
        "fragments_loaded": len(fragments),
        "canonical_candidates": 1 if ctx.canonical_candidate is not None else 0,
        "identity_clusters": len(ctx.identity_resolution_result.get("clusters", [])) if ctx.identity_resolution_result else 0,
        "merge_decisions": len(ctx.merge_decisions),
        "overall_confidence": ctx.canonical_candidate.confidence.value if (ctx.canonical_candidate and ctx.canonical_candidate.confidence) else 0.0,
        "schema_validation": schema_status,
        "execution_time_ms": elapsed_ms,
    }

    if ctx.canonical_candidate is None:
        return None, ctx.warnings, ctx.errors, stats

    svc = ProjectionService()
    output = svc.project(ctx.canonical_candidate, ProjectionRequest())
    return output, ctx.warnings, ctx.errors, stats


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def _compare(
    actual: Optional[Dict[str, Any]],
    expected: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    if not expected:
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
                        f"{key}.{sub_key}: expected='{sub_exp}' actual='{sub_act}'"
                    )
        elif isinstance(exp_val, list):
            if not isinstance(act_val, list):
                failures.append(f"{key}: expected list, got {type(act_val).__name__}")
            else:
                for item in exp_val:
                    found = any(str(item).lower() in str(a).lower() for a in act_val)
                    if not found:
                        failures.append(f"{key}: '{item}' not found in output")
        elif act_val is None and exp_val is not None:
            failures.append(f"{key}: expected='{exp_val}' actual=None")
        elif str(act_val).lower() != str(exp_val).lower():
            failures.append(f"{key}: expected='{exp_val}' actual='{act_val}'")

    return len(failures) == 0, failures


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_all_test_cases(test_cases_dir: Path, config_dir: Path) -> None:
    """
    Discover and run all test cases. Never asks for user input.
    Prints a detailed PASS/FAIL report using cli_display helpers.
    """
    cli_display.test_suite_header()

    cases = _discover_test_cases(test_cases_dir)
    if not cases:
        typer.echo(
            f"\n  [!] No test cases found in '{test_cases_dir}'.\n"
            "      Each case needs: inputs/ and expected/ subdirectories.\n"
        )
        return

    passed_count = 0
    failed_count = 0
    total_canonical_candidates = 0
    total_execution_time_ms = 0

    for case_dir in cases:
        meta = _load_scenario_meta(case_dir)
        expected = _load_expected(case_dir)

        try:
            actual, warnings, errors, stats = _run_test_case(case_dir, config_dir)
        except Exception as exc:
            actual, warnings, errors = None, [], [f"Exception: {exc}"]
            stats = {
                "fragments_loaded": 0,
                "canonical_candidates": 0,
                "identity_clusters": 0,
                "merge_decisions": 0,
                "overall_confidence": 0.0,
                "schema_validation": "FAILED",
                "execution_time_ms": 0,
            }
            logger.debug(traceback.format_exc())

        passed, failures = _compare(actual, expected)

        expected_str = meta.get("expected_behaviour", "Pipeline completes.")

        cli_display.test_case_result(
            name=case_dir.name,
            scenario=meta.get("scenario", case_dir.name),
            expected=expected_str,
            passed=passed,
            fragments_loaded=stats["fragments_loaded"],
            canonical_candidates=stats["canonical_candidates"],
            identity_clusters=stats["identity_clusters"],
            merge_decisions=stats["merge_decisions"],
            overall_confidence=stats["overall_confidence"],
            schema_validation=stats["schema_validation"],
            execution_time_ms=stats["execution_time_ms"],
            failures=failures,
            warnings=warnings,
            errors=errors,
        )

        total_canonical_candidates += stats["canonical_candidates"]
        total_execution_time_ms += stats["execution_time_ms"]

        if passed:
            passed_count += 1
        else:
            failed_count += 1

    total_tests = passed_count + failed_count
    avg_execution_time_ms = int(total_execution_time_ms / total_tests) if total_tests > 0 else 0

    cli_display.test_suite_summary(
        total=total_tests,
        passed=passed_count,
        failed=failed_count,
        canonical_candidates=total_canonical_candidates,
        avg_execution_time_ms=avg_execution_time_ms,
    )

    if failed_count > 0:
        raise typer.Exit(code=1)
