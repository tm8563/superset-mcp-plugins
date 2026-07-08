"""Plain-language error recovery (roadmap #26).

Categorizes chat failures into a user-friendly ``{category, message,
next_step}`` so the UI never shows a stack trace or raw exception string.
Covers: LLM unreachable (incl. Ollama fallback exhausted), auth/permission
failure, Superset REST error, SQL failure, MCP/tool error, and a generic
fallback. Built on the #17 structured streaming error path.
"""
import logging

logger = logging.getLogger(__name__)

try:  # httpx is a runtime dep but may be absent in the test environment
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

# category -> (user-facing message, suggested next step)
_CATEGORIES = {
    'llm_unreachable': (
        "The AI model couldn't be reached.",
        "Check that your LLM (e.g. Ollama) is running and reachable from "
        "Superset, then try again."),
    'auth_failure': (
        "Superset rejected the request for permission or login reasons.",
        "Check that your Superset account or API key has access to the "
        "requested dashboard/dataset."),
    'sql_failure': (
        "The generated SQL failed to run against the dataset.",
        "Try rephrasing the question, or ask about a different metric or "
        "column."),
    'superset_rest_error': (
        "Superset returned an error for the request.",
        "The dashboard/dataset may not exist or may be misconfigured; verify "
        "it in Superset, then try again."),
    'mcp_tool_error': (
        "A tool the assistant uses returned an error.",
        "Try again, or ask a simpler question."),
    'unknown': (
        "Something went wrong while processing your request.",
        "Please try again, or rephrase your question."),
}


def classify_error(exc) -> dict:
    """Map an exception to ``{category, message, next_step}``."""
    message_text = str(exc) if exc is not None else ''
    low = message_text.lower() or (exc.__class__.__name__ if exc else '').lower()
    response = getattr(exc, 'response', None)
    status = getattr(response, 'status_code', None)

    if httpx is not None and isinstance(exc, (
            httpx.ConnectError, httpx.ConnectTimeout,
            httpx.RemoteProtocolError, httpx.PoolTimeout)):
        category = 'llm_unreachable'
    elif isinstance(exc, ConnectionError) or any(
            k in low for k in ('connection', 'unreachable', 'refused',
                              'timeout', 'temporarily unavailable')):
        category = 'llm_unreachable'
    elif status in (401, 403) or any(
            k in low for k in ('unauthorized', 'forbidden', 'permission',
                              'not authenticated')):
        category = 'auth_failure'
    elif status is not None and 400 <= status < 500:
        category = 'superset_rest_error'
    elif status is not None and status >= 500:
        category = 'superset_rest_error'
    elif any(k in low for k in ('sql', 'syntax', 'relation', 'column ',
                               'database error', 'psql', 'odbc')):
        category = 'sql_failure'
    elif any(k in low for k in ('tool', 'mcp')):
        category = 'mcp_tool_error'
    else:
        category = 'unknown'

    msg, next_step = _CATEGORIES[category]
    logger.info('Classified chat error: category=%s detail=%s',
                category, message_text)
    return {'category': category, 'message': msg, 'next_step': next_step}


def error_event(exc) -> dict:
    """Build a structured streaming error event (#17 path)."""
    ev = classify_error(exc)
    ev['type'] = 'error'
    return ev