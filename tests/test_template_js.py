"""Tests for the chat template JS (roadmap #17): syntax + no regex artifacts."""
import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stubs  # noqa: F401  (keeps test discovery consistent)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, 'superset_chat', 'templates', 'ai_assistant.html')


def _read_template():
    with open(TEMPLATE) as fh:
        return fh.read()


def _extract_js():
    src = _read_template()
    m = re.search(r'<script[^>]*>(.*)</script>', src, re.S)
    body = m.group(1)
    # Strip Jinja substitutions so node --check sees valid JS (e.g. the
    # capabilities_json injection from roadmap #24).
    body = re.sub(r'\{%.*?%\}', '', body, flags=re.S)
    body = re.sub(r'\{\{.*?\}\}', '0', body, flags=re.S)
    return body


class TestTemplateJS(unittest.TestCase):
    def test_regex_artifacts_gone(self):
        src = _read_template()
        for artifact in ('Start Running Tool', '§§§', 'startPattern',
                         'outputPattern', 'toolStarts', 'toolOutputs',
                         'RegExp', 'fullMatch', 'pairPlaceholders'):
            self.assertNotIn(artifact, src, f'regex artifact present: {artifact}')

    def test_structured_event_handlers_present(self):
        src = _read_template()
        for marker in ("case 'tool_start'", "case 'tool_end'",
                       "case 'chunk'", "case 'done'",
                       'createToolBlock', 'renderMarkdown'):
            self.assertIn(marker, src)

    def test_node_syntax_check(self):
        js = _extract_js()
        import tempfile
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
            f.write(js)
            tmp = f.name
        try:
            proc = subprocess.run(['node', '--check', tmp], capture_output=True)
            self.assertEqual(proc.returncode, 0,
                             f'JS syntax error: {proc.stderr.decode("utf-8", "replace")}')
        finally:
            os.unlink(tmp)


if __name__ == '__main__':
    unittest.main()