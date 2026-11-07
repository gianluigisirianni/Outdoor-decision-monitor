from __future__ import annotations

import unittest

from streamlit.testing.v1 import AppTest


class OutdoorDashboardTests(unittest.TestCase):
    def test_initial_render(self) -> None:
        at = AppTest.from_file("app.py", default_timeout=20).run()

        self.assertFalse(at.exception)
        self.assertEqual(at.title[0].value, "Outdoor decision monitor")
        self.assertEqual(len(at.metric), 7)
        self.assertEqual(at.metric[3].value, "100%")
        self.assertGreaterEqual(len(at.dataframe), 3)
        self.assertTrue(at.success)

    def test_location_filter(self) -> None:
        at = AppTest.from_file("app.py", default_timeout=20).run()
        at.multiselect(key="locations").set_value(["Andalo"]).run()

        self.assertFalse(at.exception)
        windows = at.dataframe[0].value
        self.assertFalse(windows.empty)
        self.assertEqual(set(windows["Località"]), {"Andalo"})
        self.assertEqual(at.metric[0].value, "1")

    def test_zero_rain_threshold(self) -> None:
        at = AppTest.from_file("app.py", default_timeout=20).run()
        at.slider(key="rain_threshold").set_value(0).run()

        self.assertFalse(at.exception)
        best_hours = at.dataframe[1].value
        self.assertFalse(best_hours.empty)
        self.assertTrue((best_hours["Pioggia (%)"] == 0).all())

    def test_empty_location_selection(self) -> None:
        at = AppTest.from_file("app.py", default_timeout=20).run()
        at.multiselect(key="locations").set_value([]).run()

        self.assertFalse(at.exception)
        self.assertTrue(at.warning)
        self.assertEqual(
            at.warning[0].value,
            "Nessun dato disponibile con i filtri selezionati.",
        )


if __name__ == "__main__":
    unittest.main()
