"""Narrow Bitunix adapter: reads, reduce-only ONE_WAY closes and owned SL only."""
from datetime import datetime,timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
import hashlib
import json
import secrets
import time
import requests
from guardian_bitunix import signature
from .accounting import stop_interval

D=Decimal
POSITIONS='/api/v1/futures/position/get_pending_positions'
TPSL='/api/v1/futures/tpsl/get_pending_orders'
TRADES='/api/v1/futures/trade/get_history_trades'
ORDERS='/api/v1/futures/trade/get_pending_orders'
DETAIL='/api/v1/futures/trade/get_order_detail'
HISTORY_POSITIONS='/api/v1/futures/position/get_history_positions'
ACCOUNT='/api/v1/futures/account'
TICKER='/api/v1/futures/market/tickers'
PAIRS='/api/v1/futures/market/trading_pairs'
KLINES='/api/v1/futures/market/kline'
REDUCE='/api/v1/futures/trade/place_order'
PLACE_STOP='/api/v1/futures/tpsl/place_order'
MODIFY_STOP='/api/v1/futures/tpsl/modify_order'
PLACE_POSITION_STOP='/api/v1/futures/tpsl/position/place_order'
MODIFY_POSITION_STOP='/api/v1/futures/tpsl/position/modify_order'
READS={POSITIONS,TPSL,TRADES,ORDERS,DETAIL,HISTORY_POSITIONS,ACCOUNT,TICKER,PAIRS,KLINES}
PUBLIC={TICKER,PAIRS,KLINES}


class Rejected(ValueError):
    pass


def count(value):
    if type(value) is int and value>=0:return value
    if isinstance(value,str) and value.isascii() and value.isdecimal():return int(value)
    raise ValueError('CAPITAL_TOTAL_INVALID')


def rows(data,key):
    if isinstance(data,list):return data,None
    if not isinstance(data,dict) or not isinstance(data.get(key),list):raise ValueError('CAPITAL_RESPONSE_SCHEMA')
    return data[key],count(data['total'])


class Client:
    def __init__(self,key,secret,*,transport=None,clock=time.time,execution=False,approval_hash=''):
        self.key,self.secret=key,secret
        self.http=transport or requests.Session();self.http.trust_env=False;self.http.auth=None
        self.clock,self.execution,self.approval_hash=clock,execution,approval_hash
        self.used=set();self._wire_permit=None;self.deadline=None

    def begin_cycle(self,seconds=8):
        self.deadline=self.clock()+seconds

    def _wire(self,method,path,params=None,body=None):
        if method=='POST':
            permit=(path,json.dumps(body,sort_keys=True,separators=(',',':')))
            if self._wire_permit!=permit:raise ValueError('CAPITAL_WIRE_PERMIT_REQUIRED')
            self._wire_permit=None
        elif method!='GET' or path not in READS:
            raise ValueError('CAPITAL_WIRE_METHOD_BLOCKED')
        remaining=5 if self.deadline is None else self.deadline-self.clock()
        if remaining<=0:raise ValueError('CAPITAL_CYCLE_TIME_BUDGET')
        params=params or {};payload=json.dumps(body,separators=(',',':')) if body is not None else ''
        nonce=secrets.token_hex(16);stamp=str(int(self.clock()*1000))
        headers={'Content-Type':'application/json','language':'en-US'}
        if path not in PUBLIC:
            headers.update({'api-key':self.key,'nonce':nonce,'timestamp':stamp,
                            'sign':signature(self.key,self.secret,nonce,stamp,params,payload)})
        # No retries: ambiguous writes require exchange reconciliation.
        try:
            response=self.http.request(method,'https://fapi.bitunix.com'+path,params=params,data=payload or None,
                                       headers=headers,timeout=(min(2,remaining/2),min(3,remaining/2)),allow_redirects=False)
            if response.status_code!=200:raise ValueError('CAPITAL_HTTP_UNAVAILABLE')
            server=parsedate_to_datetime(response.headers['Date']).timestamp()
            if abs(server-self.clock())>5:raise ValueError('CAPITAL_SERVER_TIME_UNVERIFIED')
            value=response.json()
            if not isinstance(value,dict) or type(value.get('code')) is not int:raise ValueError('CAPITAL_API_SCHEMA')
            if value['code']!=0:raise Rejected('CAPITAL_API_REJECTED')
            if 'data' not in value:raise ValueError('CAPITAL_API_SCHEMA')
            return value['data']
        except ValueError:raise
        except Exception:raise ValueError('CAPITAL_REQUEST_UNCERTAIN') from None

    def get(self,path,params):
        if path not in READS:raise ValueError('CAPITAL_READ_BLOCKED')
        allowed={POSITIONS:{'symbol','includeSubAccounts'},TPSL:{'symbol','positionId','limit','skip'},
                 TRADES:{'symbol','positionId','limit','skip'},HISTORY_POSITIONS:{'symbol','positionId','limit','skip'},
                 ORDERS:{'symbol','clientId','limit','skip'},DETAIL:{'clientId'},
                 ACCOUNT:{'marginCoin'},TICKER:{'symbols'},PAIRS:{'symbols'},
                 KLINES:{'symbol','interval','limit','type'}}
        if set(params)-allowed[path]:raise ValueError('CAPITAL_READ_BLOCKED')
        if path==ACCOUNT and params!={'marginCoin':'USDT'}:raise ValueError('CAPITAL_ACCOUNT_SCOPE')
        if path in (TICKER,PAIRS) and params!={'symbols':'BTCUSDT'}:raise ValueError('CAPITAL_SYMBOL_SCOPE')
        if path not in (ACCOUNT,TICKER,PAIRS,DETAIL) and params.get('symbol')!='BTCUSDT':raise ValueError('CAPITAL_SYMBOL_SCOPE')
        if path==POSITIONS and params.get('includeSubAccounts')!='false':raise ValueError('CAPITAL_MAIN_ACCOUNT_ONLY')
        if path==KLINES and params!={'symbol':'BTCUSDT','interval':'1h','limit':100,'type':'MARK_PRICE'}:
            raise ValueError('CAPITAL_CLOSED_MARK_CONTEXT_ONLY')
        return self._wire('GET',path,params)

    def pages(self,path,params,key):
        result=[];expected=None
        for skip in range(0,2000,100):
            page,total=rows(self.get(path,dict(params,limit=100,skip=skip)),key)
            if total is not None:
                if expected is not None and total!=expected:raise ValueError('CAPITAL_PAGINATION_CHANGED')
                expected=total
            result.extend(page)
            if len(page)<100 or (expected is not None and len(result)==expected):
                if expected is not None and len(result)!=expected:raise ValueError('CAPITAL_PAGINATION_INCOMPLETE')
                return result
        raise ValueError('CAPITAL_PAGINATION_INCOMPLETE')

    def mutate(self,path,body,*,journal,intent_id,policy_hash,position,owned_order_ids=()):
        """No callers in production until explicit GLOBAL protection authorization."""
        from .global_policy import POLICY_HASH
        if (not self.execution or policy_hash!=POLICY_HASH or policy_hash!=self.approval_hash
                or journal.poisoned):raise ValueError('CAPITAL_EXECUTION_DISARMED')
        if intent_id in self.used or not any(r['id']==intent_id and r['kind']=='INTENT' for r in journal.rows):
            raise ValueError('CAPITAL_DURABLE_FRESH_INTENT_REQUIRED')
        if journal.pending() is None:raise ValueError('CAPITAL_INTENT_MISSING')
        pending=journal.pending()
        if pending.get('path')!=path or pending.get('body')!=body:raise ValueError('CAPITAL_INTENT_SHAPE_MISMATCH')
        if int(self.clock()*1000)-pending['prepared_ms'] not in range(0,5001):raise ValueError('CAPITAL_PREFLIGHT_EXPIRED')
        if (position['symbol']!='BTCUSDT' or position['positionMode']!='ONE_WAY'
                or position.get('side') not in ('LONG','SHORT')
                or not 0<=int(self.clock()*1000)-position.get('_observed_ms',-10_000)<=5000):
            raise ValueError('CAPITAL_POSITION_SCOPE_OR_FRESHNESS')
        qty=D(str(position['qty']))
        if not qty.is_finite() or qty<=0:raise ValueError('CAPITAL_QTY_INVALID')
        if path==REDUCE:
            required={'symbol','positionId','side','orderType','qty','reduceOnly','clientId'}
            if (set(body)!=required or body['symbol']!='BTCUSDT' or body['positionId']!=position['positionId']
                    or body['side']!=('SELL' if position['side']=='LONG' else 'BUY')
                    or body['orderType']!='MARKET' or body['reduceOnly'] is not True
                    or not D('0')<D(body['qty'])<=qty or body['clientId']!=pending['client_id']):
                raise ValueError('CAPITAL_REDUCTION_BLOCKED')
        elif path in (PLACE_POSITION_STOP,MODIFY_POSITION_STOP):
            if (set(body)!={'symbol','positionId','slPrice','slStopType'} or body['symbol']!='BTCUSDT'
                    or body['positionId']!=position['positionId'] or body['slStopType']!='MARK_PRICE'):
                raise ValueError('CAPITAL_POSITION_STOP_BLOCKED')
            if path==MODIFY_POSITION_STOP:
                orders=self.pages(TPSL,{'symbol':'BTCUSDT','positionId':position['positionId']},'orderList')
                owned=[r for r in orders if str(r.get('id')) in owned_order_ids
                       and owned_order_ids[str(r['id'])].get('position_dynamic') is True
                       and owned_order_ids[str(r['id'])]['position_id']==position['positionId']]
                if len(owned)!=1 or owned[0].get('tpPrice') not in (None,'',0,'0'):
                    raise ValueError('CAPITAL_MANUAL_POSITION_STOP_UNTOUCHABLE')
        else:raise ValueError('CAPITAL_MUTATION_PATH_BLOCKED')
        if path in (PLACE_STOP,MODIFY_STOP,PLACE_POSITION_STOP,MODIFY_POSITION_STOP):
            price=D(body['slPrice']);mark=D(str(pending['mark']));liq=D(str(position['liqPrice']))
            if not stop_interval(position['side'],mark,liq,price):raise ValueError('CAPITAL_STOP_INTERVAL')
        if not 0<=int(self.clock()*1000)-position['_observed_ms']<=5000:raise ValueError('CAPITAL_PREFLIGHT_EXPIRED')
        self.used.add(intent_id)  # consumed before the one and only POST
        self._wire_permit=(path,json.dumps(body,sort_keys=True,separators=(',',':')))
        return self._wire('POST',path,body=body)
