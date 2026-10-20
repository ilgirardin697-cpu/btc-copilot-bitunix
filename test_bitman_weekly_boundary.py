"""Stdlib-only production-isolation and immutable-source guards."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parent
MODULES=('bitman_weekly_data','bitman_weekly_expansion','bitman_weekly_reporting')


def forbidden_dependencies(source):
    found=[]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node,ast.Import):
            found += [a.name for a in node.names if a.name=='research' or a.name.startswith('research.') or any(x in MODULES for x in a.name.split('.'))]
        elif isinstance(node,ast.ImportFrom) and ((node.module or '').split('.')[0]=='research' or any(x in MODULES for x in (node.module or '').split('.'))):
            found.append(node.module)
        elif isinstance(node,ast.alias) and any(x in MODULES for x in node.name.split('.')):
            found.append('ALIASED_WEEKLY_RESEARCH_REFERENCE')
        elif isinstance(node,ast.Constant) and isinstance(node.value,str) and any(name in node.value for name in MODULES):
            found.append('DYNAMIC_WEEKLY_RESEARCH_REFERENCE')
        elif isinstance(node,(ast.Name,ast.Attribute)) and getattr(node,'id',getattr(node,'attr','')) in MODULES:
            found.append('WEEKLY_RESEARCH_REFERENCE')
    return found


class WeeklyBoundaryTests(unittest.TestCase):
    def test_all_61_base_python_and_config_sources_immutable(self):
        baseline=json.loads((ROOT/'research/results/bitman_weekly_source_baseline.json').read_text('utf-8'))
        self.assertEqual(baseline['base'],'9c660035f912be4640f09cf6e2d4c48583c20b04')
        self.assertEqual(len(baseline['sha256']),61)
        for name,checksum in baseline['sha256'].items():
            with self.subTest(path=name):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),checksum)

    def test_every_production_module_including_new_files_has_no_research_dependency(self):
        names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','--','*.py'],cwd=ROOT).decode().splitlines()
        for name in names:
            if name.startswith('research/') or Path(name).name.startswith('test_') or 'tests' in Path(name).parts:
                continue
            with self.subTest(path=name):
                self.assertEqual(forbidden_dependencies((ROOT/name).read_text('utf-8-sig')),[])

    def test_guard_rejects_import_alias_dynamic_and_subprocess_couplings(self):
        for code in ('from research.bitman_weekly_expansion import features',
                     'import research.bitman_weekly_expansion as weekly',
                     'from . import bitman_weekly_expansion as weekly',
                     'from .bitman_weekly_expansion import features',
                     'from research import bitman_weekly_data', 'import research',
                     'importlib.import_module("research.bitman_weekly_reporting")',
                     'subprocess.run(["python","-m","research.bitman_weekly_expansion"])'):
            with self.subTest(code=code):
                self.assertTrue(forbidden_dependencies(code))

    def test_protocol_and_scope_never_allow_runtime_or_live_execution(self):
        for name in MODULES:
            path=ROOT/'research'/(name+'.py')
            if not path.exists():
                continue
            tree=ast.parse(path.read_text('utf-8'))
            imports=[]
            for node in ast.walk(tree):
                if isinstance(node,ast.Import): imports += [a.name for a in node.names]
                elif isinstance(node,ast.ImportFrom): imports.append(node.module or '')
            self.assertFalse(any(any(x in name for x in ('guardian','bitunix','telegram','live_auto','mlrsi')) for name in imports))
        self.assertIn('protocol fixed before outcome analysis',(ROOT/'research/results/BITMAN_WEEKLY_EXPANSION_PROTOCOL.md').read_text('utf-8'))


if __name__=='__main__':
    unittest.main()
