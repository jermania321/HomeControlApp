import unittest

from homecontrol.priority_classifier import priority_color, priority_rank


class PriorityColorTests(unittest.TestCase):
    def test_priority_mapping_is_stable_and_case_insensitive(self):
        self.assertEqual(priority_color("HIGH"), "#a61b1b")
        self.assertEqual(priority_color("medium"), "#8a6500")
        self.assertEqual(priority_color("LOW"), "#247a3b")
        self.assertEqual(priority_color("unknown"), "#404040")

    def test_priority_order_is_high_medium_low_and_stable(self):
        priorities = ["LOW", "HIGH", "MEDIUM", "HIGH", "LOW"]
        ordered = sorted(enumerate(priorities), key=lambda item: priority_rank(item[1]))
        self.assertEqual([priority for _, priority in ordered],
                         ["HIGH", "HIGH", "MEDIUM", "LOW", "LOW"])
        self.assertEqual([index for index, priority in ordered if priority == "HIGH"], [1, 3])


if __name__ == "__main__":
    unittest.main()
