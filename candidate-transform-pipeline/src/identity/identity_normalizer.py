"""
IdentityNormalizer — normalizes identity fields across candidate fragments
before cross-source resolution is attempted.

Normalises:
  - Phone numbers → E.164-like string  (+919876543210)
  - Email addresses → lowercase
  - Names → title-cased, collapsed whitespace
  - GitHub URLs → canonical https://github.com/<user> form
"""

import copy
import re
from typing import List, Optional

from src.models.candidate_fragment import CandidateFragment
from src.models.processing_context import ProcessingContext
from src.pipeline.stage import Stage
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_PHONE_DIGITS_RE = re.compile(r"\D")          # strip non-digits
_GITHUB_PROFILE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9\-]+)", re.IGNORECASE
)


class IdentityNormalizer(Stage):
    """
    Pipeline stage that normalizes identity-bearing fields across all
    candidate fragments to a consistent canonical form.

    The original fragments are NOT mutated. Normalised copies are stored
    in ``context.normalized_fragments``.
    """

    # ------------------------------------------------------------------
    # Stage entry point
    # ------------------------------------------------------------------

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Normalise identity fields in every candidate fragment.

        Args:
            context: Shared pipeline context with raw candidate fragments.

        Returns:
            Updated context with ``normalized_fragments`` populated.
        """
        logger.info(
            "IdentityNormalizer: normalizing %d fragment(s).",
            len(context.candidate_fragments),
        )
        normalised: List[CandidateFragment] = []
        for fragment in context.candidate_fragments:
            try:
                normalised.append(self._normalize_fragment(fragment))
            except Exception as exc:  # noqa: BLE001
                warning = (
                    f"IdentityNormalizer: failed to normalise fragment "
                    f"from source='{fragment.source}': {exc}"
                )
                logger.warning(warning)
                context.warnings.append(warning)
                # Fall back to a shallow copy so downstream stages still
                # receive something to work with.
                normalised.append(fragment.model_copy(deep=True))

        context.normalized_fragments = normalised
        logger.info(
            "IdentityNormalizer: completed — %d normalised fragment(s).",
            len(normalised),
        )
        return context

    # ------------------------------------------------------------------
    # Fragment-level normalisation
    # ------------------------------------------------------------------

    def _normalize_fragment(self, fragment: CandidateFragment) -> CandidateFragment:
        """
        Return a deep copy of *fragment* with identity fields normalised.
        """
        fields = copy.deepcopy(fragment.extracted_fields)

        # Normalise each identity field in place.
        if "email" in fields:
            fields["email"] = self.normalize_email(fields["email"])

        if "phone" in fields:
            fields["phone"] = self.normalize_phone(fields["phone"])

        for name_key in ("full_name", "first_name", "last_name"):
            if name_key in fields:
                fields[name_key] = self.normalize_name(fields[name_key])

        if "github" in fields:
            fields["github"] = self.normalize_github_url(fields["github"])

        return CandidateFragment(
            source=fragment.source,
            extracted_fields=fields,
            metadata=copy.deepcopy(fragment.metadata),
            raw_input_reference=fragment.raw_input_reference,
        )

    # ------------------------------------------------------------------
    # Field-level normalisation methods (public for unit testing)
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_email(value: Optional[str]) -> Optional[str]:
        """
        Normalise an email address to lowercase.

        Examples:
            SAM@GMAIL.COM → sam@gmail.com
        """
        if not value or not isinstance(value, str):
            return value
        return value.strip().lower()

    @staticmethod
    def normalize_phone(value: Optional[str]) -> Optional[str]:
        """
        Normalise a phone number to a compact E.164-like digit string.

        Strips all non-digit characters, then applies simple country-code
        heuristics for Indian numbers (leading 0 → +91).

        Examples:
            9876543210     → +919876543210
            09876543210    → +919876543210
            +91 9876543210 → +919876543210
            +1-800-555-0100 → +18005550100
        """
        if not value or not isinstance(value, str):
            return value

        digits = _PHONE_DIGITS_RE.sub("", value.strip())

        # Preserve leading + indicator.
        has_plus = value.strip().startswith("+")

        if has_plus:
            return f"+{digits}"

        # 10-digit Indian mobile (no country code).
        if len(digits) == 10 and digits[0] in "6789":
            return f"+91{digits}"

        # 11-digit with leading 0 (Indian STD format).
        if len(digits) == 11 and digits.startswith("0"):
            return f"+91{digits[1:]}"

        # 12-digit with 91 prefix (already has country code, no +).
        if len(digits) == 12 and digits.startswith("91"):
            return f"+{digits}"

        # Default: return digits only.
        return digits

    @staticmethod
    def normalize_name(value: Optional[str]) -> Optional[str]:
        """
        Title-case a name and collapse internal whitespace.

        Examples:
            "  john  doe  " → "John Doe"
            "ALICE SMITH"   → "Alice Smith"
        """
        if not value or not isinstance(value, str):
            return value
        return " ".join(value.split()).title()

    @staticmethod
    def normalize_github_url(value: Optional[str]) -> Optional[str]:
        """
        Normalise a GitHub URL or username to the canonical profile URL.

        Examples:
            github.com/johndoe         → https://github.com/johndoe
            https://github.com/johndoe → https://github.com/johndoe
            johndoe                    → https://github.com/johndoe
        """
        if not value or not isinstance(value, str):
            return value
        value = value.strip()
        match = _GITHUB_PROFILE_RE.match(value)
        if match:
            return f"https://github.com/{match.group(1)}"
        # Bare username (no slashes or dots).
        if "/" not in value and "." not in value:
            return f"https://github.com/{value}"
        return value
