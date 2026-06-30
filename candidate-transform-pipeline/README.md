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
6. **Projecting** the final output at runtime — choose which fields, renames, and missing-value behaviour via an interactive wizard.
7. **Validating** the output against a JSON Schema before writing to disk.

---

## Two Execution Modes

| Mode | Command | Purpose |
|------|---------|---------|
| **Demo / Real Dataset** | `python -m src.main run` | Processes real multi-candidate data interactively |
| **Functional Validation** | `python -m src.main test` | Validates pipeline behaviour against curated test cases |

These modes are completely independent. `run` never touches `test_cases/`, and `test` never touches `input/`.

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
ProcessingContext        (single mutable object carrying all state through every stage)
    ↓
Canonical Candidate Builder   (assembles CanonicalCandidate from merge decisions)
    ↓
Interactive Projection Wizard (runtime field selection, renaming, missing-value policy)
    ↓
Projection Service       (include_fields → apply_missing_policy → rename_fields)
    ↓
Output Schema Validator  (jsonschema Draft-7)
    ↓
Final JSON (candidate_001.json, candidate_002.json, ...)
```

---

## Folder Structure

```
candidate-transform-pipeline/
├── input/                     # Default demo dataset (multi-candidate)
│   ├── recruiter.csv          # Recruiter spreadsheet (10 candidates)
│   ├── ats.json               # ATS export (10 candidates)
│   ├── resumes/               # PDF resume files (10 files)
│   │   ├── candidate1.pdf
│   │   └── ...
│   └── github/                # GitHub mock JSON profiles (6 profiles)
│       ├── candidate1.json
│       └── ...
├── src/
│   ├── adapters/              # CSV, ATS, Resume, GitHub adapters
│   ├── models/                # Pydantic models (fragments, candidate, context, etc.)
│   ├── pipeline/              # Stage ABC, Orchestrator, CanonicalCandidateBuilder
│   ├── identity/              # IdentityNormalizer, IdentityResolutionService
│   ├── normalization/         # CanonicalNormalizer
│   ├── resolver/              # MergeEngine, MergeStrategy, 3 strategy implementations
│   ├── confidence/            # EvidenceEngine
│   ├── projection/            # ProjectionService, interactive Wizard
│   ├── validation/            # SchemaValidator
│   ├── config/                # ConfigLoader (pipeline.yaml, resolver.yaml, confidence.yaml)
│   ├── runner/                # DatasetLoader, MultiCandidateRunner
│   ├── tests/                 # Internal test runner (used by `python -m src.main test`)
│   ├── utils/                 # logger, constants
│   └── main.py                # Typer CLI (run, inspect, test, validate, version)
├── configs/
│   ├── pipeline.yaml          # Stage order
│   ├── resolver.yaml          # Merge strategy + source priorities
│   └── confidence.yaml        # Confidence weights
├── test_cases/                # 7 curated end-to-end test cases (inputs/ + expected/)
├── tests/                     # pytest unit test suite (56 tests)
├── output/                    # Pipeline JSON output
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

# 3. Run the pipeline (launches interactive source selection)
python -m src.main run

# 4. Run without the projection wizard (output all fields automatically)
python -m src.main run --no-wizard

# 5. Dry run — process data but don't write files to disk
python -m src.main run --no-wizard --dry-run

# 6. Run the 7 curated test cases
python -m src.main test

# 7. Inspect all available canonical fields
python -m src.main inspect

# 8. Validate a JSON output file
python -m src.main validate output/candidate_001.json

# 9. Show version
python -m src.main version
```

---

## Mode 1 — Default Demo Dataset

When you run `python -m src.main run`, the CLI first asks how you want to provide input:

```
=========================================
  Input Source Selection
=========================================
  1. Use bundled demo dataset  (Recommended)
  2. Use my own input files

  Your choice [1]:
```

Selecting **1** loads all data from the `input/` directory automatically:

```
============================================
  Loading Default Input Dataset...
============================================
  Recruiter CSV .............. 10 Candidates
  ATS JSON ................... 10 Candidates
  Resume PDFs ..................... 10 Files
  GitHub Profiles ............... 6 Profiles
============================================

  Running Pipeline...

  ✓ Identity Resolution Complete
  ✓ Normalization Complete
  ✓ Merge Complete
  ✓ Confidence Calculated
  ✓ Generated 10 Canonical Candidate(s)
```

The pipeline:
- Automatically discovers all `.pdf` files in `input/resumes/`
- Automatically discovers all `.json` files in `input/github/`
- Performs **global** identity resolution across all 36+ fragments
- Runs a focused per-cluster merge pipeline for each resolved identity
- Generates one `candidate_NNN.json` per unique person in `output/`

---

## Mode 2 — Custom Dataset

Selecting **2** in the source selection menu prompts you to provide your own file paths:

```
  Please provide paths to your input files.
  Press Enter to skip a source (at least one is required).

  Recruiter CSV path []:         data/my_candidates.csv
  ATS JSON path []:              data/my_ats_export.json
  Resume folder path []:         data/resumes/
  GitHub folder path []:         data/github_profiles/
```

Each path is validated before the pipeline begins. Any skipped or missing source is silently excluded.

---

## Projection Wizard

After all canonical candidates are produced, the pipeline asks how you want to project the output:

```
=========================================
  Pipeline Complete
  Generated 10 Canonical Candidate(s)
=========================================

  Apply Projection To:
  1. All Candidates
  2. Select One Candidate

  Your choice [1]:
```

If you select **2**, a numbered list of candidates is shown by name so you can pick one.

The Projection Wizard then guides you through:

```
────────────────────────────────────────────────────────────
  Available Canonical Fields
────────────────────────────────────────────────────────────
   1. Candidate ID       (candidate_id)
   2. Personal Info      (personal_info)
   3. Contact Details    (contact)
   4. Education          (education)
   5. Experience         (experience)
   6. Projects           (projects)
   7. Skills             (skills)
   8. Links              (links)
   9. Confidence         (confidence)
  10. Provenance         (provenance)

  Select fields to include (comma-separated numbers or names).
  Press Enter with no input to include ALL fields.

  Your selection: 2,3,7

  Would you like to rename any fields?
  1 Yes  2 No: 1
  Field: 7
  New output name for 'skills': techStack

  Missing Value Policy
  1  Omit   — field is silently excluded from output
  2  Null   — field is included with a null value
  3  Error  — raise an error and halt

  Policy (1/2/3): 1

  ────────────────────────────────────────────────────────────
  Projection Summary
  ────────────────────────────────────────────────────────────
  Included Fields:
    ✓ Personal Info
    ✓ Contact Details
    ✓ Skills
  Renames:
    skills  →  techStack
  Missing Value Policy:  OMIT

  Proceed with this projection? (Y/n): Y
```

---

## Input Folder Structure

The `input/` directory represents a realistic enterprise ingestion dataset. All sources contain records for the same pool of candidates:

| Source | File | Candidates |
|--------|------|-----------|
| Recruiter CSV | `input/recruiter.csv` | 10 |
| ATS JSON | `input/ats.json` | 10 |
| Resume PDFs | `input/resumes/*.pdf` | 10 |
| GitHub Profiles | `input/github/*.json` | 6 |

The identity resolution layer clusters matching records across sources so that cross-source duplicates are merged into a single canonical profile.

---

## Pipeline Flow

Each `Stage` receives the shared `ProcessingContext`, reads what it needs, and writes results back. The `PipelineOrchestrator` drives sequential execution, catches all exceptions per stage, and continues where possible.

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

### Multi-Candidate Runner
The `MultiCandidateRunner` runs identity resolution globally across all fragments, then executes a focused pipeline (normalizer → merge → evidence → builder → validator) **per resolved cluster**. This ensures each unique identity is processed independently without cross-contamination.

### Runtime Projection Wizard
Projection is not driven by config files. After canonical candidates are built, an interactive wizard asks the user to choose fields, optionally rename them, and set a missing-value policy. This builds a `ProjectionRequest` at runtime, keeping `CanonicalCandidate` immutable and reusable.

### ProcessingContext
A single Pydantic model is passed by reference through every stage. Stages are naturally decoupled — each reads what it needs and writes its own section. The context also carries a full decision trace (`execution_logs`, `warnings`, `errors`, provenance records).

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

The `python -m src.main test` command runs all 7 curated end-to-end test cases from `test_cases/`. It **never** uses data from `input/`.

| ID | Scenario | Sources |
|----|----------|---------|
| TC01 | Happy Path | CSV + ATS + GitHub |
| TC02 | Identity Resolution | CSV + ATS (same person, different name casing / phone format) |
| TC03 | Malformed Input | Invalid ATS JSON + valid CSV fallback |
| TC04 | Runtime Projection | CSV only; tests ProjectionService |
| TC05 | Merge Policy | CSV + ATS with conflicting job title |
| TC06 | Missing Source | CSV only |
| TC07 | Multi-Source Conflict | CSV + ATS + GitHub with city/title conflict |

Each test case displays:

```
──────────────────────────────────────────────────────────────────
  TC01_HappyPath
  Scenario : TC01 — Happy Path: Single Candidate from CSV + ATS + GitHub
  Expected : Pipeline merges all three sources, produces one canonical candidate
  Actual   : Output produced

  Result   : PASS ✓
```

Expected output after running all tests:

```
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

## CLI Reference

| Command | Description |
|---------|-------------|
| `python -m src.main run` | Run the full pipeline (interactive source + projection) |
| `python -m src.main run --no-wizard` | Run and output all fields without the projection wizard |
| `python -m src.main run --dry-run` | Process data but skip writing output to disk |
| `python -m src.main test` | Run all 7 curated test cases |
| `python -m src.main inspect` | Display all available canonical candidate fields |
| `python -m src.main validate <file>` | Validate a JSON output file against the output schema |
| `python -m src.main version` | Print the pipeline version |

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
