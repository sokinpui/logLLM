# src/logllm/agents/timestamp_normalizer/api/timestamp_normalization_service.py
import re
from datetime import datetime, timezone
from typing import Any, Optional

import dateutil.parser  # type: ignore

from ....utils.logger import Logger


class TimestampNormalizationService:
    """
    Service responsible for the core logic of parsing and normalizing
    timestamp values.
    """

    def __init__(self, logger: Optional[Logger] = None):
        self._logger = logger if logger else Logger()
        self.original_timestamp_field_name: str = "timestamp"
        self.target_timestamp_field_name: str = "@timestamp"
        self._iso8601_regex = re.compile(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
        )
        # Regex to check if a string is purely numeric (potentially an epoch string)
        self._numeric_string_regex = re.compile(r"^\d+(\.\d+)?$")

    def is_already_iso8601_utc(self, timestamp_str: str) -> bool:
        """
        Checks if the string appears to be in ISO8601 format and is UTC.
        This is a heuristic check.
        """
        if not isinstance(timestamp_str, str):
            return False
        if self._iso8601_regex.match(timestamp_str):
            try:
                dt = dateutil.parser.isoparse(timestamp_str)
                if dt.tzinfo == timezone.utc or (
                    dt.tzinfo is not None
                    and dt.tzinfo.utcoffset(dt) == timezone.utc.utcoffset(None)
                ):
                    return True
            except ValueError:
                return False
        return False

    def _try_parse_string_as_epoch(self, timestamp_str: str) -> Optional[datetime]:
        """
        Tries to parse a string as a numeric Unix epoch (seconds or milliseconds).
        Returns a datetime object if successful, None otherwise.
        """
        if self._numeric_string_regex.match(timestamp_str):
            try:
                # Attempt to convert to float first, as it can handle both "123" and "123.456"
                epoch_val = float(timestamp_str)
                # Apply the same heuristic as for int/float types
                if epoch_val > 99999999999:  # Likely milliseconds
                    return datetime.fromtimestamp(epoch_val / 1000.0, tz=timezone.utc)
                else:  # Likely seconds
                    return datetime.fromtimestamp(epoch_val, tz=timezone.utc)
            except (
                ValueError
            ):  # String is numeric but not a valid float (should be caught by regex mostly)
                return None
            except OverflowError:  # Timestamp too large/small for fromtimestamp
                self._logger.warning(
                    f"Epoch string '{timestamp_str}' resulted in OverflowError during conversion."
                )
                return None
        return None

    def normalize_timestamp_value(self, raw_timestamp: Any) -> Optional[str]:
        """
        Attempts to parse various raw timestamp formats (string, epoch int/float)
        and converts them to a UTC ISO8601 string with millisecond precision.
        Logs a warning if parsing fails.
        If raw_timestamp is a string that already appears to be ISO8601 UTC, it's returned directly.

        Args:
            raw_timestamp: The raw timestamp value to normalize.

        Returns:
            The normalized ISO8601 string, or None if parsing fails or input is None/empty.
        """
        if raw_timestamp is None:
            return None

        dt_obj: Optional[datetime] = None

        if isinstance(raw_timestamp, str):
            if not raw_timestamp.strip():
                return None

            # Optimization: If it already looks like ISO8601 UTC, return it
            if self.is_already_iso8601_utc(raw_timestamp):
                return raw_timestamp

            # NEW: Check if the string is a numeric epoch timestamp
            dt_from_epoch_str = self._try_parse_string_as_epoch(raw_timestamp)
            if dt_from_epoch_str:
                dt_obj = dt_from_epoch_str
            else:
                # If not an epoch string, try general parsing with dateutil
                try:
                    dt_obj = dateutil.parser.parse(raw_timestamp)
                except (
                    ValueError,
                    TypeError,
                ) as e:  # dateutil.parser.parse specific errors
                    self._logger.warning(
                        f"dateutil.parser.parse could not parse timestamp string '{str(raw_timestamp)[:100]}': {e}"
                    )
                    return None  # Failed to parse as a date string by dateutil

        elif isinstance(raw_timestamp, (int, float)):
            try:
                if raw_timestamp > 99999999999:
                    dt_obj = datetime.fromtimestamp(
                        raw_timestamp / 1000.0, tz=timezone.utc
                    )
                else:
                    dt_obj = datetime.fromtimestamp(raw_timestamp, tz=timezone.utc)
            except OverflowError:
                self._logger.warning(
                    f"Numeric epoch {raw_timestamp} resulted in OverflowError during conversion."
                )
                return None
        else:
            self._logger.warning(
                f"Timestamp field is of unsupported type: {type(raw_timestamp)}, value: {str(raw_timestamp)[:100]}. Cannot normalize."
            )
            return None

        # Common post-processing for dt_obj if it was successfully created
        if dt_obj:
            try:
                # If parsed datetime is naive, assume it's UTC.
                # If it has timezone info, convert it to UTC.
                if dt_obj.tzinfo is None or dt_obj.tzinfo.utcoffset(dt_obj) is None:
                    dt_obj = dt_obj.replace(tzinfo=timezone.utc)
                else:
                    dt_obj = dt_obj.astimezone(timezone.utc)
                return dt_obj.isoformat(timespec="milliseconds")
            except (
                Exception
            ) as e_post_process:  # Catch errors during timezone conversion or formatting
                self._logger.error(
                    f"Error post-processing datetime object from '{str(raw_timestamp)[:100]}': {e_post_process}"
                )
                return None

        # If dt_obj is still None here, it means none of the parsing paths succeeded.
        # (though most paths that fail should return None earlier)
        if (
            dt_obj is None
            and not isinstance(raw_timestamp, str)
            and not isinstance(raw_timestamp, (int, float))
        ):
            # This case should ideally be caught by the initial type check, but as a safeguard.
            self._logger.warning(
                f"Timestamp '{str(raw_timestamp)[:100]}' could not be converted to a datetime object."
            )

        return None  # Default return if all attempts fail or dt_obj remains None
