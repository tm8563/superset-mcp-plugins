"""Tests for the semantic-layer module (roadmap #12, #13)."""
import asyncio
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401

import superset_chat.app.server.semantic_layer as sl


def httpx():
    return sys.modules['httpx']


def _set_resp(method, path, data):
    httpx().responses[(method, f'http://localhost:8088{path}')] = data


def _calls(method, substr=None):
    return [c for c in httpx().calls if c[0] == method and (substr is None or substr in c[1])]


DATASET = {
    'result': {
        'table_name': 'orders', 'schema': 'public',
        'description': 'Customer orders.',
        'sql': 'SELECT * FROM raw_orders',
        'columns': [
            {'column_name': 'id', 'type': 'INTEGER'},
            {'column_name': 'created_at', 'type': 'TIMESTAMP', 'description': 'Order timestamp'},
        ],
        'metrics': [
            {'metric_name': 'total_revenue', 'expression': 'SUM(amount)', 'description': 'Sum of orders'},
        ],
    }
}


class TestRestClientAuth(unittest.TestCase):
    def setUp(self):
        httpx().calls.clear()
        os.environ['SUPERSET_API_URL'] = 'http://localhost:8088'

    def test_api_key_no_login(self):
        os.environ['SUPERSET_API_KEY'] = 'sst-x'
        os.environ.pop('SUPERSET_USERNAME', None)
        _set_resp('GET', '/api/v1/dataset/1', DATASET)
        c = sl.SupersetRestClient()
        c.get('/api/v1/dataset/1')
        self.assertFalse(any(call[0] == 'POST' for call in httpx().calls))
        get_headers = [call[2] for call in httpx().calls if call[0] == 'GET'][0]
        self.assertEqual(get_headers['Authorization'], 'Bearer sst-x')

    def test_username_password_jwt(self):
        os.environ.pop('SUPERSET_API_KEY', None)
        os.environ['SUPERSET_USERNAME'] = 'admin'
        os.environ['SUPERSET_PASSWORD'] = 'admin'
        _set_resp('POST', '/api/v1/security/login', {'access_token': 'jwt-xyz'})
        _set_resp('GET', '/api/v1/dataset/1', DATASET)
        c = sl.SupersetRestClient()
        c.get('/api/v1/dataset/1')
        posts = [call for call in httpx().calls if call[0] == 'POST']
        self.assertEqual(len(posts), 1)
        self.assertTrue(posts[0][1].endswith('/api/v1/security/login'))
        self.assertEqual(posts[0][3],
                         {'username': 'admin', 'password': 'admin', 'provider': 'db', 'refresh': True})
        get_headers = [call[2] for call in httpx().calls if call[0] == 'GET'][0]
        self.assertEqual(get_headers['Authorization'], 'Bearer jwt-xyz')

    def test_put_and_delete(self):
        os.environ['SUPERSET_API_KEY'] = 'sst-x'
        _set_resp('PUT', '/api/v1/dataset/1', {'result': {}})
        _set_resp('DELETE', '/api/v1/dataset/1', {'message': 'deleted'})
        c = sl.SupersetRestClient()
        c.put('/api/v1/dataset/1', json_body={'extra': '{}'})
        c.delete('/api/v1/dataset/1')
        self.assertTrue(_calls('PUT', '/api/v1/dataset/1'))
        self.assertTrue(_calls('DELETE', '/api/v1/dataset/1'))


class _FakeClient:
    def __init__(self, data):
        self.data = data
        self.fetched = None

    def get(self, path):
        self.fetched = path
        return self.data


class TestContext(unittest.TestCase):
    def test_context_format(self):
        fc = _FakeClient(DATASET)
        ctx = sl.get_semantic_layer_context(fc, 1)
        self.assertEqual(fc.fetched, '/api/v1/dataset/1')
        self.assertIn('orders', ctx)
        self.assertIn('schema=public', ctx)
        self.assertIn('Customer orders.', ctx)
        self.assertIn('created_at (TIMESTAMP)', ctx)
        self.assertIn('Order timestamp', ctx)
        self.assertIn('total_revenue = SUM(amount)', ctx)
        self.assertIn('Sum of orders', ctx)
        self.assertIn('SELECT * FROM raw_orders', ctx)

    def test_context_no_sidecar_graceful(self):
        ds = {'result': {'table_name': 't', 'columns': [], 'metrics': []}}
        ctx = sl.get_semantic_layer_context(_FakeClient(ds), 2)
        self.assertNotIn('Friendly name', ctx)


class TestSidecar(unittest.TestCase):
    def test_roundtrip(self):
        sc = sl.SemanticSidecar(friendly_name='Revenue', synonyms=['sales'],
                                primary_date_field='created_at',
                                default_aggregations={'amount': 'SUM'},
                                disallowed_aggregations=['COUNT'])
        d = sc.to_dict()
        self.assertEqual(d['friendly_name'], 'Revenue')
        self.assertEqual(d['synonyms'], ['sales'])
        sc2 = sl.SemanticSidecar.from_dict(d)
        self.assertEqual(sc2.friendly_name, 'Revenue')

    def test_parse_extra(self):
        self.assertEqual(sl._parse_extra({}), {})
        self.assertEqual(sl._parse_extra({'extra': ''}), {})
        self.assertEqual(sl._parse_extra({'extra': '{"a":1}'}), {'a': 1})
        self.assertEqual(sl._parse_extra({'extra': 'bad'}), {})

    def test_set_preserves_other_keys(self):
        httpx().calls.clear()
        os.environ['SUPERSET_API_KEY'] = 'sst-x'
        os.environ['SUPERSET_API_URL'] = 'http://localhost:8088'
        ds = {'result': {'extra': json.dumps({'other': 'keep',
                  'ai_semantic_sidecar': {'friendly_name': 'Old'}})}}
        _set_resp('GET', '/api/v1/dataset/1', ds)
        _set_resp('PUT', '/api/v1/dataset/1', {'result': {}})
        c = sl.SupersetRestClient()
        sl.set_semantic_sidecar(c, 1, sl.SemanticSidecar(friendly_name='New'))
        put = _calls('PUT', '/api/v1/dataset/1')[0]
        extra = json.loads(put[3]['extra'])
        self.assertEqual(extra['other'], 'keep')
        self.assertEqual(extra['ai_semantic_sidecar']['friendly_name'], 'New')


class TestNLToSQL(unittest.TestCase):
    def test_structured_output(self):
        class _Structured:
            async def ainvoke(self, prompt):
                return sl.SQLResult(sql='SELECT 1', explanation='one')

        class _FakeLLM:
            def with_structured_output(self, cls):
                return _Structured()
        sl.ChatModel = _FakeLLM
        result = asyncio.run(sl.nl_to_sql('how many', 1, client=_FakeClient(DATASET)))
        self.assertEqual(result.sql, 'SELECT 1')
        self.assertEqual(result.explanation, 'one')


if __name__ == '__main__':
    unittest.main()