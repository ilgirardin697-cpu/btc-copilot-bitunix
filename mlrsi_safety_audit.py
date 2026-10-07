"""Offline baseline audit: remove only the exact passive host/command additions.

All remaining Guardian AST, restored live_auto and frozen V8 git objects must match.
No executors are imported or started by this script.
"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

BASELINE = '9d0024a45d8e40193162a3864a876ca5ab61d1da'
HELP_LINE = '/mlrsi\n→ estado completo ML RSI 15m / 1H / 4H\n\n'


def fingerprint(tree):
    return ast.dump(tree, include_attributes=False)


def _node(source):
    return ast.parse(source).body[0]


def _remove(body, source):
    matches = [n for n in body if fingerprint(n) == fingerprint(_node(source))]
    assert len(matches) == 1, 'Passive integration differs from audited addition'
    body.remove(matches[0])


def guardian_baseline_tree(path):
    tree = ast.parse(Path(path).read_text('utf-8'))
    if path == 'trade_guardian.py':
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        _remove(main.body, 'mlrsi = None')
        block = next(n for n in main.body if isinstance(n, ast.Try))
        _remove(block.body, """try:
    from mlrsi_guardian_host import MLRSIHost
    mlrsi = MLRSIHost(send=guardian.telegram.send, logger=Telegram._diagnostic)
    mlrsi.start()
except Exception:
    Telegram._diagnostic('MLRSI_HOST_UNAVAILABLE')""")
        _remove(block.finalbody, """if mlrsi is not None:
    try:
        mlrsi.stop()
    except Exception:
        Telegram._diagnostic('MLRSI_STOP_FAILED_IGNORED')""")
        count = 0
        for n in ast.walk(main):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'TelegramCommands':
                kw = next(k for k in n.keywords if k.arg == 'mlrsi_status')
                expected = ast.parse('mlrsi.status_cache.read if mlrsi is not None else None', mode='eval').body
                assert fingerprint(kw.value) == fingerprint(expected), 'Command received broader capabilities'
                n.keywords.remove(kw)
                count += 1
        assert count == 1
    elif path == 'guardian_commands.py':
        commands = next(n for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == 'COMMANDS')
        assert commands.value.elts[-1].value == '/mlrsi'
        commands.value.elts.pop()
        help_node = next(n for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == 'HELP')
        assert help_node.value.value.count(HELP_LINE) == 1
        help_node.value.value = help_node.value.value.replace(HELP_LINE, '')
        renderer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'render_command')
        _remove(renderer.body, """if command == '/mlrsi':
    return 'ML RSI MTF Observer: OFF / no disponible\\nSHADOW ONLY\\nTRADE AUTHORITY: NONE'""")
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TelegramCommands')
        init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
        assert init.args.args[-1].arg == 'mlrsi_status' and init.args.defaults[-1].value is None
        init.args.args.pop()
        init.args.defaults.pop()
        _remove(init.body, 'self._mlrsi_status = mlrsi_status')
        _remove(cls.body, """def _read_mlrsi(self):
    try:
        view = self._mlrsi_status() if self._mlrsi_status is not None else {}
        if not isinstance(view, dict) or not isinstance(view.get('text'), str):
            raise ValueError
        return view['text'], view.get('enabled') is True
    except Exception:
        return render_command('/mlrsi', None, 0), False""")
        process = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'process')
        block = next(n for n in process.body if isinstance(n, ast.Try))
        _remove(block.body, """if command == '/mlrsi':
    return bool(self._reply(self._read_mlrsi()[0]))""")
        _remove(block.body, """if command == '/status' and self._mlrsi_status is not None:
    status = render_command(command, self._cache.read(), self._clock())
    status += '\\nML RSI MTF Observer: ' + ('ON' if self._read_mlrsi()[1] else 'OFF')
    return bool(self._reply(status))""")
    else:
        raise ValueError('UNSUPPORTED_AUDIT_MODULE')
    return tree


def verify_guardian_ast():
    for path in ('trade_guardian.py', 'guardian_commands.py'):
        base = subprocess.check_output(['git', 'show', BASELINE + ':' + path]).decode('utf-8')
        assert fingerprint(guardian_baseline_tree(path)) == fingerprint(ast.parse(base)), path + ' operational AST changed'
    return True


def verify_live_ast():
    base = subprocess.check_output(['git', 'show', BASELINE + ':live_auto.py']).decode('utf-8')
    assert Path('live_auto.py').read_text('utf-8') == base.replace('\r\n', '\n'), 'live_auto not fully restored'
    return True


def verify_protected_sources():
    manifest = json.loads(Path('tests/fixtures/mlrsi_safety_baselines.json').read_text('utf-8'))
    preset = manifest['live_observer_preset']
    assert preset['config_version'] == 'CAPTURE_LOW29_EMA4_PINE_PARITY_V4' and preset['rsi_length'] == 29
    assert set(preset['files']) == {'mlrsi_math.py', 'mlrsi_observer.py', 'mlrsi_telegram.py'}
    recovery = manifest['provider_recovery']
    assert recovery['baseline_commit'] == 'f6612014be20aca52fd35b872bc504e8f0727eb1'
    assert set(recovery['files']) == {'mlrsi_public.py', 'mlrsi_observer.py'}
    for path in ('mlrsi_math.py', 'mlrsi_pine_reference.py', 'mlrsi_telegram.py'):
        old = subprocess.check_output(['git', 'show', recovery['baseline_commit'] + ':' + path])
        assert Path(path).read_bytes().replace(b'\r\n', b'\n') == old.replace(b'\r\n', b'\n'), path + ' V4 mathematics/presentation changed'
    for group in ('main_files', 'validated_core', 'integration_files'):
        for path, record in manifest[group].items():
            # Only the three explicitly authorized passive mathematical files change.
            if group == 'validated_core' and path in preset['files']:
                record = preset['files'][path]
            if group == 'validated_core' and path == 'mlrsi_public.py':
                record = recovery['files'][path]
            current = subprocess.check_output(['git', 'hash-object', '--path=' + path, path]).decode().strip()
            assert current == record['git_blob'], path + ' differs from immutable baseline'
    historical = ast.parse(subprocess.check_output(['git', 'show', manifest['validated_core_commit'] + ':mlrsi_math.py']).decode('utf-8'))
    current = ast.parse(Path('mlrsi_math.py').read_text('utf-8'))
    event_class = lambda tree: next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ResearchEvents')
    assert fingerprint(event_class(current)) == fingerprint(event_class(historical)), 'Frozen CROSS/RESUME policies changed'
    v8ref = 'origin/v8-real-executor'
    assert subprocess.check_output(['git', 'rev-parse', v8ref]).decode().strip() == manifest['v8_commit'], 'V8 baseline ref changed'
    for path, record in manifest['v8_files'].items():
        data = subprocess.check_output(['git', 'show', v8ref + ':' + path])
        assert hashlib.sha256(data).hexdigest() == record['sha256'], path + ' V8 object changed'
        if path in ('v8_executor.py', 'v8_bitunix.py', 'v8_notifications.py'):
            assert not Path(path).exists(), 'Do not port V8 execution files into observer branch'
    return True


def verify_observer_boundary():
    forbidden = {'place_market', 'place_order', 'flash_close_position', 'change_leverage',
                 'change_margin', 'open_real', 'manage_real', 'can_enter', 'auto_enabled',
                 'fee_guard', 'reversal', 'thesis_invalidation', '_act', 'preflight', 'execute', 'reconcile'}
    modules = ('mlrsi_math.py', 'mlrsi_public.py', 'mlrsi_observer.py', 'mlrsi_telegram.py', 'mlrsi_guardian_host.py')
    for path in modules:
        tree = ast.parse(Path(path).read_text('utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in forbidden, 'Operational reference in observer'
                assert node.attr not in {'post', 'request', 'put', 'delete', 'patch'}, 'Mutating HTTP capability'
            if isinstance(node, ast.Import):
                assert all(n.name not in {'main', 'live_auto', 'guardian_bitunix', 'trade_guardian', 'guardian_commands'} for n in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module not in {'main', 'live_auto', 'guardian_bitunix', 'trade_guardian', 'guardian_commands'}
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not any(k in node.value for k in ('BITUNIX_API_', 'BITUNIX_SECRET', 'igod_live_state', '/futures/trade/', 'getUpdates'))
            if isinstance(node, ast.keyword) and node.arg == 'trade_authority':
                assert isinstance(node.value, ast.Constant) and node.value.value is False, 'Authority must be literal false'
    return True


if __name__ == '__main__':
    verify_live_ast()
    verify_guardian_ast()
    verify_protected_sources()
    verify_observer_boundary()
    print('MLRSI_SAFETY_AUDIT_OK — Guardian protection AST unchanged; V8 hashes unchanged; trade_authority=false')
