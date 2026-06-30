# candidate-transform-pipeline

A production-grade candidate data transformation pipeline modelled after enterprise AI talent platforms such as Eightfold AI.

---

## Problem Statement

Candidate data arrives from multiple, heterogeneous sources — CSV exports, ATS systems, PDF resumes, and GitHub profiles. Each source uses different field names, formats, and quality levels. Without a principled transformation layer, downstream systems receive inconsistent, duplicated, or conflicting candidate records.

This pipeline solves that by:

1. **Ingesting** records from all sources via typed adapters.
2. **Normalising** identity fields (phone, email, name) to a canonical form.
3. **Resolving** cross-source duplicates using fuzzy matching and configurable thresholds.
4. **Merging** conflicting field values using a pluggable strategy (weighted priority, majority vote, or latest timestamp).
5. **Scoring** the merged record with evidence-based confidence.
6. **Projecting** the final output at runtime — the user chooses which fields, renames, and missing-value behaviour via an interactive wizard.
7. **Validating** the output against a JSON Schema before writing to disk.

---

## Architecture

```
Input Sources
    ↓
Source Adapters          (CSVAdapter | ATSAdapter | ResumeAdapter | GitHubAdapter)
    ↓
Candidate Fragments      (one CandidateFragment per source record)
    ↓
Identity Normalizer      (phone → E.164, email → lowercase, name → title case, github → URL)
    ↓
Identity Resolution      (blocking + RapidFuzz weighted similarity → clusters)
    ↓
Canonical Normalizer     (skills, companies, locations, job titles, dates → controlled vocab)
    ↓
Merge Policy Engine      (Strategy Pattern: WeightedPriority | MajorityVote | LatestTimestamp)
    ↓
Evidence Scoring Engine  (reliability × coverage − conflict penalty → Confidence score)
    ↓
ProcessingContext         (single mutable object carrying all state through every stage)
    ↓
Canonical Candidate Builder   (assembles CanonicalCandidate from merge decisions)
    ↓
Interactive Projection Wizard (runtime field selection, renaming, missing-value policy)
    ↓
Projection Service        (include_fields → apply_missing_policy → rename_fields)
    ↓
Output Schema Validator   (jsonschema Draft-7)
    ↓
Final JSON
```

---

## Pipeline Flow

Each `Stage` receives the shared `ProcessingContext`, reads what it needs, and writes results back. The `PipelineOrchestrator` drives sequential execution, catches all exceptions per-stage, and continues where possible.

| Stage | Output written to `ProcessingContext` |
|-------|---------------------------------------|
| IdentityNormalizer | `normalized_fragments` |
| IdentityResolutionService | `identity_resolution_result` |
| CanonicalNormalizer | `normalized_fragments` (updated) |
| MergeEngine | `merge_decisions` |
| EvidenceEngine | `evidence`, `canonical_candidate.confidence` |
| CanonicalCandidateBuilder | `canonical_candidate` |
| SchemaValidator | `errors` (if validation fails) |

---

## Design Decisions

### Adapter Pattern
Every source implements `BaseAdapter` with three methods: `load()`, `parse()`, `to_candidate_fragment()`. Adding a new source (e.g. LinkedIn, Greenhouse) requires only a new adapter file — no other code changes.

### Strategy Pattern (Merge Policy)
`MergeEngine` holds a `MergeStrategy` reference and delegates all field-level decisions to it. The strategy is loaded from `resolver.yaml` and can be swapped at runtime:
- **WeightedPriority** — picks the value from the highest-trust source.
- **MajorityVote** — picks the value most sources agree on.
- **LatestTimestamp** — picks the most recent value.

### Runtime Projection Wizard
Projection is not driven by config files. After the canonical candidate is built, an interactive Typer wizard asks the user to choose fields, optionally rename them, and set a missing-value policy. This builds a `ProjectionRequest` at runtime, keeping `CanonicalCandidate` immutable and reusable.

### ProcessingContext
A single Pydantic model is passed by reference through every stage. This means stages are naturally decoupled — each reads what it needs and writes its own section. The context also carries a full decision trace (`execution_logs`, `warnings`, `errors`, provenance records).

---

## Folder Structure

```
candidate-transform-pipeline/
├── src/
│   ├── adapters/          # CSV, ATS, Resume, GitHub adapters
│   ├── models/            # Pydantic models (fragments, candidate, context, etc.)
│   ├── pipeline/          # Stage ABC, Orchestrator, CanonicalCandidateBuilder
│   ├── identity/          # IdentityNormalizer, IdentityResolutionService
│   ├── normalization/     # CanonicalNormalizer
│   ├── resolver/          # MergeEngine, MergeStrategy, 3 strategy implementations
│   ├── confidence/        # EvidenceEngine
│   ├── projection/        # ProjectionService, interactive Wizard
│   ├── validation/        # SchemaValidator
│   ├── config/            # ConfigLoader (pipeline.yaml, resolver.yaml, confidence.yaml)
│   ├── tests/             # Internal test runner (used by `python main.py test`)
│   ├── utils/             # logger, constants
│   └── main.py            # Typer CLI (run, inspect, test, validate, version)
├── configs/
│   ├── pipeline.yaml      # Stage order
│   ├── resolver.yaml      # Merge strategy + source priorities
│   └── confidence.yaml    # Confidence weights
├── test_cases/            # 7 curated end-to-end test cases (inputs/ + expected/)
├── tests/                 # pytest unit test suite (56 tests)
├── output/                # Pipeline JSON output
├── requirements.txt
└── README.md
```

---

## Quick Start

```bash
# 1. Create and activate a virtual environment
/Users/samrudhp/.pyenv/versions/3.10.11/bin/python -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the full pipeline (launches interactive wizard)
python -m src.main run --source csv:test_cases/TC01_HappyPath/inputs/candidates.csv \
                       --source ats:test_cases/TC01_HappyPath/inputs/ats_record.json

# 4. Inspect all available canonical fields
python -m src.main inspect

# 5. Run the 7 curated test cases
python -m src.main test

# 6. Validate a JSON output file
python -m src.main validate output/cluster_0.json

# 7. Show version
python -m src.main version
```

---

## CLI Commands

### `run`
Runs the complete pipeline end-to-end.

```bash
python -m src.main run \
  --source csv:data/candidates.csv \
  --source ats:data/ats_export.json \
  --source resume:resumes/john_doe.pdf \
  --source github:/path/to/johndoe_github.json \
  --config-dir configs/ \
  --output-dir output/ \
  [--dry-run] \
  [--no-wizard]
```

After pipeline stages complete, launches the **Interactive Projection Wizard**:

```
──────────────────────────────────────────────────────────
  Available Canonical Fields
──────────────────────────────────────────────────────────
   1. Candidate ID       (candidate_id)
   2. Personal Info      (personal_info)
   3. Contact Details    (contact)
   ...

  Select fields to include (comma-separated numbers or names):
  Your selection: 2,3,7

  Would you like to rename any fields? (1 Yes / 2 No): 1
  Field: 7
  New output name for 'skills': techStack

  Missing Value Policy — 1 Omit  2 Null  3 Error: 1

──────────────────────────────────────────────────────────
  Projection Summary
──────────────────────────────────────────────────────────
  Included: Personal Info, Contact Details, Skills
  Renames:  skills → techStack
  Policy:   OMIT

  Proceed? (Y/n): Y
```

### `inspect`
Displays all available canonical candidate fields and their types.

### `test`
Runs all 7 curated test cases and prints a detailed PASS/FAIL report.

### `validate`
Validates a JSON output file against the output schema.

### `version`
Prints the pipeline version.

---

## Merge Policies

Configured in `configs/resolver.yaml`:

| Strategy | Description |
|----------|-------------|
| `weighted_priority` | Selects the value from the highest-trust source (default: ATS > Resume > CSV > GitHub) |
| `majority_vote` | Selects the value agreed upon by the most sources |
| `latest_timestamp` | Selects the most recently timestamped value |

List fields (skills, education, experience, projects) are always **unioned** across all sources.

---

## Test Cases

| ID | Scenario | Sources |
|----|----------|---------|
| TC01 | Happy Path | CSV + ATS + GitHub |
| TC02 | Identity Resolution | CSV + ATS (same person, different name casing / phone format) |
| TC03 | Malformed Input | Invalid ATS JSON + valid CSV fallback |
| TC04 | Runtime Projection | CSV only; tests ProjectionService |
| TC05 | Merge Policy | CSV + ATS with conflicting job title |
| TC06 | Missing Source | CSV only |
| TC07 | Multi-Source Conflict | CSV + ATS + GitHub with city/title conflict |

Run them all:
```bash
python -m src.main test
```

Expected output:
```
==================================================================
  Candidate Pipeline Test Suite
==================================================================
  TC01_HappyPath          Result: PASS ✓
  TC02_IdentityResolution Result: PASS ✓
  TC03_MalformedInput     Result: PASS ✓
  TC04_RuntimeProjection  Result: PASS ✓
  TC05_MergePolicy        Result: PASS ✓
  TC06_MissingSource      Result: PASS ✓
  TC07_MultiSourceConflict Result: PASS ✓
==================================================================
  7 / 7 Tests Passed
==================================================================
```

---

## Running Unit Tests

```bash
python -m pytest tests/ -v
# 56 tests, 0 failures
```

---

## Future Extensions

| Area | Extension |
|------|-----------|
| Adapters | Add `LinkedInAdapter`, `GreenhouseAdapter`, `WorkdayAdapter` by implementing `BaseAdapter` |
| Merge strategies | Add `ConfidenceWeightedStrategy` (uses evidence scores per field) |
| Identity resolution | Add ML-based embeddings as a second resolution pass |
| Output formats | Add CSV, Parquet, and JSONL output writers |
| Observability | Add OpenTelemetry tracing per pipeline stage |
| API mode | Wrap pipeline in a FastAPI service for batch and real-time processing |
| Projections | Allow projection templates to be saved and reloaded |
