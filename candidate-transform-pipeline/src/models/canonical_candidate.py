"""
CanonicalCandidate model — the master internal representation of a candidate.

This is the central data object produced by the merge and normalization stages
and consumed by projection and output validation.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.models.confidence import Confidence
from src.models.provenance import Provenance


class PersonalInfo(BaseModel):
    """Basic personal identity fields."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None


class ContactInfo(BaseModel):
    """Contact details for a candidate."""

    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None


class Education(BaseModel):
    """A single education entry."""

    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    gpa: Optional[float] = None


class Experience(BaseModel):
    """A single work experience entry."""

    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    is_current: bool = False


class Project(BaseModel):
    """A single project entry."""

    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class Links(BaseModel):
    """External profile links."""

    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: Dict[str, str] = Field(default_factory=dict)


class CanonicalCandidate(BaseModel):
    """
    Master internal representation of a fully resolved and merged candidate.

    This object is constructed by the pipeline after identity resolution,
    normalization, and merge processing. It serves as the source of truth
    fed into projection and output validation.

    Attributes:
        candidate_id: Unique pipeline-assigned identifier for this candidate.
        personal_info: Basic personal identity fields.
        contact: Contact details.
        education: Ordered list of education entries.
        experience: Ordered list of work experience entries.
        projects: List of project entries.
        skills: List of normalized skill strings.
        links: External profile links.
        confidence: Aggregate confidence metadata for this record.
        provenance: List of provenance records tracking field-level origin.
    """

    candidate_id: str = Field(..., description="Pipeline-assigned unique candidate ID.")
    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    contact: ContactInfo = Field(default_factory=ContactInfo)
    education: List[Education] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    links: Links = Field(default_factory=Links)
    confidence: Optional[Confidence] = Field(
        None, description="Aggregate confidence score for this candidate record."
    )
    provenance: List[Provenance] = Field(
        default_factory=list,
        description="Field-level provenance tracking from all contributing sources.",
    )
