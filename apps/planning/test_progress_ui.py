"""Manual completion percentages must not declare unfinished work complete."""

from django.test import SimpleTestCase

from .progress_ui import completion_percentage


class CompletionPercentageTests(SimpleTestCase):
    def test_empty_equal_weight_and_near_complete_percentages(self):
        for completed, total, expected in (
            (0, 0, 0), (0, 11, 0), (1, 11, 9), (3, 11, 27),
            (1, 3, 33), (2, 3, 66), (499, 500, 99), (500, 500, 100),
        ):
            with self.subTest(completed=completed, total=total):
                self.assertEqual(completion_percentage(completed, total), expected)
