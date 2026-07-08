"""Tests for context-aware prompt suggestions (roadmap #25)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401  (stubs httpx/langchain etc.)

import superset_chat.app.server.suggestions as sugg


class _FakeClient:
    def __init__(self, data):
        self.data = data
        self.fetched = None

    def get(self, path):
        self.fetched = path
        return self.data


ORDERS = {'result': {
    'table_name': 'orders',
    'columns': [
        {'column_name': 'id', 'type': 'INTEGER'},
        {'column_name': 'created_at', 'type': 'TIMESTAMP',
         'description': 'Order time'},
        {'column_name': 'amount', 'type': 'NUMERIC'},
    ],
    'metrics': [{'metric_name': 'total_revenue', 'expression': 'SUM(amount)'}],
    'extra': ('{"ai_semantic_sidecar":{"friendly_name":"Orders",'
              '"primary_date_field":"created_at","synonyms":["sales"]}}'),
}}


class TestSuggestions(unittest.TestCase):
    def test_questions_grounded_in_real_columns_metrics(self):
        qs = sugg.suggest_questions(_FakeClient(ORDERS), 1)
        self.assertGreaterEqual(len(qs), 3)
        self.assertLessEqual(len(qs), 4)
        blob = ' '.join(qs).lower()
        self.assertIn('total_revenue', blob)
        self.assertIn('created_at', blob)
        self.assertIn('orders', blob)

    def test_no_airflow_references(self):
        qs = sugg.suggest_questions(_FakeClient(ORDERS), 1)
        blob = ' '.join(qs).lower()
        for bad in ('dag', 'airflow', 'sensor', 'workflow'):
            self.assertNotIn(bad, blob)

    def test_deterministic(self):
        a = sugg.suggest_questions(_FakeClient(ORDERS), 1)
        b = sugg.suggest_questions(_FakeClient(ORDERS), 1)
        self.assertEqual(a, b)

    def test_uses_sidecar_primary_date_and_synonym(self):
        qs = sugg.suggest_questions(_FakeClient(ORDERS), 1)
        blob = ' '.join(qs)
        # primary_date_field -> appears in a "over time by created_at" question
        self.assertTrue(any('created_at' in q and 'over time' in q for q in qs),
                        f'no date-trend question (got {qs})')
        # synonym 'sales' -> a trend question references it
        self.assertTrue(any('sales' in q for q in qs),
                        f'no synonym-grounded question (got {qs})')

    def test_no_metrics_still_suggests(self):
        ds = {'result': {'table_name': 'events',
                         'columns': [{'column_name': 'event_id', 'type': 'INTEGER'},
                                     {'column_name': 'ts', 'type': 'TIMESTAMP'}],
                         'metrics': [], 'extra': ''}}
        qs = sugg.suggest_questions(_FakeClient(ds), 2)
        self.assertGreaterEqual(len(qs), 1)
        self.assertTrue(any('events' in q for q in qs))

    def test_empty_dataset_fallback(self):
        ds = {'result': {'table_name': '', 'columns': [], 'metrics': [],
                         'extra': ''}}
        qs = sugg.suggest_questions(_FakeClient(ds), 3)
        self.assertEqual(len(qs), 1)
        self.assertIn('dataset 3', qs[0])

    def test_capped_at_max(self):
        qs = sugg.suggest_questions(_FakeClient(ORDERS), 1, max_questions=2)
        self.assertLessEqual(len(qs), 2)

    def test_single_fetch(self):
        c = _FakeClient(ORDERS)
        sugg.suggest_questions(c, 1)
        self.assertEqual(c.fetched, '/api/v1/dataset/1')


if __name__ == '__main__':
    unittest.main()