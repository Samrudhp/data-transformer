"""
SchemaValidator — validates the final projected output against a JSON Schema.

Uses jsonschema Draft-7. Raises informative errors on failure.
"""

import time
from typing import Any, Dict

import jsonschema
from jsonschema import Draft7Validator, ValidationError

from src.models.processing_context import ProcessingContext
from src.pipeline.stage import Stage
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Default minimal schema — accepts any object.
# The ``run`` command passes a richer schema built from the projection.
_DEFAULT_SCHEMA: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
}


class SchemaValidator(Stage):
    """
    Pipeline stage that validates the projected output dictionary against
    a JSON Schema, ensuring structural and type correctness before the
    result is returned to the caller.
    """

    def __init__(self, schema: Dict[str, Any] = _DEFAULT_SCHEMA) -> None:
        """
        Args:
            schema: JSON Schema dict (Draft-07). Defaults to a permissive
                    object schema.
        """
        self.schema = schema
        self._validator = Draft7Validator(schema)

    def validate(self, output: Dict[str, Any]) -> bool:
        """
        Validate ``output`` against the configured JSON Schema.

        Args:
            output: The final projected candidate output dictionary.

        Returns:
            ``True`` if valid.

        Raises:
            jsonschema.ValidationError: If the output does not conform.
        """
        errors = sorted(
            self._validator.iter_errors(output), key=lambda e: list(e.path)
        )
        if errors:
            messages = "; ".join(e.message for e in errors[:5])
            raise ValidationError(
                f"Output schema validation failed: {messages}",
                instance=output,
                schema=self.schema,
            )
        return True

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Validate the projected output stored in the context.

        Looks for ``context.evidence``'s sibling ``projected_output`` key
        injected by the CLI, or falls back to validating the canonical
        candidate serialisation.

        Args:
            context: Shared pipeline context.

        Returns:
            Updated context (errors recorded if validation fails).
        """
        start = time.time()
        logger.info("SchemaValidator: validating final output.")

        # The projected output is passed via a custom metadata slot.
        output: Any = getattr(context, "_projected_output", None)
        if output is None and context.canonical_candidate is not None:
            output = context.canonical_candidate.model_dump(mode="python")

        if output is None:
            warning = "SchemaValidator: nothing to validate (no output available)."
            logger.warning(warning)
            context.warnings.append(warning)
            return context

        try:
            self.validate(output)
            elapsed = time.time() - start
            logger.info(
                "SchemaValidator: validation passed in %.3fs.", elapsed
            )
        except ValidationError as exc:
            error_msg = f"SchemaValidator: validation failed — {exc.message}"
            logger.error(error_msg)
            context.errors.append(error_msg)

        return context
