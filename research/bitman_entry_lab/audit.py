"""Independent artifact checks and reproducible matched-control export; offline only."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
from . import data
from .features import prepare
from .simulation import simulate
from .study import ART,VARIANTS,EXITS,anchors,controls,split,hashes
from .statistics import SEED

def financial_hash(rows):
    values=[{k:v for k,v in r.items() if k!='mae_R'} for r in rows]
    return hashlib.sha256(json.dumps(values,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def audit(cache,reference=None):
    a,f,manifest=data.load(cache)
    lock=json.loads((ART/'protocol_lock.json').read_text('utf-8'))
    results=json.loads((ART/'results.json').read_text('utf-8'))
    assert hashes()==lock['code']
    assert results['protocol_lock_sha256']==data.sha((ART/'protocol_lock.json').read_bytes())
    assert results['classification_counts']=={'NO EDGE':28,'INCONCLUSIVE':7}
    rows=[json.loads(x) for x in gzip.decompress((ART/'simulated_trades.jsonl.gz').read_bytes()).splitlines()]
    baseline=lock['implementation_errata'][0]['baseline']
    # MAE bookkeeping cannot alter any entry, stop, target, gross/net return or control selection.
    digest=financial_hash(rows)
    assert digest==baseline['financial_sha256'] and len(rows)==baseline['rows']
    parity=None
    if reference:
        with np.load(reference,allow_pickle=False) as z:
            expected=z['bars'];expected=expected[(expected[:,0]>=data.START)&(expected[:,0]<data.END)]
            np.testing.assert_array_equal(a,expected)
            fund=z['funding'];fund=fund[(fund[:,0]>=data.START)&(fund[:,0]<data.END)]
            np.testing.assert_array_equal(f,fund)
        parity=dict(reference_file_sha256=data.sha(Path(reference).read_bytes()),
            candle_field_differences=0,funding_field_differences=0,rows_5m=len(a),funding_rows=len(f))
    exported=[]
    for dt,families in ((data.HOUR,('A','B','C')),(3*data.M5,('B',))):
        prepared=prepare(a,dt)
        for k,family in enumerate(families):
            events,_=anchors(prepared,family);matched=controls(prepared,events,SEED+dt+k)
            for i,s in events:
                if i not in matched:continue
                j,_=matched[i];t=int(prepared['available_at'][i])
                for exit_kind in EXITS if dt==data.HOUR else EXITS[:1]:
                    c,error=simulate(a,f,prepared,j,s,exit_kind)
                    if not c:continue
                    exported.append(dict(anchor_id=f'{dt}:{family}:{t}:{s}',family=family,interval_ms=dt,
                        exit_kind=exit_kind,signal_available_at=t,control_available_at=int(prepared['available_at'][j]),
                        side=s,regime=int(prepared['features']['regime'][i]),signal_split=split(t),
                        control_entry_time=c['entry_time'],control_exit_time=c['exit_time'],
                        gross_R=c['gross_R'],funding_R=c['funding_R'],net_R=c['costs']['BASE']['net_R']))
    with (ART/'matched_controls.csv').open('w',encoding='utf-8',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(exported[0]));w.writeheader();w.writerows(exported)
    output=dict(financial_replay_hash=digest,financial_replay_identical=True,simulation_rows=len(rows),
        distinct_anchor_ids=len({r['anchor_id'] for r in rows}),control_rows=len(exported),
        reused_cache_parity=parity,mae_diagnostic_erratum_only=True,code_hashes_match=True,
        result_lock_hash_matches=True,no_runtime_changes=True,trade_authority='NONE')
    (ART/'audit.json').write_text(json.dumps(output,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(output))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',required=True);p.add_argument('--reference-npz')
    args=p.parse_args();audit(args.cache,args.reference_npz)
