"""Best-effort PDF/screenshot reporting over Superset dashboards & charts
(roadmap #23).

This wraps Superset's EXISTING screenshot/thumbnail machinery rather than
building a new headless renderer:

- ``POST /api/v1/dashboard/<id>/cache_dashboard_screenshot/`` — trigger the
  Celery screenshot worker to (re)render and cache a dashboard screenshot.
- ``GET  /api/v1/dashboard/<id>/screenshot/<digest>/`` — fetch the cached
  dashboard screenshot (PNG bytes).
- ``GET  /api/v1/chart/<id>/cache_screenshot/`` and
  ``GET  /api/v1/chart/<id>/screenshot/<digest>/`` — the chart equivalents.

Superset itself builds paginated PDFs server-side via
``superset/utils/pdf.py:build_pdf_from_screenshots`` inside the reports
worker (delivered by email/Slack, not a downloadable REST endpoint), and
requires the Playwright screenshot worker to be enabled
(``ENABLE_PLAYWRIGHT=true``; the real /home/mlfts/superset dev instance has
it OFF, so these endpoints return 404 there until Playwright is enabled).

This module's client-side ``screenshot_to_pdf`` is BEST-EFFORT: it wraps the
fetched PNG into a single-page PDF (via reportlab if installed). It is NOT a
QuickSight-style paginated report.

GAP vs QuickSight paginated reports (documented honestly, not overclaimed):
- No pixel-perfect multi-page layout control (header/footer, page breaks,
  repeating table headers). The client-side path is a single image-in-PDF.
- No bursting (per-recipient segmented output).
- No scheduled batch PDF generation from the plugin; Superset's scheduled
  reports + ``build_pdf_from_screenshots`` are the server-side equivalent and
  are reached via the #15 report-execute tool, not a new renderer here.
- Requires Superset's Playwright worker to be enabled to produce any output
  at all; otherwise the screenshot endpoints 404.
"""
import logging
import os
from typing import Optional

from langchain.tools import Tool

from .semantic_layer import SupersetRestClient

logger = logging.getLogger(__name__)


def trigger_dashboard_screenshot(client: SupersetRestClient, dashboard_id) -> dict:
    """Trigger Superset to (re)render + cache a dashboard screenshot
    (POST /api/v1/dashboard/<id>/cache_dashboard_screenshot/)."""
    return client.post(
        f'/api/v1/dashboard/{dashboard_id}/cache_dashboard_screenshot/',
        json_body={})


def get_dashboard_screenshot(client: SupersetRestClient, dashboard_id,
                             digest: str) -> bytes:
    """Fetch a cached dashboard screenshot as PNG bytes
    (GET /api/v1/dashboard/<id>/screenshot/<digest>/)."""
    return client.get_bytes(
        f'/api/v1/dashboard/{dashboard_id}/screenshot/{digest}/')


def trigger_chart_screenshot(client: SupersetRestClient, chart_id) -> dict:
    """Trigger Superset to (re)render + cache a chart screenshot
    (GET /api/v1/chart/<id>/cache_screenshot/)."""
    return client.get(f'/api/v1/chart/{chart_id}/cache_screenshot/')


def get_chart_screenshot(client: SupersetRestClient, chart_id,
                         digest: str) -> bytes:
    """Fetch a cached chart screenshot as PNG bytes."""
    return client.get_bytes(
        f'/api/v1/chart/{chart_id}/screenshot/{digest}/')


def screenshot_to_pdf(image_bytes: bytes) -> Optional[bytes]:
    """BEST-EFFORT: wrap a PNG screenshot into a single-page PDF.

    Returns PDF bytes if ``reportlab`` is installed, else ``None`` (caller
    should fall back to the PNG). This is a single image-in-PDF, not a
    paginated report.
    """
    if not image_bytes:
        return None
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
    except ImportError:
        logger.info(
            'screenshot_to_pdf: reportlab not installed; returning PNG only '
            '(best-effort PDF unavailable).')
        return None
    try:
        import io
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        img = ImageReader(io.BytesIO(image_bytes))
        iw, ih = img.getSize()
        pw, ph = letter
        scale = min(pw / iw, ph / ih)
        dw, dh = iw * scale, ih * scale
        c.drawImage(img, (pw - dw) / 2, (ph - dh) / 2, dw, dh)
        c.showPage()
        c.save()
        return buf.getvalue()
    except Exception as exc:  # pragma: no cover - best-effort
        logger.warning('screenshot_to_pdf: failed to build PDF (%s); '
                       'returning PNG only.', exc)
        return None


def export_dashboard_pdf(client: SupersetRestClient, dashboard_id,
                         digest: str, out_dir: str = '/tmp') -> dict:
    """Fetch a dashboard screenshot and best-effort save it as a PDF (or PNG
    fallback). Returns ``{path, format, size, pdf_available, gap_note}``.
    """
    png = get_dashboard_screenshot(client, dashboard_id, digest)
    pdf = screenshot_to_pdf(png)
    if pdf is not None:
        path = os.path.join(out_dir, f'dashboard_{dashboard_id}.pdf')
        with open(path, 'wb') as fh:
            fh.write(pdf)
        return {'path': path, 'format': 'pdf', 'size': len(pdf),
                'pdf_available': True,
                'gap_note': GAP_NOTE}
    path = os.path.join(out_dir, f'dashboard_{dashboard_id}.png')
    with open(path, 'wb') as fh:
        fh.write(png)
    return {'path': path, 'format': 'png', 'size': len(png),
            'pdf_available': False,
            'gap_note': GAP_NOTE + ' (reportlab not installed -> PNG only.)'}


GAP_NOTE = (
    'Best-effort only: NOT QuickSight-style paginated reports. '
    'No pixel-perfect multi-page layout/bursting; single image-in-PDF. '
    'Requires Superset Playwright worker enabled to produce output.'
)


# --- LangChain tool wrappers ---

def _client() -> SupersetRestClient:
    return SupersetRestClient()


def _tool_trigger_dashboard_screenshot(dashboard_id: int) -> str:
    return str(trigger_dashboard_screenshot(_client(), dashboard_id))


def _tool_trigger_chart_screenshot(chart_id: int) -> str:
    return str(trigger_chart_screenshot(_client(), chart_id))


def _tool_export_dashboard_pdf(dashboard_id: int, digest: str,
                               out_dir: str = '/tmp') -> str:
    return str(export_dashboard_pdf(_client(), dashboard_id, digest, out_dir))


PdfReportTools = [
    Tool(
        name="TriggerDashboardScreenshot",
        func=_tool_trigger_dashboard_screenshot,
        description=(
            "Trigger Superset to (re)render and cache a dashboard screenshot "
            "(POST /api/v1/dashboard/<id>/cache_dashboard_screenshot/). "
            "Input: dashboard_id (int). Requires the Superset Playwright "
            "screenshot worker to be enabled (ENABLE_PLAYWRIGHT=true). "
            "Best-effort PDF reporting (roadmap #23)."
        ),
    ),
    Tool(
        name="TriggerChartScreenshot",
        func=_tool_trigger_chart_screenshot,
        description=(
            "Trigger Superset to (re)render and cache a chart screenshot "
            "(GET /api/v1/chart/<id>/cache_screenshot/). Input: chart_id. "
            "Requires the Playwright worker enabled."
        ),
    ),
    Tool(
        name="ExportDashboardPdf",
        func=_tool_export_dashboard_pdf,
        description=(
            "Fetch a dashboard's cached screenshot and best-effort save it as "
            "a PDF (single image-in-PDF; falls back to PNG if reportlab isn't "
            "installed). Inputs: dashboard_id (int), digest (the dashboard's "
            "screenshot digest), optional out_dir. Returns the saved file path "
            "+ a gap note. NOT a QuickSight-style paginated report. Requires "
            "the Playwright worker enabled to have a cached screenshot."
        ),
    ),
]