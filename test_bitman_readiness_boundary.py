"""CI-only architecture guard: technical gates belong solely to manual display.

Scan every repository Python source, including new/untracked modules, without
importing any of them. Also scan the separately pinned V8 executor sources.
This is a conservative source guard, not a sandbox for adversarial Python.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent
REQUIRE_V8 = '--require-v8' in sys.argv
DISPLAY = 'bitman_manual/render.py'
GATES = 'bitman_manual/readiness.py'
REQUIRED_EXECUTION = ('trade_guardian.py', 'guardian_bitunix.py', 'guardian_risk.py',
                      'live_auto.py', 'main.py', 'trend_v8.py')
V8_EXECUTION = ('v8_executor.py', 'v8_bitunix.py', 'trend_v8.py', 'v8_notifications.py')
RESERVED = {'readiness', 'gates_ready', 'operability_lines'}
# Only these pre-existing manual routes may request a rendered panel/fallback.
RENDER_IMPORTS = {'bitman_manual/host.py': {'render', 'unavailable'},
                  'guardian_commands.py': {'unavailable'}}


def repository_sources():
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others',
                                     '--exclude-standard', '--', '*.py'], cwd=ROOT).decode().splitlines()
    return {name: (ROOT / name).read_text('utf-8-sig') for name in names
            if not Path(name).name.startswith('test_') and 'tests' not in Path(name).parts}


def import_module(path, node):
    if not node.level:
        return node.module or ''
    package = path.split('/')[:-node.level]
    return '.'.join(package + ([node.module] if node.module else []))


def boundary_violations(sources):
    """Reject consumers everywhere, rather than relying on an execution filename list.

    Check AST identifiers, attributes, keywords and string constants, including
    aliased/relative/dynamic imports and gate-key access. Renderer imports are
    restricted to the exact pre-existing passive route surfaces.
    """
    violations = []
    for path, source in sources.items():
        if path in (DISPLAY, GATES):
            continue
        for node in ast.walk(ast.parse(source, filename=path)):
            identifiers = []
            if isinstance(node, ast.Name):
                identifiers.append(node.id)
            elif isinstance(node, ast.Attribute):
                identifiers.append(node.attr)
            elif isinstance(node, ast.arg):
                identifiers.append(node.arg)
            elif isinstance(node, ast.keyword):
                identifiers.append(node.arg or '')
            elif isinstance(node, ast.alias):
                identifiers += [node.name, node.asname or '']
            elif isinstance(node, ast.ImportFrom):
                identifiers.append(node.module or '')
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                identifiers.append(node.name)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                identifiers.append(node.value)
            if any(RESERVED.intersection(re.split(r'[^A-Za-z0-9_]+', value)) for value in identifiers):
                violations.append((path, node.lineno, 'READINESS_OUTSIDE_MANUAL_DISPLAY'))
            if isinstance(node, ast.ImportFrom):
                module = import_module(path, node)
                if module == 'bitman_manual.readiness':
                    violations.append((path, node.lineno, 'READINESS_IMPORT'))
                if module == 'bitman_manual.render':
                    allowed = RENDER_IMPORTS.get(path, set())
                    if not all(alias.name in allowed for alias in node.names):
                        violations.append((path, node.lineno, 'RENDERER_REEXPORT_OR_NEW_CONSUMER'))
                if module == 'bitman_manual' and any(a.name in ('render', '*') for a in node.names):
                    violations.append((path, node.lineno, 'RENDERER_MODULE_ACCESS'))
            if isinstance(node, ast.Import) and any(a.name == 'bitman_manual.render' for a in node.names):
                violations.append((path, node.lineno, 'RENDERER_MODULE_ACCESS'))
            if isinstance(node, ast.Constant) and node.value == 'bitman_manual.render':
                violations.append((path, node.lineno, 'DYNAMIC_RENDERER_ACCESS'))
    return sorted(set(violations))


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_every_repository_runtime_module_keeps_readiness_out_of_execution(self):
        sources = repository_sources()
        self.assertTrue(set(REQUIRED_EXECUTION).issubset(sources))
        self.assertEqual(boundary_violations(sources), [])

    def test_renderer_is_the_only_direct_readiness_consumer_and_has_only_pure_imports(self):
        tree = ast.parse((ROOT / DISPLAY).read_text('utf-8'))
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        actual = [(node.module if isinstance(node, ast.ImportFrom) else '',
                   node.level if isinstance(node, ast.ImportFrom) else 0,
                   tuple((a.name, a.asname) for a in node.names)) for node in imports]
        self.assertEqual(actual, [('datetime', 0, (('datetime', None), ('timezone', None))),
                                  ('', 0, (('math', None),)), ('readiness', 1, (('evaluate', None),))])

    def test_guard_rejects_direct_aliased_relative_and_dynamic_imports_in_all_execution_modules(self):
        imports = ('from bitman_manual.readiness import evaluate as check',
                   'import bitman_manual.readiness as technical',
                   'from bitman_manual import readiness as technical',
                   'from .readiness import evaluate', 'from . import readiness',
                   'import importlib\ncheck = importlib.import_module("bitman_manual.readiness").evaluate',
                   'check = __import__("bitman_manual." + "readiness", fromlist=["evaluate"]).evaluate')
        for path in (*REQUIRED_EXECUTION, *V8_EXECUTION):
            for source in imports:
                with self.subTest(path=path, source=source):
                    self.assertTrue(boundary_violations({path: source}))

    def test_guard_rejects_gate_consumption_even_without_a_readiness_import(self):
        uses = ('if result["gates_ready"]: client.place_order()',
                'if result.get("gates_ready"): client.close_position()',
                'if result.gates_ready: client.cancel_order()',
                'gates_ready = True', 'def open_position(gates_ready): pass',
                'client.place_order(gates_ready=True)', 'getattr(result, "gates_ready")')
        for path in (*REQUIRED_EXECUTION, *V8_EXECUTION, 'new_runtime/order_router.py'):
            for source in uses:
                with self.subTest(path=path, source=source):
                    self.assertTrue(boundary_violations({path: source}))

    def test_guard_rejects_indirect_helper_modules_and_renderer_reexports(self):
        sources = {'new_runtime/technical_helper.py': 'from bitman_manual.readiness import evaluate as check',
                   'new_runtime/executor.py': 'from .technical_helper import check\ncheck({})'}
        self.assertTrue(boundary_violations(sources))
        for source in ('from bitman_manual.render import evaluate',
                       'from bitman_manual.render import operability_lines',
                       'from bitman_manual.render import *', 'import bitman_manual.render as panel',
                       'from bitman_manual import render',
                       '__import__("bitman_manual.render", fromlist=["evaluate"])'):
            for path in (*REQUIRED_EXECUTION, 'bitman_manual/host.py', 'guardian_commands.py'):
                with self.subTest(path=path, source=source):
                    self.assertTrue(boundary_violations({path: source}))

    def test_guard_preserves_existing_passive_routes_and_unrelated_readiness_messages(self):
        self.assertEqual(boundary_violations({
            'bitman_manual/host.py': 'from .render import render, unavailable',
            'guardian_commands.py': 'from bitman_manual.render import unavailable as bitman_unavailable',
            'live_auto.py': 'class OldBot:\n    def readiness_message(self): return "ready"'}), [])

    def test_separately_pinned_v8_executor_and_order_clients_have_no_readiness_coupling(self):
        baseline = json.loads((ROOT / 'tests/fixtures/mlrsi_safety_baselines.json').read_text('utf-8'))
        ref = 'origin/v8-real-executor'
        result = subprocess.run(['git', 'rev-parse', '--verify', ref], cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            if REQUIRE_V8:
                self.fail('Required frozen V8 reference missing; fetch full history before this audit')
            self.skipTest('Shallow dependency-free checkout; dedicated CI requires frozen V8 reference')
        self.assertEqual(result.stdout.strip(), baseline['v8_commit'])
        sources = {}
        for path in V8_EXECUTION:
            data = subprocess.check_output(['git', 'show', ref + ':' + path], cwd=ROOT)
            self.assertEqual(hashlib.sha256(data).hexdigest(), baseline['v8_files'][path]['sha256'])
            sources[path] = data.decode('utf-8')
        self.assertEqual(boundary_violations(sources), [])


if __name__ == '__main__':
    if REQUIRE_V8:
        sys.argv.remove('--require-v8')
    unittest.main()
