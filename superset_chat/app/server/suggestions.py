"""Context-aware prompt suggestions grounded in a dataset's actual
columns/metrics (roadmap #25).

Replaces the stale hardcoded Airflow-DAG ``showExamples()`` with suggestions
derived from a dataset's real columns, metrics, and the #13 Q-style sidecar
(friendly name, synonyms, primary date field). Deterministic (no LLM), so it
works instantly on first open with zero setup — the user sees dataset-grounded
example questions instead of a blank input box.
"""
import re
from typing import List

from .semantic_layer import (
    SupersetRestClient,
    SemanticSidecar,
    _parse_extra,
    SIDECAR_EXTRA_KEY,
)

_DATE_TYPES = ('TIMESTAMP', 'DATETIME', 'DATE', 'TIMESTAMPTZ', 'TIME')


def _first_date_column(columns) -> str | None:
    for col in columns:
        col_type = (col.get('type') or '').upper()
        if any(d in col_type for d in _DATE_TYPES):
            return col.get('column_name')
    return None


def _clean(name) -> str:
    return re.sub(r'\s+', ' ', str(name or '').strip())


def suggest_questions(client: SupersetRestClient, dataset_id,
                      max_questions: int = 4) -> List[str]:
    """Return up to ``max_questions`` example questions grounded in the
    dataset's real columns/metrics + #13 sidecar. Single REST fetch."""
    data = client.get(f'/api/v1/dataset/{dataset_id}')
    ds = data.get('result', data)
    table = _clean(ds.get('table_name') or ds.get('name')) \
        or f'dataset {dataset_id}'
    columns = ds.get('columns') or []
    metrics = ds.get('metrics') or []
    sidecar = SemanticSidecar.from_dict(
        _parse_extra(ds).get(SIDECAR_EXTRA_KEY, {}))

    col_names = [_clean(c.get('column_name')) for c in columns]
    col_names = [c for c in col_names if c]
    metric_names = [_clean(m.get('metric_name')) for m in metrics]
    metric_names = [m for m in metric_names if m]
    date_col = sidecar.primary_date_field or _first_date_column(columns)
    subject = sidecar.friendly_name or table

    questions = []
    if metric_names and col_names:
        questions.append(f'What is the total {metric_names[0]} by {col_names[0]}?')
    if date_col and metric_names:
        questions.append(f'Show {metric_names[0]} over time by {date_col}.')
    elif date_col and col_names:
        questions.append(f'How many records are there per {date_col}?')
    if sidecar.synonyms and metric_names:
        questions.append(f'What is the trend of {sidecar.synonyms[0]}?')
    if col_names:
        questions.append(f'How many {subject} records are there?')
        questions.append(f'What are the distinct values of {col_names[0]}?')

    # De-duplicate, preserve order, cap.
    seen = set()
    out = []
    for q in questions:
        q = _clean(q)
        if q and q not in seen:
            seen.add(q)
            out.append(q)
        if len(out) >= max_questions:
            break
    if not out:
        out = [f'Tell me about the {subject} dataset.']
    return out[:max_questions]