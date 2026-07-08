import logging
import os
from typing import Any, Dict, List, Tuple

from langchain_core.messages import BaseMessage, AIMessage

logger = logging.getLogger(__name__)


def _parse_model_id() -> Tuple[str, str]:
    """Parse ``LLM_MODEL_ID`` (``provider:model_id``) safely.

    A malformed value (e.g. missing colon, empty provider/model) must never
    crash the plugin at import time. Returns ``('mock', 'mock')`` and logs a
    warning so the agent degrades to :class:`MockChatModel` with a clear
    signal instead of a stack trace.
    """
    raw = os.environ.get('LLM_MODEL_ID', 'mock:mock')
    try:
        model_type, model_id = raw.split(':', 1)
    except ValueError:
        logger.warning(
            "LLM_MODEL_ID=%r is malformed (expected 'provider:model_id'); "
            "falling back to the mock chat model.",
            raw,
        )
        return 'mock', 'mock'
    if not model_type or not model_id:
        logger.warning(
            "LLM_MODEL_ID=%r has an empty provider or model id; falling back "
            "to the mock chat model.",
            raw,
        )
        return 'mock', 'mock'
    return model_type, model_id


model_type, model_id = _parse_model_id()

class MockChatModel:
    """Mock chat model for testing when no real model is configured"""

    def __init__(self, **kwargs):
        self.model = "mock-model"

    def invoke(self, messages: List[BaseMessage], **kwargs) -> AIMessage:
        """Mock invoke method that returns a helpful message"""
        user_message = ""
        for msg in messages:
            if hasattr(msg, 'content'):
                user_message = str(msg.content)
                break

        mock_response = f"""I'm a mock AI assistant running in demo mode. You asked: "{user_message}"

To enable real AI functionality, you need to:
1. Set the LLM_MODEL_ID environment variable (e.g., 'openai:gpt-4')
2. Configure the appropriate API keys

For now, I can help with basic Superset questions using my mock responses."""

        return AIMessage(content=mock_response)

    def stream(self, messages: List[BaseMessage], **kwargs):
        """Mock streaming method"""
        response = self.invoke(messages, **kwargs)
        import time
        words = response.content.split()
        for word in words:
            from langchain_core.messages import AIMessageChunk
            # Add a small delay to simulate real streaming
            time.sleep(0.05)
            yield AIMessageChunk(content=word + " ")

_KNOWN_PROVIDERS = ('bedrock', 'anthropic', 'openai')

if model_type == 'bedrock':
    try:
        from .inference.bedrock_model import ChatBedrock
        ChatModel = ChatBedrock
    except Exception as exc:  # pragma: no cover - depends on env/deps
        logger.warning(
            "Failed to initialize the 'bedrock' chat model (%s); falling back "
            "to the mock chat model. Ensure langchain_aws is installed and "
            "AWS credentials are set.",
            exc,
        )
        ChatModel = MockChatModel
elif model_type in ('anthropic', 'antropic'):
    # 'antropic' is kept as a backward-compatible alias for the original
    # (mis-spelled) provider token; 'anthropic' is the canonical spelling.
    try:
        from .inference.anthropic_model import ChatAnthropic
        ChatModel = ChatAnthropic
    except Exception as exc:  # pragma: no cover - depends on env/deps
        logger.warning(
            "Failed to initialize the %r chat model (%s); falling back to the "
            "mock chat model. Ensure langchain_anthropic is installed and "
            "ANTHROPIC_API_KEY is set.",
            model_type, exc,
        )
        ChatModel = MockChatModel
elif model_type == 'openai':
    try:
        from .inference.openai_model import ChatOpenAI
        ChatModel = ChatOpenAI
    except Exception as exc:  # pragma: no cover - depends on env/deps
        logger.warning(
            "Failed to initialize the 'openai' chat model (%s); falling back "
            "to the mock chat model. Ensure langchain_openai is installed and "
            "OPENAI_API_KEY is set.",
            exc,
        )
        ChatModel = MockChatModel
else:
    logger.warning(
        "Unknown LLM provider %r (LLM_MODEL_ID=%r); falling back to the mock "
        "chat model. Set LLM_MODEL_ID to 'provider:model_id' where provider "
        "is one of: %s.",
        model_type, os.environ.get('LLM_MODEL_ID'),
        ', '.join(_KNOWN_PROVIDERS),
    )
    ChatModel = MockChatModel