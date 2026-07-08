"""Minimal-friction onboarding smoke test (roadmap #28).

Demonstrates that a fresh user can go from opening the assistant to a grounded
answer with ZERO prior configuration beyond the #13 auto-populated sidecar —
no separate "topic" or "dataset training" step. Exercises the real components:
#24 capability disclosure (no setup), #25 dataset-grounded suggestions (auto
sidecar), #12 NLQ grounded in the auto-derived semantic context. The LLM is
stubbed (no real model in CI), but the *grounding* is real and uncurated.
"""
import asyncio
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401  (stubs langchain/httpx/pydantic etc.)

from superset_chat.app.server import capabilities, suggestions
from superset_chat.app.server import semantic_layer as sl

# A dataset whose #13 sidecar is AUTO-POPULATED (no manual curation).
ORDERS = {'result': {
    'table_name': 'orders',
    'columns': [
        {'column_name': 'id', 'type': 'INTEGER'},
        {'column_name': 'created_at', 'type': 'TIMESTAMP'},
        {'column_name': 'amount', 'type': 'NUMERIC'},
    ],
    'metrics': [{'metric_name': 'total_revenue', 'expression': 'SUM(amount)'}],
    'extra': ('{"ai_semantic_sidecar":{"friendly_name":"Orders",'
              '"primary_date_field":"created_at","synonyms":["sales"]}}'),
}}


class _FakeClient:
    def __init__(self, data):
        self.data = data
        self.fetched = None

    def get(self, path):
        self.fetched = path
        return self.data


class _FakeStructured:
    def __init__(self, captured, rv):
        self.captured = captured
        self.rv = rv

    async def ainvoke(self, prompt):
        self.captured.append(prompt)
        return self.rv


class _FakeChatModel:
    captured = []

    def with_structured_output(self, cls):
        return _FakeStructured(
            _FakeChatModel.captured,
            sl.SQLResult(sql='SELECT SUM(amount) FROM orders',
                         explanation='total revenue'))


class TestOnboardingSmoke(unittest.TestCase):
    def setUp(self):
        self._cm = sl.ChatModel
        sl.ChatModel = _FakeChatModel
        _FakeChatModel.captured = []

    def tearDown(self):
        sl.ChatModel = self._cm

    def test_zero_setup_disclosure_no_training_required(self):
        """#24: capabilities are shown with no setup; no training/curation step
        is required or mentioned."""
        caps = capabilities.get_capabilities()
        self.assertTrue(any('NLQ' in c['title'] for c in caps))
        blob = json.dumps(caps).lower()
        for bad in ('training step', 'curation step', 'topic setup', 'airflow', 'dag'):
            self.assertNotIn(bad, blob)
        nlq = [c for c in caps if 'NLQ' in c['title']][0]
        self.assertIn('No topic/synonym setup needed', nlq['blurb'])

    def test_suggestions_grounded_in_auto_sidecar(self):
        """#25: suggestions come from the auto-populated sidecar, not a
        training step, and reference the dataset's real columns/metrics."""
        qs = suggestions.suggest_questions(_FakeClient(ORDERS), 1)
        self.assertGreaterEqual(len(qs), 3)
        blob = ' '.join(qs).lower()
        self.assertIn('total_revenue', blob)
        self.assertIn('orders', blob)
        for bad in ('dag', 'airflow', 'training', 'curation', 'topic setup'):
            self.assertNotIn(bad, blob)

    def test_nlq_answer_grounded_without_curation(self):
        """#12: asking a question yields a grounded answer using the
        auto-derived context — no manual curation."""
        result = asyncio.run(
            sl.nl_to_sql('What was total revenue?', 1, client=_FakeClient(ORDERS)))
        self.assertEqual(result.sql, 'SELECT SUM(amount) FROM orders')
        prompt = _FakeChatModel.captured[0]
        self.assertIn('total_revenue', prompt)   # real metric
        self.assertIn('Orders', prompt)           # sidecar friendly name
        self.assertIn('created_at', prompt)       # real column
        self.assertNotIn('training', prompt.lower())
        self.assertNotIn('curat', prompt.lower())

    def test_end_to_end_no_curation_step(self):
        """Full path: capabilities -> pick dataset -> grounded suggestions ->
        grounded answer, with no training/curation step anywhere."""
        caps = capabilities.get_capabilities()
        client = _FakeClient(ORDERS)
        qs = suggestions.suggest_questions(client, 1)
        result = asyncio.run(sl.nl_to_sql(qs[0], 1, client=client))
        self.assertTrue(result.sql)
        whole = (json.dumps(caps) + ' '.join(qs)
                 + (_FakeChatModel.captured[0] if _FakeChatModel.captured else ''))
        self.assertNotIn('training', whole.lower())
        self.assertNotIn('curat', whole.lower())


if __name__ == '__main__':
    unittest.main()