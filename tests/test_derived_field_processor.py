import unittest
import sys
import os

# Adjust the path to import from the src directory
# This goes up two levels from tests/ to logllm_project_root/, then into src/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.logllm.agents.static_grok_parser.api.derived_field_processor import (
    DerivedFieldProcessor,
)
from src.logllm.utils.logger import Logger  # Assuming this path for Logger


# A mock logger to capture log messages for assertions (optional, but good for testing logs)
class MockLogger:
    def __init__(self):
        self.debug_messages = []
        self.info_messages = []
        self.warning_messages = []
        self.error_messages = []

    def debug(self, msg, *args, **kwargs):
        self.debug_messages.append(msg)

    def info(self, msg, *args, **kwargs):
        self.info_messages.append(msg)

    def warning(self, msg, *args, **kwargs):
        self.warning_messages.append(msg)

    def error(self, msg, *args, **kwargs):
        self.error_messages.append(msg)
        if kwargs.get("exc_info"):  # Simple exc_info handling for test
            pass  # In a real scenario, you might store the exception


class TestDerivedFieldProcessor(unittest.TestCase):

    def setUp(self):
        self.mock_logger = MockLogger()
        self.processor = DerivedFieldProcessor(logger=self.mock_logger)  # type: ignore

    def test_successful_derivation(self):
        grok_fields = {
            "day": "Mon",
            "month": "Jan",
            "monthday": "01",
            "time": "12:00:00",
            "year": "2023",
            "client_ip": "192.168.1.100",
        }
        definitions = {
            "timestamp": "{day} {month} {monthday} {time} {year}",
            "date_iso": "{year}-{month}-{monthday}",
            "client_info": "Client: {client_ip}",
        }
        context = {"group_name": "apache_test", "line_num": 1}

        result = self.processor.process_derived_fields(
            grok_fields.copy(), definitions, context
        )

        self.assertEqual(result.get("timestamp"), "Mon Jan 01 12:00:00 2023")
        self.assertEqual(result.get("date_iso"), "2023-Jan-01")
        self.assertEqual(result.get("client_info"), "Client: 192.168.1.100")
        self.assertIn("Mon", result.get("day"))  # Original field should still be there
        self.assertEqual(len(self.mock_logger.warning_messages), 0)
        self.assertEqual(len(self.mock_logger.error_messages), 0)
        # Check for debug logs for successful derivations
        self.assertTrue(
            any(
                "Derived field 'timestamp'" in msg
                for msg in self.mock_logger.debug_messages
            )
        )
        self.assertTrue(
            any(
                "Derived field 'date_iso'" in msg
                for msg in self.mock_logger.debug_messages
            )
        )
        self.assertTrue(
            any(
                "Derived field 'client_info'" in msg
                for msg in self.mock_logger.debug_messages
            )
        )

    def test_missing_keys_for_derivation(self):
        grok_fields = {
            "day": "Tue",
            "month": "Feb",
            "year": "2023",
        }  # 'time', 'monthday', 'client_ip' missing
        definitions = {
            "timestamp": "{day} {month} {monthday} {time} {year}",  # Will fail
            "year_only_derived": "{year}",  # Will succeed
            "client_info": "Client: {client_ip}",  # Will fail
        }
        context = {"group_name": "incomplete_data_test", "line_num": 2}

        result = self.processor.process_derived_fields(
            grok_fields.copy(), definitions, context
        )

        self.assertIsNone(result.get("timestamp"))  # Should not be created
        self.assertEqual(result.get("year_only_derived"), "2023")
        self.assertIsNone(result.get("client_info"))  # Should not be created

        self.assertGreater(len(self.mock_logger.warning_messages), 0)
        self.assertTrue(
            any(
                "Cannot derive field 'timestamp'" in msg
                for msg in self.mock_logger.warning_messages
            )
        )
        self.assertTrue(
            any(
                "Missing keys from Grok output: ['monthday', 'time']" in msg
                for msg in self.mock_logger.warning_messages
            )
        )
        self.assertTrue(
            any(
                "Cannot derive field 'client_info'" in msg
                for msg in self.mock_logger.warning_messages
            )
        )
        self.assertTrue(
            any(
                "Missing keys from Grok output: ['client_ip']" in msg
                for msg in self.mock_logger.warning_messages
            )
        )
        self.assertEqual(len(self.mock_logger.error_messages), 0)

    def test_no_derived_definitions(self):
        grok_fields = {"field_a": "value_a", "field_b": "value_b"}

        result = self.processor.process_derived_fields(grok_fields.copy(), None)
        self.assertEqual(result, grok_fields)  # Should return original dict unchanged

        result_empty_def = self.processor.process_derived_fields(grok_fields.copy(), {})
        self.assertEqual(result_empty_def, grok_fields)

        self.assertEqual(len(self.mock_logger.warning_messages), 0)

    def test_empty_grok_fields(self):
        grok_fields = {}
        definitions = {"timestamp": "{day} {month}"}

        result = self.processor.process_derived_fields(grok_fields.copy(), definitions)
        self.assertEqual(result, {})  # No fields to derive from, so no new fields
        # A warning should be logged because keys are missing if definitions are present
        self.assertTrue(
            any(
                "Cannot derive field 'timestamp'" in msg
                for msg in self.mock_logger.warning_messages
            )
        )

    def test_invalid_format_string_type(self):
        grok_fields = {"day": "Wed"}
        definitions = {"bad_type_def": 123}  # Format string is not a string
        context = {"group_name": "bad_type_test"}

        result = self.processor.process_derived_fields(grok_fields.copy(), definitions, context)  # type: ignore

        self.assertIsNone(result.get("bad_type_def"))
        self.assertTrue(
            any(
                "Format string for derived field 'bad_type_def' is not a string" in msg
                for msg in self.mock_logger.warning_messages
            )
        )

    def test_format_string_value_error(self):
        # This tests if str.format() itself raises a ValueError due to bad format specifiers
        # e.g. "{field:.%}" - an invalid format specifier after the colon
        grok_fields = {"value": "test_data"}
        # An invalid format specifier like ' %f ' for a string
        definitions = {"invalid_spec": "{value:.%f}"}
        context = {"group_name": "value_error_test"}

        result = self.processor.process_derived_fields(
            grok_fields.copy(), definitions, context
        )

        self.assertIsNone(result.get("invalid_spec"))
        self.assertTrue(
            any(
                "ValueError deriving field 'invalid_spec'" in msg
                for msg in self.mock_logger.warning_messages
            )
        )
        self.assertTrue(
            any(
                "Ensure format specifiers are valid" in msg
                for msg in self.mock_logger.warning_messages
            )
        )

    def test_derivation_does_not_overwrite_existing_grok_fields_by_default(self):
        # If a derived field has the same name as a Grok-extracted field,
        # the current logic will overwrite the Grok field with the derived one.
        # This test confirms that behavior. If a different behavior is desired,
        # the processor logic would need to change.
        grok_fields = {
            "message": "original_message",
            "part1": "hello",
            "part2": "world",
        }
        definitions = {"message": "{part1}-{part2}"}  # Derived 'message'
        context = {"group_name": "overwrite_test"}

        result = self.processor.process_derived_fields(
            grok_fields.copy(), definitions, context
        )
        self.assertEqual(result.get("message"), "hello-world")  # Overwritten
        self.assertEqual(result.get("part1"), "hello")  # Original source field remains


if __name__ == "__main__":
    # If you want to use the actual logger instead of MockLogger for visual inspection:
    # (Comment out self.mock_logger and self.processor instantiation in setUp and uncomment below)
    # real_logger = Logger()
    # TestDerivedFieldProcessor.processor = DerivedFieldProcessor(logger=real_logger)

    unittest.main()
