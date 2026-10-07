import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from server.time_context import local_time_context, machine_timezone, validate_timezone


class TimeContextTests(unittest.TestCase):
    def test_client_timezone_determines_date_and_offset(self):
        instant = datetime(2026, 10, 7, 1, 30, tzinfo=timezone.utc)
        result = local_time_context("America/New_York", instant)
        self.assertEqual("2026-10-06", result["current_date"])
        self.assertEqual("2026-10-06T21:30:00-04:00", result["current_time"])
        self.assertEqual("-04:00", result["utc_offset"])

    def test_dst_is_calculated_for_the_instant_not_a_fixed_offset(self):
        before = local_time_context("America/New_York", datetime(2026, 3, 8, 6, 59, tzinfo=timezone.utc))
        after = local_time_context("America/New_York", datetime(2026, 3, 8, 7, 1, tzinfo=timezone.utc))
        self.assertEqual("-05:00", before["utc_offset"])
        self.assertEqual("-04:00", after["utc_offset"])
        self.assertIn("03:01:00", after["current_time"])

    def test_invalid_zones_cannot_be_paths_or_shell_content(self):
        for value in (None, "", "/etc/passwd", "../UTC", "America/New_York\nUTC", "Not/A_Zone", 5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_timezone(value)
        self.assertEqual("UTC", validate_timezone(" UTC "))

    def test_fallback_uses_machine_zone_only_before_client_sync(self):
        with patch.dict("os.environ", {"TZ": "Asia/Kolkata"}):
            self.assertEqual("Asia/Kolkata", machine_timezone())
            self.assertEqual("+05:30", local_time_context(None, 0)["utc_offset"])
            self.assertEqual("+00:00", local_time_context("UTC", 0)["utc_offset"])
