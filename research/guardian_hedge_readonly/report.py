"""Pure HEDGE inventory interpretation. No exchange clients or action decisions."""
from decimal import Decimal,InvalidOperation

class Unverified(ValueError):
    pass

def number(value):
    if isinstance(value,bool) or value is None:raise Unverified('NUMBER_MISSING')
    try:n=Decimal(str(value))
    except (InvalidOperation,ValueError):raise Unverified('NUMBER_INVALID') from None
    if not n.is_finite():raise Unverified('NUMBER_INVALID')
    return n

def positive(value):
    n=number(value)
    if n<=0:raise Unverified('NONPOSITIVE_NUMBER')
    return n

def positions(rows):
    if not isinstance(rows,list):raise Unverified('POSITIONS_NOT_LIST')
    out=[];seen=set();accounts=set()
    for raw in rows:
        if not isinstance(raw,dict):raise Unverified('POSITION_MALFORMED')
        pid=raw.get('positionId')
        if not isinstance(pid,str) or not pid.isdecimal():raise Unverified('POSITION_ID_UNVERIFIED')
        if pid in seen:raise Unverified('DUPLICATE_POSITION_ID')
        seen.add(pid)
        if raw.get('symbol')!='BTCUSDT':raise Unverified('UNEXPECTED_SYMBOL')
        side={'BUY':'LONG','SELL':'SHORT','LONG':'LONG','SHORT':'SHORT'}.get(raw.get('side'))
        if not side:raise Unverified('SIDE_UNVERIFIED')
        if raw.get('marginMode') not in ('CROSS','ISOLATION') or raw.get('positionMode') not in ('HEDGE','ONE_WAY'):
            raise Unverified('MODE_UNVERIFIED')
        account=str(raw.get('subAccountId','MAIN_SCOPE_UNLABELLED'));accounts.add(account)
        out.append(dict(id=pid,side=side,mode=raw['positionMode'],margin_mode=raw['marginMode'],
            qty=positive(raw.get('qty')),entry=positive(raw.get('avgOpenPrice')),leverage=positive(raw.get('leverage')),
            margin=number(raw.get('margin')),liquidation=number(raw.get('liqPrice')),
            realized_excluding_costs=number(raw.get('realizedPNL')),unrealized=number(raw.get('unrealizedPNL')),
            fee_reported=number(raw.get('fee')),funding_reported=number(raw.get('funding'))))
    if len(accounts)>1:raise Unverified('MIXED_ACCOUNT_SCOPE')
    if len(out)>1 and any(p['mode']!='HEDGE' for p in out):raise Unverified('MULTI_POSITION_MODE_INCOHERENT')
    if len({p['side'] for p in out})!=len(out):raise Unverified('DUPLICATED_SIDE_REQUIRES_REVIEW')
    return sorted(out,key=lambda p:p['id'])

def partition_orders(rows,position_ids,complete):
    """Read-only partition of a COMPLETE wider reply, never trust server filtering."""
    if complete is not True:raise Unverified('ORDERS_PAGINATION_INCOMPLETE')
    if not isinstance(rows,list):raise Unverified('ORDERS_UNAVAILABLE')
    grouped={pid:[] for pid in position_ids};seen=set()
    for row in rows:
        if not isinstance(row,dict) or row.get('symbol')!='BTCUSDT' or row.get('positionId') not in grouped:
            raise Unverified('UNASSIGNED_ORDER_SCOPE')
        oid=row.get('id')
        if not isinstance(oid,str) or not oid or oid in seen:raise Unverified('DUPLICATE_OR_MISSING_ORDER_ID')
        seen.add(oid);grouped[row['positionId']].append(row)
    return grouped

def orders_report(position,rows,mark,last):
    """Separate each positionId. Never infer full protection from missing/zero qty."""
    result=dict(status='UNVERIFIED',tp_orders=0,sl_orders=0,explicit_market_sl_qty=Decimal(0),full_market_sl_orders=0,issues=[],risk_notes=[])
    if not isinstance(rows,list):result['issues']=['ORDERS_UNAVAILABLE'];return result
    seen=set()
    for row in rows:
        if not isinstance(row,dict) or row.get('positionId')!=position['id'] or row.get('symbol')!='BTCUSDT':
            result['issues'].append('ORDER_SCOPE_MISMATCH');continue
        oid=row.get('id')
        if not isinstance(oid,str) or not oid or oid in seen:
            result['issues'].append('ORDER_ID_MISSING_OR_DUPLICATE');continue
        seen.add(oid)
        try:
            tp=number(row.get('tpPrice') or 0);sl=number(row.get('slPrice') or 0)
            if tp>0:result['tp_orders']+=1
            if sl<=0:continue
            result['sl_orders']+=1
            quantity=number(row.get('slQty'))
            if quantity<=0:raise Unverified('SL_FULL_QUANTITY_SEMANTICS_UNVERIFIED')
            reference={'MARK_PRICE':mark,'LAST_PRICE':last}.get(row.get('slStopType'))
            if reference is None:raise Unverified('SL_TRIGGER_REFERENCE_UNVERIFIED')
            if row.get('slOrderType')!='MARKET':raise Unverified('SL_LIMIT_OR_TYPE_UNVERIFIED')
            if not (sl<reference if position['side']=='LONG' else sl>reference):raise Unverified('SL_TRIGGER_ALREADY_PASSED')
            liq=position['liquidation'];directional=liq<mark if position['side']=='LONG' else liq>mark
            if liq>0 and directional and not (sl>liq if position['side']=='LONG' else sl<liq):raise Unverified('SL_BEYOND_LIQUIDATION_REFERENCE')
            if liq>0 and not directional:result['risk_notes'].append('LIQUIDATION_DIRECTION_UNVERIFIED')
            result['explicit_market_sl_qty']+=quantity
            if quantity>=position['qty']:result['full_market_sl_orders']+=1
        except Unverified as error:result['issues'].append(str(error))
    if not rows:result['status']='NO_REGISTERED_TPSL_RETURNED'
    elif not result['issues'] and result['full_market_sl_orders']:
        result['status']='REGISTERED_EXPLICIT_FULL_MARKET_SL'
    elif result['sl_orders'] and not result['issues']:
        result['status']='PARTIAL_OR_SPLIT_COVERAGE_REQUIRES_REVIEW'
    elif not result['sl_orders'] and not result['issues']:result['status']='NO_REGISTERED_SL_RETURNED'
    return result

def build_report(rows,orders_by_id,mark,last):
    mark=positive(mark);last=positive(last)
    parsed=positions(rows);reports=[]
    for p in parsed:
        liq=p['liquidation'];distance=None
        if liq<=0:liq_status='DOCUMENTED_NONPOSITIVE_NO_ESTIMATE_CURRENTLY'
        else:
            distance=(mark-liq)/mark if p['side']=='LONG' else (liq-mark)/mark
            liq_status='CRITICAL_2PCT' if distance<=Decimal('.02') else 'POSITIVE_ESTIMATE'
            if distance<=0:
                liq_status='CROSS_HEDGE_DIRECTIONAL_LIQUIDATION_UNVERIFIED' if p['margin_mode']=='CROSS' else 'LIQUIDATION_REFERENCE_INCOHERENT_OR_CROSSED'
        reports.append(dict(**p,mark_notional=p['qty']*mark,liquidation_distance_fraction=distance,
            liquidation_status=liq_status,tpsl=orders_report(p,orders_by_id.get(p['id']),mark,last)))
    total=lambda field:sum((p[field] for p in parsed),Decimal(0))
    net=sum((p['qty']*(1 if p['side']=='LONG' else -1) for p in parsed),Decimal(0))
    return dict(status='READ_ONLY_REVIEW',trade_authority='NONE',protection_decision=False,positions=reports,
        gross_btc=total('qty'),net_btc=net,gross_notional=total('qty')*mark,net_notional=net*mark,
        sum_reported_position_margin=total('margin'),realized_excluding_costs=total('realized_excluding_costs'),
        unrealized=total('unrealized'),fee_reported=total('fee_reported'),funding_reported=total('funding_reported'),
        account_equity=None,account_risk='CROSS_ACCOUNT_RISK_NOT_INFERRED_FROM_NET_EXPOSURE',
        all_sides_explicit_sl_registered=bool(reports) and all(p['tpsl']['status']=='REGISTERED_EXPLICIT_FULL_MARKET_SL' for p in reports),
        limitations=['PENDING_REGISTRATION_IS_NOT_GUARANTEED_EXECUTION','CROSS_MARGIN_IS_SHARED_NOT_ADDITIVE_EQUITY',
            'FEES_AND_FUNDING_REPORTED_SEPARATELY_NO_UNVERIFIED_NETTING','NON_ATOMIC_API_SNAPSHOTS_REQUIRE_STABILITY_CHECK'])
