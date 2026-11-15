"""Offline cash ledger. No broker, account credentials, order placement or leverage."""
from dataclasses import dataclass
import numpy as np

from .data import HOUR,iso


@dataclass(frozen=True)
class Assumptions:
    target_r: float=2.
    atr_multiple: float=1.5
    hold_bars: int=24
    fee: float=.001
    slippage: float=.0005
    risk: float=.01
    initial: float=200.
    funding_mode: str='CONSERVATIVE_BOUND'


def simulate(bars,atr,long,short,funding,start=0,end=None,side_filter=0,p=Assumptions(),curve=True):
    a=np.asarray(bars,float);end=len(a) if end is None else min(int(end),len(a));start=int(start)
    if p.target_r<=0 or p.atr_multiple<=0 or p.hold_bars<1 or not 0<p.risk<=.01:raise ValueError('INVALID_RESEARCH_RISK')
    if not 0<=start<end or not np.isfinite(a).all():raise ValueError('INVALID_INPUT')
    candidates=np.flatnonzero((np.asarray(long,bool) if side_filter==1 else np.asarray(short,bool) if side_filter==-1 else np.asarray(long,bool)|np.asarray(short,bool)))
    candidates=candidates[(candidates>=start)&(candidates<end)]
    f=np.asarray(funding,float)
    if f.size==0:f=np.empty((0,6))
    if f.ndim!=2 or f.shape[1]!=6:raise ValueError('FUNDING_SIX_FIELDS')
    fund_by_hour={int(r[0]//HOUR*HOUR):r for r in f}
    cash=p.initial;deals=[];decisions=[];last_exit=start-1
    marked=np.full(end-start,p.initial) if curve else None
    adverse=np.full(end-start,p.initial) if curve else None
    fill_from=start
    for s in candidates:
        side=1 if long[s] else -1;entry_i=s+1
        d=dict(signal_i=int(s),side=side,signal_open=iso(a[s,0]),available_at=iso(a[s,0]+HOUR))
        if bool(long[s]) and bool(short[s]):decisions.append(dict(**d,status='REJECTED_CONFLICT'));continue
        if s<last_exit:decisions.append(dict(**d,status='OVERLAPPING_POSITION'));continue
        if entry_i+p.hold_bars>=end:decisions.append(dict(**d,status='PURGED_END_HORIZON'));continue
        if cash<=0:decisions.append(dict(**d,status='CAPITAL_EXHAUSTED'));continue
        distance=p.atr_multiple*atr[s]
        entry=a[entry_i,1]*(1+side*p.slippage);stop=entry-side*distance;target=entry+side*p.target_r*distance
        stop_fill=stop*(1-side*p.slippage)
        planned_unit_loss=side*(entry-stop_fill)+p.fee*(entry+stop_fill)
        if not np.isfinite([distance,entry,stop,target,planned_unit_loss]).all() or min(distance,entry,stop,target,planned_unit_loss)<=0:
            decisions.append(dict(**d,status='INVALID_RISK'));continue
        qty=min(cash*p.risk/planned_unit_loss,cash/(entry*(1+p.fee)))
        before=cash;entry_fee=qty*entry*p.fee;cash-=entry_fee;fund_paid=0.;low=high=entry;ambiguous=False
        missing_marks=0;funding_ambiguities=0
        if curve:
            marked[fill_from:entry_i-start]=before;adverse[fill_from:entry_i-start]=before
        for j in range(entry_i,entry_i+p.hold_bars+1):
            t=int(a[j,0]);opened=a[j,1];raw_exit=None;reason=''
            open_stop=(opened<=stop if side==1 else opened>=stop)
            open_target=(opened>=target if side==1 else opened<=target)
            if open_stop:raw_exit=opened;reason='STOP_GAP'
            elif open_target:raw_exit=target;reason='TARGET_AT_OPEN_CONSERVATIVE'
            elif j==entry_i+p.hold_bars:raw_exit=opened;reason='TIME_24H_NEXT_OPEN'
            else:
                hit_stop=(a[j,3]<=stop if side==1 else a[j,2]>=stop)
                hit_target=(a[j,2]>=target if side==1 else a[j,3]<=target)
                if hit_stop:
                    raw_exit=stop;ambiguous=bool(hit_target);reason='STOP_AMBIGUOUS_BOTH' if hit_target else 'STOP'
                elif hit_target:raw_exit=target;reason='TARGET'
                low=min(low,a[j,3]);high=max(high,a[j,2])
            if t in fund_by_hour:
                fr=fund_by_hour[t];settlement=int(fr[0])
                open_exit=raw_exit is not None and ('OPEN' in reason or reason=='STOP_GAP')
                could_owe=(settlement>int(a[entry_i,0]) and not (open_exit and settlement>t))
                if could_owe:
                    mark=fr[2]
                    if not np.isfinite(mark):
                        if p.funding_mode=='EXACT_MARK_REQUIRED':raise ValueError('EXACT_FUNDING_MARK_UNAVAILABLE')
                        missing_marks+=1
                        costly=side*fr[1]>=0
                        if p.funding_mode=='OPTIMISTIC_MARK_BOUND':costly=not costly
                        mark=fr[5] if costly else fr[4]
                    amount=side*qty*fr[1]*mark
                    uncertain=raw_exit is not None and not open_exit and settlement>t
                    if uncertain:
                        funding_ambiguities+=1
                        if amount<0:amount=0.
                    cash-=amount;fund_paid+=amount
            if curve:
                worst=min(opened,a[j,3]) if side==1 else max(opened,a[j,2])
                # Includes the whole exit candle: explicitly a conservative upper
                # bound on adverse exposure, not a claimed observed intrabar path.
                adverse[j-start]=cash+side*qty*(worst-entry)
            if raw_exit is None:
                if curve:marked[j-start]=cash+side*qty*(a[j,4]-entry)
                continue
            exit_fill=raw_exit*(1-side*p.slippage);exit_fee=qty*exit_fill*p.fee
            gross=side*qty*(exit_fill-entry);cash+=gross-exit_fee
            gross_reference=side*qty*(raw_exit-a[entry_i,1]);slip_cost=gross_reference-gross
            net=cash-before;risk_amount=qty*planned_unit_loss
            if curve:
                marked[j-start]=cash;adverse[j-start]=min(adverse[j-start],cash)
                fill_from=j-start+1
            last_exit=j
            deals.append(dict(**d,entry_i=int(entry_i),exit_i=int(j),entry_time=iso(a[entry_i,0]),
                exit_bar_open=iso(a[j,0]),exit_bar_end=iso(a[j,0]+HOUR),
                exit_timing='EXACT_MODEL_OPEN' if 'OPEN' in reason or reason=='STOP_GAP' else 'UNKNOWN_WITHIN_CLOSED_H1',
                entry_reference=float(a[entry_i,1]),entry=float(entry),exit_reference=float(raw_exit),exit=float(exit_fill),
                stop=float(stop),target=float(target),signal_atr=float(atr[s]),qty_btc=float(qty),
                gross_before_friction=float(gross_reference),slippage_cost=float(slip_cost),
                fees=float(entry_fee+exit_fee),funding_paid=float(fund_paid),net_usdt=float(net),
                funding_missing_marks_used=missing_marks,funding_timing_ambiguities=funding_ambiguities,
                planned_risk_usdt=float(risk_amount),net_r=float(net/risk_amount),
                capital_before=float(before),capital_after=float(cash),reason=reason,ambiguous=ambiguous,
                bars_exposure_upper=int(j-entry_i+('TIME' not in reason)),
                mfe_h1_upper_r=float(max(0,(high-entry if side==1 else entry-low))/distance),
                mae_h1_upper_r=float(max(0,(entry-low if side==1 else high-entry))/distance),
                risk_budget_breached=bool(net< -before*p.risk-1e-9)))
            decisions.append(dict(**d,status='SIMULATED',trade_number=len(deals)))
            break
    if curve:
        marked[fill_from:]=cash;adverse[fill_from:]=cash
        equity=np.c_[a[start:end,0]+HOUR,marked,adverse]
    else:equity=None
    return deals,equity,decisions


def metrics(trades,equity,initial=200.,hours=None):
    r=np.array([t['net_r'] for t in trades]);pnl=np.array([t['net_usdt'] for t in trades])
    gains=float(pnl[pnl>0].sum());losses=float(-pnl[pnl<0].sum())
    result=dict(n=len(trades),wins=int((pnl>0).sum()),win_rate=float((pnl>0).mean()) if len(pnl) else None,
        expectancy_r=float(r.mean()) if len(r) else None,median_r=float(np.median(r)) if len(r) else None,
        profit_factor=gains/losses if losses else None,profit_factor_denominator_zero=losses==0,
        gross_before_friction=sum(t['gross_before_friction'] for t in trades),
        fees=sum(t['fees'] for t in trades),slippage_cost=sum(t['slippage_cost'] for t in trades),
        funding_paid=sum(t['funding_paid'] for t in trades),net_usdt=float(pnl.sum()),
        return_pct=float(pnl.sum()/initial*100),ambiguous=sum(t['ambiguous'] for t in trades),
        risk_budget_breaches=sum(t['risk_budget_breached'] for t in trades),
        funding_missing_marks_used=sum(t['funding_missing_marks_used'] for t in trades),
        funding_timing_ambiguities=sum(t['funding_timing_ambiguities'] for t in trades),
        ex_best1_mean_r=float(np.mean(np.sort(r)[:-1])) if len(r)>1 else None,
        ex_best3_mean_r=float(np.mean(np.sort(r)[:-3])) if len(r)>3 else None,
        exposure_upper_hours=sum(t['bars_exposure_upper'] for t in trades),
        mean_mfe_h1_upper_r=float(np.mean([t['mfe_h1_upper_r'] for t in trades])) if trades else None,
        mean_mae_h1_upper_r=float(np.mean([t['mae_h1_upper_r'] for t in trades])) if trades else None)
    result.update(max_dd_close_pct=None,max_dd_adverse_bound_pct=None,sharpe_hourly_annualized=None)
    if equity is not None and len(equity):
        eq=np.r_[initial,equity[:,1]];peak=np.maximum.accumulate(eq)
        result['max_dd_close_pct']=float((1-eq/peak).max()*100)
        result['max_dd_adverse_bound_pct']=float(np.maximum(0,1-equity[:,2]/peak[1:]).max()*100)
        returns=np.diff(eq)/eq[:-1]
        if len(returns)>1 and returns.std(ddof=1)>0:
            result['sharpe_hourly_annualized']=float(np.sqrt(365.25*24)*returns.mean()/returns.std(ddof=1))
        hours=len(equity)
    result['exposure_upper_fraction']=result['exposure_upper_hours']/hours if hours else None
    return result
