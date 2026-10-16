"""Offline source/capability audit; no production client is instantiated."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
from research.bitman_real.safety import audit as parent_audit
from .spec import BASE_SHA


def audit():
    root=Path(__file__).resolve().parents[2];parent=parent_audit();hashes={}
    # Every file introduced/changed by PR23 remains exactly the frozen parent.
    names=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r',BASE_SHA],cwd=root,text=True).splitlines()
    for name in names:
        old=subprocess.check_output(['git','show',BASE_SHA+':'+name],cwd=root)
        new=(root/name).read_bytes()
        if old.replace(b'\r\n',b'\n')!=new.replace(b'\r\n',b'\n'):raise ValueError('PR23_CHANGED')
        hashes[name]=hashlib.sha256(old).hexdigest()
    forbidden=('requests','httpx','aiohttp','urllib','socket','main','live_auto','trade_guardian',
        'guardian_bitunix','guardian_risk','v8_executor','v8_bitunix','mlrsi_observer','mlrsi_math',
        'early_breakout_shadow','research.bitman')
    for path in (root/'research/bitman_phase4').glob('*.py'):
        tree=ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            imports=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
            if any(n==f or n.startswith(f+'.') for n in imports for f in forbidden):raise ValueError('FORBIDDEN_IMPORT')
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in (
                'post','request','getUpdates','place_order','place_market','flash_close_position',
                'change_leverage','change_margin','withdraw','transfer'):
                raise ValueError('OPERATIONAL_CAPABILITY')
    return dict(status='PASS',shadow_only=True,trade_authority=False,
        network_transport=False,private_api=False,account_access=False,order_capability=False,
        telegram_transport=False,additional_command_poller=False,
        production_source_unchanged=True,guardian_protection_unchanged=True,
        v8_unchanged=True,mlrsi_unchanged=True,early_breakout_unchanged=True,
        manual_copilot_unchanged=True,production_variables_changed=False,
        pr23_status='INCONCLUSIVE; immutable, not rejection of the complete methodology',
        pr23_sha256=hashes,parent_source_audit=parent)


if __name__=='__main__':print(json.dumps(audit(),indent=2))
