"""Explicit offline CLI. Freeze rules before run; no automatic runtime consumer."""
import argparse,csv,hashlib,json,platform,subprocess
from collections import Counter
from pathlib import Path
import numpy as np
from . import data,models,simulation,statistics,report
HERE=Path(__file__).parent
OUT=HERE/'artifacts'
BOUND=('__init__.py','specification.md','source_audit.json','requirements.txt','data.py','models.py',
       'simulation.py','statistics.py','report.py','study.py')
PREDECLARED='5ccea82'
PRIMARY=report.PRIMARY
def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
def source_hashes():
    return {p:file_hash(HERE/p) for p in BOUND}
def production_hashes():
    paths=subprocess.check_output(['git','ls-files','*.py'],text=True).splitlines()
    return {p:file_hash(p) for p in paths if not (p.startswith(('research/','tests/','test_')) or '/test_' in p)}
def freeze(cache):
    lock=HERE/'protocol_lock.json'
    if lock.exists():raise ValueError('LOCK_ALREADY_EXISTS_NO_SILENT_REFREEZE')
    _,_,_,manifest=data.load(cache)
    payload=dict(protocol='KILL_ZONES_RESEARCH_V0',predeclared_commit=PREDECLARED,base='9d40020d539033cefb8f01734db8c6a6fdbba2e3',
                 source_hashes=source_hashes(),production_hashes=production_hashes(),
                 dataset={k:manifest[k] for k in ('bars_sha256','hourly_sha256','funding_sha256')},
                 environment=dict(python=platform.python_version(),numpy=np.__version__))
    payload['lock_hash']=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    lock.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(dict(protocol=payload['protocol'],lock_hash=payload['lock_hash'],rules_frozen_before_outcomes=True)))
def verify(manifest=None):
    payload=json.loads((HERE/'protocol_lock.json').read_text(encoding='utf-8'))
    expected=payload.pop('lock_hash')
    assert expected==hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'LOCK_HASH'
    assert payload['source_hashes']==source_hashes(),'RESEARCH_SOURCE_CHANGED'
    assert payload['production_hashes']==production_hashes(),'PRODUCTION_CHANGED'
    if manifest:
        assert payload['dataset']=={k:manifest[k] for k in payload['dataset']},'DATASET_CHANGED'
    return expected
def subset(trades,model,split):
    return [t for t in trades if t['model']==model and t['split']==split]
def run(cache):
    base,hourly,funding,manifest=data.load(cache);lock_hash=verify(manifest)
    signals,reject=models.candidates(hourly);context=models.context(hourly)
    trades,rejected,portfolios=simulation.replay(signals,base,funding)
    stress,sreject,sp=simulation.replay(signals,base,funding,slip=simulation.STRESS_SLIPPAGE)
    model_names=[f'{clock}_{geo}_TP{round(fr*100)}' for clock in models.CLOCKS for geo in models.GEOMETRIES for fr in models.FRACTIONS]
    result=dict(protocol='KILL_ZONES_RESEARCH_V0',lock_hash=lock_hash,predeclared_commit=PREDECLARED,data=manifest,
        source_audit=json.loads((HERE/'source_audit.json').read_text()),cells={},ablations={},session_rejections=reject,
        no_virgin_holdout=True,provenance='HISTORICAL_PUBLIC_DATA_NOT_REAL_FORWARD_OBSERVED',
        rejections=dict(Counter(r['reason'] for r in rejected)),stress_rejections=dict(Counter(r['reason'] for r in sreject)))
    for name in model_names:
        cell=dict(metrics={},stress={},stability={})
        for split in simulation.SPLITS:
            ts=subset(trades,name,split);ss=subset(stress,name,split)
            cell['metrics'][split]=statistics.metrics(ts,split,portfolios.get(name+'|'+split))
            cell['stress'][split]=statistics.metrics(ss,split,sp.get(name+'|'+split),False)
        ev=subset(trades,name,'EVALUATION')
        for year in (2024,2025,2026):
            ts=[t for t in trades if t['model']==name and t['date'].startswith(str(year))]
            cell['stability'][str(year)]=statistics.metrics(ts,'EVALUATION',with_ci=False)
        for label,chosen in (('LONG',[r for r in ev if r['side']==1]),('SHORT',[r for r in ev if r['side']==-1]),
                            ('WEEKDAY',[r for r in ev if not r['weekend']]),('WEEKEND',[r for r in ev if r['weekend']]),
                            ('2026_H1',[r for r in ev if r['date']<'2026-07-01']),('2026_H2',[r for r in ev if r['date']>='2026-07-01'])):
            cell['stability'][label]=statistics.metrics(chosen,'EVALUATION',with_ci=False)
        baseline=name.replace('EXTREME_TIMES','RANGE').replace('BOX_ENDS','RANGE')
        cell['paired']=statistics.paired(ev,subset(trades,baseline,'EVALUATION'),'EVALUATION')
        cell['line_drift_count']=sum(t['line_drift_only'] for t in ev)
        cell['classification']=statistics.classify(cell['metrics']['EVALUATION'],cell['metrics']['VALIDATION'],
            cell['stress']['EVALUATION'],cell['paired'],{k:v for k,v in cell['stability'].items() if k in ('2026_H1','2026_H2')})
        result['cells'][name]=cell
    for gate in ('ALL','AO','DMI_ADX','KONKORDE_PROXY','AO_DMI_KONKORDE'):
        filtered=[s for s in signals if s['model']==PRIMARY]
        ts,_,ps=simulation.replay(filtered,base,funding,features=context,gate_name=gate)
        result['ablations'][gate]={split:statistics.metrics(subset(ts,PRIMARY,split),split,ps.get(PRIMARY+'|'+split)) for split in simulation.SPLITS}
    selected=[result['cells'][f'NY_{g}_TP{tp}'] for g in ('EXTREME_TIMES','BOX_ENDS') for tp in (100,95)]
    if (result['cells'][PRIMARY]['classification']=='PROMISING' and all(
        c['metrics']['EVALUATION'].get('mean_net_r',-1)>0 and c['stress']['EVALUATION'].get('mean_net_r',-1)>0 for c in selected)):
        conclusion='PROMISING'
    elif all(c['classification']=='NO EDGE' for c in selected):conclusion='NO EDGE'
    else:conclusion='INCONCLUSIVE'
    result['conclusion']=conclusion
    OUT.mkdir(exist_ok=True)
    (OUT/'data_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    fields=('model','split','date','side','signal_at','entry_at','entry_price','stop','target','exit_at','exit_price',
            'reason','ambiguous','net_r','gross_r','net_bps','fees_unit','slippage_unit','funding_unit','qty','pnl','equity_after',
            'mae_r','mfe_r','duration_hours','target_hit','line_drift_only')
    with (OUT/'trades.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(trades)
    serial=lambda x:x.item() if isinstance(x,np.generic) else None
    local=Path(cache);(local/'raw_candidates.json').write_text(json.dumps(signals,default=serial),encoding='utf-8')
    (local/'rejections.json').write_text(json.dumps(rejected,default=serial),encoding='utf-8')
    report.write(OUT,result,trades,hourly,portfolios)
    i=-1;diagnostic={}
    for key,values in context.items():
        v=values[i];diagnostic[key]=str(v) if isinstance(v,str) else float(v) if np.isfinite(v) else None
    # Closed historical endpoint context is not an operational signal.
    (OUT/'last_historical_context.json').write_text(json.dumps(dict(available_at=data.iso(hourly[-1,0]+data.HOUR),
        not_a_current_signal=True,confirmed_mlrsi='UNAVAILABLE',components=diagnostic),indent=2),encoding='utf-8')
    print(json.dumps(dict(conclusion=conclusion,trades=len(trades),primary=result['cells'][PRIMARY],
                         classifications=dict(Counter(c['classification'] for c in result['cells'].values())))))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','run'));p.add_argument('--cache',required=True)
    a=p.parse_args();(freeze if a.command=='freeze' else run)(a.cache)
