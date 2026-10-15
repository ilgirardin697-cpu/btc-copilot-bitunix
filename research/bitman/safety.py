"""Automated safety/source-identity audit, never invoked against live stores."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
from .spec import BASE_SHA, OBSERVER_SHA
from .mlrsi import frozen_source_ok


def audit():
    root=Path(__file__).resolve().parents[2]
    protected=['trade_guardian.py','guardian_bitunix.py','guardian_risk.py','guardian_commands.py',
               'guardian_signals.py','guardian_market.py','guardian_store.py','guardian_telegram.py',
               'copilot_audit.py','early_breakout_core.py','early_breakout_shadow.py','railway.json',
               'live_auto.py','main.py','trend_v8.py','PRE_BITMAN_AUDIT.md','research/import_forward_journals.py',
               'research/pre_bitman_audit.py']
    protected=sorted(set(protected)|set(subprocess.check_output(
        ['git','diff-tree','--no-commit-id','--name-only','-r',BASE_SHA],cwd=root).decode().splitlines()))
    hashes={}
    for name in protected:
        original=subprocess.check_output(['git','show',BASE_SHA+':'+name],cwd=root)
        current=(root/name).read_bytes()
        if original.replace(b'\r\n',b'\n')!=current.replace(b'\r\n',b'\n'): raise ValueError('PROTECTED_SOURCE_CHANGED')
        hashes[name]=hashlib.sha256(original).hexdigest()
    for name in ('v8_executor.py','v8_bitunix.py','trend_v8.py'):
        original=subprocess.check_output(['git','show','724f14fdd723eabf9ebcf3dbd51b4ab271aec9e6:'+name],cwd=root)
        hashes['v8-real-executor/'+name]=hashlib.sha256(original).hexdigest()
    for name in ('mlrsi_math.py','mlrsi_public.py','mlrsi_observer.py','mlrsi_guardian_host.py'):
        original=subprocess.check_output(['git','show',OBSERVER_SHA+':'+name],cwd=root)
        hashes['mlrsi-mtf-observer/'+name]=hashlib.sha256(original).hexdigest()
        if name=='mlrsi_math.py' and (root/'research/bitman/vendor/mlrsi_math.py').read_bytes()!=original:
            raise ValueError('VENDORED_MATH_NOT_BYTE_IDENTICAL')
    for path in (root/'research/bitman').glob('*.py'):
        tree=ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node,ast.Import) and any(alias.name.split('.')[0] in (
                    'trade_guardian','guardian_bitunix','v8_executor','live_auto') for alias in node.names):
                raise ValueError('OPERATIONAL_IMPORT')
            if isinstance(node,ast.ImportFrom) and node.module and node.module.split('.')[0] in (
                    'trade_guardian','guardian_bitunix','v8_executor','live_auto'):
                raise ValueError('OPERATIONAL_IMPORT')
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in (
                    'post','place_order','place_market','flash_close_position','change_leverage','transfer','withdraw'):
                raise ValueError('MUTATING_CAPABILITY')
    frozen_source_ok()
    return dict(status='PASS',protected_sha256=hashes,frozen_ml_math=True,trade_authority=False,
                audit_base=BASE_SHA,real_orders=False,railway_changes=False,
                note='Hashes identify protected branch blobs; no operational file changed in this worktree.')


if __name__=='__main__': print(json.dumps(audit(),indent=2))
