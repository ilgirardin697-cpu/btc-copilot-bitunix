"""Paper-only isolation and immutable production-source checks."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent


class IsolationTests(unittest.TestCase):
    def test_all_87_existing_protected_sources_are_unchanged(self):
        manifest = json.loads((ROOT / 'igod_paper/protected_sources.json').read_text())
        self.assertEqual(manifest['base'], 'fc211d8e36c6db55185efa8309eb8f980beab2ea')
        for name, expected in manifest['sha256_lf'].items():
            with self.subTest(path=name):
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest(), expected)

    def test_no_production_module_can_import_paper(self):
        names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '--', '*.py'], cwd=ROOT, text=True).splitlines()
        for name in names:
            if name.startswith(('test_', 'tests/', 'igod_paper/')) or not name.endswith('.py'):
                continue
            for node in ast.walk(ast.parse((ROOT / name).read_text('utf-8-sig'))):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or '').startswith('igod_paper'), name)
                if isinstance(node, ast.Import):
                    self.assertFalse(any(a.name.startswith('igod_paper') for a in node.names), name)
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertFalse(node.value.startswith('igod_paper'), name)

    def test_paper_dependency_allowlist_excludes_execution_and_messaging(self):
        allowed = {'__future__', 'argparse', 'collections', 'copy', 'csv', 'dataclasses',
                   'datetime', 'decimal', 'hashlib', 'html', 'http', 'json', 'math',
                   'os', 'pathlib', 'sys', 'threading', 'time', 'typing', 'fcntl',
                   'msvcrt', 'requests', 'numpy', 'guardian_signals', 'socket'}
        for path in (ROOT / 'igod_paper').rglob('*.py'):
            for node in ast.walk(ast.parse(path.read_text('utf-8'))):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(alias.name.split('.')[0], allowed, str(path))
                if isinstance(node, ast.ImportFrom) and not node.level:
                    self.assertIn(node.module.split('.')[0], allowed, str(path))
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        self.assertNotIn(node.func.id, ('eval', 'exec', '__import__'), str(path))
                    if isinstance(node.func, ast.Attribute):
                        self.assertNotIn(node.func.attr, ('post', 'put', 'patch', 'delete', 'place_order', 'cancel_order', 'execute'), str(path))

    def test_network_only_in_allowlisted_market_module(self):
        for path in (ROOT / 'igod_paper').rglob('*.py'):
            if path.name in ('market.py', '__main__.py'):
                continue
            text = path.read_text('utf-8')
            self.assertNotIn('requests.', text)
            self.assertNotIn('urlopen', text)

    def test_docker_image_contains_no_live_clients(self):
        source = (ROOT / 'igod_paper/Dockerfile').read_text()
        copies = [line for line in source.splitlines() if line.startswith('COPY ')]
        self.assertEqual(copies, ['COPY guardian_signals.py /app/guardian_signals.py',
                                 'COPY igod_paper /app/igod_paper'])
        self.assertNotIn('live_auto', source)
        self.assertNotIn('BITUNIX', source)

    def test_original_attachment_engine_sha256(self):
        p = ROOT / 'igod_paper/vendor/paper_engine_v0.py'
        source = json.loads((ROOT / 'igod_paper/attachment_manifest.json').read_text())
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), source['engine_sha256'])

    def test_protocol_V1_and_readiness_golden_are_untouched(self):
        # Existing suites assert the frozen V1 hash and all 900 original states.
        manifest = json.loads((ROOT / 'igod_paper/protected_sources.json').read_text())['sha256_lf']
        for name in ('bitman_weekly_forward/protocol_v1.json', 'bitman_manual/readiness.py',
                     'tests/fixtures/weekly_forward_protocol.sha256'):
            original = subprocess.check_output(['git', 'show', 'fc211d8e36c6db55185efa8309eb8f980beab2ea:' + name], cwd=ROOT)
            self.assertEqual((ROOT / name).read_bytes().replace(b'\r\n', b'\n'), original.replace(b'\r\n', b'\n'))


if __name__ == '__main__':
    unittest.main()
