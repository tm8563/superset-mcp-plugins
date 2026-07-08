"""Tests for the governance/audit tools (roadmap #16)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401

import superset_chat.app.server.governance as gov


def httpx():
    return sys.modules['httpx']


def _calls(method, substr=None):
    return [c for c in httpx().calls if c[0] == method and (substr is None or substr in c[1])]


class TestGovernance(unittest.TestCase):
    def setUp(self):
        httpx().calls.clear()
        os.environ['SUPERSET_API_KEY'] = 'sst-x'
        os.environ['SUPERSET_API_URL'] = 'http://localhost:8088'

    def test_list_rls(self):
        gov.list_rls(gov.SupersetRestClient())
        self.assertTrue(_calls('GET', '/api/v1/rowlevelsecurity/'))

    def test_get_rls(self):
        gov.get_rls(gov.SupersetRestClient(), 3)
        self.assertTrue(_calls('GET', '/api/v1/rowlevelsecurity/3'))

    def test_list_roles(self):
        gov.list_roles(gov.SupersetRestClient())
        self.assertTrue(_calls('GET', '/api/v1/security/roles/'))

    def test_get_role(self):
        gov.get_role(gov.SupersetRestClient(), 7)
        self.assertTrue(_calls('GET', '/api/v1/security/roles/7'))

    def test_list_tags(self):
        gov.list_tags(gov.SupersetRestClient())
        self.assertTrue(_calls('GET', '/api/v1/tag/'))

    def test_get_tagged_objects(self):
        gov.get_tagged_objects(gov.SupersetRestClient())
        self.assertTrue(_calls('GET', '/api/v1/tag/get_objects/'))

    def test_get_tagged_objects_filters(self):
        gov.get_tagged_objects(gov.SupersetRestClient(), tags='prod', types='dashboard,chart')
        gto = _calls('GET', '/api/v1/tag/get_objects/')[0]
        self.assertIn('tags=prod', gto[1])
        self.assertIn('types=dashboard,chart', gto[1])

    def test_tools_present(self):
        names = {t.name for t in gov.GovernanceTools}
        self.assertEqual(names, {'ListRLS', 'ListRoles', 'ListTags',
                                 'GetTaggedObjects'})

    def test_list_rls_tool(self):
        [t for t in gov.GovernanceTools if t.name == 'ListRLS'][0].func()
        self.assertTrue(_calls('GET', '/api/v1/rowlevelsecurity/'))


if __name__ == '__main__':
    unittest.main()