"""
Tests for Pydantic data models.
"""

import pytest
from src.models.candidate_fragment import CandidateFragment
from src.models.canonical_candidate import CanonicalCandidate, PersonalInfo, ContactInfo
from src.models.projection_request import ProjectionRequest
from src.models.processing_context import ProcessingContext
from src.models.confidence import Confidence
from src.models.provenance import Provenance
from datetime import datetime


class TestCandidateFragment:
    def test_instantiation_defaults(self):
        f = CandidateFragment(source="csv")
        assert f.source == "csv"
        assert f.extracted_fields == {}
        assert f.metadata == {}
        assert f.raw_input_reference is None

    def test_with_fields(self):
        f = CandidateFragment(
            source="ats",
            extracted_fields={"email": "a@b.com", "skills": ["Python"]},
            metadata={"row": 0},
            raw_input_reference="/data/file.json",
        )
        assert f.extracted_fields["email"] == "a@b.com"
        assert f.metadata["row"] == 0


class TestCanonicalCandidate:
    def test_instantiation(self):
        c = CanonicalCandidate(candidate_id="test-001")
        assert c.candidate_id == "test-001"
        assert c.personal_info.full_name is None
        assert c.skills == []
        assert c.education == []
        assert c.experience == []

    def test_with_full_data(self):
        conf = Confidence(value=0.85, supporting_sources=["csv", "ats"], reasons=["test"])
        c = CanonicalCandidate(
            candidate_id="c-002",
            personal_info=PersonalInfo(full_name="Jane Doe"),
            contact=ContactInfo(email="jane@example.com"),
            skills=["Python", "Go"],
            confidence=conf,
        )
        assert c.personal_info.full_name == "Jane Doe"
        assert c.contact.email == "jane@example.com"
        assert "Python" in c.skills
        assert c.confidence.value == 0.85


class TestProjectionRequest:
    def test_defaults(self):
        req = ProjectionRequest()
        assert req.include == []
        assert req.rename == {}
        assert req.missing_policy == "omit"

    def test_missing_policy_literal(self):
        for policy in ("omit", "null", "error"):
            req = ProjectionRequest(missing_policy=policy)
            assert req.missing_policy == policy

    def test_invalid_policy_raises(self):
        with pytest.raises(Exception):
            ProjectionRequest(missing_policy="ignore")

    def test_with_rename(self):
        req = ProjectionRequest(
            include=["skills", "contact"],
            rename={"contact": "contactDetails"},
            missing_policy="null",
        )
        assert req.rename["contact"] == "contactDetails"


class TestProcessingContext:
    def test_instantiation_empty(self):
        ctx = ProcessingContext()
        assert ctx.candidate_fragments == []
        assert ctx.normalized_fragments == []
        assert ctx.merge_decisions == []
        assert ctx.errors == []
        assert ctx.warnings == []
        assert ctx.canonical_candidate is None

    def test_with_fragments(self):
        f = CandidateFragment(source="csv", extracted_fields={"email": "x@y.com"})
        ctx = ProcessingContext(candidate_fragments=[f])
        assert len(ctx.candidate_fragments) == 1
        assert ctx.candidate_fragments[0].source == "csv"
