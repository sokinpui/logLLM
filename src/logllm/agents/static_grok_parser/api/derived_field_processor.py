# src/logllm/agents/static_grok_parser/api/derived_field_processor.py
import string
from typing import Any, Dict, Optional

from ....utils.logger import Logger  # Assuming logger is in utils


class DerivedFieldProcessor:
    def __init__(self, logger: Optional[Logger] = None):
        self._logger = logger if logger else Logger()  # Use provided or default logger
        self._string_formatter = string.Formatter()

    def _get_required_keys_from_format_string(self, format_string: str) -> list[str]:
        """Extracts placeholder keys from a Python format string."""
        return [
            fname
            for _, fname, _, _ in self._string_formatter.parse(format_string)
            if fname is not None
        ]

    def process_derived_fields(
        self,
        parsed_grok_fields: Dict[str, Any],
        derived_field_definitions: Optional[Dict[str, str]],
        context_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Processes Grok-parsed fields to create new derived fields based on definitions.

        Args:
            parsed_grok_fields: The dictionary of fields extracted by the main Grok pattern.
                                This dictionary will be modified in place if derived fields are created.
            derived_field_definitions: A dictionary where keys are new field names and
                                       values are Python format strings (e.g., {"new_ts": "{day} {month}"}).
            context_info: Optional dictionary with context for logging (e.g.,
                          {"log_file_id": "id123", "line_num": 42, "group_name": "apache"}).

        Returns:
            The `parsed_grok_fields` dictionary, augmented with any successfully derived fields.
        """
        if not derived_field_definitions or not parsed_grok_fields:
            return parsed_grok_fields  # Return original if no definitions or no initial fields

        log_context_str = ""
        if context_info:
            log_context_str = (
                f" (Context: {', '.join(f'{k}={v}' for k, v in context_info.items())})"
            )

        for derived_field_name, format_string in derived_field_definitions.items():
            if not isinstance(format_string, str):
                self._logger.warning(
                    f"Format string for derived field '{derived_field_name}' is not a string (got {type(format_string)}). Skipping.{log_context_str}"
                )
                continue

            try:
                required_keys = self._get_required_keys_from_format_string(
                    format_string
                )

                missing_keys = [
                    key for key in required_keys if key not in parsed_grok_fields
                ]

                if missing_keys:
                    self._logger.warning(
                        f"Cannot derive field '{derived_field_name}'. Missing keys from Grok output: {missing_keys} for format string '{format_string}'. Available Grok keys: {list(parsed_grok_fields.keys())}.{log_context_str}"
                    )
                    continue

                derived_value = format_string.format(**parsed_grok_fields)
                parsed_grok_fields[derived_field_name] = (
                    derived_value  # Add to the dictionary
                )
                self._logger.debug(
                    f"Derived field '{derived_field_name}' = '{derived_value}'.{log_context_str}"
                )

            except (
                KeyError
            ) as ke:  # Should be caught by missing_keys check, but as a safeguard
                self._logger.warning(
                    f"KeyError deriving field '{derived_field_name}'. Missing key {ke} in Grok output for format string '{format_string}'.{log_context_str}"
                )
            except (
                ValueError
            ) as ve:  # e.g. if format specifiers are incorrect like {var:xyz} with bad xyz
                self._logger.warning(
                    f"ValueError deriving field '{derived_field_name}' with format '{format_string}'. Error: {ve}. Ensure format specifiers are valid.{log_context_str}"
                )
            except Exception as e_derive:
                self._logger.error(
                    f"Unexpected error deriving field '{derived_field_name}' with format '{format_string}'. Error: {e_derive}.{log_context_str}",
                    exc_info=False,  # Set to True for full traceback if needed during debugging
                )

        return parsed_grok_fields
