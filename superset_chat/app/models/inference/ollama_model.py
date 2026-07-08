import os

from langchain_ollama import ChatOllama as BaseChatOllama


class ChatOllama(BaseChatOllama):
    """A wrapper for `langchain_ollama.ChatOllama` supporting local + cloud.

    LOCAL: ``OLLAMA_BASE_URL=http://localhost:11434`` (no auth).
    CLOUD: ``OLLAMA_BASE_URL=https://ollama.com`` with ``OLLAMA_API_KEY`` sent
    as ``Authorization: Bearer`` via ``client_kwargs['headers']``.
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