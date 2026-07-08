"""Tests for session ownership (roadmap #3) and the access decorator (#4)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401

import superset_chat.ai_superset_assistant as view


def _user():
    return sys.modules['flask_login'].current_user


def _set_user(authenticated, username='anonymous', roles=None):
    u = _user()
    u.is_authenticated = authenticated
    u.username = username
    u.roles = roles or []
    return u


class TestSessionOwnership(unittest.TestCase):
    """roadmap #3: session_id bound to current_user; cross-user reuse rejected."""
    def setUp(self):
        _set_user(False)

    def test_create_session_binds_owner(self):
        _set_user(True, 'alice')
        agent = view.AIAssistantAgent()
        sid = agent.create_session()
        self.assertEqual(agent.sessions[sid]['username'], 'alice')

    def test_owner_owns_session(self):
        _set_user(True, 'alice')
        agent = view.AIAssistantAgent()
        sid = agent.create_session()
        self.assertTrue(agent.owns_session(sid, 'alice'))
        self.assertFalse(agent.session_belongs_to_other(sid, 'alice'))

    def test_non_owner_flagged(self):
        _set_user(True, 'alice')
        agent = view.AIAssistantAgent()
        sid = agent.create_session()
        self.assertFalse(agent.owns_session(sid, 'bob'))
        self.assertTrue(agent.session_belongs_to_other(sid, 'bob'))

    def test_unknown_session_is_neither(self):
        _set_user(True, 'alice')
        agent = view.AIAssistantAgent()
        self.assertFalse(agent.owns_session('unknown-uuid', 'alice'))
        self.assertFalse(agent.session_belongs_to_other('unknown-uuid', 'alice'))

    def test_anonymous_binding(self):
        _set_user(False)
        agent = view.AIAssistantAgent()
        sid = agent.create_session()
        self.assertEqual(agent.sessions[sid]['username'], 'anonymous')


class _FakeRole:
    def __init__(self, name):
        self.name = name


class TestAIAssistantOnly(unittest.TestCase):
    """roadmap #4: auth required + optional role allowlist, fail-closed."""
    def _wrap(self):
        @view.ai_assistant_only
        def handler():
            return 'ALLOWED'
        return handler

    def _status(self, result):
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], int):
            return result[1]
        return 200

    def setUp(self):
        os.environ.pop('AI_ASSISTANT_ALLOWED_ROLES', None)

    def test_unauthenticated_401(self):
        _set_user(False)
        self.assertEqual(self._status(self._wrap()()), 401)

    def test_allowed_role_200(self):
        os.environ['AI_ASSISTANT_ALLOWED_ROLES'] = 'Admin'
        _set_user(True, 'alice', [_FakeRole('Admin')])
        self.assertEqual(self._status(self._wrap()()), 200)

    def test_non_allowed_role_403(self):
        os.environ['AI_ASSISTANT_ALLOWED_ROLES'] = 'Admin'
        _set_user(True, 'bob', [_FakeRole('Viewer')])
        self.assertEqual(self._status(self._wrap()()), 403)

    def test_one_of_multiple_roles_200(self):
        os.environ['AI_ASSISTANT_ALLOWED_ROLES'] = 'Admin, Alpha'
        _set_user(True, 'carol', [_FakeRole('Viewer'), _FakeRole('Admin')])
        self.assertEqual(self._status(self._wrap()()), 200)

    def test_no_roles_with_allowlist_403(self):
        os.environ['AI_ASSISTANT_ALLOWED_ROLES'] = 'Admin'
        _set_user(True, 'dave', [])
        self.assertEqual(self._status(self._wrap()()), 403)

    def test_unset_allowlist_any_authenticated_200(self):
        os.environ.pop('AI_ASSISTANT_ALLOWED_ROLES', None)
        _set_user(True, 'erin', [])
        self.assertEqual(self._status(self._wrap()()), 200)

    def test_blank_allowlist_deny_all_403(self):
        os.environ['AI_ASSISTANT_ALLOWED_ROLES'] = '  ,  '
        _set_user(True, 'gina', [])
        self.assertEqual(self._status(self._wrap()()), 403)

    def test_string_role_fallback_200(self):
        os.environ['AI_ASSISTANT_ALLOWED_ROLES'] = 'Admin'
        _set_user(True, 'frank', ['Admin'])
        self.assertEqual(self._status(self._wrap()()), 200)


if __name__ == '__main__':
    unittest.main()