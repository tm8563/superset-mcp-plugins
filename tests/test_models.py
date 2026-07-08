"""Tests for the LLM provider dispatch (roadmap #1, #2, #9)."""
import importlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401  installs stub deps


def _fresh_models():
    for m in list(sys.modules):
        if m.startswith('superset_chat.app.models'):
            del sys.modules[m]
    return importlib.import_module('superset_chat.app.models')


class TestModelDispatch(unittest.TestCase):
    def setUp(self):
        os.environ.pop('LLM_MODEL_ID', None)
        for m in list(sys.modules):
            if m.startswith('superset_chat.app.models'):
                del sys.modules[m]

    def test_anthropic_canonical(self):
        os.environ['LLM_MODEL_ID'] = 'anthropic:claude-3-5-sonnet'
        M = _fresh_models()
        self.assertEqual(M.ChatModel.__name__, 'ChatAnthropic')

    def test_antropic_alias(self):
        os.environ['LLM_MODEL_ID'] = 'antropic:claude-3'
        M = _fresh_models()
        self.assertEqual(M.ChatModel.__name__, 'ChatAnthropic')

    def test_openai(self):
        os.environ['LLM_MODEL_ID'] = 'openai:gpt-4o'
        M = _fresh_models()
        self.assertEqual(M.ChatModel.__name__, 'ChatOpenAI')

    def test_bedrock(self):
        os.environ['LLM_MODEL_ID'] = 'bedrock:anthropic.claude-3'
        M = _fresh_models()
        self.assertEqual(M.ChatModel.__name__, 'ChatBedrock')

    def test_ollama(self):
        os.environ['LLM_MODEL_ID'] = 'ollama:llama3.1'
        M = _fresh_models()
        self.assertEqual(M.ChatModel.__name__, 'ChatOllama')

    def test_unknown_falls_back_to_mock(self):
        os.environ['LLM_MODEL_ID'] = 'bogus:x'
        M = _fresh_models()
        self.assertEqual(M.ChatModel.__name__, 'MockChatModel')

    def test_known_providers_listed(self):
        M = _fresh_models()
        self.assertEqual(M._KNOWN_PROVIDERS,
                         ('bedrock', 'anthropic', 'openai', 'ollama'))


class TestParseGuard(unittest.TestCase):
    """roadmap #2: LLM_MODEL_ID parse must not crash on missing colon."""
    def setUp(self):
        for m in list(sys.modules):
            if m.startswith('superset_chat.app.models'):
                del sys.modules[m]

    def _import_raises(self, val, unset=False):
        import logging
        if unset:
            os.environ.pop('LLM_MODEL_ID', None)
        else:
            os.environ['LLM_MODEL_ID'] = val
        try:
            _fresh_models()
            return False
        except Exception:
            return True

    def test_no_colon_does_not_raise(self):
        self.assertFalse(self._import_raises('garbage'))

    def test_empty_value_does_not_raise(self):
        self.assertFalse(self._import_raises('', unset=True))

    def test_empty_provider_does_not_raise(self):
        self.assertFalse(self._import_raises(':gpt-4'))

    def test_empty_model_id_does_not_raise(self):
        self.assertFalse(self._import_raises('openai:'))

    def test_unset_defaults_to_mock(self):
        os.environ.pop('LLM_MODEL_ID', None)
        M = _fresh_models()
        self.assertEqual(M.ChatModel.__name__, 'MockChatModel')


class TestOllamaWrapper(unittest.TestCase):
    """roadmap #9: ollama_model.py local + cloud kwargs."""
    def setUp(self):
        for m in list(sys.modules):
            if m.startswith('superset_chat.app.models'):
                del sys.modules[m]
        os.environ['LLM_MODEL_ID'] = 'ollama:llama3.1'
        for k in ('OLLAMA_BASE_URL', 'OLLAMA_API_KEY', 'OLLAMA_MODEL'):
            os.environ.pop(k, None)

    def _kwargs(self):
        M = _fresh_models()
        M.ChatModel()
        return sys.modules['stubs']._ChatBase.last_kwargs

    def test_local_defaults(self):
        kw = self._kwargs()
        self.assertEqual(kw['model'], 'llama3.1')
        self.assertEqual(kw['base_url'], 'http://localhost:11434')
        self.assertEqual(kw['temperature'], 0)
        self.assertEqual(kw['client_kwargs'], {})

    def test_cloud_bearer_header(self):
        os.environ['OLLAMA_BASE_URL'] = 'https://ollama.com'
        os.environ['OLLAMA_API_KEY'] = 'oll-test'
        kw = self._kwargs()
        self.assertEqual(kw['base_url'], 'https://ollama.com')
        self.assertEqual(kw['client_kwargs']['headers']['Authorization'],
                         'Bearer oll-test')

    def test_model_override(self):
        os.environ['OLLAMA_MODEL'] = 'qwen2.5:14b'
        kw = self._kwargs()
        self.assertEqual(kw['model'], 'qwen2.5:14b')

    def test_missing_key_no_header(self):
        os.environ['OLLAMA_BASE_URL'] = 'https://ollama.com'
        kw = self._kwargs()
        self.assertEqual(kw['client_kwargs'], {})


if __name__ == '__main__':
    unittest.main()