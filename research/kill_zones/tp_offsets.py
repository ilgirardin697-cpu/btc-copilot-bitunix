"""Four fixed, owner-requested POST-HOC research sensitivities; no notifier."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from bitman_manual.frozen.indicators import calculate
from . import data,models,simulation,statistics
from .study import verify,file_hash,OUT
from .report import table,fmt
HERE=Path(__file__).parent
OFFSETS=(('ATR010','ATR',.10),('ATR025','ATR',.25),('BPS5','BPS',5.),('BPS10','BPS',10.))
def targets(signals,atr):
    result=[]
    for signal in signals:
        if signal['model']!='NY_EXTREME_TIMES_TP100':continue
        for name,kind,value in OFFSETS:
            raw_atr=atr[signal['signal_index']]
            if kind=='ATR' and (not np.isfinite(raw_atr) or raw_atr<=0):continue
            offset=float(raw_atr*value if kind=='ATR' else signal['signal_close']*value/10000)
            row=dict(signal,model='NY_EXTREME_TIMES_'+name,geometric_target=signal['full_target'],
                     target=signal['full_target']-signal['side']*offset,offset_kind=kind,offset_value=value,offset_price=offset)
            result.append(row)
    return sorted(result,key=lambda r:(r['entry_at'],r['model']))
def lock_payload():
    return dict(protocol='POST_HOC_REQUESTED_TP_OFFSET_SENSITIVITY_V0',base_lock=verify(),
        files={name:file_hash(HERE/name) for name in ('tp_offset_addendum_specification.md','tp_offsets.py')},
        offsets=OFFSETS,no_independent_holdout=True)
def freeze():
    p=HERE/'tp_offset_lock.json'
    if p.exists():raise ValueError('OFFSET_LOCK_ALREADY_EXISTS')
    r=lock_payload();r['hash']=hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    p.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');print(r['hash'])
def run(cache):
    locked=json.loads((HERE/'tp_offset_lock.json').read_text());expected=locked.pop('hash')
    assert expected==hashlib.sha256(json.dumps(locked,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    actual=json.loads(json.dumps(lock_payload()))
    assert actual==locked,'TP_OFFSET_PROTOCOL_CHANGED'
    base,hourly,funding,manifest=data.load(cache);verify(manifest)
    raw,_=models.candidates(hourly);atr=calculate(hourly)['atr']
    signals=targets(raw,atr)
    trades,reject,ports=simulation.replay(signals,base,funding)
    stress,sreject,sp=simulation.replay(signals,base,funding,slip=simulation.STRESS_SLIPPAGE)
    original=json.loads((OUT/'results.json').read_text())
    from csv import DictReader
    # Baseline outcomes are already frozen; do not alter or select them.
    baselines={}
    with (OUT/'trades.csv').open(encoding='utf-8') as handle:
        for row in DictReader(handle):
            if row['split']=='EVALUATION' and row['model'] in ('NY_EXTREME_TIMES_TP100','NY_RANGE_TP100'):
                baselines.setdefault(row['model'],[]).append(dict(date=row['date'],net_r=float(row['net_r'])))
    result=dict(protocol=locked['protocol'],lock_hash=expected,post_hoc=True,no_virgin_holdout=True,offsets={},
                rejection_counts={},alert_implementation='NOT IMPLEMENTED — ROBUST EDGE NOT DEMONSTRATED')
    for name,kind,value in OFFSETS:
        model='NY_EXTREME_TIMES_'+name
        cell=dict(metrics={},stress={})
        for split in simulation.SPLITS:
            ts=[t for t in trades if t['model']==model and t['split']==split]
            ss=[t for t in stress if t['model']==model and t['split']==split]
            cell['metrics'][split]=statistics.metrics(ts,split,ports.get(model+'|'+split))
            cell['stress'][split]=statistics.metrics(ss,split,sp.get(model+'|'+split),False)
        ev=[t for t in trades if t['model']==model and t['split']=='EVALUATION']
        cell['paired_vs_geometric']=statistics.paired(ev,baselines['NY_EXTREME_TIMES_TP100'],'EVALUATION')
        cell['paired_vs_range']=statistics.paired(ev,baselines['NY_RANGE_TP100'],'EVALUATION')
        e=cell['metrics']['EVALUATION']
        cell['classification']='NO EDGE' if e['n']>=30 and e['mean_net_r']<=0 and (e['profit_factor'] or 0)<=1 else 'INCONCLUSIVE'
        result['offsets'][name]=cell
    from collections import Counter
    result['rejection_counts']=dict(Counter(x['reason'] for x in reject))
    text=['# Conservative TP offsets — requested post-hoc addendum','','**POST-HOC. NO INDEPENDENT HOLDOUT.**',
      'Four offsets were fixed before their own calculations, after the original twelve-cell result was known. '
      'Original rules, data, stops, costs, splits and outputs are unchanged. All four offsets are reported; none is selected for deployment.','',
      'Only NY / EXTREME_TIMES / original full geometric target. LONG subtracts the offset, SHORT adds it. '
      'ATR14 is calculated by the unchanged frozen public formula, using only the confirmation close. '
      'Fixed offsets: 0.10 ATR, 0.25 ATR, 5 bps and 10 bps of the confirmation close. '
      'Targets already behind the actual slipped entry are rejected rather than forced.','',
      table(['Offset','Split','n','Net R mean','95% block CI','PF','TP %','Net %','DD %','Stress R','Classification'],
        [[name,split,m['n'],fmt(m['mean_net_r']),str([round(x,3) if x is not None else None for x in m['ci95']]),
          fmt(m.get('profit_factor')),fmt(100*m.get('target_hit_rate',0),1),fmt(m.get('net_return_pct'),2),fmt(m.get('mtm_drawdown_pct'),2),
          fmt(cell['stress'][split].get('mean_net_r')),cell['classification'] if split=='EVALUATION' else 'DESCRIPTIVE']
         for name,cell in result['offsets'].items() for split,m in cell['metrics'].items()]),'',
      table(['Offset','vs TP100 daily R','95% CI','vs RANGE daily R','95% CI'],
        [[name,fmt(c['paired_vs_geometric']['mean_daily_r_difference']),str(c['paired_vs_geometric']['ci95']),
          fmt(c['paired_vs_range']['mean_daily_r_difference']),str(c['paired_vs_range']['ci95'])] for name,c in result['offsets'].items()]),'',
      'Rejections: '+json.dumps(result['rejection_counts'],sort_keys=True)+'.','',
      '## Future informative alert — not implemented',
      'No robust advantage was demonstrated by the original protocol. No Telegram integration, emitter, scheduler, daily signal requirement or operational payload was added. '
      'A future independently approved protocol could describe a hypothetical side, next executable entry/zone, geometric and conservative TP, structural SL, estimated net RR, confirmation/expiry and missing conditions. '
      'Estimated RR must include both commission/slippage legs; future funding is UNKNOWN at confirmation and cannot be filled using future outcomes. '
      'LONG conservative TP is below the full target, SHORT is above. No guarantee that either is reached.','',
      '**RECOMMENDATION: DO NOT INTEGRATE. SHADOW ONLY. TRADE AUTHORITY: NONE.**']
    (OUT/'TP_OFFSET_ADDENDUM.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    (OUT/'tp_offset_results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:dict(n=v['metrics']['EVALUATION']['n'],mean_net_r=v['metrics']['EVALUATION']['mean_net_r'],
                            classification=v['classification']) for k,v in result['offsets'].items()}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','run'));p.add_argument('--cache',default='research/cache/kill_zones_public')
    a=p.parse_args();freeze() if a.command=='freeze' else run(a.cache)
