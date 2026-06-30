"""
Tests for source adapters.
"""

import json
from pathlib import Path
import pytest
import tempfile
import os


class TestCSVAdapter:
    def test_load_and_parse(self, tmp_path):
        from src.adapters.csv_adapter import CSVAdapter
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("full_name,email,phone,skills\nAlice Smith,alice@example.com,9876543210,Python\n")
        adapter = CSVAdapter(csv_file)
        raw = adapter.load()
        parsed = adapter.parse(raw)
        assert len(parsed) == 1
        assert parsed[0]["full_name"] == "Alice Smith"
        assert parsed[0]["email"] == "alice@example.com"

    def test_to_candidate_fragment(self, tmp_path):
        from src.adapters.csv_adapter import CSVAdapter
        csv_file = tmp_path / "test.csv"
        csv_file.write_text('full_name,email,skills\nBob Jones,bob@x.com,"Python,Go"\n')
        adapter = CSVAdapter(csv_file)
        raw = adapter.load()
        parsed = adapter.parse(raw)
        fragments = adapter.to_candidate_fragment(parsed)
        assert len(fragments) == 1
        assert fragments[0].source == "csv"
        assert "Python" in fragments[0].extracted_fields["skills"]

    def test_missing_file_raises(self):
        from src.adapters.csv_adapter import CSVAdapter
        adapter = CSVAdapter(Path("/nonexistent/file.csv"))
        with pytest.raises(FileNotFoundError):
            adapter.load()

    def test_empty_csv_raises(self, tmp_path):
        from src.adapters.csv_adapter import CSVAdapter
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("full_name,email\n")
        adapter = CSVAdapter(csv_file)
        with pytest.raises(ValueError):
            adapter.load()


class TestATSAdapter:
    def test_load_single_candidate(self, tmp_path):
        from src.adapters.ats_adapter import ATSAdapter
        data = {"candidates": [{"candidateName": "Carol", "emailAddress": "carol@x.com"}]}
        f = tmp_path / "ats.json"
        f.write_text(json.dumps(data))
        adapter = ATSAdapter({"file_path": str(f)})
        raw = adapter.load()
        parsed = adapter.parse(raw)
        assert len(parsed) == 1
        assert parsed[0]["candidateName"] == "Carol"

    def test_field_mapping(self, tmp_path):
        from src.adapters.ats_adapter import ATSAdapter
        data = {"candidates": [{"candidateName": "Dave", "emailAddress": "dave@x.com", "mobilePhone": "9000000001"}]}
        f = tmp_path / "ats.json"
        f.write_text(json.dumps(data))
        adapter = ATSAdapter({"file_path": str(f)})
        raw = adapter.load()
        parsed = adapter.parse(raw)
        frags = adapter.to_candidate_fragment(parsed)
        assert frags[0].extracted_fields["full_name"] == "Dave"
        assert frags[0].extracted_fields["email"] == "dave@x.com"

    def test_malformed_json_raises(self, tmp_path):
        from src.adapters.ats_adapter import ATSAdapter
        f = tmp_path / "bad.json"
        f.write_text("{ INVALID }")
        adapter = ATSAdapter({"file_path": str(f)})
        with pytest.raises(ValueError):
            adapter.load()

    def test_missing_file_raises(self):
        from src.adapters.ats_adapter import ATSAdapter
        adapter = ATSAdapter({"file_path": "/no/such/file.json"})
        with pytest.raises(FileNotFoundError):
            adapter.load()


class TestGitHubAdapter:
    def test_load_mock_file(self, tmp_path):
        from src.adapters.github_adapter import GitHubAdapter
        data = {"login": "johndoe", "name": "John Doe", "email": "john@x.com",
                "repositories": [{"language": "Python"}, {"language": "Go"}]}
        f = tmp_path / "johndoe_github.json"
        f.write_text(json.dumps(data))
        adapter = GitHubAdapter(username=str(f))
        raw = adapter.load()
        parsed = adapter.parse(raw)
        assert parsed["full_name"] == "John Doe"
        assert "Python" in parsed["skills"]
        assert parsed["github"] == "https://github.com/johndoe"

    def test_missing_file_raises(self):
        from src.adapters.github_adapter import GitHubAdapter
        adapter = GitHubAdapter(username="/nonexistent/file.json")
        with pytest.raises(FileNotFoundError):
            adapter.load()
