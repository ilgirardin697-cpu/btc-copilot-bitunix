"""Declared Nov26 companion. Offline source-selected reconstruction, never a signal service."""
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import argparse,csv,gzip,hashlib,json
import numpy as np
from ..maths import Frame,fortnight,concordance,H,M,WEEK
from ..engine import Engine,Ledger
from ..paper import Paper
from ..run import START,END as OLD_END,csvwrite,dump
from ...backquant import OriginalMLRSI
from research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.forward_shadow.swing_capture.simulator import be_level,FEE,SLIP
HERE=Path(__file__).resolve().parent
CUT=1795676400000
POLICIES=('BASELINE_ATR','BBWP_TURN_EXIT','KONCORDE_CROSS_EXIT','TP1_NET_BE','TP1_STRUCTURE')

def utc(t):return datetime.fromtimestamp(t/1000,timezone.utc).isoformat()
def load(data=HERE/'d'):
    manifest=json.loads((data/'manifest.json').read_text('utf-8'));frames={}
    if (manifest['venue'],manifest['symbol'],manifest['cutoff'])!=('BINANCE_SPOT','BTCUSDT',CUT):raise ValueError('PROVENANCE')
    for name,meta in manifest['frames'].items():
        path=data/(name+'.csv.gz')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:raise ValueError('INPUT_HASH')
        with gzip.open(path,'rt') as f:raw=list(csv.reader(f))[1:]
        with gzip.open(HERE.parent/'d'/(name+'.csv.gz'),'rt') as f:old=list(csv.reader(f))[1:]
        if raw[:len(old)]!=old or len(raw)!=meta['rows']:raise ValueError('ORIGINAL_PREFIX_CHANGED')
        frames[name]=Frame(np.array(raw,float),name,CUT)
    for receipt in manifest['receipts']:
        if hashlib.sha256((data/receipt['file']).read_bytes()).hexdigest()!=receipt['sha256']:raise ValueError('RAW_BYTES_CHANGED')
    frames['2w']=Frame(fortnight(frames['1w'].a),'2w',CUT)
    return frames,manifest

def replay(frames,end=CUT):
    ledger=Ledger();engine=Engine(ledger);broker=Paper(ledger);plans={}
    for row in frames['15m'].a:
        if row[0]<START or row[0]+M>end:continue
        broker.step(row,frames['1h'].at(int(row[0]))['atr'])
        for plan in engine.consume({k:f.at(int(row[0]+M)) for k,f in frames.items()}):
            plans[plan['id']]=deepcopy(plan);broker.enqueue(plan)
    return ledger,broker,plans

def modality(frames,when,side):
    signs=[]
    for tf in ('4h','1d'):
        r=frames[tf].at(when)
        if any(r.get(k) is None for k in ('plus_di','minus_di','tsa_trend')):return 'UNKNOWN'
        d=np.sign(r['plus_di']-r['minus_di']);p=np.sign(r['close']-r['tsa_trend'])
        signs.append(int(d) if d==p else 0)
    return 'WITH_TREND' if all(x==side for x in signs) else 'COUNTER_TREND' if all(x==-side for x in signs) else 'MIXED'

def daily_rows(frames):
    out=[];memory={}
    for r in frames['1d'].records:
        if not START<=r['available_at']<=CUT:continue
        for field in ('bbwp','ao','adx','pececillos'):
            if r.get(field+'_turn'):memory[field]=dict(at=r['available_at'],turn=r[field+'_turn'])
        out.append(dict(available_at=r['available_at'],utc=utc(r['available_at']),
            **{k:r.get(k) for k in ('ao','ao_slope','adx','adx_slope','pececillos','pececillos_slope','bbwp','bbwp_slope')},
            bbwp_cooling=r.get('bbwp_slope') is not None and r['bbwp_slope']<0,
            ao_recovering=r.get('ao_slope') is not None and r['ao_slope']>0,
            adx_still_rising=r.get('adx_slope') is not None and r['adx_slope']>0,
            pececillos_recovering=r.get('pececillos_slope') is not None and r['pececillos_slope']>0,
            structure=r['structure'],memory=deepcopy(memory),
            interpretation='SEPARATE_OBSERVATIONS_NOT_AN_ENTRY_RULE'))
    return out

def weekly(frames):
    f=frames['1w'];rows=[];summary=[]
    for i,r in enumerate(f.records):
        slope=r.get('bbwp_slope')
        if slope is None:continue
        groups=['ALL','RISING' if slope>0 else 'NON_RISING']
        prev=f.records[i-1].get('bbwp_slope') if i else None
        if slope>0 and prev is not None and prev<=0:groups.append('TURN_UP')
        for n in (1,2,4):
            if i+n>=len(f.a):continue
            b=f.a[i+1:i+n+1];c=r['close']
            exc=max(b[:,2].max()/c-1,1-b[:,3].min()/c)
            for g in groups:rows.append(dict(group=g,horizon=n,at=r['available_at'],bbwp=r['bbwp'],slope=slope,
                absolute_return=abs(b[-1,4]/c-1),max_absolute_excursion=exc,
                excursion_atr=exc*c/r['atr'] if r.get('atr') else None,
                era=utc(r['available_at'])[:4],overlap='YES_DESCRIPTIVE_NOT_INDEPENDENT'))
    for g in ('ALL','RISING','NON_RISING','TURN_UP'):
        for n in (1,2,4):
            a=[r for r in rows if r['group']==g and r['horizon']==n]
            z=dict(group=g,horizon=n,n=len(a))
            for k in ('absolute_return','max_absolute_excursion','excursion_atr'):
                v=[r[k] for r in a if r[k] is not None]
                z[k+'_mean']=float(np.mean(v)) if v else None;z[k+'_median']=float(np.median(v)) if v else None
            summary.append(z)
    return rows,summary

def rsi_comparison(frame):
    # Original TradingOne source vs the operational V4 kernel on identical Spot inputs.
    # No private Bitman parity, and neither is fed into this engine's entry rules.
    from mlrsi_math import CausalSeries
    original=OriginalMLRSI(len(frame.a)-1);operational=CausalSeries();operational.configure_bootstrap(len(frame.a)-1)
    out=[];previous=[None,None]
    for row in frame.a:
        a=original.push(float(row[3]));b=operational.push(float(row[3]));when=int(row[0]+H)
        bcolor=b['color']
        if START<=when<=CUT or utc(when)[:10] in ('2026-11-05','2026-11-22'):
            out.append(dict(available_at=when,utc=utc(when),open_time=int(row[0]),close=row[4],
                original_color=a['color'],original_value=a['value'],original_transition=a['color']!=previous[0],
                operational_color=bcolor,operational_value=b['mlrsi_smoothed'],operational_transition=bcolor!=previous[1],
                original_profile='LOW27_ALMA4_SIGMA1_OFFSET0_ORIGINAL',operational_profile='LOW29_EMA4_V4',
                private_bitman_contract_and_parameters='UNKNOWN_NOT_PARITY'))
        previous=[a['color'],bcolor]
    return out

def sniper(frames,minutes):
    published=1795629840000 # 25Nov18:04UTC =19:04Madrid
    rows=[r for r in frames['1h'].records if r['available_at']>published and r['close']>59758.]
    if not rows:return dict(published=published,confirmation=None,target_touch=None)
    r=rows[0];after=[b for b in minutes if b[0]>=r['available_at'] and float(b[2])>=60900.]
    return dict(attribution='SNIPERRBW_MEMBER_NOT_BITMAN',published=published,published_utc=utc(published),threshold=59758.,
        confirmation=r['available_at'],confirmation_utc=utc(r['available_at']),confirmation_close=r['close'],
        claimed_confirmation_utc='2026-11-25T20:00:00+00:00',claimed_close=59879.23,
        target=60900.,target_touch=int(after[0][0]) if after else None,
        target_touch_interval_end=int(after[0][0]+60000) if after else None,
        target_touch_utc=utc(int(after[0][0])) if after else None,
        result='PUBLIC_PRICE_RECONSTRUCTION_NOT_PROOF_OF_TRADE',stop='UNKNOWN',entry='NOT_EXECUTED',net_pnl='NOT_ESTIMABLE')

def paired(entry,frames,policy):
    if policy not in POLICIES:raise ValueError('ONLY_DECLARED_POLICIES')
    t0=entry['available_at'];side=entry['side'];price=entry['entry'];qty=entry['qty'];left=qty
    stop=entry['stop'];target=entry['target'];peak=trough=price;tp1=False;pending=None;fills=[];updates=[]
    risk=entry['risk'];stop_kind='INITIAL_STOP';ambiguous=False;gross=fees=0.;last=None
    def fill(qty_,reference,reason,t,interval):
        nonlocal left,gross,fees
        executed=reference*(1-side*SLIP);g=side*qty_*(executed-price);fee=qty_*executed*FEE
        left-=qty_;gross+=g;fees+=fee
        fills.append(dict(at=t,window_end=t+interval,reason=reason,qty=qty_,price=executed,gross=g,fee=fee))
    for row in frames['15m'].a:
        t,o,h,l,c,_=row;t=int(t)
        if t<t0:continue
        last=int(t+M);peak=max(peak,h);trough=min(trough,l)
        stop_hit=l<=stop if side==1 else h>=stop
        target_hit=not tp1 and (h>=target if side==1 else l<=target)
        if side*(o-stop)<=0:fill(left,o,'GAP_'+stop_kind,t,0)
        elif pending:fill(left,o,pending,t,0)
        elif stop_hit:
            ambiguous=ambiguous or bool(target_hit);fill(left,stop,stop_kind,t,M)
        else:
            if target_hit:fill(min(left,qty*.5),target,'TP1',t,M);tp1=True
            if left>qty*1e-12 and t+M-t0>=24*H:fill(left,c,'TIME_EXIT_24H',t+M,0)
        if left<=qty*1e-12:break
        old=stop
        if tp1:
            be=be_level(price,side,0.)
            if policy in ('TP1_NET_BE','TP1_STRUCTURE'):
                stop=max(stop,be) if side==1 else min(stop,be);stop_kind='NET_BE_STOP'
                if policy=='TP1_STRUCTURE':
                    base=frames['15m'].at(t+M);atr=frames['1h'].at(t+M)['atr']
                    pivot=base['known_low' if side==1 else 'known_high']
                    if pivot and atr:
                        level=pivot['price']-side*.2*atr
                        new=max(stop,level) if side==1 else min(stop,level)
                        if new!=stop:stop_kind='STRUCTURE_STOP'
                        stop=new
            else:
                atr=frames['1h'].at(t)['atr']
                if atr:
                    trail=peak-1.5*atr if side==1 else trough+1.5*atr
                    stop=max(stop,be,trail) if side==1 else min(stop,be,trail)
                    if stop!=old:stop_kind='TRAIL_STOP' if side*(trail-be)>0 else 'NET_BE_STOP'
        if old!=stop:updates.append(dict(effective_at=t+M,old=old,new=stop))
        if (t+M)%H==0:
            r=frames['1h'].at(t+M)
            if policy=='BBWP_TURN_EXIT' and r['bbwp_turn']==-1:pending='BBWP_TURN_EXIT'
            if policy=='KONCORDE_CROSS_EXIT' and r['pececillos_cross_roja']==-side:pending='KONCORDE_CROSS_EXIT'
    net=gross-qty*price*FEE-fees
    marked=net+(side*left*(c-price) if last is not None else 0.)
    return dict(id=entry['trade_id'],policy=policy,side=side,entry_at=t0,entry=price,qty=qty,initial_stop=entry['stop'],
        risk=risk,completed=left<=qty*1e-12,net=net,net_R=net/risk,marked_net=marked,remaining=left,
        tp1=tp1,exit_reason=fills[-1]['reason'] if fills else None,exit_at=fills[-1]['window_end'] if fills else None,
        ambiguous=ambiguous,fills=fills,stop_updates=updates,funding='NOT_APPLICABLE_SPOT',
        shorts='SYNTHETIC_BORROW_OR_FUTURES_COSTS_NOT_MODELED',portfolio='INDEPENDENT_PAIRED_TRADES_NOT_COMPOUNDED')

def execute(out):
    if out.exists():raise ValueError('NEVER_OVERWRITE_ADDENDUM_RESULTS')
    frames,manifest=load();cross=concordance(frames)
    ledger,broker,plans=replay(frames)
    old=[r for r in ledger.rows if r['available_at']<=OLD_END]
    with gzip.open(HERE.parent/'out/ledger.gz','rt',encoding='utf-8') as f:expected=[json.loads(x) for x in f]
    if old!=expected:raise ValueError('PREVIOUS_REPLAY_CHANGED')
    Ledger.verify(ledger.rows)
    entries=[r for r in ledger.rows if r['kind']=='SIM_ENTRY']
    pairs=[]
    for entry in entries:
        for p in POLICIES:
            r=paired(entry,frames,p);r['modality']=modality(frames,entry['available_at'],entry['side']);pairs.append(r)
    for trade in broker.trades:
        r=next(r for r in pairs if r['id']==trade['id'] and r['policy']=='BASELINE_ATR')
        if not r['completed'] or abs(r['net']-trade['net'])>1e-8 or r['exit_at']!=trade['exit_at']:
            raise ValueError('BASELINE_MANAGEMENT_NOT_EQUIVALENT')
    weekrows,weeksummary=weekly(frames)
    minutes=json.loads((HERE/'d/1m.json').read_text('utf-8'))
    snippet=sniper(frames,minutes);rsi=rsi_comparison(frames['1h'])
    summary=dict(plan_sha256=hashlib.sha256((HERE/'plan.json').read_bytes()).hexdigest(),cutoff=CUT,
        old_replay_exact_prefix=True,old_ledger_records=len(expected),new_records=len(ledger.rows)-len(expected),
        events=dict(Counter(r['kind'] for r in ledger.rows)),simulation=broker.summary(),
        paired_management={p:dict(completed=sum(r['completed'] for r in pairs if r['policy']==p),
            censored=sum(not r['completed'] for r in pairs if r['policy']==p),
            net_completed=sum(r['net'] for r in pairs if r['policy']==p and r['completed'])) for p in POLICIES},
        modalities=dict(Counter(modality(frames,e['available_at'],e['side']) for e in entries)),
        weekly=weeksummary,sniper=snippet,concordance=cross,
        conclusion='SOURCE_ALIGNMENT_ONLY; ECONOMIC_EDGE_NOT_ESTABLISHED; NO_INDEPENDENT_VALIDATION',
        vidiq_calls=0,vidiq_credits=0,murphy='NOT_AVAILABLE_NOT_CITED',
        exchange_stop='NOT_VERIFIED; no private account calls; warning is not exchange protection',
        authority='NONE',production_changes=False)
    out.mkdir();dump(out/'summary.json',summary)
    for name,rows in [('daily',daily_rows(frames)),('weekly',weekrows),('weekly_summary',weeksummary),('rsi',rsi),('paired',pairs),('entries',entries)]:csvwrite(out/(name+'.csv'),rows)
    dump(out/'sniper.json',snippet);dump(out/'paired.json',pairs)
    with gzip.GzipFile(filename='',fileobj=(out/'ledger.gz').open('wb'),mode='wb',mtime=0) as f:
        for r in ledger.rows:f.write(json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n')
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=HERE/'out');args=p.parse_args()
    s=execute(args.out)
    print(json.dumps({k:s[k] for k in ('old_replay_exact_prefix','new_records','events','paired_management','sniper','conclusion')}))
