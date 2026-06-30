# Test Cases

This directory contains curated end-to-end test input fixtures for the
`candidate-pipeline test` CLI command.

Each test case is a subdirectory containing:

```
test_cases/
└── <case_name>/
    ├── inputs/         # Source files (CSV, PDF, JSON, etc.)
    └── expected.json   # Expected pipeline output for comparison
```

Test cases will be added in Prompt 2 alongside the full implementation.
