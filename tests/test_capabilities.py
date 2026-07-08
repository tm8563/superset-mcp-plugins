"""Tests for zero-setup capability disclosure (roadmap #24)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401  (stubs langchain.tools etc.)

import superset_chat.app.server.capabilities as caps


class TestCapabilities(unittest.TestCase):
    EXPECTED_TITLES = [
        'Browse Superset',
        'Ask questions in plain English (NLQ → SQL)',
        'Embed dashboards & mint guest tokens',
        'Alerts & scheduled reports',
        'Governance & audit',
        'Anomaly detection & forecasting',
        'PDF / screenshot export',
    ]

    def test_get_capabilities_shape_and_titles(self):
        c = caps.get_capabilities()
        self.assertEqual([cap['title'] for cap in c], self.EXPECTED_TITLES)
        for cap in c:
            self.assertIn('blurb', cap)
            self.assertIn('examples', cap)
            self.assertGreaterEqual(len(cap['examples']), 1)

    def test_no_airflow_references(self):
        """The disclosure must be Superset-relevant, not stale Airflow DAG copy."""
        blob = json.dumps(caps.get_capabilities()).lower()
        self.assertNotIn('dag', blob)
        self.assertNotIn('airflow', blob)
        self.assertNotIn('sensor', blob)

    def test_nlq_capability_advertises_no_setup(self):
        nlq = [c for c in caps.get_capabilities()
               if 'NLQ' in c['title']][0]
        self.assertIn('No topic/synonym setup needed', nlq['blurb'])

    def test_capabilities_track_tool_surface(self):
        """If a tool group is empty, its capability is not advertised."""
        original = caps.EmbeddingTools
        caps.EmbeddingTools = []
        try:
            titles = [c['title'] for c in caps.get_capabilities()]
            self.assertNotIn('Embed dashboards & mint guest tokens', titles)
            self.assertEqual(len(titles), len(self.EXPECTED_TITLES) - 1)
        finally:
            caps.EmbeddingTools = original

    def test_browse_always_present(self):
        """The MCP Superset browse capability is always advertised."""
        titles = [c['title'] for c in caps.get_capabilities()]
        self.assertIn('Browse Superset', titles)

    def test_get_capabilities_json_valid(self):
        data = json.loads(caps.get_capabilities_json())
        self.assertIsInstance(data, list)
        self.assertEqual(data[0]['title'], 'Browse Superset')


if __name__ == '__main__':
    unittest.main()