# Candidate Data Transformation Pipeline

> **Eightfold AI Assignment** — Enterprise-grade candidate data normalisation, identity resolution, and multi-source merging pipeline modelled after real-world AI talent platforms.

---

## Problem Statement

Candidate data arrives from multiple, heterogeneous sources — recruiter CSVs, ATS exports, PDF resumes, and GitHub profiles. Each source uses different field names, formats, and quality levels. Without a principled transformation layer, downstream systems receive inconsistent, duplicated, or conflicting records.

This pipeline solves that by:

1. **Ingesting** records from all sources via typed adapters
2. **Normalising** identity fields (phone → E.164, email → lowercase, name → title case)
3. **Resolving** cross-source duplicates using fuzzy matching and configurable thresholds
4. **Merging** conflicting values using a pluggable strategy (weighted priority / majority vote / latest timestamp)
5. **Scoring** the merged record with evidence-based confidence
6. **Projecting** the final output at runtime via an interactive wizard (choose fields, renames, missing-value policy)
7. **Validating** output against a JSON Schema before writing to disk

---

## Two Execution Modes

| Mode | Command | Purpose |
|------|---------|---------|
| **Demo / Production** | `python -m src.main run` | Processes real multi-candidate data interactively |
| **Functional Validation** | `python -m src.main test` | Runs all 7 curated test cases automatically |

These modes are **completely independent**. `run` never touches `test_cases/`. `test` never touches `input/`.

---

## Quick Start

```bash
# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the pipeline (interactive)
python -m src.main run

# 4. Run without the Projection Wizard (output all fields)
python -m src.main run --no-wizard

# 5. Dry run — process data without writing files
python -m src.main run --no-wizard --dry-run

# 6. Run the 7 curated test cases
python -m src.main test

# 7. Inspect the canonical candidate schema
python -m src.main inspect

# 8. Validate an output JSON file
python -m src.main validate output/candidate_001.json

# 9. Show version
python -m src.main version
```

---

## Startup Banner

Every command displays a consistent banner:

```
==============================================================
            Candidate Data Transformation Pipeline
                   Eightfold AI Assignment
==============================================================
  Version        : 1.0.0
  Architecture   : Enterprise Modular ETL Pipeline
  Sources        :
    ✓  Recruiter CSV
    ✓  ATS JSON
    ✓  Resume PDF
    ✓  GitHub Mock
==============================================================
```

---

## `python -m src.main run` — Full Pipeline Flow

### Step 1 — Dataset Selection

The CLI detects whether the bundled `input/` folder is present and shows what is inside:

```
==============================================================
  Loading bundled demonstration dataset...
──────────────────────────────────────────────────────────────
  ✓  recruiter.csv
  ✓  ats.json
  ✓  Resume PDFs        (10 files)
  ✓  GitHub Profiles    (6 profiles)
==============================================================

  Press ENTER to continue with this dataset.
  Type  C  to use your own input files.

  > 
```

- **Press ENTER** → uses the bundled `input/` folder automatically.
- **Type `C`** → launches the custom input wizard (see below).

### Step 2 — Dataset Summary

After loading, dynamic counts are displayed:

```
==============================================================
  Dataset Summary
──────────────────────────────────────────────────────────────
  Recruiter CSV .................................... 10 records
  ATS JSON ......................................... 10 records
  Resume PDFs ........................................ 10 files
  GitHub Profiles .................................. 6 profiles
  ──────────────────────────────────────────────────────────────
  Total Candidate Fragments ................................ 36
==============================================================
```

### Step 3 — Pipeline Execution

```
==============================================================
  Running Pipeline
==============================================================
  ✓  Identity Resolution
  ✓  Normalization
  ✓  Merge Policy
  ✓  Confidence Scoring
  ✓  Canonical Profiles  —  10 candidate(s) generated
```

### Step 4 — Identity Resolution Summary

```
==============================================================
  Identity Resolution Complete
──────────────────────────────────────────────────────────────
  Input Fragments .......................................... 36
  Canonical Candidates ..................................... 10
  Duplicate Fragments Merged ............................... 26
==============================================================
```

### Step 5 — Projection Target

```
  Apply Projection To:
  1. All Candidates
  2. Select One Candidate

  > 
```

Selecting **2** shows a named candidate list for single-candidate projection.

### Step 6 — Projection Wizard

An interactive wizard guides field selection, renaming, and missing-value policy:

```
──────────────────────────────────────────────────────────────
  Available Canonical Fields
──────────────────────────────────────────────────────────────
   1. Candidate ID       (candidate_id)
   2. Personal Info      (personal_info)
   3. Contact Details    (contact)
   ...
  10. Provenance         (provenance)

  Select fields to include (comma-separated numbers or names).
  Press Enter with no input to include ALL fields.

  Your selection: 2,3,7
```

Projection summary before confirmation:

```
==============================================================
  Projection Summary
──────────────────────────────────────────────────────────────

  Included Fields
    ✓  Personal Info
    ✓  Contact Details
    ✓  Skills

  Missing Policy
    Omit

==============================================================
  Proceed with this projection? (Y/n):
```

### Step 7 — Output Summary

```
==============================================================
  Pipeline Completed Successfully
──────────────────────────────────────────────────────────────
  Canonical Candidates   10
  Output Folder          output/
  Files Generated
    candidate_001.json
    candidate_002.json
    ...
==============================================================
```

---

## Custom Dataset Mode

If you type `C` at the dataset prompt, the wizard asks for paths with retry on invalid input:

```
  Custom Dataset — provide paths to your input files.
  Press ENTER to skip a source.

  Recruiter CSV path: data/my_candidates.csv
  ATS JSON path: data/my_ats_export.json
  Resume folder path (contains .pdf files): data/resumes/
  GitHub folder path (contains .json files): data/github/
```

If a path is invalid, the wizard re-prompts instead of skipping silently:

```
  [!] Not found: data/wrong.csv  — try again, or press ENTER to skip.
  Recruiter CSV path: 
```

---

## `python -m src.main test` — Test Runner

Runs all 7 curated test cases automatically. **No user input required.**

```
==============================================================
  Candidate Pipeline Test Suite
==============================================================

  TC01 — HappyPath
  ──────────────────────────────────────────────────────────────
  Scenario   : Single Candidate from CSV + ATS + GitHub
  Expected   : Pipeline merges all three sources into one canonical candidate
  Actual     : Output produced
  Result     : PASS  ✓

  TC02 — IdentityResolution
  ──────────────────────────────────────────────────────────────
  Scenario   : Same candidate from CSV and ATS with different name casing
  Expected   : Records resolved as the same identity, merged output produced
  Actual     : Output produced
  Result     : PASS  ✓

  ...

==============================================================
  Summary
──────────────────────────────────────────────────────────────
  Tests Executed ............................................ 7
  Passed .................................................... 7
  Failed .................................................... 0
  Overall Result ......................................... PASS
==============================================================
```

### Test Cases

| ID | Scenario | Sources |
|----|----------|---------|
| TC01 | Happy Path | CSV + ATS + GitHub |
| TC02 | Identity Resolution | CSV + ATS (same person, different formatting) |
| TC03 | Malformed Input | Invalid ATS JSON + valid CSV fallback |
| TC04 | Runtime Projection | CSV only — validates ProjectionService |
| TC05 | Merge Policy | CSV + ATS with conflicting job title |
| TC06 | Missing Source | CSV only |
| TC07 | Multi-Source Conflict | CSV + ATS + GitHub with city/title conflict |

---

## `python -m src.main inspect` — Schema Reference

```
==============================================================
  Canonical Candidate Schema
==============================================================

  Personal Information
     1.  Full Name  (full_name)
     2.  First Name  (first_name)
     3.  Last Name  (last_name)
     ...

  Contact
     7.  Email  (email)
     8.  Phone  (phone)
     ...

  Professional
    14.  Current Title  (current_title)
    16.  Skills  (skills)
    17.  Experience  (experience)
    ...

  Links
    20.  LinkedIn  (linkedin)
    21.  GitHub  (github)
    22.  Portfolio  (portfolio)

  Metadata
    23.  Candidate ID  (candidate_id)
    24.  Confidence Score  (confidence)
    25.  Provenance Records  (provenance)
==============================================================
```

---

## Architecture

```
Input Sources
    ↓
Source Adapters         (CSVAdapter | ATSAdapter | ResumeAdapter | GitHubAdapter)
    ↓
CandidateFragment[]     (one fragment per source record)
    ↓
IdentityNormalizer      (phone → E.164, email → lowercase, name → title case)
    ↓
IdentityResolutionService  (fuzzy similarity → Union-Find clusters)
    ↓
CanonicalNormalizer     (skills / companies / locations / titles / dates → vocab)
    ↓
MergeEngine             (Strategy: WeightedPriority | MajorityVote | LatestTimestamp)
    ↓
EvidenceEngine          (reliability × coverage − conflict penalty → Confidence)
    ↓
CanonicalCandidateBuilder  (assembles typed CanonicalCandidate from merge decisions)
    ↓
Projection Wizard       (runtime field selection, renaming, missing-value policy)
    ↓
ProjectionService       (include_fields → missing_policy → rename_fields)
    ↓
SchemaValidator         (jsonschema Draft-7)
    ↓
output/candidate_NNN.json
```

**Key design patterns:**
- **Adapter Pattern** — each source type has an isolated adapter; adding a new source requires only one new file
- **Strategy Pattern** — merge policy is swappable via `configs/resolver.yaml` with no code changes
- **ProcessingContext** — single shared state object passed by reference through every stage; stages are fully decoupled
- **MultiCandidateRunner** — global identity resolution clusters all fragments, then a focused pipeline runs per cluster; no cross-contamination between candidates

---

## Folder Structure

```
candidate-transform-pipeline/
├── input/                      # Bundled demo dataset (multi-candidate)
│   ├── recruiter.csv           # 10 candidates
│   ├── ats.json                # 10 candidates
│   ├── resumes/                # 10 PDF resume files
│   └── github/                 # 6 GitHub JSON profiles
├── src/
│   ├── adapters/               # CSV, ATS, Resume, GitHub adapters
│   ├── confidence/             # EvidenceEngine
│   ├── config/                 # ConfigLoader (YAML → typed config models)
│   ├── identity/               # IdentityNormalizer, IdentityResolutionService
│   ├── models/                 # Pydantic models (fragment, candidate, context…)
│   ├── normalization/          # CanonicalNormalizer
│   ├── pipeline/               # Stage ABC, Orchestrator, CanonicalCandidateBuilder
│   ├── projection/             # ProjectionService, interactive Wizard
│   ├── resolver/               # MergeEngine + 3 strategy implementations
│   ├── runner/                 # DatasetLoader, MultiCandidateRunner
│   ├── tests/                  # Internal test runner (used by `test` command)
│   ├── utils/                  # logger, constants, cli_display
│   ├── validation/             # SchemaValidator
│   └── main.py                 # Typer CLI entry point
├── configs/
│   ├── pipeline.yaml
│   ├── resolver.yaml
│   └── confidence.yaml
├── test_cases/                 # 7 curated end-to-end scenarios
├── tests/                      # pytest unit suite (56 tests)
├── output/                     # Pipeline JSON output
└── requirements.txt
```

---

## Configuration

### `configs/resolver.yaml` — Merge Strategy

```yaml
resolver:
  merge_strategy: weighted_priority   # weighted_priority | majority_vote | latest_timestamp
  source_priorities:
    ats: 1.0
    resume: 0.8
    csv: 0.6
    github: 0.4
```

### `configs/confidence.yaml` — Confidence Weights

```yaml
confidence:
  minimum_confidence_threshold: 0.5
  source_weights:
    ats: 0.9
    resume: 0.75
    csv: 0.6
    github: 0.5
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `python -m src.main run` | Full interactive pipeline (source selection + projection wizard) |
| `python -m src.main run --no-wizard` | Run and output all fields, no wizard |
| `python -m src.main run --dry-run` | Process data, skip writing files |
| `python -m src.main test` | Run all 7 curated test cases (no user input) |
| `python -m src.main inspect` | Display canonical schema grouped by category |
| `python -m src.main validate <file>` | Validate a JSON output file against schema |
| `python -m src.main version` | Print pipeline version |

---

## Test Results

```
56 / 56  unit tests passing   (pytest tests/)
 7 /  7  integration tests passing   (python -m src.main test)
```
