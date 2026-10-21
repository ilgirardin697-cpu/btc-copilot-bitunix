"""Source-level allowlist: weekly observations cannot feed execution or gates."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

from bitman_weekly_forward.safety import ADDITIONS,normalize_source

ROOT=Path(__file__).resolve().parent
PACKAGE={'__init__','protocol','features','models','outcomes','market','journal','observer','host','worker','render','safety'}
ALLOWED={'bitman_weekly_forward/'+name+'.py' for name in PACKAGE}
TOKENS={'weekly_forward','weekly_state','weekly_event','large_move_watch'}
REQUIRE_V8='--require-v8' in sys.argv


def violations(sources):
    """Only audited passive fragments can enter existing modules; no reexports."""
    errors=[]
    for name,source in sources.items():
        if name.startswith('research/') or name in ALLOWED:
            continue
        if name.startswith('bitman_weekly_forward/'):
            errors.append((name,'UNAPPROVED_PACKAGE_SURFACE'));continue
        if name in ADDITIONS:
            try:source=normalize_source(name,source)
            except AssertionError:errors.append((name,'PASSIVE_FRAGMENT_CHANGED'));continue
        for node in ast.walk(ast.parse(source)):
            values=[]
            if isinstance(node,ast.Name):values=[node.id]
            elif isinstance(node,ast.Attribute):values=[node.attr]
            elif isinstance(node,ast.arg):values=[node.arg]
            elif isinstance(node,ast.keyword):values=[node.arg or '']
            elif isinstance(node,ast.alias):values=[node.name,node.asname or '']
            elif isinstance(node,ast.ImportFrom):values=[node.module or '']
            elif isinstance(node,(ast.FunctionDef,ast.ClassDef,ast.AsyncFunctionDef)):values=[node.name]
            elif isinstance(node,ast.Constant) and isinstance(node.value,str):values=[node.value]
            words=[w for value in values for w in re.split(r'[^a-zA-Z0-9_]+',value)]
            if any(w in TOKENS or 'bitman_weekly_forward' in w or w.startswith(('REACCELERATION','ZERO_CROSS')) for w in words):
                errors.append((name,'WEEKLY_OUTSIDE_PASSIVE_BOUNDARY'))
    return errors


class WeeklyBoundary(unittest.TestCase):
    def test_all_runtime_sources_including_new_helpers(self):
        files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','--','*.py'],cwd=ROOT).decode().splitlines()
        sources={name:(ROOT/name).read_text('utf-8-sig') for name in files
                 if not Path(name).name.startswith('test_') and 'tests' not in Path(name).parts}
        self.assertEqual(violations(sources),[])

    def test_guard_rejects_all_execution_and_gate_consumers(self):
        paths=('trade_guardian.py','guardian_bitunix.py','guardian_risk.py','live_auto.py','main.py',
               'bitman_manual/readiness.py','v8_executor.py','v8_bitunix.py','trend_v8.py','v8_notifications.py',
               'new_module/position_manager.py','new_module/stop_loss.py','new_module/take_profit.py')
        attempts=('from bitman_weekly_forward.models import calculate_models as check',
                  'from . import weekly_forward', 'import bitman_weekly_forward as state',
                  '__import__("bitman_weekly_forward.observer")',
                  'if result["weekly_state"]: client.place_order()',
                  'if result.weekly_event: client.close_position()',
                  'if result.get("large_move_watch"): client.cancel_order()',
                  'def gate(weekly_state): pass', 'client.stop_loss(weekly_event=True)',
                  'if state == "REACCELERATION_UP": change_sl()',
                  'if state == "ZERO_CROSS_DOWN_EXPANSION": change_tp()')
        for path in paths:
            for attempt in attempts:
                with self.subTest(path=path,attempt=attempt):self.assertTrue(violations({path:attempt}))

    def test_indirect_reexports_and_new_package_helpers_rejected(self):
        for path in ('new_module/helper.py','bitman_weekly_forward/order_adapter.py'):
            self.assertTrue(violations({path:'from bitman_weekly_forward import models as decision'}))
        self.assertTrue(violations({'bitman_weekly_forward/order_adapter.py':'from .models import calculate_models as decision'}))
        self.assertTrue(violations({'new_module/helper.py':'if event.startswith("REACCELERATION"): send_order()'}))

    def test_exact_old_source_baselines_preserved_after_passive_removal(self):
        baseline=json.loads((ROOT/'tests/fixtures/weekly_forward_base.json').read_text())
        for name,expected in baseline['sha256'].items():
            text=(ROOT/name).read_text('utf-8')
            if name in ADDITIONS:text=normalize_source(name,text)
            self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),expected,name)

    def test_guardian_hook_is_after_completed_cycle_never_in_cycle(self):
        tree=ast.parse((ROOT/'trade_guardian.py').read_text('utf-8'))
        guardian=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Guardian')
        self.assertFalse(any(isinstance(n,ast.ImportFrom) and 'weekly' in (n.module or '') for n in ast.walk(guardian)))
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        loop=next(n for n in ast.walk(main) if isinstance(n,ast.While))
        self.assertIsInstance(loop.body[1],ast.Expr)
        self.assertEqual(ast.unparse(loop.body[1]),'guardian.cycle()')
        self.assertIn('after_cycle()',ast.unparse(loop.body[2]))
        self.assertIsInstance(loop.body[2],ast.Try)

    def test_normalization_rejects_changed_passive_work_and_retains_protection_edits(self):
        text=(ROOT/'trade_guardian.py').read_text('utf-8')
        with self.assertRaises(AssertionError):
            normalize_source('trade_guardian.py',text.replace('after_cycle()','after_cycle(client)'))
        original=normalize_source('trade_guardian.py',text)
        edited=normalize_source('trade_guardian.py',text.replace('guardian.cycle()','guardian.cycle(unsafe=True)'))
        self.assertNotEqual(original,edited)

    def test_observer_has_no_research_trading_telegram_or_gate_imports(self):
        prohibited=('research','guardian','mlrsi','live_auto','main','v8','ccxt','requests','telegram')
        for file in (ROOT/'bitman_weekly_forward').glob('*.py'):
            if file.name=='safety.py':continue
            tree=ast.parse(file.read_text('utf-8'))
            for node in ast.walk(tree):
                if isinstance(node,(ast.Import,ast.ImportFrom)):
                    names=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or '']
                    for name in names:self.assertFalse(any(name.lower().startswith(p) for p in prohibited),(file.name,name))
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                    self.assertNotIn(node.func.attr,('place_order','create_order','cancel_order','close_position','send_message','post'))
        imports=ast.parse((ROOT/'bitman_weekly_forward/__init__.py').read_text()).body
        self.assertFalse(any(isinstance(n,(ast.Import,ast.ImportFrom)) for n in imports))

    def test_frozen_engine_and_protected_sources_match_production(self):
        baseline='9c660035f912be4640f09cf6e2d4c48583c20b04'
        frozen=json.loads((ROOT/'tests/fixtures/weekly_forward_base.json').read_text())
        self.assertEqual(frozen['base'],baseline)
        names={name for name in frozen['sha256'] if name.startswith('bitman_manual/frozen/')}
        actual={path.relative_to(ROOT).as_posix() for path in (ROOT/'bitman_manual/frozen').iterdir() if path.is_file()}
        self.assertEqual(names,actual)
        self.assertTrue({'mlrsi_math.py','guardian_risk.py','guardian_bitunix.py','trend_v8.py'}.issubset(frozen['sha256']))
        # File hashes remain enforceable in the dependency-free shallow V8 job.
        self.test_exact_old_source_baselines_preserved_after_passive_removal()

    def test_frozen_separately_deployed_v8_has_no_weekly_dependency(self):
        baseline=json.loads((ROOT/'tests/fixtures/mlrsi_safety_baselines.json').read_text())
        ref='origin/v8-real-executor'
        result=subprocess.run(['git','rev-parse','--verify',ref],cwd=ROOT,capture_output=True,text=True)
        if result.returncode:
            if REQUIRE_V8:self.fail('Mandatory frozen V8 reference missing')
            self.skipTest('Dedicated full-history workflow requires frozen V8 ref')
        self.assertEqual(result.stdout.strip(),baseline['v8_commit'])
        sources={}
        for name,record in baseline['v8_files'].items():
            raw=subprocess.check_output(['git','show',ref+':'+name],cwd=ROOT)
            self.assertEqual(hashlib.sha256(raw).hexdigest(),record['sha256'])
            sources[name]=raw.decode()
        self.assertEqual(violations(sources),[])


if __name__=='__main__':
    if REQUIRE_V8:sys.argv.remove('--require-v8')
    unittest.main()
