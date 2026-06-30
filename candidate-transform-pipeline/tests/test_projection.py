"""
Tests for the ProjectionService.
"""

import pytest
from src.projection.projection_service import ProjectionService
from src.models.projection_request import ProjectionRequest
from src.models.canonical_candidate import CanonicalCandidate, PersonalInfo, ContactInfo


def _make_candidate() -> CanonicalCandidate:
    return CanonicalCandidate(
        candidate_id="test-001",
        personal_info=PersonalInfo(full_name="Test User", first_name="Test", last_name="User"),
        contact=ContactInfo(email="test@example.com", phone="+919876543210"),
        skills=["Python", "Go", "Docker"],
    )


class TestProjectionService:
    def setup_method(self):
        self.svc = ProjectionService()
        self.candidate = _make_candidate()

    def test_include_all_when_empty(self):
        req = ProjectionRequest()
        out = self.svc.project(self.candidate, req)
        assert "personal_info" in out
        assert "skills" in out
        assert "contact" in out

    def test_include_specific_fields(self):
        req = ProjectionRequest(include=["skills", "contact"])
        out = self.svc.project(self.candidate, req)
        assert "skills" in out
        assert "contact" in out
        assert "personal_info" not in out
        assert "education" not in out

    def test_rename_fields(self):
        req = ProjectionRequest(
            include=["skills", "contact"],
            rename={"skills": "technicalSkills", "contact": "contactDetails"},
        )
        out = self.svc.project(self.candidate, req)
        assert "technicalSkills" in out
        assert "contactDetails" in out
        assert "skills" not in out
        assert "contact" not in out

    def test_missing_policy_omit(self):
        req = ProjectionRequest(
            include=["skills", "nonexistent_field"],
            missing_policy="omit",
        )
        out = self.svc.project(self.candidate, req)
        assert "skills" in out
        assert "nonexistent_field" not in out

    def test_missing_policy_null(self):
        req = ProjectionRequest(
            include=["skills", "nonexistent_field"],
            missing_policy="null",
        )
        out = self.svc.project(self.candidate, req)
        assert "skills" in out
        assert out.get("nonexistent_field") is None

    def test_missing_policy_error(self):
        req = ProjectionRequest(
            include=["nonexistent_field"],
            missing_policy="error",
        )
        with pytest.raises(KeyError):
            self.svc.project(self.candidate, req)

    def test_candidate_unmodified_after_projection(self):
        """CanonicalCandidate must remain unchanged after projection."""
        original_skills = list(self.candidate.skills)
        req = ProjectionRequest(include=["skills"], rename={"skills": "s"})
        self.svc.project(self.candidate, req)
        assert self.candidate.skills == original_skills

    def test_include_fields_standalone(self):
        d = {"a": 1, "b": 2, "c": 3}
        result = self.svc.include_fields(d, ["a", "c"])
        assert result == {"a": 1, "c": 3}

    def test_rename_fields_standalone(self):
        d = {"skills": ["Python"], "contact": {"email": "x@y.com"}}
        result = self.svc.rename_fields(d, {"skills": "techSkills"})
        assert "techSkills" in result
        assert "skills" not in result

    def test_apply_missing_policy_omit(self):
        d = {"a": 1}
        result = self.svc.apply_missing_policy(d, ["a", "b"], "omit")
        assert "b" not in result

    def test_apply_missing_policy_null(self):
        d = {"a": 1}
        result = self.svc.apply_missing_policy(d, ["a", "b"], "null")
        assert result["b"] is None
