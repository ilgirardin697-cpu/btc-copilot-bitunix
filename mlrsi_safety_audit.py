"""Reproducible AST comparison against the immutable pre-observer main.

Run: python mlrsi_safety_audit.py. Does not import/start either executor.
"""
import ast
from pathlib import Path
import subprocess

BASELINE = '9d0024a45d8e40193162a3864a876ca5ab61d1da'
HELP_LINE = '/mlrsi — estado completo ML RSI 15m / 1H / 4H\n'
NEW_METHODS = {'_init_mlrsi_observer', '_start_mlrsi_observer', '_mlrsi_observer_label', '_send_mlrsi_status'}


def fingerprint(tree):
    return ast.dump(tree, include_attributes=False)


def verify_live_ast():
    base = subprocess.check_output(['git', 'show', BASELINE + ':live_auto.py']).decode('utf-8')
    current = ast.parse(Path('live_auto.py').read_text('utf-8'))
    real = next(n for n in current.body if isinstance(n, ast.ClassDef) and n.name == 'RealAuto')
    added = {n.name for n in real.body if isinstance(n, ast.FunctionDef) and n.name in NEW_METHODS}
    assert added == NEW_METHODS, 'Integration helper set differs'
    for method in real.body:
        if isinstance(method, ast.FunctionDef) and method.name in NEW_METHODS:
            for node in ast.walk(method):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'self':
                    assert node.attr in {'mlrsi_observer', 'tg'}, 'Trading capability passed to helper'
    real.body = [n for n in real.body if not isinstance(n, ast.FunctionDef) or n.name not in NEW_METHODS]
    removed_hooks = set()
    for method in real.body:
        if not isinstance(method, ast.FunctionDef):
            continue
        hook = {'__init__': '_init_mlrsi_observer', 'run': '_start_mlrsi_observer'}.get(method.name)
        if hook:
            exact = ast.parse('self.' + hook + '()').body[0]
            found = [n for n in method.body if fingerprint(n) == fingerprint(exact)]
            assert len(found) == 1, 'Hook count differs'
            method.body.remove(found[0])
            removed_hooks.add(hook)
        if method.name == 'commands':
            loop = method.body[0]
            exact = ast.parse('if cmd == "/mlrsi":\n    self._send_mlrsi_status()\n    continue').body[0]
            assert fingerprint(loop.body[0]) == fingerprint(exact), 'Command routing differs'
            loop.body.pop(0)
            modified = 0
            for node in ast.walk(method):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'send' and len(node.args) == 1:
                    expected = ast.parse('self.status() + "\\nML RSI MTF Observer: " + self._mlrsi_observer_label()', mode='eval').body
                    if fingerprint(node.args[0]) == fingerprint(expected):
                        node.args[0] = ast.parse('self.status()', mode='eval').body
                        modified += 1
            assert modified == 1, 'Status instrumentation differs'
    assert len(removed_hooks) == 2
    help_count = 0
    for node in ast.walk(current):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if HELP_LINE in node.value:
                help_count += 1
                node.value = node.value.replace(HELP_LINE, '')
            node.value = node.value.replace('V7.3.8.7', 'V7.3.8.6')
    assert help_count == 1, 'Help update differs'
    assert fingerprint(current) == fingerprint(ast.parse(base)), 'Operational AST differs from baseline'
    return True


def verify_observer_boundary():
    forbidden = {'place_market', 'place_order', 'flash_close_position', 'change_leverage',
                 'change_margin', 'open_real', 'manage_real', 'can_enter', 'auto_enabled',
                 'fee_guard', 'reversal', 'thesis_invalidation'}
    modules = ('mlrsi_math.py', 'mlrsi_public.py', 'mlrsi_observer.py', 'mlrsi_telegram.py')
    for path in modules:
        tree = ast.parse(Path(path).read_text('utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in forbidden, 'Operational reference in observer'
                assert node.attr not in {'post', 'request', 'put', 'delete', 'patch'}, 'Mutating HTTP capability'
            if isinstance(node, ast.Import):
                assert all(n.name not in {'main', 'live_auto', 'guardian_bitunix', 'trade_guardian'} for n in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module not in {'main', 'live_auto', 'guardian_bitunix', 'trade_guardian'}
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not any(k in node.value for k in ('BITUNIX_API_', 'BITUNIX_SECRET', 'igod_live_state', '/futures/trade/'))
            if isinstance(node, ast.keyword) and node.arg == 'trade_authority':
                assert isinstance(node.value, ast.Constant) and node.value.value is False, 'Authority must be literal false'
    return True


if __name__ == '__main__':
    verify_live_ast()
    verify_observer_boundary()
    print('MLRSI_SAFETY_AUDIT_OK — operational AST unchanged; trade_authority=false')
