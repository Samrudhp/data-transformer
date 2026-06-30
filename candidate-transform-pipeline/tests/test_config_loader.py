"""
Tests for the ConfigLoader.
"""

import pytest
from pathlib import Path
from src.config.config_loader import ConfigLoader, AppConfig, PipelineConfig, ResolverConfig, ConfidenceConfig


class TestConfigLoader:
    def test_load_pipeline_config(self, tmp_path):
        (tmp_path / "pipeline.yaml").write_text(
            "pipeline:\n  stage_order:\n    - identity_normalizer\n    - merge_engine\n  max_errors_before_abort: 3\n"
        )
        (tmp_path / "resolver.yaml").write_text("resolver:\n  merge_strategy: weighted_priority\n")
        (tmp_path / "confidence.yaml").write_text("confidence:\n  minimum_confidence_threshold: 0.6\n")
        config = ConfigLoader(tmp_path).load()
        assert isinstance(config.pipeline, PipelineConfig)
        assert "identity_normalizer" in config.pipeline.stage_order
        assert config.pipeline.max_errors_before_abort == 3

    def test_load_resolver_config(self, tmp_path):
        (tmp_path / "pipeline.yaml").write_text("pipeline:\n  stage_order: []\n")
        (tmp_path / "resolver.yaml").write_text(
            "resolver:\n  merge_strategy: majority_vote\n  source_priorities:\n    ats: 1.0\n    csv: 0.6\n"
        )
        (tmp_path / "confidence.yaml").write_text("confidence:\n")
        config = ConfigLoader(tmp_path).load()
        assert config.resolver.merge_strategy == "majority_vote"
        assert config.resolver.source_priorities["ats"] == 1.0

    def test_load_confidence_config(self, tmp_path):
        (tmp_path / "pipeline.yaml").write_text("pipeline:\n  stage_order: []\n")
        (tmp_path / "resolver.yaml").write_text("resolver:\n")
        (tmp_path / "confidence.yaml").write_text(
            "confidence:\n  minimum_confidence_threshold: 0.75\n  source_weights:\n    ats: 1.0\n    csv: 0.5\n"
        )
        config = ConfigLoader(tmp_path).load()
        assert config.confidence.minimum_confidence_threshold == 0.75
        assert config.confidence.source_weights["ats"] == 1.0

    def test_missing_file_uses_defaults(self, tmp_path):
        config = ConfigLoader(tmp_path).load()
        assert isinstance(config, AppConfig)
        assert config.resolver.merge_strategy == "weighted_priority"

    def test_returns_app_config(self):
        config = ConfigLoader(Path("configs")).load()
        assert isinstance(config, AppConfig)
        assert isinstance(config.pipeline, PipelineConfig)
        assert isinstance(config.resolver, ResolverConfig)
        assert isinstance(config.confidence, ConfidenceConfig)
