"""Governance & audit tools (roadmap #16).

Read-only wrappers over the Superset REST APIs for row-level security, roles,
and tags — the programmatic-governance analogue of QuickSight's
CloudTrail/IAM observability. These let the agent (and operators) audit access
controls without mutating them.

``GovernanceTools`` exposes the audit reads as LangChain tools for the ReAct
agent.
"""
import logging
from typing import Optional

from langchain.tools import Tool

from .semantic_layer import SupersetRestClient

logger = logging.getLogger(__name__)


def list_rls(client: SupersetRestClient) -> dict:
    """List row-level security rules (GET /api/v1/rowlevelsecurity/)."""
    return client.get('/api/v1/rowlevelsecurity/')


def get_rls(client: SupersetRestClient, rls_id: int) -> dict:
    """Get a row-level security rule by id (GET /api/v1/rowlevelsecurity/<id>)."""
    return client.get(f'/api/v1/rowlevelsecurity/{rls_id}')


def list_roles(client: SupersetRestClient) -> dict:
    """List FAB roles (GET /api/v1/security/roles/)."""
    return client.get('/api/v1/security/roles/')


def get_role(client: SupersetRestClient, role_id: int) -> dict:
    """Get a role by id (GET /api/v1/security/roles/<id>)."""
    return client.get(f'/api/v1/security/roles/{role_id}')


def list_tags(client: SupersetRestClient) -> dict:
    """List tags (GET /api/v1/tag/)."""
    return client.get('/api/v1/tag/')


def get_tagged_objects(client: SupersetRestClient,
                       tags: Optional[str] = None,
                       types: Optional[str] = None) -> dict:
    """List objects that have tags (GET /api/v1/tag/get_objects/).

    Optional ``tags`` and ``types`` are comma-separated filters.
    """
    path = '/api/v1/tag/get_objects/'
    params = []
    if tags:
        params.append(f'tags={tags}')
    if types:
        params.append(f'types={types}')
    if params:
        path += '?' + '&'.join(params)
    return client.get(path)


# --- LangChain tool wrappers (operate against the configured Superset) ---

def _client() -> SupersetRestClient:
    return SupersetRestClient()


def _tool_list_rls() -> str:
    return str(list_rls(_client()))


def _tool_list_roles() -> str:
    return str(list_roles(_client()))


def _tool_list_tags() -> str:
    return str(list_tags(_client()))


def _tool_get_tagged_objects(tags: str = '', types: str = '') -> str:
    return str(get_tagged_objects(_client(), tags or None, types or None))


GovernanceTools = [
    Tool(
        name="ListRLS",
        func=_tool_list_rls,
        description=(
            "List Superset row-level security rules "
            "(GET /api/v1/rowlevelsecurity/). Use to audit RLS policies "
            "(which datasets have row-level filters and their clauses)."
        ),
    ),
    Tool(
        name="ListRoles",
        func=_tool_list_roles,
        description=(
            "List FAB roles (GET /api/v1/security/roles/). Use to audit "
            "access roles for governance."
        ),
    ),
    Tool(
        name="ListTags",
        func=_tool_list_tags,
        description=(
            "List Superset tags (GET /api/v1/tag/)."
        ),
    ),
    Tool(
        name="GetTaggedObjects",
        func=_tool_get_tagged_objects,
        description=(
            "List objects that have tags (GET /api/v1/tag/get_objects/). "
            "Optional inputs: tags, types (comma-separated). Use to audit "
            "which dashboards/charts/datasets are tagged."
        ),
    ),
]