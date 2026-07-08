"""Tests for Langfuse observability wiring (roadmap #21).

The Langfuse callback is attached to the agent run config in
``get_user_chat_config`` and is provider-agnostic, so it covers every LLM
backend including Ollama (and the Ollama cloud->local fallback, whose LLM
call is traced via the propagated run_manager). These tests verify the wiring
and the missing-key guard without requiring langfuse to be installed.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401  (stubs heavy deps; keeps test discovery consistent)

import superset_chat.app.server.llm as llm


class _StubHandler:
    """Records the kwargs passed to the Langfuse CallbackHandler."""
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        _StubHandler.instances.append(self)


class TestLangfuse(unittest.TestCase):
    def setUp(self):
        self._avail = llm.LANGFUSE_AVAILABLE
        self._cb = llm.CallbackHandler
        _StubHandler.instances.clear()
        for k in ('LANGFUSE_HOST', 'LANGFUSE_PUBLIC_KEY', 'LANGFUSE_SECRET_KEY',
                  'LLM_MODEL_ID'):
            os.environ.pop(k, None)

    def tearDown(self):
        llm.LANGFUSE_AVAILABLE = self._avail
        llm.CallbackHandler = self._cb
        for k in ('LANGFUSE_HOST', 'LANGFUSE_PUBLIC_KEY', 'LANGFUSE_SECRET_KEY',
                  'LLM_MODEL_ID'):
            os.environ.pop(k, None)

    def _enable(self):
        llm.LANGFUSE_AVAILABLE = True
        llm.CallbackHandler = _StubHandler

    def test_callback_attached_for_ollama_run(self):
        """The Ollama path gets the Langfuse callback (provider-agnostic)."""
        self._enable()
        os.environ['LLM_MODEL_ID'] = 'ollama:llama3.1'
        os.environ['LANGFUSE_HOST'] = 'https://lf.cloud'
        os.environ['LANGFUSE_PUBLIC_KEY'] = 'pk-lf'
        os.environ['LANGFUSE_SECRET_KEY'] = 'sk-lf'
        cfg = llm.get_user_chat_config('s1', 'alice')
        self.assertIn('callbacks', cfg)
        self.assertEqual(len(cfg['callbacks']), 1)
        h = _StubHandler.instances[-1]
        self.assertEqual(h.kwargs['user_id'], 'alice')
        self.assertEqual(h.kwargs['session_id'], 's1')
        self.assertEqual(h.kwargs['public_key'], 'pk-lf')
        self.assertEqual(h.kwargs['secret_key'], 'sk-lf')
        self.assertEqual(h.kwargs['host'], 'https://lf.cloud')
        # thread_id still namespaced by username (not regressed by #21).
        self.assertEqual(cfg['configurable']['thread_id'], 'alice:s1')

    def test_partial_config_no_callback(self):
        """LANGFUSE_HOST set but keys missing -> no callback (graceful)."""
        self._enable()
        os.environ['LANGFUSE_HOST'] = 'https://lf.cloud'
        cfg = llm.get_user_chat_config('s1', 'alice')
        self.assertNotIn('callbacks', cfg)
        self.assertEqual(_StubHandler.instances, [])

    def test_no_host_no_callback(self):
        self._enable()
        cfg = llm.get_user_chat_config('s1', 'alice')
        self.assertNotIn('callbacks', cfg)
        self.assertEqual(_StubHandler.instances, [])

    def test_not_available_no_callback(self):
        """langfuse not installed -> no callback even if env is set."""
        llm.LANGFUSE_AVAILABLE = False
        os.environ['LANGFUSE_HOST'] = 'https://lf.cloud'
        os.environ['LANGFUSE_PUBLIC_KEY'] = 'pk'
        os.environ['LANGFUSE_SECRET_KEY'] = 'sk'
        cfg = llm.get_user_chat_config('s1', 'alice')
        self.assertNotIn('callbacks', cfg)

    def test_anonymous_user_uses_session_id(self):
        self._enable()
        os.environ['LANGFUSE_HOST'] = 'https://lf.cloud'
        os.environ['LANGFUSE_PUBLIC_KEY'] = 'pk'
        os.environ['LANGFUSE_SECRET_KEY'] = 'sk'
        cfg = llm.get_user_chat_config('s1', None)
        h = _StubHandler.instances[-1]
        self.assertEqual(h.kwargs['user_id'], 's1')


if __name__ == '__main__':
    unittest.main()