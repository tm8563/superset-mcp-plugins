"""Tests for the embedding/guest-token tools (roadmap #14), incl. audit safety."""
import hashlib
import io
import json
import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401

import superset_chat.app.server.embedding as emb


def httpx():
    return sys.modules['httpx']


def _set_resp(method, path, data):
    httpx().responses[(method, f'http://localhost:8088{path}')] = data


def _calls(method, substr=None):
    return [c for c in httpx().calls if c[0] == method and (substr is None or substr in c[1])]


class TestEmbedding(unittest.TestCase):
    def setUp(self):
        httpx().calls.clear()
        os.environ['SUPERSET_API_KEY'] = 'sst-x'
        os.environ['SUPERSET_API_URL'] = 'http://localhost:8088'
        emb.GUEST_TOKEN_AUDIT_LOG.clear()

    def test_configure_embedding(self):
        _set_resp('POST', '/api/v1/dashboard/5/embedded', {'result': {'uuid': 'u5'}})
        r = emb.configure_embedding(emb.SupersetRestClient(), 5, ['a.com', 'b.com'])
        post = _calls('POST', '/dashboard/5/embedded')[0]
        self.assertEqual(post[3], {'allowed_domains': ['a.com', 'b.com']})
        self.assertEqual(r['result']['uuid'], 'u5')

    def test_get_embedding(self):
        _set_resp('GET', '/api/v1/dashboard/5/embedded', {'result': {'uuid': 'u5'}})
        emb.get_embedding(emb.SupersetRestClient(), 5)
        self.assertTrue(_calls('GET', '/dashboard/5/embedded'))

    def test_revoke(self):
        _set_resp('DELETE', '/api/v1/dashboard/5/embedded', {'message': 'deleted'})
        emb.revoke_guest_tokens(emb.SupersetRestClient(), 5)
        self.assertTrue(_calls('DELETE', '/dashboard/5/embedded'))

    def test_build_embed_url(self):
        self.assertEqual(emb.build_embed_url('http://localhost:8088', 'u5'),
                         'http://localhost:8088/embedded/u5')
        self.assertEqual(emb.build_embed_url('http://localhost:8088/', 'u5', ui_config=15),
                         'http://localhost:8088/embedded/u5?uiConfig=15')

    def test_mint_guest_token_body(self):
        _set_resp('POST', '/api/v1/security/guest_token/', {'token': 'T'})
        emb.mint_guest_token(emb.SupersetRestClient(),
                             [{'type': 'dashboard', 'id': 'u5'}],
                             rls=[{'dataset': 2, 'clause': 'user_id=1'}], datasets=[2])
        post = _calls('POST', '/guest_token/')[0]
        self.assertEqual(post[3]['resources'], [{'type': 'dashboard', 'id': 'u5'}])
        self.assertEqual(post[3]['rls'], [{'dataset': 2, 'clause': 'user_id=1'}])
        self.assertEqual(post[3]['datasets'], [2])

    def test_audit_safety_no_raw_token(self):
        _set_resp('POST', '/api/v1/security/guest_token/', {'token': 'SECRET-RAW'})
        buf = io.StringIO()
        h = logging.StreamHandler(buf)
        logging.getLogger('superset_chat.app.server.embedding').addHandler(h)
        logging.getLogger('superset_chat.app.server.embedding').setLevel(logging.INFO)
        r = emb.mint_guest_token(emb.SupersetRestClient(),
                                 [{'type': 'dashboard', 'id': 'u5'}])
        self.assertEqual(r['token'], 'SECRET-RAW')  # returned to caller
        self.assertEqual(len(emb.GUEST_TOKEN_AUDIT_LOG), 1)
        entry = emb.GUEST_TOKEN_AUDIT_LOG[0]
        self.assertEqual(entry['sha256'],
                         hashlib.sha256(b'SECRET-RAW').hexdigest())
        self.assertNotIn('SECRET-RAW', json.dumps(entry))
        self.assertNotIn('SECRET-RAW', buf.getvalue())
        self.assertIn('sha256=', buf.getvalue())


class TestEmbeddingTools(unittest.TestCase):
    def setUp(self):
        httpx().calls.clear()
        os.environ['SUPERSET_API_KEY'] = 'sst-x'
        os.environ['SUPERSET_API_URL'] = 'http://localhost:8088'

    def test_all_five_tools_present(self):
        names = {t.name for t in emb.EmbeddingTools}
        self.assertEqual(names, {'ConfigureEmbedding', 'GetEmbedding',
                                 'MintGuestToken', 'BuildEmbedUrl',
                                 'RevokeGuestTokens'})

    def test_configure_tool_parses_csv(self):
        _set_resp('POST', '/api/v1/dashboard/7/embedded', {'result': {'uuid': 'u7'}})
        tool = [t for t in emb.EmbeddingTools if t.name == 'ConfigureEmbedding'][0]
        tool.func(7, 'a.com, b.com ,c.com')
        post = _calls('POST', '/dashboard/7/embedded')[0]
        self.assertEqual(post[3], {'allowed_domains': ['a.com', 'b.com', 'c.com']})


if __name__ == '__main__':
    unittest.main()