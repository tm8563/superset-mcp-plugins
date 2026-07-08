"""Natural-language query over the Superset semantic layer.

This module provides the "Q"-style NLQ capability (roadmap #12):

- :class:`SupersetRestClient` authenticates to Superset (API key preferred,
  else username/password JWT) and performs read-only GET requests.
- :func:`get_semantic_layer_context` fetches a dataset's columns, metrics,
  and description fields (the accessible semantic layer) and formats them as
  context for SQL generation.
- :func:`nl_to_sql` produces a SQL query + explanation from a natural-language
  question via structured LLM output, grounded in that context. The resulting
  SQL is meant to be run via the agent's ``sql_lab`` MCP tool.
- :data:`SemanticLayerMetadataTool` exposes the context to the ReAct agent so
  it can ground SQL before writing it.

The structured semantic-layer view models in ``superset/semantic_layers/`` are
reached through the dataset's columns/metrics and their ``description`` fields
exposed by the Superset REST API, so this stays portable across Superset
versions without importing Superset internals.
"""
import json
import os
from typing import Dict, List, Optional

import httpx
from pydantic import BaseModel
from langchain.tools import Tool

from ..models import ChatModel


class SQLResult(BaseModel):
    """Structured output for natural-language -> SQL generation."""
    sql: str
    explanation: str


# Key under which the Q-style sidecar is stored in a dataset's `extra` JSON
# field, so the metadata lives alongside the dataset (portable, REST-accessible,
# no extra tables).
SIDECAR_EXTRA_KEY = 'ai_semantic_sidecar'


class SemanticSidecar(BaseModel):
    """Q-style governance metadata stored alongside a Superset dataset.

    Held in the dataset's ``extra`` JSON field under ``ai_semantic_sidecar``;
    used to ground and constrain natural-language SQL generation.
    """
    friendly_name: Optional[str] = None
    synonyms: List[str] = []
    primary_date_field: Optional[str] = None
    default_aggregations: Dict[str, str] = {}
    disallowed_aggregations: List[str] = []

    def to_dict(self) -> dict:
        """pydantic v1/v2-compatible serialization (drops None values)."""
        try:
            return self.model_dump(exclude_none=True)
        except AttributeError:  # pragma: no cover - pydantic v1
            return {k: v for k, v in self.dict().items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> 'SemanticSidecar':
        """pydantic v1/v2-compatible construction."""
        data = data or {}
        try:
            return cls.model_validate(data)
        except AttributeError:  # pragma: no cover - pydantic v1
            return cls.parse_obj(data)


def _parse_extra(dataset: dict) -> dict:
    """Parse a dataset's `extra` field (a JSON string or dict) into a dict."""
    extra = dataset.get('extra')
    if not extra:
        return {}
    try:
        return json.loads(extra) if isinstance(extra, str) else extra
    except (ValueError, TypeError):
        return {}


class SupersetRestClient:
    """Minimal read-only Superset REST client.

    Prefers a scoped FAB API key (Authorization: Bearer <key>) over the
    service-account username/password, mirroring the MCP server auth path.
    """

    def __init__(self, base_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 username: Optional[str] = None,
                 password: Optional[str] = None):
        self._base = (base_url or os.environ.get(
            'SUPERSET_API_URL', 'http://localhost:8088')).rstrip('/')
        self._api_key = api_key or os.environ.get('SUPERSET_API_KEY')
        self._username = username or os.environ.get('SUPERSET_USERNAME')
        self._password = password or os.environ.get('SUPERSET_PASSWORD')
        self._token: Optional[str] = None

    def _headers(self) -> dict:
        headers = {'Content-Type': 'application/json'}
        if self._api_key:
            headers['Authorization'] = f'Bearer {self._api_key}'
        elif self._token:
            headers['Authorization'] = f'Bearer {self._token}'
        return headers

    def _login(self):
        """Fetch a JWT access token (service-account fallback, no API key)."""
        response = httpx.post(
            f'{self._base}/api/v1/security/login',
            json={'username': self._username, 'password': self._password,
                  'provider': 'db', 'refresh': True},
            timeout=10,
        )
        response.raise_for_status()
        self._token = response.json()['access_token']

    def get(self, path: str) -> dict:
        if not self._api_key and self._token is None:
            self._login()
        url = path if path.startswith('http') else f'{self._base}{path}'
        response = httpx.get(url, headers=self._headers(), timeout=15)
        response.raise_for_status()
        return response.json()

    def put(self, path: str, json_body: dict) -> dict:
        if not self._api_key and self._token is None:
            self._login()
        url = path if path.startswith('http') else f'{self._base}{path}'
        response = httpx.put(url, headers=self._headers(), json=json_body,
                             timeout=15)
        response.raise_for_status()
        return response.json()


def get_semantic_sidecar(client: SupersetRestClient, dataset_id) -> SemanticSidecar:
    """Read the Q-style sidecar from a dataset's `extra` field."""
    data = client.get(f'/api/v1/dataset/{dataset_id}')
    ds = data.get('result', data)
    return SemanticSidecar.from_dict(_parse_extra(ds).get(SIDECAR_EXTRA_KEY, {}))


def set_semantic_sidecar(client: SupersetRestClient, dataset_id,
                         sidecar: SemanticSidecar) -> dict:
    """Write the Q-style sidecar into a dataset's `extra` field.

    Preserves any other keys already present in `extra`.
    """
    data = client.get(f'/api/v1/dataset/{dataset_id}')
    ds = data.get('result', data)
    extra = _parse_extra(ds)
    extra[SIDECAR_EXTRA_KEY] = sidecar.to_dict()
    return client.put(f'/api/v1/dataset/{dataset_id}',
                      json_body={'extra': json.dumps(extra)})


def get_semantic_layer_context(client: SupersetRestClient, dataset_id) -> str:
    """Fetch and format a dataset's semantic-layer metadata for SQL grounding.

    Returns a compact text description of the dataset's columns (name, type,
    description) and metrics (name, SQL expression, description), plus the
    dataset's own description and virtual SQL when present.
    """
    data = client.get(f'/api/v1/dataset/{dataset_id}')
    ds = data.get('result', data)
    columns = ds.get('columns') or []
    metrics = ds.get('metrics') or []
    sidecar = SemanticSidecar.from_dict(
        _parse_extra(ds).get(SIDECAR_EXTRA_KEY, {}))
    lines = [
        f"Dataset: {ds.get('table_name') or ds.get('name') or dataset_id}"
        f" (schema={ds.get('schema') or 'unknown'})",
    ]
    if ds.get('description'):
        lines.append(f"Description: {ds['description']}")
    if sidecar.friendly_name:
        lines.append(f"Friendly name: {sidecar.friendly_name}")
    if sidecar.synonyms:
        lines.append(f"Synonyms: {', '.join(sidecar.synonyms)}")
    if sidecar.primary_date_field:
        lines.append(f"Primary date field: {sidecar.primary_date_field}")
    if sidecar.default_aggregations:
        lines.append("Default aggregations: " + ", ".join(
            f"{k}={v}" for k, v in sidecar.default_aggregations.items()))
    if sidecar.disallowed_aggregations:
        lines.append(f"Disallowed aggregations: "
                     f"{', '.join(sidecar.disallowed_aggregations)}")
    if ds.get('sql'):
        lines.append(f"Virtual dataset SQL:\n{ds['sql']}")
    lines.append("Columns:")
    for col in columns:
        desc = f" — {col['description']}" if col.get('description') else ''
        lines.append(
            f"  - {col.get('column_name')} ({col.get('type')}){desc}")
    lines.append("Metrics:")
    for metric in metrics:
        desc = f" — {metric['description']}" if metric.get('description') else ''
        lines.append(
            f"  - {metric.get('metric_name')} = {metric.get('expression')}{desc}")
    return "\n".join(lines)


async def nl_to_sql(question: str, dataset_id,
                    client: SupersetRestClient = None) -> SQLResult:
    """Generate SQL for a natural-language question, grounded in the dataset.

    Fetches the dataset's semantic-layer context, then asks the LLM (via
    structured output) for a single SELECT query plus a short explanation.
    The caller runs the returned SQL via the ``sql_lab`` MCP tool.
    """
    client = client or SupersetRestClient()
    context = get_semantic_layer_context(client, dataset_id)
    prompt = (
        "You are a SQL expert. Using only the columns and metrics in the "
        "Superset dataset metadata below, write a single SELECT query that "
        "answers the user's question. Return the SQL and a short explanation.\n\n"
        f"Dataset metadata:\n{context}\n\n"
        f"User question: {question}\n"
    )
    structured = ChatModel().with_structured_output(SQLResult)
    result = await structured.ainvoke(prompt)
    return result


def _semantic_layer_metadata(dataset_id: int) -> str:
    """LangChain tool entrypoint: return dataset semantic-layer context."""
    return get_semantic_layer_context(SupersetRestClient(), dataset_id)


SemanticLayerMetadataTool = Tool(
    name="SemanticLayerMetadata",
    func=_semantic_layer_metadata,
    description=(
        "Fetch a Superset dataset's columns, metrics, and description fields "
        "(the semantic layer) to ground SQL generation. Input: the dataset id "
        "(integer). Call this before writing SQL for a natural-language "
        "question about a dataset, then run the SQL via the sql_lab tool."
    ),
)