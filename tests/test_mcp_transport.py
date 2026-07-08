"""Tests for the MCP transport selection (roadmap #19).

Covers the built-in superset mcp_service over streamable-http, legacy SSE,
and the stdio alpha path; SUPERSET_API_KEY preferred over MCP_TOKEN; and the
no-token (no `Bearer None`) fix.
"""
import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401

import superset_chat.app.server.llm as llm

captured = []


class FakeMCPClient:
    def __init__(self, mcps):
        captured.append(mcps)
        self.mcps = mcps

    async def get_tools(self):
        return ['t']


def _reset():
    llm.MultiServerMCPClient = FakeMCPClient
    llm._mcp_pool._client = None
    llm._mcp_pool._tools = None
    llm._mcp_pool._cached_sig = None
    captured.clear()


def _run():
    async def go():
        await llm.get_stream_agent_responce('s', 'hi', None, 'alice')
    asyncio.run(go())


class TestTransport(unittest.TestCase):
    def setUp(self):
        for k in ('LANGFUSE_HOST', 'GRAPH_DB', 'SUPERSET_API_KEY', 'MCP_TOKEN',
                  'MCP_SERVICE_URL'):
            os.environ.pop(k, None)
        _reset()

    def test_stdio_alpha(self):
        os.environ['TRANSPORT_TYPE'] = 'stdio'
        os.environ['SUPERSET_API_URL'] = 'http://superset:8088'
        os.environ['SUPERSET_USERNAME'] = 'admin'
        os.environ['SUPERSET_PASSWORD'] = 'admin'
        _run()
        cfg = captured[-1]['SupersetMCP']
        self.assertEqual(cfg['transport'], 'stdio')
        self.assertIn('superset_mcp_server.mcp_server', cfg['args'])

    def test_streamable_http_built_in(self):
        os.environ['TRANSPORT_TYPE'] = 'streamable_http'
        os.environ['mcp_host'] = 'mcp_service:5008'
        os.environ['SUPERSET_API_KEY'] = 'sst-key'
        _run()
        cfg = captured[-1]['SupersetMCP']
        self.assertEqual(cfg['transport'], 'streamable_http')
        self.assertEqual(cfg['url'], 'http://mcp_service:5008/mcp')
        self.assertEqual(cfg['headers']['Authorization'], 'Bearer sst-key')

    def test_sse_legacy(self):
        os.environ['TRANSPORT_TYPE'] = 'sse'
        os.environ['mcp_host'] = 'mcp:8000'
        os.environ['MCP_TOKEN'] = 'tok'
        _run()
        cfg = captured[-1]['SupersetMCP']
        self.assertEqual(cfg['transport'], 'sse')
        self.assertEqual(cfg['url'], 'http://mcp:8000/sse')
        self.assertEqual(cfg['headers']['Authorization'], 'Bearer tok')

    def test_no_token_no_bearer_header(self):
        os.environ['TRANSPORT_TYPE'] = 'streamable_http'
        os.environ['mcp_host'] = 'mcp_service:5008'
        _run()
        self.assertEqual(captured[-1]['SupersetMCP']['headers'], {})

    def test_api_key_preferred_over_mcp_token(self):
        os.environ['TRANSPORT_TYPE'] = 'streamable_http'
        os.environ['mcp_host'] = 'mcp_service:5008'
        os.environ['SUPERSET_API_KEY'] = 'sst-key'
        os.environ['MCP_TOKEN'] = 'tok'
        _run()
        self.assertEqual(captured[-1]['SupersetMCP']['headers']['Authorization'],
                         'Bearer sst-key')

    def test_mcp_service_url_override(self):
        os.environ['TRANSPORT_TYPE'] = 'streamable_http'
        os.environ['MCP_SERVICE_URL'] = 'http://custom:9000/mcp'
        os.environ['SUPERSET_API_KEY'] = 'k'
        _run()
        self.assertEqual(captured[-1]['SupersetMCP']['url'],
                         'http://custom:9000/mcp')


if __name__ == '__main__':
    unittest.main()