"""Tests for the ML anomaly-detection + forecasting tools (roadmap #22)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401  (stubs langchain.tools etc.)

import superset_chat.app.server.ml_analytics as ml


class TestMLAnalytics(unittest.TestCase):
    SERIES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 50]  # 50 is the outlier

    def test_zscore_flags_only_outlier(self):
        r = ml.detect_anomalies(self.SERIES, method='zscore', threshold=2.0)
        self.assertEqual(r['count'], 11)
        self.assertEqual(len(r['anomalies']), 1)
        self.assertEqual(r['anomalies'][0]['index'], 10)
        self.assertAlmostEqual(r['anomalies'][0]['value'], 50.0)
        self.assertAlmostEqual(r['stats']['mean'], 105 / 11)

    def test_iqr_flags_outlier(self):
        r = ml.detect_anomalies(self.SERIES, method='iqr', threshold=1.5)
        self.assertTrue(any(a['index'] == 10 for a in r['anomalies']))

    def test_flat_series_no_anomalies(self):
        r = ml.detect_anomalies([5, 5, 5, 5, 5], method='zscore', threshold=3.0)
        self.assertEqual(r['anomalies'], [])

    def test_single_point_no_crash(self):
        r = ml.detect_anomalies([42], method='zscore')
        self.assertEqual(r['anomalies'], [])
        self.assertEqual(r['count'], 1)

    def test_non_numeric_skipped(self):
        r = ml.detect_anomalies([1, 2, 'x', 3, None, 4], method='zscore',
                                threshold=3.0)
        self.assertEqual(r['count'], 4)

    def test_linear_forecast(self):
        r = ml.forecast_series([1, 2, 3, 4, 5], horizon=3, method='linear')
        self.assertEqual(len(r['forecast']), 3)
        self.assertAlmostEqual(r['slope'], 1.0)
        self.assertAlmostEqual(r['intercept'], 1.0)
        self.assertAlmostEqual(r['forecast'][0], 6.0)
        self.assertAlmostEqual(r['forecast'][2], 8.0)

    def test_moving_average_forecast(self):
        r = ml.forecast_series([1, 2, 3, 4, 5], horizon=3,
                               method='moving_average')
        self.assertEqual(r['forecast'], [3.0, 3.0, 3.0])
        self.assertEqual(r['window'], 5)

    def test_forecast_empty_series(self):
        r = ml.forecast_series([], horizon=5, method='linear')
        self.assertEqual(r['forecast'], [])

    def test_anomaly_narrative(self):
        nr = ml.anomaly_narrative(
            ml.detect_anomalies(self.SERIES, method='zscore', threshold=2.0))
        self.assertIn('1 anomaly', nr)
        self.assertIn('#10', nr)
        nr2 = ml.anomaly_narrative(
            ml.detect_anomalies([1, 2, 3, 4, 5], method='zscore',
                                threshold=3.0))
        self.assertIn('No anomalies', nr2)

    def test_detect_anomalies_tool(self):
        tool = [t for t in ml.MLTools if t.name == 'DetectAnomalies'][0]
        out = json.loads(tool.func(json.dumps(self.SERIES), 'zscore', 2.0))
        self.assertEqual(out['anomalies'][0]['index'], 10)

    def test_forecast_series_tool(self):
        tool = [t for t in ml.MLTools if t.name == 'ForecastSeries'][0]
        out = json.loads(tool.func(json.dumps([1, 2, 3, 4, 5]), 3, 'linear'))
        self.assertEqual(out['forecast'], [6.0, 7.0, 8.0])

    def test_ml_tools_present(self):
        names = [t.name for t in ml.MLTools]
        self.assertIn('DetectAnomalies', names)
        self.assertIn('ForecastSeries', names)


if __name__ == '__main__':
    unittest.main()