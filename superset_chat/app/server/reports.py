"""Alerts & scheduled-report orchestration (roadmap #15).

Wraps the Superset ``/api/v1/report/`` REST endpoints (``ReportScheduleRestApi``)
and exposes an on-demand snapshot/execution trigger (``POST /<pk>/execute``),
the open-source analogue of QuickSight's ``StartDashboardSnapshotJobSchedule``.

``ReportTools`` exposes a useful subset as LangChain tools for the ReAct agent.
"""
import json
import logging

from langchain.tools import Tool

from .semantic_layer import SupersetRestClient

logger = logging.getLogger(__name__)


def list_reports(client: SupersetRestClient) -> dict:
    """List scheduled reports / alerts (GET /api/v1/report/)."""
    return client.get('/api/v1/report/')


def get_report(client: SupersetRestClient, report_id: int) -> dict:
    """Get a scheduled report by id (GET /api/v1/report/<id>)."""
    return client.get(f'/api/v1/report/{report_id}')


def create_report(client: SupersetRestClient, payload: dict) -> dict:
    """Create a scheduled report / alert (POST /api/v1/report/)."""
    return client.post('/api/v1/report/', json_body=payload)


def update_report(client: SupersetRestClient, report_id: int, payload: dict) -> dict:
    """Update a scheduled report (PUT /api/v1/report/<id>)."""
    return client.put(f'/api/v1/report/{report_id}', json_body=payload)


def delete_report(client: SupersetRestClient, report_id: int) -> dict:
    """Delete a scheduled report (DELETE /api/v1/report/<id>)."""
    return client.delete(f'/api/v1/report/{report_id}')


def subscribe_report(client: SupersetRestClient, payload: dict) -> dict:
    """Subscribe to a report / alert (POST /api/v1/report/subscribe)."""
    return client.post('/api/v1/report/subscribe', json_body=payload)


def execute_report(client: SupersetRestClient, report_id: int) -> dict:
    """Trigger an on-demand snapshot/execution of a scheduled report
    (QuickSight ``StartDashboardSnapshotJobSchedule`` analogue).

    POST /api/v1/report/<id>/execute.
    """
    return client.post(f'/api/v1/report/{report_id}/execute', json_body={})


def list_slack_channels(client: SupersetRestClient) -> dict:
    """List Slack channels available for report notifications."""
    return client.get('/api/v1/report/slack_channels/')


# --- LangChain tool wrappers (operate against the configured Superset) ---

def _client() -> SupersetRestClient:
    return SupersetRestClient()


def _tool_list_reports() -> str:
    return str(list_reports(_client()))


def _tool_get_report(report_id: int) -> str:
    return str(get_report(_client(), report_id))


def _tool_execute_report(report_id: int) -> str:
    return str(execute_report(_client(), report_id))


def _tool_subscribe_report(payload: str) -> str:
    return str(subscribe_report(_client(), json.loads(payload)))


def _tool_create_report(payload: str) -> str:
    return str(create_report(_client(), json.loads(payload)))


ReportTools = [
    Tool(
        name="ListReports",
        func=_tool_list_reports,
        description=(
            "List Superset scheduled reports / alerts (GET /api/v1/report/). "
            "Returns the report schedules and their crontab/type."
        ),
    ),
    Tool(
        name="GetReport",
        func=_tool_get_report,
        description=(
            "Get a Superset scheduled report by id. Input: report_id (int)."
        ),
    ),
    Tool(
        name="ExecuteReport",
        func=_tool_execute_report,
        description=(
            "Trigger an on-demand snapshot/execution of a scheduled report "
            "(open-source analogue of QuickSight's "
            "StartDashboardSnapshotJobSchedule). Input: report_id (int). "
            "Only call when the user asks to trigger/run a report now."
        ),
    ),
    Tool(
        name="SubscribeReport",
        func=_tool_subscribe_report,
        description=(
            "Subscribe to a Superset report/alert. Input: payload JSON for "
            "the subscription. Only call when the user asks to subscribe."
        ),
    ),
    Tool(
        name="CreateReport",
        func=_tool_create_report,
        description=(
            "Create a Superset scheduled report/alert. Input: payload JSON "
            "describing the report schedule (type, crontab, dashboard/chart, "
            "recipients). Only call when the user asks to create a report."
        ),
    ),
]