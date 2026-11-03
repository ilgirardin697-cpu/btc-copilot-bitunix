"""OWNER_B PAPER reference arithmetic, not part of the educational indicator.

The 200 adjustment is a BTCUSDT PRICE distance, NOT account profit. Fees,
slippage and funding are explicit scenarios; an exact close fill is not assumed.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, localcontext

D = Decimal
TP_ADVANCE = D('200')
MIN_NET_RR = D('1.5')
RISK_FRACTION = D('0.0025')
ATR_BUFFER = D('0.20')


@dataclass(frozen=True)
class Costs:
    entry_fee: Decimal
    exit_fee: Decimal
    entry_slippage: Decimal
    exit_slippage: Decimal
    funding_reserve_per_btc: Decimal
    provenance: str


def paper_plan(snapshot, candle, capital, costs):
    r = dict(profile=snapshot.get('profile'), accepted=False, reasons=[],
             theoretical_entry=D(str(candle.close)), theoretical_target=None,
             advanced_tp=None, tp_advance_price=TP_ADVANCE, stop=None, net_rr=None,
             quantity_btc=None, actual_fill=None, trade_authority='NONE',
             operational_paper_authorized=False)
    if snapshot.get('profile') != 'OWNER_B':
        r['reasons'] = ['NOT_OWNER_B_RISK_RULES']; return r
    if not snapshot.get('data_complete'):
        r['reasons'] = ['INCOMPLETE_H1_DATA']; return r
    long, short = snapshot.get('longBreak',False), snapshot.get('shortBreak',False)
    if long == short or not snapshot.get('frozen'):
        r['reasons'] = ['NO_FIRST_CONFIRMED_SIGNAL']; return r
    if snapshot.get('time') != candle.open_time or snapshot.get('available_at') != candle.available_at:
        r['reasons'] = ['SIGNAL_CANDLE_MISMATCH']; return r
    side, direction = ('LONG',D(1)) if long else ('SHORT',D(-1))
    f = snapshot['frozen']; entry = r['theoretical_entry']
    target = D(str(f['newTopTarget'] if long else f['newBottomTarget']))
    advanced = target-direction*TP_ADVANCE
    r.update(side=side, theoretical_target=target, advanced_tp=advanced)
    atr = snapshot.get('atr14')
    if atr is None or not D(str(atr)).is_finite() or D(str(atr)) < 0:
        r['reasons'] = ['ATR14_UNAVAILABLE']; return r
    stop = (D(str(f['highGuideValue']))-ATR_BUFFER*D(str(atr)) if long else
            D(str(f['lowGuideValue']))+ATR_BUFFER*D(str(atr)))
    r['stop'] = stop
    if not advanced.is_finite() or advanced <= 0 or direction*(advanced-entry) <= 0:
        r['reasons'].append('ADVANCED_TP_NOT_AHEAD_OF_ENTRY')
    if stop <= 0 or direction*(entry-stop) <= 0:
        r['reasons'].append('SL_ENTRY_ORDER_INVALID')
    if r['reasons']: return r
    if costs is None:
        r['reasons'] = ['COST_ASSUMPTIONS_REQUIRED']; return r
    rates = (costs.entry_fee, costs.exit_fee, costs.entry_slippage, costs.exit_slippage)
    if (any(not x.is_finite() or x < 0 or x >= 1 for x in rates)
            or not costs.funding_reserve_per_btc.is_finite()
            or costs.funding_reserve_per_btc < 0 or not costs.provenance):
        r['reasons'] = ['INVALID_COST_SCENARIO']; return r
    if capital is None or not capital.is_finite() or capital <= 0:
        r['reasons'] = ['INVALID_SIMULATED_CAPITAL']; return r
    with localcontext() as ctx:
        ctx.prec = 40
        e = entry*(1+direction*costs.entry_slippage)
        s = stop*(1-direction*costs.exit_slippage)
        t = advanced*(1-direction*costs.exit_slippage)
        risk = direction*(e-s)+costs.entry_fee*e+costs.exit_fee*s+costs.funding_reserve_per_btc
        reward = direction*(t-e)-costs.entry_fee*e-costs.exit_fee*t-costs.funding_reserve_per_btc
        r.update(net_risk_per_btc=risk, net_reward_per_btc=reward,
                 adverse_entry_scenario=e, adverse_stop_scenario=s, adverse_tp_scenario=t,
                 cost_provenance=costs.provenance, net_rr=reward/risk if risk > 0 else None,
                 funding='EXPLICIT_ASSUMED_RESERVE_NOT_OBSERVED_FUNDING')
        if risk <= 0:
            r['reasons'] = ['NON_POSITIVE_RISK']; return r
        if r['net_rr'] < MIN_NET_RR:
            r['reasons'] = ['ADVANCED_TP_NET_RR_BELOW_1_5']; return r
        # Unlevered notional cap; no live lot-size, borrow or liquidation claims.
        qty = min(capital*RISK_FRACTION/risk, capital/e).quantize(D('0.000001'),rounding=ROUND_FLOOR)
        if qty <= 0:
            r['reasons'] = ['SIZE_BELOW_PAPER_GRANULARITY']; return r
        r.update(accepted=True, quantity_btc=qty, risk_budget=capital*RISK_FRACTION,
                 estimated_stop_loss=qty*risk, notional=qty*e, notional_cap=capital,
                 limitation='Reference PAPER only; latency and gaps may exceed the scenario reserve')
    return r
