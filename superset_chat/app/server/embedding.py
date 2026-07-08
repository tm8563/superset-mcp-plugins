"""Embedded-dashboard + guest-token tooling (roadmap #14).

QuickSight-style programmatic embedding via the Superset REST API:

- :func:`configure_embedding` / :func:`get_embedding` / :func:`revoke_guest_tokens`
  manage a dashboard's embedded config via POST/GET/DELETE
  ``/api/v1/dashboard/<id>/embedded``.
- :func:`mint_guest_token` POSTs ``/api/v1/security/guest_token/`` (requires
  ``can_grant_guest_token``). The raw token is **never** logged — only its
  sha256, mirroring Superset's ``build_guest_token_audit_payload``.
- :func:`build_embed_url` is a pure helper constructing the ``/embedded/<uuid>``
  iframe URL.

``EmbeddingTools`` exposes these as LangChain tools for the ReAct agent.
"""
import hashlib
import json
import logging
from typing import List, Optional

from langchain_core.tools import Tool

from .semantic_layer import SupersetRestClient

logger = logging.getLogger(__name__)

# In-process audit trail of issued guest tokens — sha256 only, NEVER raw
# tokens (mirrors Superset's build_guest_token_audit_payload).
GUEST_TOKEN_AUDIT_LOG: List[dict] = []


def configure_embedding(client: SupersetRestClient, dashboard_id,
                        allowed_domains: List[str]) -> dict:
    """Enable embedding for a dashboard and set its allowed_domains.

    POST /api/v1/dashboard/<id>/embedded {allowed_domains}. Returns the
    embedded config including the stable UUID used in embed URLs.
    """
    return client.post(f'/api/v1/dashboard/{dashboard_id}/embedded',
                       json_body={'allowed_domains': list(allowed_domains)})


def get_embedding(client: SupersetRestClient, dashboard_id) -> dict:
    """Get a dashboard's embedded configuration (UUID + allowed_domains)."""
    return client.get(f'/api/v1/dashboard/{dashboard_id}/embedded')


def mint_guest_token(client: SupersetRestClient, resources: List[dict],
                     rls: Optional[List[dict]] = None,
                     datasets: Optional[List[int]] = None,
                     user: Optional[dict] = None) -> dict:
    """Mint a short-lived guest token for embedded resources.

    ``resources``: list of ``{"type": "dashboard", "id": "<embedded_uuid>"}``.
    ``rls``: list of ``{"dataset": <int>, "clause": "<sql>"}`` (defaults to []).
    ``datasets``: optional list of dataset ids to allow.
    ``user``: optional ``{"username","first_name","last_name"}``.

    Requires the caller's account to hold ``can_grant_guest_token``. The raw
    token is NEVER logged — only its sha256 is recorded.
    """
    body = {'resources': resources, 'rls': rls or []}
    if datasets is not None:
        body['datasets'] = datasets
    if user:
        body['user'] = user
    resp = client.post('/api/v1/security/guest_token/', json_body=body)
    token = resp.get('token') if isinstance(resp, dict) else None
    if token:
        digest = hashlib.sha256(token.encode('utf-8')).hexdigest()
        GUEST_TOKEN_AUDIT_LOG.append({'sha256': digest, 'resources': resources})
        logger.info("Guest token issued (sha256=%s, resources=%s)",
                    digest, resources)
    return resp


def revoke_guest_tokens(client: SupersetRestClient, dashboard_id) -> dict:
    """Revoke embedding for a dashboard, rendering outstanding guest tokens
    for it unusable.

    Guest tokens are short-lived HS256 JWTs (auto-expire, default 300s);
    per-token revocation is not exposed via the Superset REST API. Deleting
    the dashboard's embedded config removes the stable embed UUID, so
    ``/embedded/<uuid>`` 404s and outstanding tokens for that dashboard can
    no longer be used. Global revocation requires rotating
    ``GUEST_TOKEN_JWT_SECRET`` (config-level, not REST-accessible).
    """
    return client.delete(f'/api/v1/dashboard/{dashboard_id}/embedded')


def build_embed_url(superset_domain: str, embedded_uuid: str,
                    ui_config: Optional[int] = None) -> str:
    """Construct the embedded-dashboard iframe URL (pure, no network).

    Returns ``{domain}/embedded/{uuid}``, optionally with ``?uiConfig=<bitmask>``.
    The guest token is NOT placed in the URL — it is posted to the iframe via
    the ``@superset-ui/embedded-sdk`` MessageChannel (``fetchGuestToken``
    callback). ``dashboardUiConfig`` (UI flags) is likewise passed to
    ``embedDashboard()``, not the URL.
    """
    url = f"{superset_domain.rstrip('/')}/embedded/{embedded_uuid}"
    if ui_config is not None:
        url += f"?uiConfig={int(ui_config)}"
    return url


# --- LangChain tool wrappers (operate against the configured Superset) ---

def _client() -> SupersetRestClient:
    return SupersetRestClient()


def _tool_configure_embedding(dashboard_id: int, allowed_domains: str) -> str:
    domains = [d.strip() for d in str(allowed_domains).split(',') if d.strip()]
    return str(configure_embedding(_client(), dashboard_id, domains))


def _tool_get_embedding(dashboard_id: int) -> str:
    return str(get_embedding(_client(), dashboard_id))


def _tool_mint_guest_token(resources: str, rls: str = '', datasets: str = '',
                           user: str = '') -> str:
    res = json.loads(resources)
    r = json.loads(rls) if rls else None
    ds = json.loads(datasets) if datasets else None
    u = json.loads(user) if user else None
    return str(mint_guest_token(_client(), res, rls=r, datasets=ds, user=u))


def _tool_build_embed_url(superset_domain: str, embedded_uuid: str,
                          ui_config: int = None) -> str:
    return build_embed_url(superset_domain, embedded_uuid, ui_config)


def _tool_revoke_guest_tokens(dashboard_id: int) -> str:
    return str(revoke_guest_tokens(_client(), dashboard_id))


EmbeddingTools = [
    Tool(
        name="ConfigureEmbedding",
        func=_tool_configure_embedding,
        description=(
            "Enable embedding for a Superset dashboard and set its "
            "allowed_domains. Inputs: dashboard_id (int), allowed_domains "
            "(comma-separated list of domains). Returns the embedded config "
            "incl. the embed UUID. Only call when the user asks to enable "
            "embedding for a dashboard."
        ),
    ),
    Tool(
        name="GetEmbedding",
        func=_tool_get_embedding,
        description=(
            "Get a Superset dashboard's embedded configuration (UUID + "
            "allowed_domains). Input: dashboard_id (int)."
        ),
    ),
    Tool(
        name="MintGuestToken",
        func=_tool_mint_guest_token,
        description=(
            "Mint a short-lived guest token for an embedded dashboard. "
            "Input `resources` as JSON: "
            '[{"type":"dashboard","id":"<embedded_uuid>"}]. Optional rls, '
            "datasets, user as JSON strings. Requires can_grant_guest_token. "
            "Only call when the user explicitly asks to mint an embed token."
        ),
    ),
    Tool(
        name="BuildEmbedUrl",
        func=_tool_build_embed_url,
        description=(
            "Construct the embedded-dashboard iframe URL. Inputs: "
            "superset_domain, embedded_uuid, optional ui_config (int bitmask). "
            "The guest token is posted separately via the embedded SDK."
        ),
    ),
    Tool(
        name="RevokeGuestTokens",
        func=_tool_revoke_guest_tokens,
        description=(
            "Revoke embedding for a dashboard (deletes its embedded config; "
            "outstanding guest tokens for it become unusable). Input: "
            "dashboard_id (int). Only call when the user asks to revoke "
            "embedding."
        ),
    ),
]