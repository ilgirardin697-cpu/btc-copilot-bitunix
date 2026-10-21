"""Summarize pinned PR33 evidence; never rerun or revise its backtest."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
PR33='f71947224d4afc8f97ed72b34d8fe15be2770167'
BASE='fc211d8e36c6db55185efa8309eb8f980beab2ea'
ROOT=Path(__file__).resolve().parents[2]
PACKAGE=Path(__file__).parent
ALLOWED=('features.py','simulation.py','specification.md','statistics.py','artifacts/results.json',
    'artifacts/data_manifest.json','artifacts/protocol_lock.json','artifacts/audit.json')
def pinned(name):
    if name not in ALLOWED:raise ValueError('UNAPPROVED_REFERENCE_FILE')
    return subprocess.check_output(['git','show',PR33+':research/bitman_entry_lab/'+name],cwd=ROOT)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def summary():
    source={name:sha(pinned(name)) for name in ALLOWED}
    results=json.loads(pinned('artifacts/results.json'));manifest=json.loads(pinned('artifacts/data_manifest.json'))
    if results['classification_counts']!={'NO EDGE':28,'INCONCLUSIVE':7}:raise ValueError('PR33_REFERENCE_CHANGED')
    months=32
    rows=[]
    for variant in ('AO_ONLY','AO_CONTEXT','AO_FE'):
        key='60m:A:'+variant+':STRUCTURE_2R';c=results['candidates'][key];s=c['splits']['REUSED_EVALUATION']
        n=s['n'];rate=n/months
        rows.append(dict(candidate=variant,exit='STRUCTURE_2R',selection_status='POST_HOC_FROM_PR33',
            reused_evaluation_n=n,long=s['long'],short=s['short'],calendar_months=months,per_calendar_month=rate,
            per_calendar_year=rate*12,calendar_months_for_100_at_same_rate=100/rate if rate else None,
            mean_net_R=s['mean_R'],ci95_net_R=s['ci95_R'],classification=c['classification'],
            annual_counts={y:c['annual'][y]['n'] for y in ('2024','2025','2026')},
            annual_counts_all_periods={y:c['annual'][y]['n'] for y in c['annual']},
            side_counts={side:c['side'][side]['n'] for side in ('1','-1')}))
    return dict(reference_pr=33,reference_head=PR33,base=BASE,source_sha256=source,
        original_comparisons=35,original_classifications=results['classification_counts'],
        historical_cutoff=manifest['last_close'],candidate_selection='POST_HOC_NOT_INDEPENDENT',
        calendar_rate_denominator='2024-01-01 through 2026-09-01: 32 calendar months, not active-span metric from PR33',
        new_backtest=False,new_parameter_selection=False,candidates=rows)
if __name__=='__main__':
    result=summary();out=PACKAGE/'artifacts/pr33_reference_summary.json';out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(candidates=result['candidates'],original_classifications=result['original_classifications'])))
