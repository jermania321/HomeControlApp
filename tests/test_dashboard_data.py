import unittest
from zoneinfo import ZoneInfoNotFoundError
from datetime import datetime, timezone
from homecontrol.dashboard_data import (CoalescingWorkQueue, local_time,
                                        parse_frankfurter, validate_cached_rates)
from homecontrol import load_settings


class DashboardDataTests(unittest.TestCase):
    def test_parse_single_usd_base_response(self):
        rates, date = parse_frankfurter({"date": "2026-11-10", "rates": {"INR": 88, "JPY": 150}})
        self.assertEqual(date, "2026-11-10")
        self.assertEqual(rates["INR_per_JPY"], 88 / 150)

    def test_fx_rates_must_be_finite_and_positive(self):
        for value in (0, -1, float("inf"), float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_frankfurter({"date": "2026-11-10", "rates": {"INR": value, "JPY": 150}})

    def test_invalid_cached_rates_are_unavailable(self):
        self.assertIsNone(validate_cached_rates(None))
        self.assertIsNone(validate_cached_rates({"INR": "nan", "JPY": 150, "INR_per_JPY": 0.5}))
        self.assertEqual(validate_cached_rates({"INR": 88, "JPY": 150, "INR_per_JPY": 88 / 150})["INR"], 88)

    def test_cached_cross_rate_must_match_base_rates(self):
        self.assertIsNone(validate_cached_rates({"INR": 88, "JPY": 150, "INR_per_JPY": 0.9}))

    def test_work_queue_coalesces_categories_and_preserves_order(self):
        queue = CoalescingWorkQueue()
        first, duplicate, other = object(), object(), object()
        self.assertTrue(queue.enqueue("poll", first, None))
        self.assertFalse(queue.enqueue("poll", duplicate, None))
        self.assertTrue(queue.enqueue("fx", other, None))
        self.assertEqual(queue.pop(), ("poll", first, None))
        self.assertEqual(queue.pop(), ("fx", other, None))
        self.assertFalse(queue)

    def test_timezone_conversion(self):
        now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
        try:
            result = local_time("Asia/Kolkata", now)
        except ZoneInfoNotFoundError:
            self.skipTest("Install tzdata from requirements.txt")
        self.assertEqual(result, "05:30 PM")

    def test_default_poll_interval(self):
        settings = load_settings()
        self.assertGreaterEqual(settings["poll_interval_minutes"], 1)
        self.assertLessEqual(settings["poll_interval_minutes"], 1440)


if __name__ == "__main__":
    unittest.main()
