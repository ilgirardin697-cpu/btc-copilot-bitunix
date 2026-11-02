"""Reference-price risk arithmetic. Never places orders or declares an actual fill."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, localcontext

MIN_NET_RR = Decimal('1.5')
ATR_BUFFER = Decimal('0.20')
RISK_FRACTION = Decimal('0.0025')


@dataclass(frozen=True)
class Costs:
    entry_fee: Decimal
    exit_fee: Decimal
    entry_slippage: Decimal
    exit_slippage: Decimal
    funding_reserve_per_btc: Decimal
    provenance: str


def estimate(side,entry,high,low,target,atr,costs,capital):
    r = dict(risk_filter_passed=False,reason_codes=[],theoretical_entry=entry,side=side,
             stop=None,target=target,net_rr=None,quantity_btc=None,
             actual_fill=None,execution_authority='NONE',funding='NOT_ASSESSED')
    if side not in ('LONG','SHORT'):
        r['reason_codes']=['SIDE_INVALID'];return r
    if any(v is None or not v.is_finite() or v <= 0 for v in (entry,high,low,target)) or high <= low:
        r['reason_codes']=['REFERENCE_PRICE_INVALID'];return r
    if atr is None or not atr.is_finite() or atr < 0:
        r['reason_codes']=['ATR14_UNAVAILABLE'];return r
    direction = Decimal(1 if side == 'LONG' else -1)
    stop = high-ATR_BUFFER*atr if side == 'LONG' else low+ATR_BUFFER*atr
    r['stop']=stop
    if direction*(target-entry) <= 0:r['reason_codes'].append('TP_NOT_AHEAD_OF_ENTRY')
    if stop <= 0 or direction*(entry-stop) <= 0:r['reason_codes'].append('SL_ENTRY_ORDER_INVALID')
    if r['reason_codes']:return r
    if costs is None:
        r['reason_codes']=['COST_ASSUMPTIONS_MISSING'];return r
    rates=(costs.entry_fee,costs.exit_fee,costs.entry_slippage,costs.exit_slippage)
    if (any(not x.is_finite() or x < 0 or x >= 1 for x in rates)
            or not costs.funding_reserve_per_btc.is_finite() or costs.funding_reserve_per_btc < 0
            or not costs.provenance):
        r['reason_codes']=['COST_ASSUMPTIONS_INVALID'];return r
    with localcontext() as ctx:
        ctx.prec=40
        # These are adverse fill SCENARIOS, not observed prices or a promise of executability.
        e = entry*(1+direction*costs.entry_slippage)
        s = stop*(1-direction*costs.exit_slippage)
        t = target*(1-direction*costs.exit_slippage)
        risk = direction*(e-s)+costs.entry_fee*e+costs.exit_fee*s+costs.funding_reserve_per_btc
        reward = direction*(t-e)-costs.entry_fee*e-costs.exit_fee*t-costs.funding_reserve_per_btc
        if risk <= 0:
            r['reason_codes']=['NET_RISK_INVALID'];return r
        rr = reward/risk
        r.update(gross_risk_per_btc=direction*(entry-stop),gross_reward_per_btc=direction*(target-entry),
                 net_risk_per_btc=risk,net_reward_per_btc=reward,net_rr=rr,
                 adverse_entry_scenario=e,adverse_stop_scenario=s,adverse_tp_scenario=t,
                 cost_provenance=costs.provenance,funding='EXPLICIT_SCENARIO_RESERVE',
                 funding_reserve_per_btc=costs.funding_reserve_per_btc,
                 limitation='No latency/gap model or executable price observed; no guaranteed risk cap')
        if rr < MIN_NET_RR:r['reason_codes'].append('NET_RR_BELOW_1_5')
        if capital is None or not capital.is_finite() or capital <= 0:
            r['reason_codes'].append('SIMULATED_CAPITAL_MISSING_OR_INVALID')
        if r['reason_codes']:return r
        budget=capital*RISK_FRACTION
        # Six-decimal BTC granularity is a simulation convention, not exchange lot rules.
        qty=min(budget/risk,capital/e).quantize(Decimal('0.000001'),rounding=ROUND_FLOOR)
        if qty <= 0:
            r['reason_codes']=['SIZE_BELOW_SIMULATION_GRANULARITY'];return r
        r.update(quantity_btc=qty,simulated_risk_budget=budget,estimated_stop_risk=qty*risk,
                 notional_scenario=qty*e,notional_cap=capital,notional_cap_multiple=1,
                 sizing_warning='Collateral/reference sizing only; no liquidation or borrow model',
                 risk_filter_passed=True)
    return r
