"""Stdlib-only research isolation, protected-source and artifact guards."""
import ast
import hashlib
import json
import re
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent
MODULES = ('bitman_state_data', 'bitman_weekly_state_machine', 'bitman_state_analysis', 'bitman_state_reporting')
BASE = '9c660035f912be4640f09cf6e2d4c48583c20b04'
PROTOCOL = '60ddd9ac1ac2c14784195e6b2ce0230dfb4103aa'


def require_history(case, commit):
    present = subprocess.run(['git', 'cat-file', '-e', commit+'^{commit}'], cwd=ROOT,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if present:
        return
    shallow = subprocess.check_output(['git', 'rev-parse', '--is-shallow-repository'], cwd=ROOT).decode().strip()
    if shallow == 'true':
        case.skipTest('Shallow checkout; dedicated research CI requires exact base and protocol commits')
    case.fail('Required audited commit missing from a full-history checkout: '+commit)


def forbidden(source):
    result = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            result += [a.name for a in node.names if a.name == 'research' or a.name.startswith('research.') or any(m in a.name.split('.') for m in MODULES)]
        elif isinstance(node, ast.ImportFrom) and ((node.module or '').split('.')[0] == 'research' or any(m in (node.module or '').split('.') for m in MODULES)):
            result.append(node.module)
        elif isinstance(node, ast.alias) and any(m in node.name.split('.') for m in MODULES):
            result.append('ALIAS')
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and any(m in node.value for m in MODULES):
            result.append('DYNAMIC')
        elif isinstance(node, (ast.Name, ast.Attribute)) and getattr(node, 'id', getattr(node, 'attr', '')) in MODULES:
            result.append('REFERENCE')
    return result


class ResearchBoundaryTests(unittest.TestCase):
    def test_all_61_protected_sources_equal_exact_production_base(self):
        manifest = json.loads((ROOT/'research/results/bitman_state_source_baseline.json').read_text('utf-8'))
        self.assertEqual(manifest['base'], '9c660035f912be4640f09cf6e2d4c48583c20b04')
        self.assertEqual(len(manifest['sha256']), 61)
        for name, checksum in manifest['sha256'].items():
            with self.subTest(path=name):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n', b'\n')).hexdigest(), checksum)

    def test_all_existing_and_new_production_modules_cannot_depend_on_research(self):
        names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '--', '*.py'], cwd=ROOT).decode().splitlines()
        for name in names:
            if name.startswith('research/') or Path(name).name.startswith('test_') or 'tests' in Path(name).parts:
                continue
            with self.subTest(path=name):
                self.assertEqual(forbidden((ROOT/name).read_text('utf-8-sig')), [])

    def test_guard_rejects_direct_relative_aliased_dynamic_and_subprocess_dependencies(self):
        for source in ('import research.bitman_weekly_state_machine as s',
                       'from research.bitman_state_analysis import analyze',
                       'from . import bitman_state_analysis as s',
                       'from .bitman_state_data import validate',
                       'importlib.import_module("research.bitman_state_reporting")',
                       'subprocess.run(["python", "-m", "research.bitman_state_analysis"])'):
            with self.subTest(source=source):
                self.assertTrue(forbidden(source))

    def test_research_imports_no_private_runtime_or_network_clients(self):
        for module in MODULES:
            path = ROOT/'research'/(module+'.py')
            tree = ast.parse(path.read_text('utf-8'))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module or '')
            self.assertFalse(any(any(x in name for x in ('guardian', 'bitunix', 'telegram', 'mlrsi', 'requests', 'urllib', 'subprocess')) for name in imports))
            if module == 'bitman_weekly_state_machine':
                self.assertIn('bitman_manual.frozen.indicators', imports)

    def test_protocol_is_earlier_separate_commit_and_scope_exact(self):
        path = 'research/results/BITMAN_WEEKLY_STATE_MACHINE_PROTOCOL.md'
        protocol = (ROOT/path).read_text('utf-8')
        self.assertIn('Protocol fixed before new episode/outcome analysis', protocol)
        self.assertIn('NO VIRGIN HOLDOUT', protocol)
        self.assertIn('EXACT BITMAN VOLATILITY PARITY: NOT PROVEN', protocol)
        self.assertIn('EXACT BITMAN OSCILLATOR PARITY: NOT PROVEN', protocol)
        require_history(self, BASE)
        require_history(self, PROTOCOL)
        commit = subprocess.check_output(['git', 'log', '--format=%H', '--', path], cwd=ROOT).decode().splitlines()[-1]
        self.assertEqual(commit, PROTOCOL)
        files = subprocess.check_output(['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', commit], cwd=ROOT).decode().splitlines()
        self.assertEqual(files, [path])

    def test_no_existing_base_files_modified(self):
        require_history(self, BASE)
        names = subprocess.check_output(['git', 'diff', '--name-status', '9c660035f912be4640f09cf6e2d4c48583c20b04'], cwd=ROOT).decode().splitlines()
        for row in names:
            status, name = row.split('\t', 1)
            self.assertEqual(status, 'A')
            self.assertTrue(name.startswith('research/') or name.startswith('test_bitman_state_') or name == '.github/workflows/bitman-state-machine-research.yml')

    def test_only_shallow_missing_history_skips_not_a_full_checkout(self):
        with patch.object(subprocess, 'run', return_value=Mock(returncode=1)):
            with patch.object(subprocess, 'check_output', return_value=b'true\n'):
                with self.assertRaises(unittest.SkipTest):
                    require_history(unittest.TestCase(), BASE)
            with patch.object(subprocess, 'check_output', return_value=b'false\n'):
                with self.assertRaises(AssertionError):
                    require_history(unittest.TestCase(), BASE)

    def test_present_history_never_skips_and_dedicated_workflow_requires_both_commits(self):
        with patch.object(subprocess, 'run', return_value=Mock(returncode=0)):
            with patch.object(subprocess, 'check_output') as unnecessary:
                require_history(unittest.TestCase(), BASE)
                unnecessary.assert_not_called()
        workflow = (ROOT/'.github/workflows/bitman-state-machine-research.yml').read_text('utf-8')
        self.assertIn('fetch-depth: 0', workflow)
        self.assertIn('git cat-file -e '+BASE+'^{commit}', workflow)
        self.assertIn('git cat-file -e '+PROTOCOL+'^{commit}', workflow)

    def test_source_audit_does_not_claim_unverified_parity_or_visual_examples(self):
        source = json.loads((ROOT/'research/results/bitman_weekly_state_machine/source_audit.json').read_text('utf-8'))
        self.assertEqual(source['new_vidiq_credits_used'], 0)
        self.assertFalse(source['independent_transcript_recovered'])
        self.assertFalse(source['independent_visual_chart_dates_verified'])
        self.assertIn('NOT ASSESSABLE', source['post_hoc_visual_consistency_check'])
        self.assertIn('NOT PROVEN', source['oscillator_parity'])
        self.assertIn('NOT PROVEN', source['volatility_parity'])

    def test_public_artifacts_integrity(self):
        directory = ROOT/'research/results/bitman_weekly_state_machine'
        manifest = json.loads((directory/'artifact_manifest.json').read_text('utf-8'))
        for name, checksum in manifest['sha256'].items():
            self.assertEqual(hashlib.sha256((directory/name).read_bytes().replace(b'\r\n', b'\n')).hexdigest(), checksum)

    def test_public_artifacts_have_no_credentials_or_private_account_fields(self):
        directory = ROOT/'research/results/bitman_weekly_state_machine'
        prohibited = re.compile(r'(?i)(?:bot_token|api_key|api_secret|chat_id|account_id|authorization|password)\s*[\"\x27]?\s*[:=]')
        telegram_token = re.compile(r'\b\d{8,12}:[A-Za-z0-9_-]{30,}\b')
        for path in directory.iterdir():
            with self.subTest(path=path.name):
                text = path.read_text('utf-8')
                self.assertIsNone(prohibited.search(text))
                self.assertIsNone(telegram_token.search(text))


if __name__ == '__main__':
    unittest.main()
