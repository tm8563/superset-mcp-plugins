import logging
import os

import httpx
from langchain_ollama import ChatOllama as BaseChatOllama

logger = logging.getLogger(__name__)

# Connection-level errors that trigger a switch to the fallback base URL.
# HTTP status errors (the server responded) are NOT included — only failures
# to reach the server at all.
_CONNECT_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.RemoteProtocolError,
    httpx.PoolTimeout,
    ConnectionError,
)


class ChatOllama(BaseChatOllama):
    """A wrapper for `langchain_ollama.ChatOllama` supporting local + cloud
    and automatic cloud->local fallback (roadmap #20).

    LOCAL: ``OLLAMA_BASE_URL=http://localhost:11434`` (no auth).
    CLOUD: ``OLLAMA_BASE_URL=https://ollama.com`` with ``OLLAMA_API_KEY`` sent
    as ``Authorization: Bearer`` via ``client_kwargs['headers']``.
    FALLBACK: if ``OLLAMA_FALLBACK_BASE_URL`` is set, a connection failure
    against ``OLLAMA_BASE_URL`` is retried once against the fallback (e.g.
    cloud primary -> local fallback, so a network outage degrades to local
    inference instead of failing the whole chat).
    """

    def __init__(self, **kwargs):
        """Initialize the `ChatOllama` with specific configuration."""
        _, model_id = os.environ.get(
            'LLM_MODEL_ID', 'ollama:llama3.1').split(':', 1)
        base_url = os.environ.get(
            'OLLAMA_BASE_URL', 'http://localhost:11434')
        client_kwargs = {}
        api_key = os.environ.get('OLLAMA_API_KEY')
        if api_key:
            # Cloud path: authenticate with the bearer token.
            client_kwargs['headers'] = {'Authorization': f'Bearer {api_key}'}
        default_kwargs = {
            'model': os.environ.get('OLLAMA_MODEL', model_id),
            'base_url': base_url,
            'temperature': 0,
            'client_kwargs': client_kwargs,
        }

        super().__init__(**(default_kwargs | kwargs))
        # Remember the config so a fallback client can be rebuilt on the fly.
        self._ollama_model = default_kwargs['model']
        self._ollama_client_kwargs = client_kwargs
        self._primary_url = base_url
        self._fallback_url = os.environ.get('OLLAMA_FALLBACK_BASE_URL')

    def _fallback_client(self):
        """Build a fresh base ChatOllama pointed at the fallback base URL."""
        return BaseChatOllama(
            model=self._ollama_model,
            base_url=self._fallback_url,
            temperature=0,
            client_kwargs=self._ollama_client_kwargs,
        )

    def _switching_to_fallback(self, exc):
        logger.warning(
            "Ollama primary %s unreachable (%s); switching to fallback %s",
            self._primary_url, exc, self._fallback_url,
        )

    # --- async path (used by the ReAct agent's astream_events) ---

    async def _astream(self, *args, **kwargs):
        yielded = False
        try:
            async for chunk in super()._astream(*args, **kwargs):
                yielded = True
                yield chunk
            return
        except _CONNECT_ERRORS as exc:
            # Don't fall back mid-stream (would garble output); only switch on a
            # connection failure before any chunks were produced.
            if not self._fallback_url or yielded:
                raise
            self._switching_to_fallback(exc)
        async for chunk in self._fallback_client()._astream(*args, **kwargs):
            yield chunk

    async def _ainvoke(self, *args, **kwargs):
        try:
            return await super()._ainvoke(*args, **kwargs)
        except _CONNECT_ERRORS as exc:
            if not self._fallback_url:
                raise
            self._switching_to_fallback(exc)
            return await self._fallback_client()._ainvoke(*args, **kwargs)

    # --- sync path ---

    def _stream(self, *args, **kwargs):
        yielded = False
        try:
            for chunk in super()._stream(*args, **kwargs):
                yielded = True
                yield chunk
            return
        except _CONNECT_ERRORS as exc:
            if not self._fallback_url or yielded:
                raise
            self._switching_to_fallback(exc)
        for chunk in self._fallback_client()._stream(*args, **kwargs):
            yield chunk

    def _invoke(self, *args, **kwargs):
        try:
            return super()._invoke(*args, **kwargs)
        except _CONNECT_ERRORS as exc:
            if not self._fallback_url:
                raise
            self._switching_to_fallback(exc)
            return self._fallback_client()._invoke(*args, **kwargs)