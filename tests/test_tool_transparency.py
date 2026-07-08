"""Tests for visible tool-use transparency (roadmap #27): the collapsed
header shows a one-line human summary, not a wall of raw JSON; the raw name +
payload remain in the expandable detail. Verified by running the template's
JS in node (with window/document stubs)."""
import json
import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401

TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'superset_chat', 'templates', 'ai_assistant.html')

STUB = (
    'global.window={};global.URLSearchParams=class{get(){return null}};'
    'class FakeEl{constructor(){this.innerHTML="";this.style={};this.className="";'
    'this._c={};this.classList={add:()=>{},remove:()=>{},toggle:()=>{}}}'
    'addEventListener(){}querySelector(s){return this._c[s]=this._c[s]||new FakeEl()}'
    'appendChild(c){return c}}'
    'global.document={getElementById:()=>new FakeEl(),querySelector:()=>new FakeEl(),'
    'addEventListener:()=>{},createElement:()=>new FakeEl()};'
)


def _body():
    src = open(TEMPLATE).read()
    body = re.search(r'<script[^>]*>(.*)</script>', src, re.S).group(1)
    body = body.replace('{{ capabilities_json|safe }}', '[]')
    body = re.sub(r'\{%.*?%\}', '', body, flags=re.S)
    body = re.sub(r'\{\{.*?\}\}', '0', body, flags=re.S)
    return body


def _run_node(js):
    proc = subprocess.run(['node', '-e', js], capture_output=True)
    return proc.returncode, proc.stdout.decode(), proc.stderr.decode()


class TestToolTransparency(unittest.TestCase):
    def test_tool_summary_one_line(self):
        js = STUB + _body() + (
            'const out={'
            'listReports:toolSummary("ListReports",""),'
            'semmeta:toolSummary("SemanticLayerMetadata","5"),'
            'exportPdf:toolSummary("ExportDashboardPdf",JSON.stringify({dashboard_id:9,digest:"abc"})),'
            'unknown:toolSummary("UnknownTool","x"),'
            'anomalies:toolSummary("DetectAnomalies",JSON.stringify([1,2,3,100,1000])),'
            'getReport:toolSummary("GetReport",JSON.stringify({report_id:3}))'
            '};console.log(JSON.stringify(out));')
        rc, out, err = _run_node(js)
        self.assertEqual(rc, 0, err)
        d = json.loads(out)
        self.assertEqual(d['listReports'], 'Listing scheduled reports…')
        self.assertEqual(d['semmeta'], 'Reading dataset metadata (5)…')
        self.assertEqual(d['exportPdf'], 'Exporting a dashboard as PDF (9)…')
        self.assertEqual(d['unknown'], 'Running UnknownTool…')
        self.assertEqual(d['anomalies'], 'Detecting anomalies…')
        self.assertEqual(d['getReport'], 'Fetching report details (3)…')

    def test_header_has_summary_raw_payload_in_detail(self):
        # createToolBlock: the header contains the human summary; the raw
        # input is in the expandable .code-block-content (collapsed by CSS).
        js = STUB + _body() + (
            'const tb=createToolBlock("DetectAnomalies",'
            'JSON.stringify([1,2,3,100,1000]));'
            'const html=tb.wrap.innerHTML;'
            'const out={hasSummary:html.indexOf("Detecting anomalies")>=0,'
            'hasRawInContent:html.indexOf("1000")>=0,'
            'hasToolName:html.indexOf("DetectAnomalies")>=0};'
            'console.log(JSON.stringify(out));')
        rc, out, err = _run_node(js)
        self.assertEqual(rc, 0, err)
        d = json.loads(out)
        self.assertTrue(d['hasSummary'], 'header shows the one-line summary')
        self.assertTrue(d['hasRawInContent'], 'raw payload is in the detail')
        self.assertTrue(d['hasToolName'], 'raw tool name is in the detail')


if __name__ == '__main__':
    unittest.main()