"""Predeclared historical price hypothesis and separate unlevered PAPER strategy."""
from collections import Counter
from dataclasses import replace
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import random
from ..profiles import OWNER_B
from ..replay import Replay
from ..risk import paper_plan,Costs
from ..paper_review import reprice,json_default
from .data import HERE,CACHE,HOUR,MINUTE,iso,ts,spec,load_interval,verify_aggregation

DAY=24*HOUR


def costs_from_spec(s):
    return Costs(*(D(s[k]) for k in ('entry_fee_rate','exit_fee_rate','entry_slippage_rate','exit_slippage_rate')),
                 D(0),s['cost_role'])


def slice_minutes(minutes,start,end):
    if not minutes or start<minutes[0].open_time or end>minutes[-1].available_at:
        raise ValueError('OUTCOME_COVERAGE_INCOMPLETE')
    i=(start-minutes[0].open_time)//MINUTE;j=(end-minutes[0].open_time)//MINUTE
    selected=minutes[i:j]
    if start!=end and (not selected or selected[0].open_time!=start or selected[-1].available_at!=end):
        raise ValueError('OUTCOME_WINDOW_GAP')
    return selected


def build_cycles(hours,s,whole_body=True):
    start,end=ts(s['evaluation_start_inclusive']),ts(s['evaluation_end_exclusive'])
    engine=Replay(OWNER_B if whole_body else replace(OWNER_B,whole_body=False))
    cycles=[];active=None
    for b in hours:
        snap=engine.append(b,as_of=b.available_at)
        if not start<=b.open_time<end:continue
        if snap['startAsia']:
            active=dict(date=iso(b.open_time)[:10],month=iso(b.open_time)[:7],
                        cycle_open=b.open_time,expiry=b.open_time+DAY,status='PAIR_INCOMPLETE',
                        variant='OWNER_B' if whole_body else 'OWNER_B_CLOSE_ONLY_SENSITIVITY')
            cycles.append(active)
        if snap['measureNow']:
            if active is None:raise ValueError('PAIR_WITHOUT_CYCLE')
            active.update(status='NO_CONFIRMATION',levels=snap['frozen'])
        if snap['longBreak'] or snap['shortBreak']:
            if active is None or 'levels' not in active:raise ValueError('INVALID_SIGNAL_PREFIX')
            active.update(status='TECHNICAL_CONFIRMATION',signal_time=b.open_time,
                          available_at=b.available_at,side='LONG' if snap['longBreak'] else 'SHORT',
                          signal_open=b.open,signal_close=b.close,atr14=snap['atr14'],
                          _snapshot=snap,_bar=b)
    if len(cycles)!=s['expected_evaluation_cycles']:
        raise ValueError('WRONG_EVALUATION_CYCLE_COUNT')
    return cycles


def price_outcome(cycle,rows):
    d=1 if cycle['side']=='LONG' else -1
    f=cycle['levels'];close=cycle['signal_close']
    theoretical=f['newTopTarget'] if d==1 else f['newBottomTarget']
    advanced=theoretical-d*200
    stop=f['highGuideValue']-.20*cycle['atr14'] if d==1 else f['lowGuideValue']+.20*cycle['atr14']
    r=dict(theoretical_target=theoretical,advanced_tp=advanced,stop=stop,
           target_ahead=d*(theoretical-close)>0,post_confirmation_minutes=len(rows),
           theoretical_touch=None,advanced_touch=None,sl_touch=None,
           theoretical_hit_same_confirmation_candle='EXCLUDED',
           coverage='COMPLETE_TO_CYCLE_EXPIRY' if rows else 'NO_POST_CONFIRMATION_TIME')
    if not rows:return r
    for b in rows:
        hit_stop=b.low<=stop if d==1 else b.high>=stop
        hit_target=b.high>=theoretical if d==1 else b.low<=theoretical
        hit_advanced=b.high>=advanced if d==1 else b.low<=advanced
        if hit_stop and r['sl_touch'] is None:r['sl_touch']=b.open_time
        if hit_target and r['target_ahead'] and r['theoretical_touch'] is None:r['theoretical_touch']=b.open_time
        if hit_advanced and d*(advanced-close)>0 and r['advanced_touch'] is None:r['advanced_touch']=b.open_time
    a,b=r['theoretical_touch'],r['sl_touch']
    if not r['target_ahead']:r['order']='TARGET_NOT_AHEAD_AT_CONFIRMATION'
    elif a is not None and b is not None:r['order']='TARGET_FIRST' if a<b else 'SL_FIRST' if b<a else 'SAME_MINUTE_AMBIGUOUS'
    elif a is not None:r['order']='TARGET_ONLY'
    elif b is not None:r['order']='SL_ONLY_NO_TARGET'
    else:r['order']='NEITHER_BY_EXPIRY'
    if a is not None:r['time_to_target_minutes_upper']=(a+MINUTE-cycle['available_at'])/MINUTE
    hi=max(b.high for b in rows);lo=min(b.low for b in rows)
    r.update(mfe_pct=((hi-close) if d==1 else (close-lo))/close*100,
             mae_pct=((close-lo) if d==1 else (hi-close))/close*100)
    return r


def settle_trade(plan,entry,rows,capital,costs):
    """One-minute scenario, stop-first only if a minute cannot resolve ordering."""
    if not rows:raise ValueError('NO_EXECUTABLE_NEXT_BAR_REFERENCE')
    d=D(1 if plan['side']=='LONG' else -1);qty=entry['quantity_btc'];e=entry['adverse_entry_scenario']
    stop,tp=float(plan['stop']),float(plan['advanced_tp'])
    entry_fee=costs.entry_fee*e*qty;curve=[(rows[0].open_time,float(capital-entry_fee))]
    bounds=[];adverse=0.;favorable=0.;exit_ref=None;outcome=None;ambiguous=False
    for i,b in enumerate(rows):
        bad=b.low if d==1 else b.high;good=b.high if d==1 else b.low
        adverse=max(adverse,float(d*(e-D(str(bad)))));favorable=max(favorable,float(d*(D(str(good))-e)))
        bounds.append((b.available_at,float(capital-entry_fee+d*(D(str(good))-e)*qty),
                       float(capital-entry_fee+d*(D(str(bad))-e)*qty)))
        hs=b.low<=stop if d==1 else b.high>=stop
        ht=b.high>=tp if d==1 else b.low<=tp
        if hs or ht:
            ambiguous=hs and ht;outcome='SL' if hs else 'TP'
            exit_ref=D(str((min(stop,b.open) if d==1 else max(stop,b.open)) if hs else tp))
            break
        curve.append((b.available_at,float(capital-entry_fee+d*(D(str(b.close))-e)*qty)))
    else:
        b=rows[-1];i=len(rows)-1;outcome='TIME_EXIT';exit_ref=D(str(b.close))
    x=exit_ref*(1-d*costs.exit_slippage)
    gross=d*(x-e)*qty;exit_fee=costs.exit_fee*x*qty;net=gross-entry_fee-exit_fee
    gross_before_costs=d*(exit_ref-D(str(rows[0].open)))*qty
    final=capital+net;curve.append((b.available_at,float(final)))
    result=dict(outcome=outcome,exit_minute=b.open_time,exit_known_at=b.available_at,
        entry_time=rows[0].open_time,entry_reference=rows[0].open,entry_scenario=e,exit_scenario=x,
        quantity_btc=qty,capital_before=capital,capital_after=final,net_pnl=net,
        gross_after_slippage=gross,gross_before_costs=gross_before_costs,
        slippage_cost=gross_before_costs-gross,entry_fee=entry_fee,exit_fee=exit_fee,funding=D(0),
        net_R=net/(qty*entry['net_risk_per_btc']),ambiguous_same_minute=ambiguous,
        holding_minutes_upper=i+1,mfe_price_bound=favorable,mae_price_bound=adverse,
        estimated_stop_risk=entry['estimated_stop_loss'],risk_budget=entry['risk_budget'],
        realized_loss_exceeds_budget=net < -entry['risk_budget'],
        notional=entry['notional'],actual_fill='NOT_OBSERVED_SCENARIO_ONLY')
    return result,curve,bounds


def drawdown(curve):
    peak=curve[0] if curve else 0;worst=0
    for v in curve:
        peak=max(peak,v)
        if peak>0:worst=max(worst,(peak-v)/peak*100)
    return worst


def conservative_bound(curve,bounds):
    peak=curve[0][1] if curve else 0;worst=0
    # Worst intraminute order: favorable extreme before adverse extreme. Include
    # closing fees/slippage in MARK observations, so the bound covers close DD.
    events=[(t,2,v) for t,v in curve]+[(t,0,g) for t,g,b in bounds]+[(t,1,b) for t,g,b in bounds]
    for t,kind,v in sorted(events):
        if kind in (0,2):peak=max(peak,v)
        if peak>0:worst=max(worst,(peak-v)/peak*100)
    return worst


def summarize(cycles,initial,curve,adverse_bound):
    signals=[c for c in cycles if 'price' in c]
    target_eligible=[c for c in signals if c['price']['target_ahead'] and c['price']['post_confirmation_minutes']]
    trades=[c['trade'] for c in cycles if 'trade' in c]
    pnl=[float(t['net_pnl']) for t in trades];rr=[float(t['net_R']) for t in trades]
    positive=sum(v for v in pnl if v>0);negative=-sum(v for v in pnl if v<0)
    orders=Counter(c['price'].get('order','NO_POST_CONFIRMATION_TIME') for c in signals)
    reasons=Counter(reason for c in cycles for reason in c.get('reasons',[]))
    price=dict(confirmations=len(signals),target_eligible=len(target_eligible),
        target_hits=sum(c['price']['theoretical_touch'] is not None for c in target_eligible),
        no_target_by_expiry=sum(c['price']['theoretical_touch'] is None for c in target_eligible),
        target_not_ahead=sum(not c['price']['target_ahead'] for c in signals),orders=dict(orders),
        sl_before_later_target=sum(c['price'].get('order')=='SL_FIRST' for c in signals),
        time_to_target_minutes_upper=[c['price']['time_to_target_minutes_upper'] for c in target_eligible if c['price']['theoretical_touch'] is not None])
    price['target_hit_rate']=price['target_hits']/len(target_eligible) if target_eligible else None
    strategy=dict(accepted_entries=len(trades),accepted_at_close=sum(c.get('close_filter_passed',False) for c in cycles),
        net_pnl=sum(pnl),ending_realized_equity=float(initial)+sum(pnl),
        net_return_pct=sum(pnl)/float(initial)*100,mean_net_R=sum(rr)/len(rr) if rr else None,
        win_rate=sum(x>0 for x in pnl)/len(pnl) if pnl else None,
        profit_factor=positive/negative if negative else None,
        realized_max_drawdown_pct=drawdown([float(initial)]+[float(t['capital_after']) for t in trades]),
        minute_close_mtm_max_drawdown_pct=drawdown([v for _,v in curve]),
        adverse_minute_drawdown_upper_bound_pct=adverse_bound,
        ambiguous_same_minute=sum(t['ambiguous_same_minute'] for t in trades),
        losses_beyond_risk_budget=sum(t['realized_loss_exceeds_budget'] for t in trades),
        holding_minutes_upper=sum(t['holding_minutes_upper'] for t in trades),
        fees=sum(float(t['entry_fee']+t['exit_fee']) for t in trades),
        gross_before_costs=sum(float(t['gross_before_costs']) for t in trades),
        slippage_cost=sum(float(t['slippage_cost']) for t in trades),
        outcomes=dict(Counter(t['outcome'] for t in trades)),rejections=dict(reasons),
        long_entries=sum(t['side']=='LONG' for t in trades),short_entries=sum(t['side']=='SHORT' for t in trades))
    strategy['by_side']={}
    for side in ('LONG','SHORT'):
        selected=[t for t in trades if t['side']==side]
        gains=sum(float(t['net_pnl']) for t in selected if t['net_pnl']>0)
        losses=-sum(float(t['net_pnl']) for t in selected if t['net_pnl']<0)
        strategy['by_side'][side]=dict(n=len(selected),net_pnl=sum(float(t['net_pnl']) for t in selected),
            mean_net_R=sum(float(t['net_R']) for t in selected)/len(selected) if selected else None,
            win_rate=sum(t['net_pnl']>0 for t in selected)/len(selected) if selected else None,
            profit_factor=gains/losses if losses else None)
    return dict(cycles=len(cycles),no_confirmation=sum(c['status']=='NO_CONFIRMATION' for c in cycles),price=price,strategy=strategy)


def run_arm(hours,minutes,s,whole_body=True):
    cycles=build_cycles(hours,s,whole_body);costs=costs_from_spec(s)
    initial=capital=D(s['initial_simulated_capital']);curve=[(cycles[0]['cycle_open'],float(initial))]
    bounds=[]
    for c in cycles:
        c['capital_before']=capital
        curve.append((c['cycle_open'],float(capital)))
        if '_snapshot' not in c:
            curve.append((c['expiry'],float(capital)));continue
        snap=c.pop('_snapshot');bar=c.pop('_bar');start=c['available_at'];end=c['expiry']
        future=slice_minutes(minutes,start,end) if start<end else []
        c['price']=price_outcome(c,future)
        plan=paper_plan(snap,bar,capital,costs);c['close_plan']=plan;c['close_filter_passed']=plan['accepted']
        if start>=end:
            c.update(status='REJECTED_NO_ENTRY_WINDOW',reasons=['CONFIRMATION_AT_CYCLE_EXPIRY'])
        elif not plan['accepted']:
            c.update(status='REJECTED_AT_CLOSE',reasons=plan['reasons'])
        else:
            entry=reprice(plan,future[0].open,capital,costs);c['next_open_check']=entry
            if not entry['accepted']:
                c.update(status='REJECTED_AT_NEXT_OPEN',reasons=entry['reasons'])
            else:
                t,path,bad=settle_trade(plan,entry,future,capital,costs);t['side']=c['side'];c['trade']=t
                c.update(status='PAPER_SCENARIO_MATURED',reasons=[])
                # Intraminute lows/highs create a conservative bound, not observed tick-order DD.
                bounds.extend(bad);curve.extend(path);capital=t['capital_after']
        curve.append((end,float(capital)))
    summary=summarize(cycles,initial,curve,conservative_bound(curve,bounds))
    summary['strategy']['exposure_pct_upper']=summary['strategy']['holding_minutes_upper']/(len(cycles)*1440)*100
    months={}
    for month in sorted({c['month'] for c in cycles}):
        subset=[c for c in cycles if c['month']==month]
        left,right=subset[0]['cycle_open'],subset[-1]['expiry']
        mcurve=[(t,v) for t,v in curve if left<=t<=right]
        mbounds=[(t,g,v) for t,g,v in bounds if left<t<=right]
        months[month]=summarize(subset,subset[0]['capital_before'],mcurve,conservative_bound(mcurve,mbounds))
    summary['monthly']=months
    return dict(variant='OWNER_B' if whole_body else 'OWNER_B_CLOSE_ONLY_SENSITIVITY',
                summary=summary,cycles=cycles,equity_curve=curve)


def bootstrap_mean_r(cycles,s):
    rng=random.Random(s['bootstrap']['seed']);n=len(cycles);block=s['bootstrap']['circular_block_days']
    values=[]
    for _ in range(s['bootstrap']['replicates']):
        sample=[]
        while len(sample)<n:
            i=rng.randrange(n);sample.extend(cycles[(i+j)%n] for j in range(block))
        rr=[float(c['trade']['net_R']) for c in sample[:n] if 'trade' in c]
        if rr:values.append(sum(rr)/len(rr))
    values.sort()
    return [values[int((len(values)-1)*.025)],values[int((len(values)-1)*.975)]] if values else [None,None]


def classify(result,s):
    summary=result['summary']['strategy'];trades=[c for c in result['cycles'] if 'trade' in c]
    ci=bootstrap_mean_r(result['cycles'],s);summary['mean_net_R_block_ci95']=ci
    n=len(trades);netrr=[float(c['trade']['net_R']) for c in trades]
    best=sorted(netrr,reverse=True)
    summary['ex_best_one_mean_R']=sum(best[1:])/(n-1) if n>1 else None
    second=sum(float(c['trade']['net_pnl']) for c in trades if c['date']>='2026-05-01')
    positive_months=sum(m['strategy']['net_pnl']>0 for m in result['summary']['monthly'].values())
    summary.update(second_half_net_pnl=second,positive_months=positive_months)
    if n<30:label='INCONCLUSIVE'
    elif ci[1]<=0:label='NO EDGE'
    elif (ci[0]>0 and (summary['profit_factor'] or 0)>1 and second>0 and positive_months>=6
          and summary['ex_best_one_mean_R']>0):label='PROMISING FOR FORWARD VALIDATION'
    else:label='INCONCLUSIVE'
    result['classification']=label


def paired_price_comparison(a,b,s):
    if [c['date'] for c in a]!=[c['date'] for c in b]:raise ValueError('CONTROL_DATES_DIFFER')
    if any(x['levels']!=y['levels'] for x,y in zip(a,b)):raise ValueError('CONTROL_LEVELS_DIFFER')
    def rate(rows):
        valid=[c['price'] for c in rows if 'price' in c and c['price']['target_ahead'] and c['price']['post_confirmation_minutes']]
        return sum(x['theoretical_touch'] is not None for x in valid)/len(valid) if valid else None
    rng=random.Random(s['bootstrap']['seed']);n=len(a);block=s['bootstrap']['circular_block_days'];diff=[]
    for _ in range(s['bootstrap']['replicates']):
        ids=[]
        while len(ids)<n:
            i=rng.randrange(n);ids.extend((i+j)%n for j in range(block))
        ra,rb=rate([a[i] for i in ids[:n]]),rate([b[i] for i in ids[:n]])
        if ra is not None and rb is not None:diff.append((ra-rb)*100)
    diff.sort();ra,rb=rate(a),rate(b)
    return dict(sessions_and_levels_exactly_identical=True,body_target_rate=ra,close_only_target_rate=rb,
                body_minus_close_percentage_points=(ra-rb)*100,target_rate_lift=ra/rb if rb else None,
                paired_block_ci95_percentage_points=[diff[int((len(diff)-1)*.025)],diff[int((len(diff)-1)*.975)]],
                interpretation='SENSITIVITY_ONLY_NOT_PARAMETER_SELECTION_NOT_PINE_A')


def main():
    s=spec();hours,hm=load_interval('1h');minutes,mm=load_interval('1m')
    matched=verify_aggregation(hours,minutes)
    if matched!=8760:raise ValueError('WRONG_EVALUATION_DATA_COVERAGE')
    result=dict(protocol=s,protocol_sha256=hashlib.sha256((HERE/'specification.json').read_bytes()).hexdigest(),
                data=dict(h1_manifest=hm,m1_manifest=mm,h1_rows=len(hours),m1_rows=len(minutes),exact_aggregated_hours=matched),arms=[])
    for body in (True,False):
        arm=run_arm(hours,minutes,s,body);classify(arm,s);result['arms'].append(arm)
        print(json.dumps(dict(variant=arm['variant'],classification=arm['classification'],
            cycles=arm['summary']['cycles'],signals=arm['summary']['price']['confirmations'],
            entries=arm['summary']['strategy']['accepted_entries'],net_pnl=arm['summary']['strategy']['net_pnl'])),flush=True)
    result['price_control_comparison']=paired_price_comparison(result['arms'][0]['cycles'],result['arms'][1]['cycles'],s)
    CACHE.mkdir(parents=True,exist_ok=True)
    (CACHE/'evaluation.json').write_text(json.dumps(result,default=json_default,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__':main()
