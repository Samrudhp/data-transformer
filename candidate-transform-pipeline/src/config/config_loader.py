"""
ConfigLoader — loads and returns strongly typed configuration objects from YAML files.

Loads exactly three configuration files:
  - pipeline.yaml  — stage order and pipeline settings.
  - resolver.yaml  — merge strategy and source priorities.
  - confidence.yaml — confidence weights per source and field.

Projection configuration is intentionally absent: projection is runtime-driven
via ProjectionRequest, not static configuration.
"""

from pathlib import Path
from typing import Any, Dict, List

import yaml
from pydantic import BaseModel, Field

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Strongly typed configuration models
# ---------------------------------------------------------------------------


class PipelineConfig(BaseModel):
    """
    Typed representation of pipeline.yaml.

    Attributes:
        stage_order: Ordered list of stage class names to execute.
        max_errors_before_abort: Stop the pipeline after this many stage errors.
    """

    stage_order: List[str] = Field(default_factory=list)
    max_errors_before_abort: int = Field(default=5)


class ResolverConfig(BaseModel):
    """
    Typed representation of resolver.yaml.

    Attributes:
        merge_strategy: Name of the default merge strategy to use.
        source_priorities: Mapping of source identifier to numeric priority weight.
    """

    merge_strategy: str = Field(default="weighted_priority")
    source_priorities: Dict[str, float] = Field(default_factory=dict)


class ConfidenceConfig(BaseModel):
    """
    Typed representation of confidence.yaml.

    Attributes:
        source_weights: Per-source reliability weights used in scoring.
        field_weights: Per-field importance weights.
        minimum_confidence_threshold: Records below this score are flagged.
    """

    source_weights: Dict[str, float] = Field(default_factory=dict)
    field_weights: Dict[str, float] = Field(default_factory=dict)
    minimum_confidence_threshold: float = Field(default=0.5)


class AppConfig(BaseModel):
    """
    Aggregated application configuration object.

    Attributes:
        pipeline: Parsed pipeline.yaml configuration.
        resolver: Parsed resolver.yaml configuration.
        confidence: Parsed confidence.yaml configuration.
    """

    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    resolver: ResolverConfig = Field(default_factory=ResolverConfig)
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class ConfigLoader:
    """
    Reads YAML configuration files and returns a fully populated AppConfig.

    Only pipeline.yaml, resolver.yaml, and confidence.yaml are loaded.
    """

    def __init__(self, config_dir: Path) -> None:
        """
        Args:
            config_dir: Directory containing the three YAML config files.
        """
        self.config_dir = config_dir

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """
        Read and parse a single YAML file from the config directory.

        Args:
            filename: File name relative to ``config_dir``.

        Returns:
            Parsed YAML as a plain dictionary. Returns empty dict if file
            is missing or empty.
        """
        filepath = self.config_dir / filename
        if not filepath.exists():
            logger.warning("Config file not found: %s — using defaults.", filepath)
            return {}
        with filepath.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if data is None:
            logger.warning("Config file is empty: %s — using defaults.", filepath)
            return {}
        logger.debug("Loaded config: %s", filepath)
        return data  # type: ignore[return-value]

    def load(self) -> AppConfig:
        """
        Load all configuration files and return a typed AppConfig.

        Returns:
            Fully populated AppConfig instance.
        """
        raw_pipeline = self._load_yaml("pipeline.yaml").get("pipeline") or {}
        raw_resolver = self._load_yaml("resolver.yaml").get("resolver") or {}
        raw_confidence = self._load_yaml("confidence.yaml").get("confidence") or {}

        pipeline_cfg = PipelineConfig(
            stage_order=raw_pipeline.get("stage_order", []),
            max_errors_before_abort=raw_pipeline.get("max_errors_before_abort", 5),
        )

        resolver_cfg = ResolverConfig(
            merge_strategy=raw_resolver.get("merge_strategy", "weighted_priority"),
            source_priorities=raw_resolver.get("source_priorities", {}),
        )

        confidence_cfg = ConfidenceConfig(
            source_weights=raw_confidence.get("source_weights", {}),
            field_weights=raw_confidence.get("field_weights", {}),
            minimum_confidence_threshold=raw_confidence.get(
                "minimum_confidence_threshold", 0.5
            ),
        )

        logger.info(
            "Configuration loaded. Strategy=%s  Stages=%d",
            resolver_cfg.merge_strategy,
            len(pipeline_cfg.stage_order),
        )
        return AppConfig(
            pipeline=pipeline_cfg,
            resolver=resolver_cfg,
            confidence=confidence_cfg,
        )
