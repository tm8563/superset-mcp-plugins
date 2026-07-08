"""Tests for the best-effort PDF/screenshot reporting tools (roadmap #23)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401  (stubs httpx/langchain etc.)

from superset_chat.app.server.semantic_layer import SupersetRestClient
import superset_chat.app.server.pdf_reports as pdf


class _Client(SupersetRestClient):
    """Overrides get_bytes with an in-memory map; post/get go through the
    stubs httpx recorder."""
    def __init__(self):
        super().__init__(api_key='sst-x')
        self.bytes_map = {}
        self.bytes_calls = []

    def get_bytes(self, path):
        self.bytes_calls.append(path)
        return self.bytes_map.get(path, b'')


class TestPdfReports(unittest.TestCase):
    def setUp(self):
        stubs.httpx().calls.clear()
        os.environ['SUPERSET_API_URL'] = 'http://localhost:8088'

    def _got(self, method, sub):
        return any(c[0] == method and sub in c[1] for c in stubs.httpx().calls)

    def test_trigger_dashboard_screenshot_path(self):
        pdf.trigger_dashboard_screenshot(_Client(), 5)
        self.assertTrue(
            self._got('POST', '/api/v1/dashboard/5/cache_dashboard_screenshot/'),
            'trailing-slash POST path')

    def test_get_dashboard_screenshot_bytes(self):
        c = _Client()
        c.bytes_map['/api/v1/dashboard/5/screenshot/abc/'] = b'\x89PNGx'
        b = pdf.get_dashboard_screenshot(c, 5, 'abc')
        self.assertEqual(b, b'\x89PNGx')
        self.assertIn('/api/v1/dashboard/5/screenshot/abc/', c.bytes_calls)

    def test_trigger_chart_screenshot_path(self):
        pdf.trigger_chart_screenshot(_Client(), 7)
        self.assertTrue(self._got('GET', '/api/v1/chart/7/cache_screenshot/'))

    def test_get_chart_screenshot_bytes(self):
        c = _Client()
        c.bytes_map['/api/v1/chart/7/screenshot/d/'] = b'\x89PNGc'
        self.assertEqual(pdf.get_chart_screenshot(c, 7, 'd'), b'\x89PNGc')

    def test_screenshot_to_pdf_best_effort_none(self):
        # reportlab not installed in the test env (or invalid image) -> None
        self.assertIsNone(pdf.screenshot_to_pdf(b''))
        self.assertIsNone(pdf.screenshot_to_pdf(b'not-an-image'))

    def test_export_dashboard_pdf_png_fallback_with_gap_note(self):
        c = _Client()
        c.bytes_map['/api/v1/dashboard/5/screenshot/abc/'] = b'\x89PNGx'
        out_dir = tempfile.mkdtemp()
        r = pdf.export_dashboard_pdf(c, 5, 'abc', out_dir=out_dir)
        self.assertEqual(r['format'], 'png')
        self.assertFalse(r['pdf_available'])
        self.assertTrue(r['path'].endswith('dashboard_5.png'))
        self.assertTrue(os.path.exists(r['path']))
        self.assertIn('Best-effort', r['gap_note'])
        self.assertIn('QuickSight', r['gap_note'])

    def test_pdf_tools_present(self):
        names = [t.name for t in pdf.PdfReportTools]
        self.assertIn('TriggerDashboardScreenshot', names)
        self.assertIn('TriggerChartScreenshot', names)
        self.assertIn('ExportDashboardPdf', names)

    def test_trigger_dashboard_screenshot_tool(self):
        tool = [t for t in pdf.PdfReportTools
                if t.name == 'TriggerDashboardScreenshot'][0]
        tool.func(5)
        self.assertTrue(
            self._got('POST', '/api/v1/dashboard/5/cache_dashboard_screenshot/'))


if __name__ == '__main__':
    unittest.main()