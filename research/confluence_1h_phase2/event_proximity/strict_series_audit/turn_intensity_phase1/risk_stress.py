"""Conditional arithmetic only. Not an exchange liquidation engine or strategy."""
from decimal import Decimal, ROUND_FLOOR


def sized_quantity(equity, entry, stop, side, fee=.001, slip=.0005, funding_reserve=.0005, step=.0001):
    if side not in (-1,1) or min(equity,entry,stop,step)<=0 or side*(entry-stop)<=0:
        raise ValueError('ORDERED_STRUCTURAL_STOP_REQUIRED')
    # Stop-fill slip is included exactly once; signal entry already executable.
    stop_fill=stop*(1-side*slip)
    loss=side*(entry-stop_fill)+fee*(entry+stop_fill)+entry*funding_reserve
    raw=min(.01*equity/loss,equity/(entry*(1+fee)))
    qty=float((Decimal(str(raw))/Decimal(str(step))).to_integral_value(rounding=ROUND_FLOOR)*Decimal(str(step)))
    return dict(qty=qty,planned_loss=qty*loss,risk_budget=.01*equity,unit_loss=loss,
                status='BELOW_MINIMUM_NO_POSITION' if qty<step else 'CONDITIONAL_SIZE_ONLY')


def isolated_threshold(entry, qty, margin, side, mmr, debited_costs=0.):
    """Opening-notional MM convention in official example, not exact venue quote.

    Tiers may change; official example has inconsistent arithmetic. Mark/fill
    prices, fee reserves and insurance behavior are NOT inferred from this.
    """
    if min(entry,qty,margin)<=0 or side not in (-1,1) or not 0<mmr<1 or debited_costs<0:
        raise ValueError('VERIFIED_INPUTS_REQUIRED')
    room=margin-entry*qty*mmr-debited_costs
    if room<=0:
        return dict(price=None,status='INSUFFICIENT_MARGIN')
    price=entry-side*room/qty
    return dict(price=price if price>0 else None,status='CONDITIONAL_NOT_VERIFIED_LIQUIDATION')


def illustrative_scenarios(mmr=.003):
    rows=[]
    for side in (1,-1):
        for distance in (.01,.05,.10):
            equity,entry=10000.,100000.;stop=entry*(1-side*distance)
            base=sized_quantity(equity,entry,stop,side)
            qty=.5*equity*10/entry
            threshold=isolated_threshold(entry,qty,.5*equity,side,mmr,qty*entry*.001)
            for model,q in [('FIXED_1PCT_RISK_NO_LEVERAGE',base['qty']),('STRESS_HALF_BALANCE_10X_ISOLATED',qty)]:
                stop_fill=stop*(1-side*.0005)
                loss=q*(side*(entry-stop_fill)+.001*(entry+stop_fill)+entry*.0005)
                gap_fill=stop_fill-side*.01*entry
                gap_loss=q*(side*(entry-gap_fill)+.001*(entry+gap_fill)+entry*.0005)
                rows.append(dict(evidence='ILLUSTRATIVE_ARITHMETIC_NOT_HISTORICAL_TRADES',model=model,side=side,
                                 equity=equity,entry=entry,stop=stop,qty=q,stop_distance_fraction=distance,
                                 planned_loss=loss,gap_1pct_loss_before_liquidation_model=gap_loss,
                                 funding_reserve_assumption=.0005,conditional_threshold=threshold['price'] if model.startswith('STRESS') else None,
                                 isolated_margin_at_risk=.5*equity if model.startswith('STRESS') else None,
                                 stop_beyond_conditional_threshold=bool(side*(stop-threshold['price'])<=0) if model.startswith('STRESS') else False,
                                 liquidation_status='NOT_VERIFIED_CONDITIONAL_ONLY'))
    return rows
