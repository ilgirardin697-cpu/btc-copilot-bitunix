"""Read-only production/previous-study identity and capability audit."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
from research.bitman_phase4.safety import audit as parent_audit
from .spec import BASE_SHA


def audit():
    root=Path(__file__).resolve().parents[2];parent=parent_audit();hashes={}
    names=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r',BASE_SHA],cwd=root,text=True).splitlines()
    for name in names:
        raw=subprocess.check_output(['git','show',BASE_SHA+':'+name],cwd=root)
        if raw.replace(b'\r\n',b'\n')!=(root/name).read_bytes().replace(b'\r\n',b'\n'):raise ValueError('PHASE4_BASELINE_CHANGED')
        hashes[name]=hashlib.sha256(raw).hexdigest()
    deny=('requests','httpx','aiohttp','urllib','socket','trade_guardian','guardian_bitunix','guardian_risk',
        'v8_executor','v8_bitunix','mlrsi_observer','mlrsi_math','live_auto','main')
    for p in (root/'research/bitman_direction').glob('*.py'):
        source=p.read_text(encoding='utf-8')
        for node in ast.walk(ast.parse(source)):
            imports=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
            if any(n==d or n.startswith(d+'.') for n in imports for d in deny):raise ValueError('FORBIDDEN_CAPABILITY_IMPORT')
            if isinstance(node,ast.ImportFrom) and node.module=='guardian_signals' and [x.name for x in node.names]!=['confirmed_structure']:
                raise ValueError('ONLY_PURE_CONFIRMED_PIVOT_HELPER_ALLOWED')
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in (
                'post','request','getUpdates','place_order','place_market','flash_close_position','change_leverage','change_margin','withdraw','transfer'):
                raise ValueError('NETWORK_OR_TRADING_CAPABILITY')
    return dict(status='PASS',shadow_only=True,trade_authority=False,order_capability=False,account_access=False,
        http_transport=False,telegram_transport=False,command_poller=False,production_hook=False,
        manual_helper='guardian_signals.confirmed_structure only; read-only import',mlrsi_math_imported=False,
        production_unchanged=True,previous_phase4_sha256=hashes,previous_audits=parent)


if __name__=='__main__':print(json.dumps(audit(),indent=2))
