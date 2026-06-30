"""
BaseAdapter — abstract interface for all source adapters.

Every concrete adapter must implement load(), parse(), and to_candidate_fragment()
following the Adapter Pattern. Each adapter has a single responsibility: ingest
data from one source type and produce CandidateFragment objects.
"""

from abc import ABC, abstractmethod
from typing import Any, List

from src.models.candidate_fragment import CandidateFragment


class BaseAdapter(ABC):
    """
    Abstract base class defining the contract for all source adapters.

    Concrete adapters implement three lifecycle methods:
        1. ``load()``   — acquire raw data from the source.
        2. ``parse()``  — transform raw data into an intermediate representation.
        3. ``to_candidate_fragment()`` — produce one or more CandidateFragment objects.
    """

    @abstractmethod
    def load(self) -> Any:
        """
        Load raw data from the upstream source.

        Returns:
            The raw data in a source-specific format (file handle, dict, etc.).
        """
        raise NotImplementedError()

    @abstractmethod
    def parse(self, raw_data: Any) -> Any:
        """
        Parse raw source data into an intermediate structured representation.

        Args:
            raw_data: The raw data returned by ``load()``.

        Returns:
            An intermediate representation ready for fragment extraction.
        """
        raise NotImplementedError()

    @abstractmethod
    def to_candidate_fragment(self, parsed_data: Any) -> List[CandidateFragment]:
        """
        Convert parsed data into one or more CandidateFragment objects.

        Args:
            parsed_data: The intermediate representation returned by ``parse()``.

        Returns:
            A list of CandidateFragment instances extracted from this source.
        """
        raise NotImplementedError()
