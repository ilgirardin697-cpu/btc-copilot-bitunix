"""Signed protection accounting; no clients, storage or execution authority."""
from decimal import Decimal
import hashlib
import json

D=Decimal
ZERO=D('0')


def number(value):
    if value is None or isinstance(value,bool):raise ValueError('CAPITAL_NUMBER_MISSING_OR_INVALID')
    result=D(str(value))
    if not result.is_finite():raise ValueError('CAPITAL_NONFINITE')
    return result


def timestamp_ms(value):
    if type(value) is int and value>=0:return value
    if isinstance(value,str) and value.isascii() and value.isdecimal():return int(value)
    raise ValueError('CAPITAL_ANCHOR_TIME_UNVERIFIED')


def stop_interval(side,mark,liquidation,price):
    mark,liquidation,price=map(number,(mark,liquidation,price))
    if side not in ('LONG','SHORT') or min(mark,price)<=0:return False
    # A finite <=0 is the documented absence of a liquidation price, not missing data.
    if side=='LONG':return price<mark and (liquidation<=0 or liquidation<price)
    return mark<price and (liquidation<=0 or price<liquidation)


def critical_liquidation(side,mark,liquidation,fraction):
    mark,liquidation,fraction=map(number,(mark,liquidation,fraction))
    if side not in ('LONG','SHORT') or mark<=0:raise ValueError('CAPITAL_MARK_OR_SIDE_INVALID')
    if liquidation<=0:return False
    distance=mark-liquidation if side=='LONG' else liquidation-mark
    return distance/mark<=fraction


def projected_net(settled_net,side,qty,entry,price,exit_cost_rate):
    if side not in ('LONG','SHORT'):raise ValueError('CAPITAL_SIDE_INVALID')
    settled_net,qty,entry,price,exit_cost_rate=map(number,(settled_net,qty,entry,price,exit_cost_rate))
    if qty<0 or min(entry,price)<=0 or exit_cost_rate<0:raise ValueError('CAPITAL_PROJECTION_INVALID')
    direction=D('1') if side=='LONG' else D('-1')
    # Clamp only a displayed loss, never the mark-to-market result before this sum.
    return settled_net+direction*qty*(price-entry)-qty*price*exit_cost_rate


def settle(trades,side,funding,expected_qty):
    if side not in ('LONG','SHORT'):raise ValueError('CAPITAL_SIDE_INVALID')
    opening='BUY' if side=='LONG' else 'SELL'
    gross=fees=opened=closed=ZERO
    ids=set()
    for trade in trades:
        identifier=trade['tradeId']
        if not isinstance(identifier,str) or not identifier or identifier in ids:raise ValueError('CAPITAL_TRADE_IDS_INVALID')
        ids.add(identifier)
        if trade.get('symbol')!='BTCUSDT' or trade.get('side') not in ('BUY','SELL'):raise ValueError('CAPITAL_TRADE_SCOPE')
        qty=number(trade['qty'])
        if qty<=0:raise ValueError('CAPITAL_TRADE_QTY_INVALID')
        if trade['side']==opening:opened+=qty
        else:closed+=qty
        gross+=number(trade['realizedPNL']);fees+=number(trade['fee'])
    if opened<=0 or opened-closed!=number(expected_qty):raise ValueError('CAPITAL_FILL_BALANCE_UNVERIFIED')
    funding=number(funding)
    digest=hashlib.sha256(json.dumps(sorted(trades,key=lambda r:r['tradeId']),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return dict(gross=str(gross),fees=str(fees),funding=str(funding),net=str(gross-fees+funding),
                opened_qty=str(opened),closed_qty=str(closed),trade_count=len(trades),trade_digest=digest)
