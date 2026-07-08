"""Tests for the structured astream_events v2 streaming (roadmap #17)."""
import asyncio
import json
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401

import superset_chat.app.server.llm as llm

CM = llm.ChatMessage
ET = llm.LLMEventType


CHUNK_EV = {'event': 'on_chat_model_stream', 'data': {'chunk': SimpleNamespace(content='Hello')}}
TOOL_START_EV = {'event': 'on_tool_start', 'name': 'SemanticLayerMetadata',
                 'data': {'input': {'dataset_id': 1}}}
TOOL_END_EV = {'event': 'on_tool_end', 'name': 'SemanticLayerMetadata',
               'data': {'output': SimpleNamespace(content='columns: ...')}}
TOOL_END_STR_EV = {'event': 'on_tool_end', 'name': 'X', 'data': {'output': 'plain'}}


class TestFromEvent(unittest.TestCase):
    def test_chunk(self):
        self.assertEqual(CM.from_event(CHUNK_EV).to_event_dict(),
                         {'type': 'chunk', 'content': 'Hello'})

    def test_tool_start_structured(self):
        d = CM.from_event(TOOL_START_EV).to_event_dict()
        self.assertEqual(d['type'], 'tool_start')
        self.assertEqual(d['name'], 'SemanticLayerMetadata')
        self.assertEqual(d['input'], '{"dataset_id": 1}')

    def test_tool_end_object_content(self):
        self.assertEqual(CM.from_event(TOOL_END_EV).to_event_dict(),
                         {'type': 'tool_end', 'name': 'SemanticLayerMetadata',
                          'output': 'columns: ...'})

    def test_tool_end_string(self):
        self.assertEqual(CM.from_event(TOOL_END_STR_EV).to_event_dict(),
                         {'type': 'tool_end', 'name': 'X', 'output': 'plain'})

    def test_ignored_event_falsy(self):
        self.assertFalse(CM.from_event({'event': 'on_chat_model_start'}))

    def test_unknown_event_raises(self):
        with self.assertRaises(ValueError):
            CM.from_event({'event': 'bogus_xyz'})

    def test_no_text_block_markers(self):
        blob = json.dumps([CM.from_event(TOOL_START_EV).to_event_dict(),
                           CM.from_event(TOOL_END_EV).to_event_dict()])
        self.assertNotIn('Start Running Tool', blob)
        self.assertNotIn('Tool Output', blob)


class _FakeInner:
    def __init__(self, events):
        self.events = events

    async def astream_events(self, msg, config, version='v2'):
        for ev in self.events:
            yield ev


class TestAstreamEvents(unittest.TestCase):
    def test_stream_order_and_structure(self):
        events = [
            {'event': 'on_chat_model_start'},  # ignored
            CHUNK_EV,
            TOOL_START_EV,
            TOOL_END_EV,
            {'event': 'on_chat_model_stream',
             'data': {'chunk': SimpleNamespace(content=' world')}},
        ]
        agent = llm.LLMAgent(tools=[], md_uri=None)
        agent._agent = _FakeInner(events)

        async def run():
            out = []
            async for cm in agent.astream_events('hi', {}):
                out.append(cm.to_event_dict())
            return out

        out = asyncio.run(run())
        self.assertEqual([d['type'] for d in out],
                         ['chunk', 'tool_start', 'tool_end', 'chunk'])
        self.assertEqual(out[0], {'type': 'chunk', 'content': 'Hello'})
        self.assertEqual(out[3], {'type': 'chunk', 'content': ' world'})
        self.assertNotIn('Start Running Tool', json.dumps(out))


if __name__ == '__main__':
    unittest.main()