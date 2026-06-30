"""
Stage — abstract base class for all pipeline stages.

Every stage in the transformation pipeline must implement the ``execute()``
method, which receives the shared ProcessingContext, operates on it,
and returns the updated context.
"""

from abc import ABC, abstractmethod

from src.models.processing_context import ProcessingContext


class Stage(ABC):
    """
    Abstract pipeline stage.

    Each concrete stage encapsulates a single, well-defined transformation
    responsibility (Single Responsibility Principle). Stages are composable
    and executed sequentially by the PipelineOrchestrator.
    """

    @property
    def name(self) -> str:
        """
        Human-readable name of this stage, used in logs and decision traces.

        Returns:
            The class name by default; subclasses may override.
        """
        return self.__class__.__name__

    @abstractmethod
    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Execute this pipeline stage against the shared processing context.

        Args:
            context: The shared ProcessingContext instance carrying all
                     intermediate state accumulated so far.

        Returns:
            The updated ProcessingContext after this stage's transformations.
        """
        raise NotImplementedError()
