"""
PipelineOrchestrator — owns and drives sequential execution of all pipeline stages.

Responsibilities:
  - Construct and own the ProcessingContext for each pipeline run.
  - Execute stages in the configured order.
  - Centralize logging for stage lifecycle events.
  - Centralize exception handling; continue execution when possible.
  - Return the final ProcessingContext to the caller.
"""

from typing import List

from src.models.processing_context import ProcessingContext
from src.pipeline.stage import Stage
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PipelineOrchestrator:
    """
    Drives sequential execution of a configured list of pipeline stages.

    The orchestrator:
      - Instantiates a fresh ProcessingContext at the start of each run.
      - Passes the context through each stage in order.
      - Logs stage start, completion, warning, and error events.
      - Catches per-stage exceptions, records them in the context, and
        continues to subsequent stages where possible.
      - Returns the fully populated ProcessingContext at the end of the run.
    """

    def __init__(self, stages: List[Stage]) -> None:
        """
        Args:
            stages: Ordered list of Stage instances to execute.
        """
        self.stages = stages

    def run(self, context: ProcessingContext) -> ProcessingContext:
        """
        Execute all pipeline stages sequentially against the given context.

        Args:
            context: The initial ProcessingContext (may already contain
                     loaded candidate fragments from adapters).

        Returns:
            The final ProcessingContext after all stages have been executed.
        """
        logger.info("Pipeline run started. Stages to execute: %d", len(self.stages))

        for stage in self.stages:
            logger.info("[STARTED]   Stage: %s", stage.name)
            context.execution_logs.append(f"STARTED: {stage.name}")

            try:
                context = stage.execute(context)
                logger.info("[COMPLETED] Stage: %s", stage.name)
                context.execution_logs.append(f"COMPLETED: {stage.name}")

            except NotImplementedError:
                warning_msg = f"Stage '{stage.name}' is not yet implemented — skipping."
                logger.warning("[WARNING]   %s", warning_msg)
                context.warnings.append(warning_msg)
                context.execution_logs.append(f"SKIPPED (not implemented): {stage.name}")

            except Exception as exc:  # noqa: BLE001
                error_msg = f"Stage '{stage.name}' raised an error: {exc}"
                logger.error("[ERROR]     %s", error_msg)
                context.errors.append(error_msg)
                context.execution_logs.append(f"ERROR: {stage.name} — {exc}")

        logger.info(
            "Pipeline run finished. Warnings: %d | Errors: %d",
            len(context.warnings),
            len(context.errors),
        )
        return context
