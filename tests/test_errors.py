"""Tests for plain-language error recovery (roadmap #26)."""
import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401  (stubs flask/langchain/httpx etc.)

from superset_chat.app.server.errors import classify_error, error_event


class _FakeResp:
    def __init__(self, status):
        self.status_code = status


class _Exc(Exception):
    def __init__(self, msg, status=None):
        super().__init__(msg)
        if status is not None:
            self.response = _FakeResp(status)


class TestClassifyError(unittest.TestCase):
    def test_llm_unreachable_connection(self):
        r = classify_error(ConnectionError('Connection refused'))
        self.assertEqual(r['category'], 'llm_unreachable')
        self.assertIn('message', r)
        self.assertIn('next_step', r)

    def test_llm_unreachable_timeout(self):
        r = classify_error(Exception('connection timeout'))
        self.assertEqual(r['category'], 'llm_unreachable')

    def test_auth_failure_403(self):
        r = classify_error(_Exc('Forbidden', status=403))
        self.assertEqual(r['category'], 'auth_failure')

    def test_auth_failure_unauthorized_text(self):
        r = classify_error(Exception('Unauthorized access'))
        self.assertEqual(r['category'], 'auth_failure')

    def test_superset_rest_4xx(self):
        r = classify_error(_Exc('Not found', status=404))
        self.assertEqual(r['category'], 'superset_rest_error')

    def test_superset_rest_5xx(self):
        r = classify_error(_Exc('boom', status=500))
        self.assertEqual(r['category'], 'superset_rest_error')

    def test_sql_failure(self):
        r = classify_error(Exception('syntax error near SELECT'))
        self.assertEqual(r['category'], 'sql_failure')

    def test_mcp_tool_error(self):
        r = classify_error(Exception('MCP tool returned an error'))
        self.assertEqual(r['category'], 'mcp_tool_error')

    def test_unknown(self):
        r = classify_error(Exception('something totally weird'))
        self.assertEqual(r['category'], 'unknown')

    def test_error_event_shape(self):
        ev = error_event(Exception('timeout'))
        self.assertEqual(ev['type'], 'error')
        for k in ('category', 'message', 'next_step'):
            self.assertIn(k, ev)

    def test_user_message_has_no_stack_trace(self):
        r = classify_error(
            Exception('Traceback (most recent call last): File "/x/y.py", line 5'))
        self.assertNotIn('Traceback', r['message'])
        self.assertNotIn('File "/', r['message'])

    def test_all_categories_have_message_and_next_step(self):
        from superset_chat.app.server.errors import _CATEGORIES
        for cat, (msg, ns) in _CATEGORIES.items():
            self.assertTrue(msg)
            self.assertTrue(ns)


class TestResponseStreamError(unittest.TestCase):
    def test_get_response_stream_yields_categorized_error(self):
        import superset_chat.ai_superset_assistant as view
        original = view.get_stream_agent_responce

        async def _raising(**kwargs):
            raise ConnectionError('Connection refused')

        view.get_stream_agent_responce = _raising
        try:
            agent = view.AIAssistantAgent()
            async def collect():
                out = []
                async for ev in agent.get_response_stream('hi', None, 'alice'):
                    out.append(ev)
                return out
            evs = asyncio.run(collect())
            self.assertEqual(len(evs), 1)
            self.assertEqual(evs[0]['type'], 'error')
            self.assertEqual(evs[0]['category'], 'llm_unreachable')
            self.assertIn('next_step', evs[0])
        finally:
            view.get_stream_agent_responce = original


if __name__ == '__main__':
    unittest.main()