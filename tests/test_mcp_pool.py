"""Tests for the pooled MultiServerMCPClient (roadmap #5)."""
import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401

import superset_chat.app.server.llm as llm

constructed = [0]


class FakeMCPClient:
    def __init__(self, mcps):
        constructed[0] += 1
        self.mcps = mcps

    async def get_tools(self):
        return [f'tool#{constructed[0]}-a', f'tool#{constructed[0]}-b']


def _stdio_mcps():
    os.environ['TRANSPORT_TYPE'] = 'stdio'
    os.environ['SUPERSET_API_URL'] = 'http://superset:8088'
    os.environ.pop('SUPERSET_API_KEY', None)
    os.environ['SUPERSET_USERNAME'] = 'admin'
    os.environ['SUPERSET_PASSWORD'] = 'admin'
    return {
        'SupersetMCP': {
            'command': 'python',
            'args': ['-m', 'superset_mcp_server.mcp_server'],
            'transport': 'stdio',
            'env': {k: v for k, v in {
                'SUPERSET_API_URL': os.getenv('SUPERSET_API_URL'),
                'SUPERSET_USERNAME': os.getenv('SUPERSET_USERNAME'),
                'SUPERSET_PASSWORD': os.getenv('SUPERSET_PASSWORD'),
            }.items() if v is not None},
        }
    }


class TestMCPPool(unittest.TestCase):
    def setUp(self):
        llm.MultiServerMCPClient = FakeMCPClient
        llm._mcp_pool._client = None
        llm._mcp_pool._tools = None
        llm._mcp_pool._cached_sig = None
        constructed[0] = 0

    def test_first_call_constructs(self):
        async def run():
            return await llm._mcp_pool.get_tools(_stdio_mcps())
        asyncio.run(run())
        self.assertEqual(constructed[0], 1)

    def test_second_call_reuses(self):
        async def run():
            await llm._mcp_pool.get_tools(_stdio_mcps())
            tools1 = llm._mcp_pool._tools
            await llm._mcp_pool.get_tools(_stdio_mcps())
            return tools1
        tools1 = asyncio.run(run())
        self.assertEqual(constructed[0], 1)
        self.assertIs(llm._mcp_pool._tools, tools1)

    def test_config_change_reinitializes(self):
        async def run():
            await llm._mcp_pool.get_tools(_stdio_mcps())
            os.environ['TRANSPORT_TYPE'] = 'sse'
            os.environ['mcp_host'] = 'mcp_sse_server:8000'
            os.environ['MCP_TOKEN'] = 'tok'
            await llm._mcp_pool.get_tools({
                'SupersetMCP': {
                    'url': 'http://mcp_sse_server:8000/sse',
                    'transport': 'sse',
                    'headers': {'Authorization': 'Bearer tok'},
                }
            })
        asyncio.run(run())
        self.assertEqual(constructed[0], 2)


if __name__ == '__main__':
    unittest.main()