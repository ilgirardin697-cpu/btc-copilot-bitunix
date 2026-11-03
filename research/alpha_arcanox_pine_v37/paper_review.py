"""Offline OWNER_B review; no runner, clients, order paths or forward activation.

The reference window is reused/selected, not an unseen profitability test.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, ROUND_FLOOR, localcontext
from pathlib import Path
from .core import HOUR
from .profiles import OWNER_B
from .replay import Replay
from .risk import Costs, paper_plan, MIN_NET_RR, RISK_FRACTION
from .evidence import analyze, bars_from_rows, load_evidence, utc

HERE=Path(__file__).resolve().parent
SPEC_PATH=HERE/'OWNER_B_REVIEW_SPEC.json'


def review_costs(spec):
    return Costs(*(D(spec[k]) for k in ('entry_fee_rate','exit_fee_rate',
        'entry_slippage_rate','exit_slippage_rate','funding_reserve_per_btc')),
        provenance=spec['cost_provenance'])


def expiry_after(signal_close):
    local=datetime.fromtimestamp(signal_close/1000,timezone.utc).astimezone(OWNER_B.tz)
    end=local.replace(hour=20,minute=0,second=0,microsecond=0)
    if end<=local:end+=timedelta(days=1)
    return int(end.timestamp()*1000)


def first_touches(side,stop,tp,theoretical,bars,not_before,expiry):
    """H1 interval resolution only. No claim of within-bar execution order."""
    direction=1 if side=='LONG' else -1
    first=None;original=None;advanced=None;stop_seen=None
    selected=[b for b in bars if not_before<=b.open_time<expiry]
    if selected and (selected[0].open_time!=not_before or any(
            b.open_time-a.open_time!=HOUR for a,b in zip(selected,selected[1:]))):
        raise ValueError('NON_CONTIGUOUS_EVALUATION_BARS')
    for b in selected:
        hit_stop=b.low<=stop if direction==1 else b.high>=stop
        hit_tp=b.high>=tp if direction==1 else b.low<=tp
        hit_original=b.high>=theoretical if direction==1 else b.low<=theoretical
        stamp=dict(bar_open_utc=utc(b.open_time),known_at_utc=utc(b.available_at))
        if hit_original and original is None:original=stamp
        if hit_tp and advanced is None:advanced=stamp
        if hit_stop and stop_seen is None:stop_seen=stamp
        if first is None and (hit_stop or hit_tp):
            first=dict(**stamp,kind='SL' if hit_stop else 'TP',
                       ambiguous=hit_stop and hit_tp,
                       reference_exit=(min(stop,b.open) if direction==1 else max(stop,b.open))
                           if hit_stop else tp)
    complete=bool(selected and selected[-1].available_at>=expiry)
    return dict(first_event=first,advanced_tp_touch=advanced,sl_touch=stop_seen,
                theoretical_target_touch=original,
                coverage_complete_to_expiry=complete,
                no_event_interpretation=None if first else 'NONE_WITHIN_COMPLETE_HORIZON' if complete else 'RIGHT_CENSORED',
                theoretical_target_role='COUNTERFACTUAL_PRICE_HITO_NOT_REALIZED_TRADE_PROFIT',
                same_confirmation_candle_excluded=True)


def reprice(plan,reference,capital,costs):
    """Same fixed stop/TP; re-evaluate at next open, never move the stop."""
    side=plan['side'];d=D(1 if side=='LONG' else -1)
    entry=D(str(reference));stop=plan['stop'];tp=plan['advanced_tp']
    r=dict(reference_entry=entry,accepted=False,reasons=[])
    if d*(tp-entry)<=0:
        r['reasons'].append('ADVANCED_TP_NOT_AHEAD_OF_NEXT_OPEN')
    if d*(entry-stop)<=0:
        r['reasons'].append('STOP_INVALID_AT_NEXT_OPEN')
    if r['reasons']:return r
    with localcontext() as ctx:
        ctx.prec=40
        e=entry*(1+d*costs.entry_slippage)
        s=stop*(1-d*costs.exit_slippage)
        t=tp*(1-d*costs.exit_slippage)
        risk=d*(e-s)+costs.entry_fee*e+costs.exit_fee*s+costs.funding_reserve_per_btc
        reward=d*(t-e)-costs.entry_fee*e-costs.exit_fee*t-costs.funding_reserve_per_btc
        rr=reward/risk if risk>0 else None
        r.update(adverse_entry_scenario=e,net_risk_per_btc=risk,net_reward_per_btc=reward,net_rr=rr)
        if risk<=0 or rr<MIN_NET_RR:
            r['reasons']=['NEXT_OPEN_NET_RR_BELOW_1_5'];return r
        qty=min(capital*RISK_FRACTION/risk,capital/e).quantize(D('0.000001'),rounding=ROUND_FLOOR)
        if qty<=0:
            r['reasons']=['SIZE_BELOW_PAPER_GRANULARITY'];return r
        r.update(accepted=True,quantity_btc=qty,notional=qty*e,risk_budget=capital*RISK_FRACTION,
                 estimated_stop_loss=qty*risk,operational_paper_authorized=False)
    return r


def evaluate_signal(snapshot,signal,bars,capital,costs):
    plan=paper_plan(snapshot,signal,capital,costs)
    result=dict(signal_bar_open_utc=utc(signal.open_time),confirmed_at_utc=utc(signal.available_at),
                plan_at_close=plan,capital_before=capital,side=plan.get('side'),
                signal_open=D(str(signal.open)),signal_close=D(str(signal.close)),
                atr14_at_confirmation=snapshot.get('atr14'),
                execution_status='NOT_ENTERED',realized_net_pnl=None,
                actual_executable_quote='NOT_AVAILABLE_FROM_H1_OHLC',
                short_inventory_or_borrow='NOT_VERIFIED_HYPOTHETICAL_DIRECTIONAL_PAPER_ONLY')
    next_bar=next((b for b in bars if b.open_time==signal.available_at),None)
    expiry=expiry_after(signal.available_at)
    result['expiry_utc']=utc(expiry)
    if next_bar is not None:
        result['next_open_reference_utc']=utc(next_bar.open_time)
        result['next_open_reference_price']=D(str(next_bar.open))
        if plan.get('side') and plan['stop'] is not None and plan['advanced_tp'] is not None:
            result['next_open_check']=reprice(plan,next_bar.open,capital,costs)
            result['next_open_check']['role']='DIAGNOSTIC_ONLY_IF_SIGNAL_ALREADY_REJECTED'
    if plan['stop'] is not None and plan['advanced_tp'] is not None:
        # Descriptive path is retained even for risk-rejected opportunities.
        # It must NEVER contribute to trade PnL or the accepted-trade denominator.
        ordered=(plan['advanced_tp']>plan['theoretical_entry']>plan['stop'] if plan['side']=='LONG'
                 else plan['advanced_tp']<plan['theoretical_entry']<plan['stop'])
        if ordered:
            result['reference_path']=first_touches(plan['side'],float(plan['stop']),
                float(plan['advanced_tp']),float(plan['theoretical_target']),bars,signal.available_at,expiry)
            result['reference_path']['role']='SIGNAL_PRICE_PATH_NOT_ACCEPTED_TRADE_RESULT'
    if not plan['accepted']:
        result['execution_status']='REJECTED_AT_CONFIRMATION';return result
    if next_bar is None:
        result['execution_status']='PENDING_NEXT_OPEN';return result
    entry=result['next_open_check']
    entry['role']='ENTRY_REVALIDATION_AFTER_ACCEPTED_CLOSE_FILTER'
    result['entry_reference_utc']=utc(next_bar.open_time)
    if not entry['accepted']:
        result['execution_status']='REJECTED_AT_NEXT_OPEN';return result
    result['execution_status']='PAPER_ENTRY_SCENARIO_NOT_REAL_FILL'
    path=first_touches(plan['side'],float(plan['stop']),float(plan['advanced_tp']),
                       float(plan['theoretical_target']),bars,next_bar.open_time,expiry)
    result['trade_path']=path
    event=path['first_event']
    exit_reference=None
    if event:
        exit_reference=D(str(event['reference_exit']))
        result['outcome']=event['kind']
        result['outcome_known_at']=event['known_at_utc']
    else:
        final=next((b for b in bars if b.available_at==expiry),None)
        if final:
            exit_reference=D(str(final.close));result['outcome']='TIME_EXIT'
            result['outcome_known_at']=utc(expiry)
        else:
            result['outcome']='RIGHT_CENSORED'
    if exit_reference is None:return result
    d=D(1 if plan['side']=='LONG' else -1)
    e=entry['adverse_entry_scenario'];x=exit_reference*(1-d*costs.exit_slippage)
    qty=entry['quantity_btc']
    gross=d*(x-e)*qty
    fees=(costs.entry_fee*e+costs.exit_fee*x)*qty
    funding=costs.funding_reserve_per_btc*qty
    result.update(exit_scenario=x,gross_after_slippage=gross,fees=fees,funding=funding,
                  realized_net_pnl=gross-fees-funding,
                  net_R=(gross-fees-funding)/(qty*entry['net_risk_per_btc']),
                  capital_after=capital+gross-fees-funding)
    return result


def review():
    parity=analyze()
    if parity['complete_cycles']<1 or parity['mismatches']:
        raise ValueError('PARITY_GATE_FAILED_NO_OWNER_REVIEW')
    spec=json.loads(SPEC_PATH.read_text(encoding='utf-8'))
    rows=load_evidence();bars=bars_from_rows(rows);costs=review_costs(spec)
    capital=D(spec['simulated_starting_capital'])
    e=Replay(OWNER_B);cycles=[];active=None;partial=dict(status='EXCLUDED_INITIAL_PARTIAL_PAIR',
        reason='EXPORT_STARTS_AFTER_ASIA_BEGAN_NO_STATE_OR_EXTREMA_INJECTED',
        first_available_bar_open_utc=utc(bars[0].open_time))
    for b in bars:
        snap=e.append(b,as_of=b.available_at)
        if snap['startAsia']:
            true_start=datetime.fromtimestamp(b.open_time/1000,timezone.utc).astimezone(OWNER_B.tz).hour==OWNER_B.asia_start
            active=dict(cycle_id=snap['cycle_id'],
                        asia_open_utc=utc(b.open_time) if true_start else None,
                        first_observed_asia_bar_utc=utc(b.open_time),
                        status='INCOMPLETE_PAIR' if true_start else 'EXCLUDED_INITIAL_PARTIAL_PAIR',signal=None)
            cycles.append(active)
        if snap['measureNow']:
            if active is None:raise ValueError('DO_NOT_FORCE_INITIAL_PARTIAL_CYCLE')
            active.update(status='NO_CONFIRMATION',levels=snap['frozen'],
                          levels_available_at_utc=utc(b.open_time),
                          atr14_at_first_outside_close=snap['atr14'])
        if snap['longBreak'] or snap['shortBreak']:
            if active is None or 'levels' not in active:
                raise ValueError('SIGNAL_WITHOUT_COMPLETE_OWNER_PAIR')
            r=evaluate_signal(snap,b,bars,capital,costs)
            active.update(status=r['execution_status'],signal=r)
            if r['realized_net_pnl'] is not None:capital=r['capital_after']
    entered=[c['signal'] for c in cycles if c['signal'] and c['signal']['execution_status']=='PAPER_ENTRY_SCENARIO_NOT_REAL_FILL']
    matured=[r for r in entered if r['realized_net_pnl'] is not None]
    return dict(scope=spec['scope'],profile='OWNER_B',venue=spec['venue'],protocol=spec,
                protocol_sha256=hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest(),
                logs_sha256=parity['source_log_sha256'],partial_cycle=partial,cycles=cycles,
                complete_pairs=sum('levels' in c for c in cycles),
                first_confirmations=sum(c['signal'] is not None for c in cycles),
                entered_scenarios=len(entered),matured_scenarios=len(matured),
                net_realized_pnl=sum((r['realized_net_pnl'] for r in matured),D(0)),
                ending_realized_capital=capital,
                profitability_conclusion='INSUFFICIENT_SAMPLE_NOT_EDGE_EVIDENCE',
                prospective_observer='NOT_IMPLEMENTED_OR_ACTIVATED',trade_authority='NONE')


def json_default(value):
    if isinstance(value,D):return str(value)
    raise TypeError('UNSUPPORTED_ARTIFACT_TYPE')


if __name__=='__main__':
    print(json.dumps(review(),default=json_default,ensure_ascii=False,indent=2,allow_nan=False))
