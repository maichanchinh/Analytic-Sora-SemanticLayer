import json
import logging
import os
import unittest
from unittest.mock import patch

from sora_semantic.logging_config import JsonFormatter, MinimumLevelFilter


class JsonFormatterTests(unittest.TestCase):
    def test_formats_operational_fields_and_request_id(self):
        record = logging.LogRecord(
            name="sora_semantic.api",
            level=logging.INFO,
            pathname=__file__,
            lineno=12,
            msg="Silver query completed: request_id=%s outcome=%s",
            args=("req-123", "success"),
            exc_info=None,
        )

        with patch.dict(os.environ, {"SERVICE_NAME": "api"}):
            event = json.loads(JsonFormatter().format(record))

        self.assertEqual(event["level"], "INFO")
        self.assertEqual(event["service"], "api")
        self.assertEqual(event["logger"], "sora_semantic.api")
        self.assertEqual(event["request_id"], "req-123")
        self.assertEqual(
            event["message"],
            "Silver query completed: request_id=req-123 outcome=success",
        )
        self.assertTrue(event["timestamp"].endswith("Z"))

    def test_minimum_level_uses_environment(self):
        debug_record = logging.LogRecord(
            "test", logging.DEBUG, __file__, 1, "debug", (), None
        )
        info_record = logging.LogRecord(
            "test", logging.INFO, __file__, 1, "info", (), None
        )

        with patch.dict(os.environ, {"LOG_LEVEL": "INFO"}):
            log_filter = MinimumLevelFilter()
            self.assertFalse(log_filter.filter(debug_record))
            self.assertTrue(log_filter.filter(info_record))


if __name__ == "__main__":
    unittest.main()
