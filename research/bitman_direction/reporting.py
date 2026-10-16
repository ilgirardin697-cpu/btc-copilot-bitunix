"""Unmix descriptive raw-vs-lean control aggregates; does not change any outcome.

Primary UP/DOWN forecasts and classification remain identical. A nondirectional
state must not mix raw BTC excess with signed lean excess in one statistic.
Original frozen artifacts are retained; this canonical reporting supplement is
derived exactly from their immutable row-level measurements.
"""
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
from .evaluation import paired_bootstrap
from .study import ART,write,sha


def unmixed(rows,h):
    raw=[];lean=[];raw_times=[];lean_times=[]
    for r in rows:
        own=r['outcomes'][str(h)];control=r['control_outcomes'][str(h)]['mean']
        if not own['complete'] or control is None:continue
        side=r['direction'];raw_control=side*control if side else control
        raw.append(own['raw_return']-raw_control);raw_times.append(r['timestamp'])
        if side:
            lean.append(r['paired_excess'][str(h)]);lean_times.append(r['timestamp'])
    return dict(raw_btc_excess=paired_bootstrap(raw,raw_times),signed_lean_excess=paired_bootstrap(lean,lean_times))


def build():
    rows=defaultdict(list)
    with gzip.open(ART/'episodes_and_outcomes.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            r=json.loads(line);rows[(r['stream'],r['period'],r['state'])].append(r)
    out={}
    for (stream,period,state),group in rows.items():
        out.setdefault(stream,{}).setdefault(period,{})[state]={h:unmixed(group,h) for h in group[0]['outcomes']}
    result=dict(reason='Reporting-only separation of raw BTC control excess and directional lean control excess. '
        'The original mixed matched field for states containing both0 and+/-1 lean must not be interpreted as directional evidence.',
        source_results_sha256=sha(ART/'results.json'),source_episodes_sha256=sha(ART/'episodes_and_outcomes.jsonl.gz'),
        reporting_source_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        signals_changed=False,outcomes_changed=False,primary_up_down_changed=False,classification_changed=False,canonical=out)
    write(ART/'canonical_control_reporting.json',result)
    return result


if __name__=='__main__':build()
