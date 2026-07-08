"""Tests for Ollama cloud->local automatic fallback (roadmap #20).

The fallback wraps _invoke/_ainvoke/_stream/_astream: on a connection-level
error against the primary OLLAMA_BASE_URL, it retries once against
OLLAMA_FALLBACK_BASE_URL. Mid-stream drops (after chunks were already
produced) must NOT fall back (would garble output) — they re-raise.
"""
import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401

import superset_chat.app.models.inference.ollama_model as om

PRIMARY = 'http://primary:11434'
FALLBACK = 'http://fallback:11434'


def _chatbase():
    return sys.modules['stubs']._ChatBase


def _connect_error():
    return sys.modules['stubs']._ConnectError


class TestOllamaFallback(unittest.TestCase):
    def setUp(self):
        os.environ['LLM_MODEL_ID'] = 'ollama:llama3.1'
        os.environ['OLLAMA_BASE_URL'] = PRIMARY
        os.environ['OLLAMA_FALLBACK_BASE_URL'] = FALLBACK
        for k in ('OLLAMA_API_KEY', 'OLLAMA_MODEL'):
            os.environ.pop(k, None)
        _chatbase()._fail_urls = {PRIMARY}
        _chatbase()._mid_fail_url = None

    def tearDown(self):
        _chatbase()._fail_urls = set()
        _chatbase()._mid_fail_url = None

    def _new(self):
        return om.ChatOllama()

    def test_invoke_falls_back(self):
        self.assertEqual(self._new()._invoke('m'), f'OK:{FALLBACK}')

    def test_ainvoke_falls_back(self):
        self.assertEqual(asyncio.run(self._new()._ainvoke('m')), f'OK:{FALLBACK}')

    def test_stream_falls_back(self):
        self.assertEqual(list(self._new()._stream('m')), ['c1', 'c2'])

    def test_astream_falls_back(self):
        async def go():
            return [c async for c in self._new()._astream('m')]
        self.assertEqual(asyncio.run(go()), ['c1', 'c2'])

    def test_primary_ok_no_fallback(self):
        _chatbase()._fail_urls = set()
        self.assertEqual(self._new()._invoke('m'), f'OK:{PRIMARY}')

    def test_no_fallback_url_reraises(self):
        os.environ.pop('OLLAMA_FALLBACK_BASE_URL', None)
        with self.assertRaises(_connect_error()):
            self._new()._invoke('m')

    def test_midstream_drop_does_not_fall_back(self):
        _chatbase()._mid_fail_url = PRIMARY
        gen = self._new()._stream('m')
        self.assertEqual(next(gen), 'c1')
        with self.assertRaises(_connect_error()):
            next(gen)

    def test_urls_recorded(self):
        w = self._new()
        self.assertEqual(w._primary_url, PRIMARY)
        self.assertEqual(w._fallback_url, FALLBACK)


if __name__ == '__main__':
    unittest.main()