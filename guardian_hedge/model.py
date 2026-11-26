"""Pure exchange evidence interpretation, separate from every protection executor."""
from decimal import Decimal, InvalidOperation
import re

ZERO=Decimal(0)
NEAR_LIQUIDATION=Decimal('.02')  # Existing reference, never an execution permission.
ERROR_CODES=frozenset('''NUMBER_MISSING NUMBER_TOO_LARGE NUMBER_INVALID NUMBER_NONPOSITIVE UNSUPPORTED_ASSET_SCOPE
POSITIONS_INCOMPLETE POSITION_SCHEMA POSITION_ID_INVALID_OR_DUPLICATE POSITION_MODE_OR_SIDE_INVALID MARGIN_INVALID
ACCOUNT_SCOPE_MIXED POSITION_MODE_MIXED ACCOUNT_AMBIGUOUS ACCOUNT_SCOPE_UNVERIFIED ACCOUNT_COMPONENT_INVALID
ORDERS_UNAVAILABLE ORDER_SCHEMA ORDER_PROTECTION_FIELDS_MISSING ORDER_ID_INVALID_OR_DUPLICATE ORDER_POSITION_SCOPE_UNVERIFIED
ORDER_TRIGGER_OR_TYPE_UNVERIFIED SL_TRIGGER_PASSED LIMIT_SL_FILL_UNVERIFIED SL_BEYOND_LIQUIDATION_REFERENCE
ACCOUNT_POSITION_MODE_MISMATCH BONUS_ACCOUNT_RECONCILIATION_UNVERIFIED TICKER_SCHEMA TICKER_DUPLICATE TICKER_SCOPE_INCOMPLETE
RESPONSE_SCHEMA RESPONSE_TOTAL GET_SCOPE_BLOCKED CREDENTIALS_UNAVAILABLE READ_DEADLINE LOCAL_CLOCK_JUMP HTTP_UNAVAILABLE
RESPONSE_TOO_LARGE EXCHANGE_TIME_UNVERIFIED API_AUTH_OR_SCHEMA_UNVERIFIED READ_UNAVAILABLE ORDERS_INCOMPLETE ORDERS_CHANGED
ORDERS_TOTAL_INVALID ORDER_ASSET_SCOPE ORDERS_SNAPSHOT_TOO_LARGE POSITIONS_CHANGED_DURING_READ ORDERS_CHANGED_DURING_READ
ACCOUNT_CHANGED_DURING_READ READ_INVALIDATED_DURING_COLLECTION READ_PENDING READ_STALE LEGACY_PRIVATE_READ_FAILED'''.split())

class Unverified(ValueError):
    def __init__(self,code):super().__init__(code if code in ERROR_CODES else 'READ_UNAVAILABLE')

def num(value):
    if isinstance(value,bool) or value is None:raise Unverified('NUMBER_MISSING')
    if len(str(value))>100:raise Unverified('NUMBER_TOO_LARGE')
    try:value=Decimal(str(value))
    except (InvalidOperation,ValueError):raise Unverified('NUMBER_INVALID') from None
    if not value.is_finite():raise Unverified('NUMBER_INVALID')
    return value

def positive(value):
    value=num(value)
    if value<=0:raise Unverified('NUMBER_NONPOSITIVE')
    return value

def symbol(value):
    if not isinstance(value,str) or not re.fullmatch('[A-Z0-9]{2,24}USDT',value):raise Unverified('UNSUPPORTED_ASSET_SCOPE')
    return value

def positions(rows):
    if not isinstance(rows,list) or len(rows)>20:raise Unverified('POSITIONS_INCOMPLETE')
    result=[];ids=set();accounts=set()
    for row in rows:
        if not isinstance(row,dict):raise Unverified('POSITION_SCHEMA')
        pid=row.get('positionId')
        if not isinstance(pid,str) or not pid.isascii() or not pid.isdecimal() or len(pid)>80 or pid in ids:
            raise Unverified('POSITION_ID_INVALID_OR_DUPLICATE')
        ids.add(pid);accounts.add(str(row.get('subAccountId','MAIN_REQUEST_SCOPE')))
        side={'BUY':'LONG','SELL':'SHORT','LONG':'LONG','SHORT':'SHORT'}.get(row.get('side'))
        if side is None or row.get('positionMode') not in ('HEDGE','ONE_WAY') or row.get('marginMode') not in ('CROSS','ISOLATION'):
            raise Unverified('POSITION_MODE_OR_SIDE_INVALID')
        margin=num(row.get('margin'))
        if margin<0:raise Unverified('MARGIN_INVALID')
        result.append(dict(position_id=pid,symbol=symbol(row.get('symbol')),side=side,
            position_mode=row['positionMode'],margin_mode=row['marginMode'],qty=positive(row.get('qty')),
            entry=positive(row.get('avgOpenPrice')),leverage=positive(row.get('leverage')),margin=margin,
            liquidation=num(row['liqPrice']) if row.get('liqPrice') not in (None,'') else None,
            realized=num(row.get('realizedPNL')),unrealized=num(row.get('unrealizedPNL')),
            fees=num(row.get('fee')),funding=num(row.get('funding'))))
    if len(accounts)>1:raise Unverified('ACCOUNT_SCOPE_MIXED')
    if len({p['position_mode'] for p in result})>1:raise Unverified('POSITION_MODE_MIXED')
    return sorted(result,key=lambda p:(p['symbol'],p['side'],p['position_id']))

def account(raw):
    if isinstance(raw,list):
        if len(raw)!=1:raise Unverified('ACCOUNT_AMBIGUOUS')
        raw=raw[0]
    if not isinstance(raw,dict) or raw.get('marginCoin')!='USDT' or raw.get('positionMode') not in ('HEDGE','ONE_WAY'):
        raise Unverified('ACCOUNT_SCOPE_UNVERIFIED')
    result={k:num(raw.get(k)) for k in ('available','frozen','margin','crossUnrealizedPNL','isolationUnrealizedPNL','bonus')}
    if any(result[k]<0 for k in ('frozen','margin','bonus')):raise Unverified('ACCOUNT_COMPONENT_INVALID')
    result['position_mode']=raw['positionMode']
    result['wallet_components']=sum((result[k] for k in ('available','frozen','margin')),ZERO)
    # Same component convention as the audited V2 reader. Realized PnL/fees/funding
    # already affect the wallet; never add them again or allocate this per side.
    result['equity_components']=result['wallet_components']+result['crossUnrealizedPNL']+result['isolationUnrealizedPNL']
    result['available_plus_cross_pnl']=result['available']+result['crossUnrealizedPNL']
    return result

def partition_orders(rows,parsed):
    if not isinstance(rows,list):raise Unverified('ORDERS_UNAVAILABLE')
    known={p['position_id']:p['symbol'] for p in parsed};result={pid:[] for pid in known};seen=set()
    for row in rows:
        if not isinstance(row,dict):raise Unverified('ORDER_SCHEMA')
        if 'tpPrice' not in row and 'slPrice' not in row:raise Unverified('ORDER_PROTECTION_FIELDS_MISSING')
        oid=row.get('id');pid=row.get('positionId')
        if not isinstance(oid,str) or not oid.isascii() or not oid.isdecimal() or oid in seen:
            raise Unverified('ORDER_ID_INVALID_OR_DUPLICATE')
        if pid not in known or row.get('symbol')!=known[pid]:raise Unverified('ORDER_POSITION_SCOPE_UNVERIFIED')
        seen.add(oid);result[pid].append(row)
    return result

def coverage(p,rows,mark,last):
    out=dict(status='ABSENT',covered_qty=ZERO,requested_qty=p['qty'],tp=[],sl=[],issues=[])
    for row in rows:
        for kind in ('tp','sl'):
            raw_price=row.get(kind+'Price')
            if raw_price in (None,'','0',0):continue
            try:
                price=positive(raw_price);qty=positive(row.get(kind+'Qty'))
                trigger=row.get(kind+'StopType');order_type=row.get(kind+'OrderType')
                if trigger not in ('MARK_PRICE','LAST_PRICE') or order_type not in ('MARKET','LIMIT'):
                    raise Unverified('ORDER_TRIGGER_OR_TYPE_UNVERIFIED')
                item=dict(id=row['id'],price=price,qty=qty,trigger=trigger,type=order_type,
                    limit_price=num(row.get(kind+'OrderPrice')) if row.get(kind+'OrderPrice') not in (None,'') else None)
                out[kind].append(item)
                if kind!='sl':continue
                reference=mark if trigger=='MARK_PRICE' else last
                if not (price<reference if p['side']=='LONG' else price>reference):raise Unverified('SL_TRIGGER_PASSED')
                if order_type!='MARKET':raise Unverified('LIMIT_SL_FILL_UNVERIFIED')
                liq=p['liquidation']
                if liq is not None and liq>0 and ((liq<mark and p['side']=='LONG') or (liq>mark and p['side']=='SHORT')):
                    if not (price>liq if p['side']=='LONG' else price<liq):raise Unverified('SL_BEYOND_LIQUIDATION_REFERENCE')
                out['covered_qty']+=qty
            except Unverified as error:
                out['issues'].append(kind.upper()+'_'+str(error))
    sl_issues=[x for x in out['issues'] if x.startswith('SL_')]
    # An uncertain stop may not be called absent, nor assumed full from qty=0.
    if sl_issues:out['status']='UNVERIFIABLE'
    elif out['sl']:
        out['status']='FULL_REGISTERED' if out['covered_qty']>=p['qty'] else 'INSUFFICIENT'
        if sum((x['qty'] for x in out['sl']),ZERO)>p['qty']:out['status']='UNVERIFIABLE';out['issues'].append('SL_OVERCOVERAGE_REQUIRES_REVIEW')
    return out

def build_view(raw_positions,raw_account,raw_orders,tickers,*,started_at,completed_at):
    parsed=positions(raw_positions);acc=account(raw_account)
    if any(p['position_mode']!=acc['position_mode'] for p in parsed):raise Unverified('ACCOUNT_POSITION_MODE_MISMATCH')
    if acc['bonus']!=0:raise Unverified('BONUS_ACCOUNT_RECONCILIATION_UNVERIFIED')
    if not isinstance(tickers,list):raise Unverified('TICKER_SCHEMA')
    prices={}
    for row in tickers:
        if not isinstance(row,dict):raise Unverified('TICKER_SCHEMA')
        s=symbol(row.get('symbol'))
        if s in prices:raise Unverified('TICKER_DUPLICATE')
        prices[s]=(positive(row.get('markPrice')),positive(row.get('lastPrice')))
    required={p['symbol'] for p in parsed}|{'BTCUSDT'}
    if set(prices)!=required:raise Unverified('TICKER_SCOPE_INCOMPLETE')
    orders=partition_orders(raw_orders,parsed);gross=ZERO;net={};reasons=set();minimum=None
    for p in parsed:
        mark,last=prices[p['symbol']];p['mark']=mark;p['notional']=p['qty']*mark
        gross+=p['notional'];net[p['symbol']]=net.get(p['symbol'],ZERO)+p['notional']*(1 if p['side']=='LONG' else -1)
        p['coverage']=coverage(p,orders[p['position_id']],mark,last)
        p['liquidation_distance']=None;p['liquidation_state']='UNAVAILABLE'
        liq=p['liquidation']
        if liq is None:reasons.add('LIQUIDATION_UNAVAILABLE')
        elif liq<=0:p['liquidation_state']='DOCUMENTED_NO_CURRENT_ESTIMATE'
        else:
            distance=abs(mark-liq)/mark;p['liquidation_distance']=distance
            minimum=distance if minimum is None else min(minimum,distance)
            expected=liq<mark if p['side']=='LONG' else liq>mark
            p['liquidation_state']='REPORTED_REFERENCE' if expected else 'DIRECTIONAL_INTERPRETATION_UNVERIFIED'
            if not expected:reasons.add('LIQUIDATION_DIRECTION_UNVERIFIED')
            if distance<=NEAR_LIQUIDATION:reasons.add('LIQUIDATION_REFERENCE_WITHIN_2_PERCENT')
        if p['coverage']['status']!='FULL_REGISTERED':reasons.add('STOP_'+p['coverage']['status'])
    sums={k:sum((p[k] for p in parsed),ZERO) for k in ('realized','unrealized','fees','funding','margin')}
    cross=sum((p['unrealized'] for p in parsed if p['margin_mode']=='CROSS'),ZERO)
    isolated=sum((p['unrealized'] for p in parsed if p['margin_mode']=='ISOLATION'),ZERO)
    pnl_consistent=cross==acc['crossUnrealizedPNL'] and isolated==acc['isolationUnrealizedPNL']
    if not pnl_consistent:reasons.add('PNL_ACCOUNT_POSITION_MISMATCH')
    if acc['equity_components']<=0 or acc['available_plus_cross_pnl']<=0:reasons.add('NONPOSITIVE_ACCOUNT_RESOURCES')
    status='CRITICAL_REFERENCE' if reasons & {'NONPOSITIVE_ACCOUNT_RESOURCES','LIQUIDATION_REFERENCE_WITHIN_2_PERCENT'} else 'UNPROTECTED' if reasons & {'STOP_ABSENT','STOP_INSUFFICIENT'} else 'UNVERIFIED' if reasons else 'COVERAGE_REGISTERED'
    return dict(schema=1,read_complete=True,started_at=started_at,completed_at=completed_at,
        scope='MAIN_ACCOUNT_ALL_USDT_POSITIONS',positions=parsed,account=acc,position_sums=sums,
        gross_notional=gross,net_notional_by_symbol=net,risk=dict(status=status,reasons=sorted(reasons),
            nearest_liquidation_reference=minimum,maintenance_headroom=None,liquidation_risk_certified=False),
        pnl_reconciled=pnl_consistent,trade_authority='NONE',protection_execution=False)
