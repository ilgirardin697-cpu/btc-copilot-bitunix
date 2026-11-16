"""Offline diagnostics of frozen PR50, data provenance and delay; no trading."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from research.confluence_1h.data import load,iso
from .. import detect as frozen
from ..evaluate import clean,write_json,write_csv,intervals,HERE as PARENT
from .trace import instrument,funnel,EXPECTED_SOURCE
from .replay import read_fixture,hourly,latency,early_turns,HERE
from .inference_costs import diagnose


def run(cache,out):
    out.mkdir(parents=True,exist_ok=True)
    a,funding,manifest=load(cache);f=frozen.features(a)
    events,audit,rows=instrument(a,f)
    expected,expected_audit=frozen.detect(a,f)
    if clean(events)!=clean(expected) or audit!=expected_audit:raise ValueError('TRACE_CHANGED_FROZEN_RESULT')
    counts,potential=funnel(a,f,events,audit,rows,intervals(a))
    import csv
    old=list(csv.DictReader((PARENT/'artifacts/comparisons.csv').open(encoding='utf-8')))
    for r in counts:
        for s in ('ALL','Q75','Q90'):
            prior=next(x for x in old if x['pattern']==r['pattern'] and int(x['side'])==r['side'] and x['stage']==r['stage'] and x['stratum']==s and x['horizon']=='12')
            if r[s]!=int(prior['valid_episodes']):raise ValueError('PUBLISHED_EPISODE_COUNT_CHANGED')
    write_csv(out/'funnel.csv',counts);write_csv(out/'trace.csv.gz',rows);write_csv(out/'opportunities.csv.gz',potential)
    development,power,cost_rows,cost_summary=diagnose(a,f,funding)
    write_csv(out/'dev_variance.csv',development);write_csv(out/'power_MDE.csv',power)
    write_csv(out/'cost_rows.csv.gz',cost_rows);write_csv(out/'cost_summary.csv',cost_summary)
    november=[];delays=[];diagnostic_trace=[];sources=[];early=[]
    for venue in ('SPOT','USDM'):
        b,m=read_fixture(venue);ff=frozen.features(b);ee,aa,tt=instrument(b,ff)
        untraced,untraced_audit=frozen.detect(b,ff)
        if clean(ee)!=clean(untraced) or aa!=untraced_audit:raise ValueError('DIAGNOSTIC_TRACE_CHANGED_RESULT')
        h=hourly(venue,b,ff,ee,tt);november.extend(h);delays.extend(latency(venue,b,ff,ee))
        early.extend(early_turns(venue,b,ff))
        opens={r['i'] for r in h};diagnostic_trace.extend(dict(venue=venue,**r) for r in tt if r['i'] in opens)
        sources.append(m)
    write_csv(out/'november.csv',november);write_csv(out/'delay.csv',delays);write_csv(out/'nov_trace.csv.gz',diagnostic_trace)
    write_csv(out/'early_turns.csv',early)
    important=[r for r in november if r['available_madrid'].startswith('2026-11-15T05:00:00')]
    write_json(out/'nov15_0500.json',important)
    metadata=dict(version='IGOD_TURN_DIAGNOSTICS_PHASE1B_V1',reference_commit='a48af422f485554dd28ee8da45a3cf1aa0a01929',
                  frozen_detector_sha256=EXPECTED_SOURCE,original_protocol_sha256=hashlib.sha256((PARENT/'protocol.json').read_bytes()).hexdigest(),
                  trace_events_identical=True,published_counts_identical=True,trace_rows=len(rows),history_rows=len(a),
                  development_sigma_identical=True,primary_power_identical=True,conservative_costs_identical=True,
                  raw_market_sources_checked=len(manifest['archives']),new_history_since2019=False,
                  november_rows=len(november),november_sources=sources,delay_rows=len(delays),
                  original_conclusion='NO TESTABLE',new_strategy_variants=0,phase2_management=False,
                  original_live_emissions_available=False,no_forward_validation=True,trade_authority='NONE')
    write_json(out/'results.json',metadata)
    print(json.dumps(clean(dict(trace_rows=len(rows),funnel=counts,nov15_0500=important)),indent=2))
    return metadata


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--out',type=Path,default=HERE/'artifacts')
    args=p.parse_args();run(args.cache,args.out)
