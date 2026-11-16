"""Explicit two-process lock probe for a separately approved EMPTY scratch root."""
import argparse,json,os,subprocess,sys
from pathlib import Path
from .ledger import Ledger

def contender(root):
    try:
        l=Ledger(root,'LOCK_PROBE_ONLY','probe');l.close();return dict(lock_acquired=True)
    except (OSError,RuntimeError):return dict(lock_acquired=False)

def probe(root,storage_scope):
    path=Path(root)
    if path.exists() and any(path.iterdir()):raise ValueError('APPROVED_EMPTY_SCRATCH_ONLY')
    first=Ledger(path,'LOCK_PROBE_ONLY','probe')
    env={k:os.environ[k] for k in ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP','PYTHONTZPATH') if k in os.environ}
    module=__name__ if __name__!='__main__' else __spec__.name
    args=[sys.executable,'-B','-m',module,'--contender',str(path)]
    try:
        r=subprocess.run(args,capture_output=True,text=True,env=env,timeout=30,check=True);blocked=not json.loads(r.stdout)['lock_acquired']
    finally:first.close()
    r=subprocess.run(args,capture_output=True,text=True,env=env,timeout=30,check=True);after=json.loads(r.stdout)['lock_acquired']
    result=dict(second_process_excluded=blocked,acquired_after_release=after,storage_scope=storage_scope,
                verified_real_volume=False,real_volume_attestation='PENDING_INDEPENDENT_INFRASTRUCTURE_REVIEW',trade_authority='NONE')
    if not blocked or not after:raise RuntimeError('FILESYSTEM_LOCK_UNSAFE')
    (path/'probe.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--contender');p.add_argument('--approved-empty-scratch');p.add_argument('--storage-scope',default='LOCAL_TEST')
    a=p.parse_args()
    if a.contender:print(json.dumps(contender(a.contender)))
    elif a.approved_empty_scratch:print(json.dumps(probe(a.approved_empty_scratch,a.storage_scope)))
    else:p.error('No default path or automatic volume access')
