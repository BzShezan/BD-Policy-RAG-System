"""CLI smoke tests; no Stage6 database, crawler or index access."""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import stage6_import_preflight as mod

class TestCLI(unittest.TestCase):
    def invoke(self, result):
        output = io.StringIO()
        argv = ['stage6_import_preflight.py', '--review-dir', 'review_dir', '--decisions', 'decisions.json', '--workspace', 'workspace']
        with patch.object(sys, 'argv', argv), patch.object(mod, 'review', return_value=result) as fake, redirect_stdout(output):
            status = mod.main()
        fake.assert_called_once_with('review_dir','decisions.json','workspace')
        return status, json.loads(output.getvalue())

    def test_cli_consistent_does_not_authorize_index(self):
        code, result = self.invoke({'status':'STAGE5_CONSISTENT_IMPORT_NOT_AUTHORIZED', 'index_import_authorized':False,'index_writes':0})
        self.assertEqual(code, 0)
        self.assertFalse(result['index_import_authorized'])
        self.assertEqual(result['index_writes'], 0)

    def test_cli_blocked_returns_nonzero(self):
        code, result = self.invoke({'status':'BLOCKED', 'index_import_authorized':False,'index_writes':0})
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'BLOCKED')

    def test_cli_review_exception_returns_blocked(self):
        output = io.StringIO()
        argv = ['stage6_import_preflight.py', '--review-dir', 'r', '--decisions', 'd']
        with patch.object(sys, 'argv', argv), patch.object(mod, 'review', side_effect=FileNotFoundError('test missing file')), redirect_stdout(output):
            status = mod.main()
        self.assertEqual(status, 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['index_writes'], 0)

if __name__ == '__main__':
    unittest.main()
