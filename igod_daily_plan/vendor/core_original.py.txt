"""I-GOD Daily Two-Leg Plan V1: read-only, causal, structure-first research.

This module NEVER opens orders, imports account/execution code, or claims parity
with third-party Pine indicators. All numeric outputs are research estimates.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from statistics import pstdev

STEPS = {'15m':900_000, '1h':3_600_000, '4h':14_400_000,
         '1d':86_400_000, '1w':604_800_000}
WEEKLY_ANCHOR = 4 * STEPS['1d']  # 1970-01-05 Monday 00:00 UTC
HISTORIES = {'15m':220,'1h':260,'4h':260,'1d':330,'1w':330}
SOURCE = 'BINANCE_USDM_PERPETUAL'
VERSION = 'IGOD_DAILY_TWO_LEG_V1_RESEARCH'

class PlanDataError(ValueError):
    pass


def safe_float(value):
    if type(value) not in (int, float, str) or isinstance(value, str) and not value.strip():
        raise PlanDataError('NONNUMERIC_MARKET_DATA')
    try:
        x = float(value)
    except (OverflowError, ValueError):
        raise PlanDataError('NONNUMERIC_MARKET_DATA') from None
    if not math.isfinite(x):
        raise PlanDataError('NONFINITE_MARKET_DATA')
    return x


def align(timestamp, tf):
    step = STEPS[tf]
    anchor = WEEKLY_ANCHOR if tf == '1w' else 0
    return (timestamp - anchor) % step == 0


def normalize(rows, tf, asof, minimum):
    """Return validated *closed* contiguous Binance-style klines.

    The open bar is ignored, never evaluated. Fully invalid closed histories
    fail closed. closeTime = openTime + interval-1 for UTC-aligned Binance bars.
    """
    if tf not in STEPS or type(asof) is not int or asof < 1_000_000_000_000:
        raise PlanDataError('INPUT_SCHEMA')
    out = []
    previous = None
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != 12:
            raise PlanDataError('KLINE_SCHEMA')
        start, end = row[0], row[6]
        if type(start) is not int or type(end) is not int or not align(start, tf):
            raise PlanDataError('KLINE_TIMESTAMP')
        if end != start + STEPS[tf] - 1 or start > asof + STEPS[tf]:
            raise PlanDataError('KLINE_CLOSE_TIMESTAMP')
        if previous is not None and start != previous + STEPS[tf]:
            raise PlanDataError('GAPPED_OR_DUPLICATE_MARKET_DATA')
        previous = start
        o, h, l, c, volume, buy = [safe_float(row[x]) for x in (1,2,3,4,5,9)]
        if not 0 < l <= min(o,c) <= max(o,c) <= h or volume < 0 or buy < 0 or buy > volume:
            raise PlanDataError('INVALID_OHLCV')
        if end < asof:  # Time interval completed, irrespective of HTTP arrival
            out.append(dict(ts=start, close_ts=end+1, o=o, h=h, l=l, c=c,
                            volume=volume, taker_buy=buy))
    if len(out) < minimum:
        raise PlanDataError(f'INSUFFICIENT_{tf.upper()}_CLOSED_HISTORY')
    # Require freshness: latest 15m ≤30m, other intervals ≤2x cadence.
    latest = out[-1]['close_ts']
    if asof - latest > (2 * STEPS[tf] + 10_000):
        raise PlanDataError('STALE_'+tf.upper()+'_CANDLES')
    return out


def sma(values, length):
    return sum(values[-length:]) / length if len(values) >= length else None


def ao_series(rows):
    med = [(x['h']+x['l'])/2 for x in rows]
    out = []
    for i in range(len(med)):
        if i < 33:out.append(None)
        else:out.append(sum(med[i-4:i+1])/5 - sum(med[i-33:i+1])/34)
    return out


def adx_series(rows, length=14):
    """Wilder DMI/ADX, with explicit seed after the initial DX window."""
    if len(rows) < 2*length+3:
        raise PlanDataError('ADX_WARMUP')
    components = []
    for i in range(1, len(rows)):
        curr, prev = rows[i], rows[i-1]
        up, down = curr['h']-prev['h'], prev['l']-curr['l']
        plus = up if up>down and up>0 else 0.0
        minus = down if down>up and down>0 else 0.0
        tr = max(curr['h']-curr['l'],abs(curr['h']-prev['c']),abs(curr['l']-prev['c']))
        components.append((tr, plus, minus))
    # Wilder smoothing of sums
    smooth = [sum(v[j] for v in components[:length]) for j in range(3)]
    dxs = []
    result = [None] * length
    for i in range(length-1, len(components)):
        if i >= length:
            for k in range(3):smooth[k] = smooth[k] - smooth[k]/length + components[i][k]
        if smooth[0] <= 0:
            plus_di, minus_di = 0.0,0.0
        else:
            plus_di, minus_di = 100*smooth[1]/smooth[0],100*smooth[2]/smooth[0]
        dx = 100*abs(plus_di-minus_di)/(plus_di+minus_di) if plus_di+minus_di else 0.0
        dxs.append(dx)
        if len(dxs) < length:
            result.append(None)
            continue
        if len(dxs) == length:
            current_adx = sum(dxs)/length
        else:
            current_adx = ((length-1)*current_adx+dx)/length
        result.append(dict(adx=current_adx, plus_di=plus_di, minus_di=minus_di))
    if len(result) != len(rows):
        raise AssertionError('ADX_ALIGNMENT')
    return result


def bbwp_series(rows, window=13, lookback=252, signal=5):
    """BBW percentile implementation; no claimed numerical TradingOne parity.

    Uses close SMA(window), population stdev, 2-sigma bands, a strict prior
    lookback of BBW values and <= percentile ties. NOT exact verified Pine.
    """
    widths = []
    for i in range(len(rows)):
        if i < window-1:
            widths.append(None)
            continue
        cs = [r['c'] for r in rows[i-window+1:i+1]]
        mean = sum(cs)/len(cs)
        widths.append(4*pstdev(cs)/abs(mean)*100 if mean else None)
    pcts = []
    for i,w in enumerate(widths):
        prior = widths[max(0,i-lookback):i]
        if w is None or len(prior) != lookback or any(x is None for x in prior):
            pcts.append(None)
        else:pcts.append(100*sum(x<=w for x in prior)/lookback)
    # Requires four previous full-history BBWP observations for signal SMA5.
    return [(p, sma([x for x in pcts[:i+1] if x is not None],signal)
             if i>=signal-1 and sum(x is not None for x in pcts[:i+1])>=signal else None)
            for i,p in enumerate(pcts)]


def pivots(rows,left=2,right=2):
    """Only levels confirmed after the two right-hand candles closed."""
    hs,ls = [],[]
    for i in range(left,len(rows)-right):
        neighborhood=rows[i-left:i+right+1]
        h,l=rows[i]['h'],rows[i]['l']
        if sum(x['h']==h for x in neighborhood)==1 and h==max(x['h'] for x in neighborhood):
            hs.append(dict(price=h, confirmed_at=rows[i+right]['close_ts'],pivot_at=rows[i]['ts']))
        if sum(x['l']==l for x in neighborhood)==1 and l==min(x['l'] for x in neighborhood):
            ls.append(dict(price=l, confirmed_at=rows[i+right]['close_ts'],pivot_at=rows[i]['ts']))
    return hs,ls


def atr14(rows):
    vals=[]
    for i,row in enumerate(rows):
        prev=rows[i-1]['c'] if i else row['c']
        vals.append(max(row['h']-row['l'],abs(row['h']-prev),abs(row['l']-prev)))
    if len(vals)<15:raise PlanDataError('ATR_WARMUP')
    out=sum(vals[:14])/14
    for v in vals[14:]:out=(13*out+v)/14
    return out


def support_resistance(level_sets, reference, min_gap):
    all_highs,all_lows=[],[]
    for tf, rows in level_sets.items():
        h,l=pivots(rows)
        all_highs += [dict(**x,timeframe=tf) for x in h if x['price']>reference]
        all_lows += [dict(**x,timeframe=tf) for x in l if x['price']<reference]
    def distinct(items):
        selected=[]
        for x in items:
            if all(abs(x['price']-y['price'])>=min_gap for y in selected):selected.append(x)
        return selected
    return {'resistances':distinct(sorted(all_highs,key=lambda x:x['price'])),
            'supports':distinct(sorted(all_lows,key=lambda x:-x['price']))}


def fmt_time(stamp):
    return datetime.fromtimestamp(stamp/1000,timezone.utc).isoformat()


def read_indicators(rows):
    ao=ao_series(rows)
    adx=adx_series(rows)
    bb=bbwp_series(rows)
    if any(x is None for x in (ao[-1],ao[-2],adx[-1],adx[-2],bb[-1][0],bb[-2][0],bb[-1][1])):
        raise PlanDataError('INDICATOR_WARMUP')
    return {
        'ao':round(ao[-1],5),'ao_previous':round(ao[-2],5),
        'adx':round(adx[-1]['adx'],4),'adx_previous':round(adx[-2]['adx'],4),
        'plus_di':round(adx[-1]['plus_di'],4),'minus_di':round(adx[-1]['minus_di'],4),
        'bbwp':round(bb[-1][0],4),'bbwp_previous':round(bb[-2][0],4),
        'bbwp_signal':round(bb[-1][1],4), 'closed_at':fmt_time(rows[-1]['close_ts'])
    }


def risk_sizing(equity,entry_a,entry_b,stop,reference,*,risk_pct=.005,max_notional_multiple=1.0,
                assumed_roundtrip_bps=18.0, qty_step=.0001):
    # Each leg is 50% of a PRE-SIZED total position, not 50% of equity/margin.
    if type(equity) not in (int,float) or not 0 < equity <= 1e9:
        raise PlanDataError('INVALID_SIMULATED_EQUITY')
    distances=[abs(entry_a-stop),abs(entry_b-stop)]
    per_btc=.5*(distances[0]+distances[1])+assumed_roundtrip_bps/10000*.5*(entry_a+entry_b)
    total_qty=min(equity*risk_pct/per_btc, equity*max_notional_multiple/max(entry_a,entry_b,reference))
    leg_qty=math.floor(total_qty/2/qty_step+1e-10)*qty_step
    if leg_qty<=0: return None
    total_risk=leg_qty*sum(distances)+(leg_qty*(entry_a+entry_b))*assumed_roundtrip_bps/10000
    notional=leg_qty*(entry_a+entry_b)
    if total_risk>equity*risk_pct+1e-8 or notional>equity*max_notional_multiple+1e-8:
        raise AssertionError('RISK_BOUND_BREACHED')
    if leg_qty*min(entry_a,entry_b)<5:return None
    return dict(qty_per_leg_btc=round(leg_qty,8),maximum_combined_estimated_loss_usdt=round(total_risk,4),
                maximum_combined_notional_usdt=round(notional,4), max_risk_pct=risk_pct*100,
                max_notional_multiple=max_notional_multiple,
                modeled_roundtrip_cost_bps=assumed_roundtrip_bps,
                estimated_loss_excludes_gaps_liquidation_funding=True)


def generate_plan(raw,asof,equity_simulated=140, *, live_public=False):
    """Build a read-only daily scenario, NOT a trade recommendation or order."""
    evidence={'version':VERSION,'mode':'SHADOW_ONLY','trade_authority':'NONE',
              'source':SOURCE,'symbol':'BTCUSDT','asof_utc':fmt_time(asof),
              'account_equity_read':False,'paper_equity_usdt':equity_simulated,
              'market_data_retrieved_live':bool(live_public),
              'model_parity':'NOT_VERIFIED_AGAINST_TRADINGONE_PINE'}
    try:
        bars={tf:normalize(raw[tf],tf,asof,HISTORIES[tf]) for tf in HISTORIES}
        daily,weekly=read_indicators(bars['1d']),read_indicators(bars['1w'])
        evidence['inputs_sha256']={tf:hashlib.sha256(json.dumps(raw[tf],separators=(',',':')).encode()).hexdigest() for tf in HISTORIES}
        evidence['indicators']={'daily':daily,'weekly':weekly}
        reference=bars['15m'][-1]['c']
        evidence['reference_close_15m']=round(reference,2)
        evidence['reference_closed_at_utc']=fmt_time(bars['15m'][-1]['close_ts'])
        down=(daily['ao']<0 and daily['ao']<daily['ao_previous'] and
              daily['adx']>daily['adx_previous'] and
              daily['bbwp']>daily['bbwp_previous'] and daily['bbwp']>daily['bbwp_signal'])
        up=(daily['ao']>0 and daily['ao']>daily['ao_previous'] and
              daily['adx']>daily['adx_previous'] and
              daily['bbwp']>daily['bbwp_previous'] and daily['bbwp']>daily['bbwp_signal'])
        signs={}
        for tf in ('1h','4h'):
            rs=bars[tf]
            price=rs[-1]['c']; ma=sma([x['c'] for x in rs],200)
            direction='BEAR' if price<ma else 'BULL'
            pattern=pivots(rs)
            high,low=pattern
            structure=('BEAR' if len(high)>=2 and len(low)>=2 and
                       high[-1]['price']<high[-2]['price'] and low[-1]['price']<low[-2]['price']
                       else 'BULL' if len(high)>=2 and len(low)>=2 and
                       high[-1]['price']>high[-2]['price'] and low[-1]['price']>low[-2]['price']
                       else 'MIXED')
            signs[tf]={'sma200_bias':direction,'confirmed_pivot_structure':structure}
        evidence['timeframe_context']=signs
        weekly_note=('WEEKLY_AO_POSITIVE_BUT_WEAKENING' if weekly['ao']>0 and weekly['ao']<weekly['ao_previous']
                     else 'WEEKLY_AO_NEGATIVE_AND_WEAKENING' if weekly['ao']<0 and weekly['ao']<weekly['ao_previous']
                     else 'WEEKLY_AO_IMPROVING_OR_MIXED')
        evidence['weekly_warning']=weekly_note
        evidence['weekly_adx_rising']=weekly['adx']>weekly['adx_previous']
        evidence['weekly_bbwp_expanding']=weekly['bbwp']>weekly['bbwp_previous']
        warnings=[]
        if weekly_note == 'WEEKLY_AO_POSITIVE_BUT_WEAKENING':
            warnings.append('Weekly AO remains positive: weakness is not a confirmed weekly bearish regime.')
        if weekly['bbwp']<weekly['bbwp_previous']:
            warnings.append('Weekly BBWP is declining; no weekly volatility-expansion confirmation.')
        # AO/ADX/BBWP by themselves do not determine a trade direction.
        if down: side='SHORT'
        elif up:side='LONG'
        else:side=None
        reasons=[]
        if side is None:
            status='WAIT';reasons.append('DAILY_AO_ADX_BBWP_CONFLUENCE_UNCONFIRMED')
        elif side == 'SHORT' and daily['minus_di']<=daily['plus_di']:
            status='WATCH_SHORT';reasons.append('DMI_NOT_BEARISH')
        elif side == 'LONG' and daily['plus_di']<=daily['minus_di']:
            status='WATCH_LONG';reasons.append('DMI_NOT_BULLISH')
        elif any(signs[tf]['sma200_bias'] != ('BEAR' if side=='SHORT' else 'BULL') for tf in signs):
            status='WATCH_'+side;reasons.append('1H_4H_PRICE_TREND_DISAGREES')
        elif any(signs[tf]['confirmed_pivot_structure'] != ('BEAR' if side=='SHORT' else 'BULL') for tf in signs):
            status='WATCH_'+side;reasons.append('1H_4H_CONFIRMED_PRICE_STRUCTURE_NOT_ALIGNED')
        else:status='SCENARIO_'+side
        evidence.update(bias=status,notes=reasons,warnings=warnings,entries=[],targets=[],risk=None)
        if not status.startswith('SCENARIO_'):
            evidence['reason_no_trade']='CONFIRMATION_MISSING'
            return evidence
        atr=atr14(bars['1h']);levels=support_resistance({'1h':bars['1h'],'4h':bars['4h']},reference,max(.25*atr,.0001*reference))
        evidence['structural_levels']=levels
        if side=='LONG':
            es=levels['supports'];ts=levels['resistances']
            # A near the market, B deeper; distinct structural targets.
            if len(es)<2 or len(ts)<2:
                evidence.update(bias='WATCH_LONG', reason_no_trade='TWO_CONFIRMED_LEVELS_MISSING')
                return evidence
            a,b=es[0]['price'],es[1]['price']; t_a,t_b=ts[1]['price'],ts[0]['price']
            stop=b-atr*.5
            valid=0<stop<b<a<reference<t_b<t_a
        else:
            es=levels['resistances'];ts=levels['supports']
            if len(es)<2 or len(ts)<2:
                evidence.update(bias='WATCH_SHORT', reason_no_trade='TWO_CONFIRMED_LEVELS_MISSING')
                return evidence
            a,b=es[0]['price'],es[1]['price'];t_a,t_b=ts[1]['price'],ts[0]['price']
            stop=b+atr*.5
            valid=0<t_a<t_b<reference<a<b<stop
        if not valid or abs(b-reference)>6*atr or abs(a-reference)>3*atr:
            evidence.update(bias='WATCH_'+side,reason_no_trade='STRUCTURAL_LEVELS_UNSUITABLE_OR_TOO_FAR')
            return evidence
        rr_a=abs(t_a-a)/abs(stop-a);rr_b=abs(t_b-b)/abs(stop-b)
        if min(rr_a,rr_b)<1.0:
            evidence.update(bias='WATCH_'+side,reason_no_trade='RISK_REWARD_TOO_LOW',
                            prospective_rr={'A':round(rr_a,3),'B':round(rr_b,3)})
            return evidence
        risk=risk_sizing(equity_simulated,a,b,stop,reference)
        if risk is None:
            evidence.update(bias='WATCH_'+side,reason_no_trade='POSITION_BELOW_SIMULATED_MINIMUM')
            return evidence
        evidence['entries']=[{'name':'A','side':side,'entry_zone_center':round(a,2),
                              'source_pivot':es[0], 'allocation':'50% OF PRE-SIZED MAX TOTAL',
                              'trigger':'CLOSED_15M_REJECTION_AND_STRUCTURE_RECONFIRMATION',
                              'conditional_not_executable':True},
                             {'name':'B','side':side,'entry_zone_center':round(b,2),
                              'source_pivot':es[1], 'allocation':'50% OF PRE-SIZED MAX TOTAL',
                              'trigger':'NEW_CLOSED_15M_REJECTION_IF_ORIGINAL_STRUCTURE_STILL_VALID',
                              'conditional_not_executable':True}]
        evidence['targets']=[{'for_entry':'A','structural_take_profit':round(t_a,2),'source_pivot':ts[1],'gross_rr':round(rr_a,3)},
                             {'for_entry':'B','structural_take_profit':round(t_b,2),'source_pivot':ts[0],'gross_rr':round(rr_b,3)}]
        evidence['invalidation']={'hard_stop_both_legs':round(stop,2),'stop_is_not_placed_on_exchange':True,
                                  'cancel_pending_b_on_structure_break':True,
                                  'no_averaging_if_invalidation_reached':True}
        evidence['risk']=risk
        evidence['execution']='NONE: CONTEXT ONLY, REQUIRES NEXT CLOSED 15M CONFIRMATION AND SEPARATE RISK AUDIT'
        return evidence
    except (KeyError,IndexError,TypeError,PlanDataError,OverflowError,ZeroDivisionError) as error:
        evidence.update(bias='UNKNOWN',entries=[],targets=[],risk=None,
                        reason_no_trade=str(error) if isinstance(error,PlanDataError) else 'INVALID_INPUT')
        return evidence


def telegram_text(plan):
    """Text preview ONLY. Does not send Telegram messages."""
    lines=[f"I-GOD · PLAN DIARIO BTCUSDT | {plan['asof_utc']}",
           'SHADOW ONLY · NO ES UNA ORDEN', f"SESGO: {plan.get('bias')}"]
    indi=plan.get('indicators',{})
    for tf in ('daily','weekly'):
        v=indi.get(tf)
        if v:
            lines.append(f"{tf.upper()}: AO {v['ao']:.2f} (ant. {v['ao_previous']:.2f}); "
                         f"ADX {v['adx']:.2f}; +DI {v['plus_di']:.2f} / -DI {v['minus_di']:.2f}; "
                         f"BBWP {v['bbwp']:.2f} (ant. {v['bbwp_previous']:.2f})")
    for leg in plan.get('entries',[]):
        tp=next(t for t in plan['targets'] if t['for_entry']==leg['name'])
        lines.append(f"{leg['name']}: {leg['side']} zona {leg['entry_zone_center']:.2f} -> TP {tp['structural_take_profit']:.2f} "
                     f"(RR bruto {tp['gross_rr']:.2f}); SOLO tras confirmacion 15m")
    if plan.get('invalidation'):
        lines.append(f"INVALIDACION/STOP TEORICO: {plan['invalidation']['hard_stop_both_legs']:.2f} (NO colocado)")
    if plan.get('risk'):
        r=plan['risk'];lines.append(f"SIMULACION: {r['qty_per_leg_btc']} BTC/tramo; perd. estimada {r['maximum_combined_estimated_loss_usdt']} USDT "
                       '(NO garantiza limite real)')
    if plan.get('reason_no_trade'):lines.append('NO OPERAR: '+plan['reason_no_trade'])
    if plan.get('weekly_warning'):lines.append('AVISO 1W: '+plan['weekly_warning'])
    lines.extend(plan.get('warnings',[]))
    return '\n'.join(lines)
