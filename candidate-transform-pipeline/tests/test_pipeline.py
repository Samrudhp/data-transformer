"""
Tests for the pipeline orchestrator and stage contract.
"""

import pytest
from src.models.processing_context import ProcessingContext
from src.pipeline.orchestrator import PipelineOrchestrator
from src.pipeline.stage import Stage


class _PassStage(Stage):
    """Stage that always succeeds and records it ran."""
    def execute(self, context: ProcessingContext) -> ProcessingContext:
        context.execution_logs.append("PassStage ran")
        return context


class _ErrorStage(Stage):
    """Stage that raises a RuntimeError."""
    def execute(self, context: ProcessingContext) -> ProcessingContext:
        raise RuntimeError("deliberate stage error")


class _NotImplStage(Stage):
    """Stage that raises NotImplementedError."""
    def execute(self, context: ProcessingContext) -> ProcessingContext:
        raise NotImplementedError()


class TestPipelineOrchestrator:
    def test_run_empty_stages(self):
        ctx = ProcessingContext()
        orch = PipelineOrchestrator(stages=[])
        result = orch.run(ctx)
        assert result is ctx

    def test_pass_stage_runs(self):
        ctx = ProcessingContext()
        orch = PipelineOrchestrator(stages=[_PassStage()])
        result = orch.run(ctx)
        assert "PassStage ran" in result.execution_logs

    def test_stage_error_is_recorded(self):
        ctx = ProcessingContext()
        orch = PipelineOrchestrator(stages=[_ErrorStage()])
        result = orch.run(ctx)
        assert len(result.errors) == 1
        assert "deliberate stage error" in result.errors[0]

    def test_stage_not_implemented_becomes_warning(self):
        ctx = ProcessingContext()
        orch = PipelineOrchestrator(stages=[_NotImplStage()])
        result = orch.run(ctx)
        assert len(result.warnings) == 1
        assert len(result.errors) == 0

    def test_pipeline_continues_after_error(self):
        """An erroring stage should not stop subsequent stages."""
        ctx = ProcessingContext()
        orch = PipelineOrchestrator(stages=[_ErrorStage(), _PassStage()])
        result = orch.run(ctx)
        assert len(result.errors) == 1
        assert "PassStage ran" in result.execution_logs

    def test_execution_logs_order(self):
        ctx = ProcessingContext()
        orch = PipelineOrchestrator(stages=[_PassStage()])
        result = orch.run(ctx)
        logs = result.execution_logs
        started = any("STARTED" in l for l in logs)
        completed = any("COMPLETED" in l for l in logs)
        assert started and completed
