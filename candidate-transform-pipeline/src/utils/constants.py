"""
Global constants for the candidate transformation pipeline.
"""

# Pipeline stage names
STAGE_IDENTITY_NORMALIZER = "identity_normalizer"
STAGE_IDENTITY_RESOLUTION = "identity_resolution"
STAGE_CANONICAL_NORMALIZER = "canonical_normalizer"
STAGE_MERGE_ENGINE = "merge_engine"
STAGE_EVIDENCE_ENGINE = "evidence_engine"
STAGE_CANONICAL_BUILDER = "canonical_builder"
STAGE_PROJECTION = "projection"
STAGE_SCHEMA_VALIDATOR = "schema_validator"

# Source adapter identifiers
SOURCE_CSV = "csv"
SOURCE_ATS = "ats"
SOURCE_RESUME = "resume"
SOURCE_GITHUB = "github"

# Missing value policies
MISSING_POLICY_OMIT = "omit"
MISSING_POLICY_NULL = "null"
MISSING_POLICY_ERROR = "error"

# Merge strategies
STRATEGY_WEIGHTED_PRIORITY = "weighted_priority"
STRATEGY_MAJORITY_VOTE = "majority_vote"
STRATEGY_LATEST_TIMESTAMP = "latest_timestamp"

# Config file names
CONFIG_PIPELINE = "pipeline.yaml"
CONFIG_RESOLVER = "resolver.yaml"
CONFIG_CONFIDENCE = "confidence.yaml"

# Default confidence threshold
DEFAULT_CONFIDENCE_THRESHOLD: float = 0.5

# Pipeline version
PIPELINE_VERSION = "1.0.0"
