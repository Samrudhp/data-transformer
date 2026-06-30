"""
MergeStrategy — abstract interface for field-level merge strategies.

Follows the Strategy Pattern: the MergeEngine holds a reference to a
MergeStrategy instance and delegates all merge decisions to it, allowing
strategies to be swapped at runtime via configuration.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class MergeStrategy(ABC):
    """
    Abstract merge strategy defining the contract for field-level value selection.

    Each concrete strategy implements a different algorithm for deciding which
    value to keep when the same field appears in multiple candidate fragments.
    """

    @abstractmethod
    def merge(
        self,
        field_name: str,
        values: List[Dict[str, Any]],
    ) -> Any:
        """
        Select or compute the winning value for a candidate field.

        Args:
            field_name: The canonical name of the field being merged.
            values: A list of candidate value dictionaries, each containing
                    at minimum ``"value"`` (the raw value) and ``"source"``
                    (the originating source identifier).

        Returns:
            The merged/selected value for the given field.
        """
        raise NotImplementedError()
