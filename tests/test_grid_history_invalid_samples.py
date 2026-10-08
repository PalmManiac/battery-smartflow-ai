from __future__ import annotations

import unittest

from custom_components.battery_smartflow_ai.grid_history import (
    GridHistory,
)


class GridHistoryInvalidSampleTests(unittest.TestCase):
    def test_invalid_reading_does_not_become_a_zero_watt_sample(self) -> None:
        history = GridHistory()
        first = history.update(grid_import_w=100.0, grid_export_w=0.0)

        gap = history.update(
            grid_import_w=0.0,
            grid_export_w=0.0,
            valid=False,
        )
        recovered = history.update(grid_import_w=120.0, grid_export_w=0.0)

        self.assertEqual(first.grid_now_w, 100.0)
        self.assertEqual(gap.grid_now_w, 100.0)
        self.assertEqual(gap.grid_avg_short_w, 100.0)
        self.assertEqual(gap.grid_delta_w, 0.0)
        self.assertEqual(recovered.grid_delta_w, 20.0)


if __name__ == "__main__":
    unittest.main()
