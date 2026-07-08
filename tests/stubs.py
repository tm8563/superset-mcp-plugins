"""Shared test stubs for superset-chat (roadmap #18).

The plugin imports heavy optional deps (langchain, langgraph, pydantic, httpx,
flask, flask_appbuilder, flask_login) that aren't installed in the test
environment. This module installs lightweight stand-ins into ``sys.modules``
so the plugin's modules can be imported and exercised in isolation.

Import this module (``import stubs``) at the top of every test module BEFORE
importing anything from ``superset_chat``. The install runs once (module
caching); expose :data:`httpx` and :data:`flask_login.current_user` to
configure responses/auth state per test.
"""
import sys
import types
from types import SimpleNamespace


class _Dummy:
    """Generic stand-in object."""
    def __init__(self, *args, **kwargs):
        pass


def _dummy(*args, **kwargs):
    return _Dummy()


# --- httpx: a configurable recording client ---
class _FakeResp:
    def __init__(self, data, status=200):
        self._d = data
        self.status_code = status

    def json(self):
        return self._d

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


class FakeHttpx:
    """Records calls and returns canned responses keyed by (method, url)."""
    def __init__(self):
        self.calls = []
        self.responses = {}

    def _resp(self, method, url):
        return _FakeResp(self.responses.get((method, url), {}))

    def get(self, url, headers=None, timeout=None):
        self.calls.append(('GET', url, headers, None))
        return self._resp('GET', url)

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(('POST', url, headers, json))
        return self._resp('POST', url)

    def put(self, url, headers=None, json=None, timeout=None):
        self.calls.append(('PUT', url, headers, json))
        return self._resp('PUT', url)

    def delete(self, url, headers=None, timeout=None):
        self.calls.append(('DELETE', url, headers, None))
        return self._resp('DELETE', url)


# --- pydantic: a v1/v2-compatible BaseModel ---
class BaseModel:
    def __init__(self, **kw):
        for k in getattr(self, '__annotations__', {}):
            if k in kw:
                setattr(self, k, kw.pop(k))
            else:
                default = type(self).__dict__.get(k)
                setattr(self, k, default.copy() if isinstance(default, (list, dict)) else default)

    def model_dump(self, exclude_none=False):
        return {k: getattr(self, k) for k in getattr(self, '__annotations__', {})
                if not (exclude_none and getattr(self, k) is None)}

    def dict(self):
        return {k: getattr(self, k) for k in getattr(self, '__annotations__', {})}

    @classmethod
    def model_validate(cls, d):
        return cls(**(d or {}))

    @classmethod
    def parse_obj(cls, d):
        return cls(**(d or {}))


# --- langchain.tools.Tool: preserve name/func ---
class FakeTool:
    def __init__(self, *args, **kwargs):
        self.name = kwargs.get('name')
        self.func = kwargs.get('func')
        self.description = kwargs.get('description')


# --- flask_login.current_user: a mutable proxy ---
class FakeUser:
    def __init__(self):
        self.is_authenticated = False
        self.username = 'anonymous'
        self.roles = []


# --- async context manager for the checkpointer ---
class _FakeAsyncCtx:
    async def __aenter__(self):
        return _Dummy()

    async def __aexit__(self, *args):
        return False


def _install():
    """Install all stub modules into sys.modules (idempotent)."""
    if getattr(sys.modules.get('stubs', None), '_installed', False):
        return

    # httpx as a configurable instance
    httpx = FakeHttpx()
    sys.modules['httpx'] = httpx

    # pydantic
    pydantic = types.ModuleType('pydantic')
    pydantic.BaseModel = BaseModel
    sys.modules['pydantic'] = pydantic

    def reg_path(path, **attrs):
        parts = path.split('.')
        for i in range(1, len(parts)):
            parent = '.'.join(parts[:i])
            if parent not in sys.modules:
                sys.modules[parent] = types.ModuleType(parent)
        m = types.ModuleType(path)
        for k, v in attrs.items():
            setattr(m, k, v)
        sys.modules[path] = m
        return m

    reg_path('langchain_core.messages',
             HumanMessage=_dummy, BaseMessage=object, SystemMessage=_dummy,
             ToolMessage=_dummy, AIMessage=_dummy, AIMessageChunk=_dummy)
    reg_path('langchain.tools', Tool=FakeTool)
    reg_path('langgraph.checkpoint.postgres.aio',
             AsyncPostgresSaver=SimpleNamespace(from_conn_string=lambda *a, **k: _FakeAsyncCtx()))
    reg_path('langgraph.prebuilt', create_react_agent=_dummy)
    reg_path('langchain_neo4j', GraphCypherQAChain=_dummy, Neo4jGraph=_dummy)
    reg_path('langchain.chains', FalkorDBQAChain=_dummy)
    reg_path('langchain_community.graphs', FalkorDBGraph=_dummy)
    reg_path('langchain_mcp_adapters.client', MultiServerMCPClient=_dummy)

    # LLM provider base classes (inference wrappers subclass these)
    class _ChatBase:
        last_kwargs = None

        def __init__(self, **kwargs):
            _ChatBase.last_kwargs = kwargs
    reg_path('langchain_anthropic', ChatAnthropic=_ChatBase)
    reg_path('langchain_openai', ChatOpenAI=_ChatBase)
    reg_path('langchain_aws', ChatBedrock=_ChatBase)
    reg_path('langchain_ollama', ChatOllama=_ChatBase)
    sys.modules['stubs']._ChatBase = _ChatBase

    # flask / flask_appbuilder / flask_login
    def jsonify(*args, **kwargs):
        return args[0] if args else dict(kwargs)

    flask = types.ModuleType('flask')
    flask.render_template_string = _dummy
    flask.request = SimpleNamespace()
    flask.jsonify = jsonify
    flask.Response = _Dummy
    flask.g = SimpleNamespace()
    flask.current_app = SimpleNamespace()
    sys.modules['flask'] = flask

    fab = types.ModuleType('flask_appbuilder')
    fab.BaseView = object
    fab.expose = lambda *a, **k: (lambda f: f)
    fab.AppBuilder = _Dummy
    sys.modules['flask_appbuilder'] = fab

    flask_login = types.ModuleType('flask_login')
    flask_login.current_user = FakeUser()
    sys.modules['flask_login'] = flask_login

    sys.modules['stubs']._installed = True


# Expose for tests
def httpx():
    return sys.modules['httpx']


def current_user():
    return sys.modules['flask_login'].current_user


_installed = False
_install()