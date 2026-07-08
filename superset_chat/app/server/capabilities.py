"""Zero-setup capability disclosure (roadmap #24).

Builds a human-friendly capability list from the agent's ACTUAL wired tool
groups (the ``*Tools`` lists imported into ``llm.py``), so the assistant
advertises what it can really do — without requiring any manual topic/synonym
curation. The #13 Q-style sidecar already auto-populates per-dataset metadata,
so NLQ works on first use with no setup step.

The capability for a tool group is included only when that group is non-empty,
so the disclosure tracks the real tool surface (if a tool group is absent, its
capability is not advertised).
"""
import json
from typing import List

from .semantic_layer import SemanticLayerMetadataTool
from .embedding import EmbeddingTools
from .reports import ReportTools
from .governance import GovernanceTools
from .ml_analytics import MLTools
from .pdf_reports import PdfReportTools


def get_capabilities() -> List[dict]:
    """Return the human-friendly capability list derived from the wired tools.

    Each entry is ``{title, blurb, examples}``. A tool group's capability is
    included only if the group is non-empty (``None`` means always-present,
    e.g. the MCP Superset browse tools).
    """
    # Built inside the function so tests can monkeypatch the tool lists and
    # verify the disclosure tracks the real surface. Each `tools` value is the
    # tool group itself (a Tool object or a list of Tools); the capability is
    # advertised only when that value is truthy. `True` means always-present
    # (the MCP Superset browse tools).
    groups = [
        (True, 'Browse Superset',
         'List and inspect dashboards, charts, datasets, and databases.',
         ['Show me all dashboards', 'What datasets do we have?']),
        (SemanticLayerMetadataTool, 'Ask questions in plain English (NLQ → SQL)',
         'Ask a natural-language question about a dataset; the assistant '
         'grounds it in the dataset\'s columns/metrics and returns SQL + an '
         'answer. No topic/synonym setup needed — dataset metadata is '
         'auto-discovered.',
         ['What was total revenue last quarter?', 'How many orders per day?']),
        (EmbeddingTools, 'Embed dashboards & mint guest tokens',
         'Enable dashboard embedding, mint short-lived guest tokens, and build '
         'embed URLs.',
         ['Enable embedding for dashboard 9',
          'Mint a guest token for the sales dashboard']),
        (ReportTools, 'Alerts & scheduled reports',
         'List scheduled reports, trigger one on demand, or subscribe.',
         ['List my scheduled reports', 'Run report 3 now']),
        (GovernanceTools, 'Governance & audit',
         'Audit row-level security rules, roles, and tags.',
         ['List RLS rules', 'Which roles exist?']),
        (MLTools, 'Anomaly detection & forecasting',
         'Detect anomalies and forecast a metric from a numeric series.',
         ['Detect anomalies in daily revenue',
          'Forecast the next 7 days of orders']),
        (PdfReportTools, 'PDF / screenshot export',
         'Trigger a dashboard screenshot and best-effort export it as PDF.',
         ['Export dashboard 9 as PDF']),
    ]
    capabilities = []
    for tools, title, blurb, examples in groups:
        if tools:
            capabilities.append({
                'title': title, 'blurb': blurb, 'examples': examples,
            })
    return capabilities


def get_capabilities_json() -> str:
    """JSON-serialize the capability list for safe injection into the template."""
    return json.dumps(get_capabilities(), default=str)