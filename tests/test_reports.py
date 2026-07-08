"""Tests for the alerts/scheduled-report orchestration (roadmap #15)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401

import superset_chat.app.server.reports as rpt


def httpx():
    return sys.modules['httpx']


def _set_resp(method, path, data):
    httpx().responses[(method, f'http://localhost:8088{path}')] = data


def _calls(method, substr=None):
    return [c for c in httpx().calls if c[0] == method and (substr is None or substr in c[1])]


class TestReports(unittest.TestCase):
    def setUp(self):
        httpx().calls.clear()
        os.environ['SUPERSET_API_KEY'] = 'sst-x'
        os.environ['SUPERSET_API_URL'] = 'http://localhost:8088'

    def test_list(self):
        _set_resp('GET', '/api/v1/report/', {'count': 0})
        rpt.list_reports(rpt.SupersetRestClient())
        self.assertTrue(_calls('GET', '/api/v1/report/'))

    def test_get(self):
        _set_resp('GET', '/api/v1/report/5', {'result': {'id': 5}})
        rpt.get_report(rpt.SupersetRestClient(), 5)
        self.assertTrue(_calls('GET', '/api/v1/report/5'))

    def test_create(self):
        _set_resp('POST', '/api/v1/report/', {'result': {'id': 9}})
        rpt.create_report(rpt.SupersetRestClient(), {'type': 'report'})
        post = _calls('POST', '/api/v1/report/')[0]
        self.assertEqual(post[3], {'type': 'report'})

    def test_update(self):
        _set_resp('PUT', '/api/v1/report/5', {'result': {'id': 5}})
        rpt.update_report(rpt.SupersetRestClient(), 5, {'name': 'r2'})
        put = _calls('PUT', '/api/v1/report/5')[0]
        self.assertEqual(put[3], {'name': 'r2'})

    def test_delete(self):
        _set_resp('DELETE', '/api/v1/report/5', {'message': 'deleted'})
        rpt.delete_report(rpt.SupersetRestClient(), 5)
        self.assertTrue(_calls('DELETE', '/api/v1/report/5'))

    def test_subscribe(self):
        _set_resp('POST', '/api/v1/report/subscribe', {'result': {}})
        rpt.subscribe_report(rpt.SupersetRestClient(), {'type': 'alert'})
        post = _calls('POST', '/api/v1/report/subscribe')[0]
        self.assertEqual(post[3], {'type': 'alert'})

    def test_execute_on_demand(self):
        _set_resp('POST', '/api/v1/report/5/execute', {'message': 'scheduled'})
        rpt.execute_report(rpt.SupersetRestClient(), 5)
        self.assertTrue(_calls('POST', '/api/v1/report/5/execute'))

    def test_slack_channels(self):
        _set_resp('GET', '/api/v1/report/slack_channels/', {'channels': []})
        rpt.list_slack_channels(rpt.SupersetRestClient())
        self.assertTrue(_calls('GET', '/api/v1/report/slack_channels/'))

    def test_tools_present(self):
        names = {t.name for t in rpt.ReportTools}
        self.assertEqual(names, {'ListReports', 'GetReport', 'ExecuteReport',
                                 'SubscribeReport', 'CreateReport'})

    def test_create_tool_parses_json(self):
        _set_resp('POST', '/api/v1/report/', {'result': {'id': 9}})
        tool = [t for t in rpt.ReportTools if t.name == 'CreateReport'][0]
        tool.func('{"type":"report","name":"r"}')
        post = _calls('POST', '/api/v1/report/')[0]
        self.assertEqual(post[3], {'type': 'report', 'name': 'r'})


if __name__ == '__main__':
    unittest.main()