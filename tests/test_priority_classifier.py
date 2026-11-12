import unittest

from homecontrol.priority_classifier import classify_priority


class ClassifyPriorityTests(unittest.TestCase):
    def test_high_keywords_are_case_insensitive(self):
        self.assertEqual(classify_priority("URGENT: review"), "HIGH")
        self.assertEqual(classify_priority("Please do this ASAP"), "HIGH")

    def test_medium_keywords_are_case_insensitive(self):
        self.assertEqual(classify_priority("Team MEETING"), "MEDIUM")
        self.assertEqual(classify_priority("Reminder: call"), "MEDIUM")

    def test_high_takes_precedence_over_medium(self):
        self.assertEqual(classify_priority("Urgent meeting"), "HIGH")
        self.assertEqual(classify_priority("Meeting is urgent"), "HIGH")

    def test_no_priority_keyword_is_low(self):
        self.assertEqual(classify_priority("Weekly update"), "LOW")

    def test_empty_or_missing_subject_is_low(self):
        self.assertEqual(classify_priority(""), "LOW")
        self.assertEqual(classify_priority(" \t\n "), "LOW")
        self.assertEqual(classify_priority(None), "LOW")


if __name__ == "__main__":
    unittest.main()
