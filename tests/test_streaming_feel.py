"""Tests for response streaming feel (roadmap #29): an early 'thinking'
indicator is emitted before the first token/tool-start, so the UI never feels
frozen during a slow answer."""
import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401  (stubs flask/langchain etc.)

import superset_chat.ai_superset_assistant as view


class TestStreamingFeel(unittest.TestCase):
    def test_thinking_emitted_before_first_chunk(self):
        original = view.get_stream_agent_responce

        async def _fake(**kwargs):
            async def factory():
                yield {'type': 'chunk', 'content': 'Hello'}
            return factory

        view.get_stream_agent_responce = _fake
        try:
            agent = view.AIAssistantAgent()

            async def collect():
                out = []
                async for ev in agent.get_response_stream('hi', None, 'alice'):
                    out.append(ev)
                return out

            evs = asyncio.run(collect())
            self.assertGreaterEqual(len(evs), 2)
            self.assertEqual(evs[0]['type'], 'thinking')   # early indicator first
            self.assertEqual(evs[1]['type'], 'chunk')
            self.assertEqual(evs[1]['content'], 'Hello')
        finally:
            view.get_stream_agent_responce = original

    def test_thinking_emitted_even_if_agent_produces_nothing(self):
        """Even if the agent is slow/empty, the thinking indicator still
        appears immediately (the UI does not freeze)."""
        original = view.get_stream_agent_responce

        async def _fake(**kwargs):
            async def factory():
                if False:  # pragma: no cover - empty async generator
                    yield {}
            return factory

        view.get_stream_agent_responce = _fake
        try:
            agent = view.AIAssistantAgent()

            async def collect():
                out = []
                async for ev in agent.get_response_stream('hi', None, 'alice'):
                    out.append(ev)
                return out

            evs = asyncio.run(collect())
            self.assertEqual(len(evs), 1)
            self.assertEqual(evs[0]['type'], 'thinking')
        finally:
            view.get_stream_agent_responce = original

    def test_thinking_does_not_pollute_sync_response(self):
        """The sync (non-streaming) path must not include the thinking event in
        its text response."""
        original = view.get_stream_agent_responce

        async def _fake(**kwargs):
            async def factory():
                yield {'type': 'chunk', 'content': 'answer'}
            return factory

        view.get_stream_agent_responce = _fake
        try:
            agent = view.AIAssistantAgent()
            text, _ = agent.sync_get_response('hi', None, 'alice')
            self.assertEqual(text, 'answer')  # no 'thinking' leakage
            self.assertNotIn('thinking', text.lower())
        finally:
            view.get_stream_agent_responce = original


if __name__ == '__main__':
    unittest.main()