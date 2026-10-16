"""Source identity and capability audit, independent of production runtimes."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
from .config import BASE_SHA,MLRSI_SHA,V8_SHA,REJECTED_PHASE2_SHA


def audit():
    root=Path(__file__).resolve().parents[2];hashes={}
    names=subprocess.check_output(['git','ls-tree','--name-only',BASE_SHA],cwd=root,text=True).splitlines()
    for name in names:
        if name.endswith('.py') or name=='railway.json':
            before=subprocess.check_output(['git','show',BASE_SHA+':'+name],cwd=root)
            after=(root/name).read_bytes()
            if before.replace(b'\r\n',b'\n')!=after.replace(b'\r\n',b'\n'):raise ValueError('PRODUCTION_BASELINE_CHANGED')
            hashes[name]=hashlib.sha256(before).hexdigest()
    for ref,names in ((V8_SHA,('v8_executor.py','v8_bitunix.py','trend_v8.py')),
                      (MLRSI_SHA,('mlrsi_math.py','mlrsi_public.py','mlrsi_observer.py','mlrsi_guardian_host.py')),
                      (REJECTED_PHASE2_SHA,('research/bitman/artifacts/test_results.json','research/bitman/spec.py'))):
        for name in names:
            raw=subprocess.check_output(['git','show',ref+':'+name],cwd=root)
            hashes[ref[:12]+'/'+name]=hashlib.sha256(raw).hexdigest()
    forbidden=('requests','httpx','aiohttp','urllib','socket','trade_guardian','guardian_bitunix',
               'v8_executor','live_auto','main','research.bitman')
    for path in (root/'research/bitman_real').glob('*.py'):
        source=path.read_text(encoding='utf-8');tree=ast.parse(source)
        for node in ast.walk(tree):
            imports=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
            if any(n==f or n.startswith(f+'.') for n in imports for f in forbidden):raise ValueError('OPERATIONAL_OR_NETWORK_IMPORT')
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in (
                'post','getUpdates','place_order','place_market','flash_close_position','change_leverage','transfer','withdraw'):
                raise ValueError('MUTATING_OR_POLLING_CAPABILITY')
    return dict(status='PASS',shadow_only=True,trade_authority=False,network_transport=False,
        account_access=False,order_capability=False,extra_telegram_poller=False,
        protected_sha256=hashes,phase2_status='REJECT',production_configuration_changed=False,
        note='Original production files identical after normalizing checkout line endings. '
             'Pinned V8/MLRSI/Phase2 blobs fingerprinted; no edits or integration with those branches.')


if __name__=='__main__':print(json.dumps(audit(),indent=2))
