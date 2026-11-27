"""Dedicated GET-only reader. Fixed origin, closed scopes, no mutation interface."""
from email.utils import parsedate_to_datetime
import hashlib
import json
import secrets
import time
import requests
from .model import Unverified,positions,symbol,build_view,account

ORIGIN='https://fapi.bitunix.com'
POSITIONS='/api/v1/futures/position/get_pending_positions'
ACCOUNT='/api/v1/futures/account'
TPSL='/api/v1/futures/tpsl/get_pending_orders'
REGULAR='/api/v1/futures/trade/get_pending_orders'
TICKER='/api/v1/futures/market/tickers'

def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()

def rows(data,key):
    if isinstance(data,list):return data,None
    if not isinstance(data,dict) or not isinstance(data.get(key),list):raise Unverified('RESPONSE_SCHEMA')
    total=data.get('total')
    if isinstance(total,str) and total.isascii() and total.isdecimal():total=int(total)
    if type(total) is not int or total<len(data[key]):raise Unverified('RESPONSE_TOTAL')
    return data[key],total

class Reader:
    def __init__(self,key,secret,*,transport=None,clock=time.time,monotonic=time.monotonic,sleep=time.sleep):
        self._key,self._secret=key,secret
        self._http=transport or requests.Session();self._http.trust_env=False;self._http.auth=None
        self.clock,self.monotonic=clock,monotonic
        self.deadline=None;self.evidence=[];self.sleep=sleep;self.last_request=None

    def get(self,path,params):
        valid=(path==POSITIONS and params=={'includeSubAccounts':'false'}) or (path==ACCOUNT and params=={'marginCoin':'USDT'})
        if path in (TPSL,REGULAR):
            valid=(set(params)=={'symbol','limit','skip'} and symbol(params['symbol'])==params['symbol'] and params['limit']==100
                   and type(params['skip']) is int and 0<=params['skip']<1000 and params['skip']%100==0)
        if path==TICKER:
            values=params.get('symbols','').split(',')
            valid=set(params)=={'symbols'} and 1<=len(values)<=21 and values==sorted(set(values)) and all(symbol(v)==v for v in values)
        if not valid:raise Unverified('GET_SCOPE_BLOCKED')
        if not self._key or not self._secret:raise Unverified('CREDENTIALS_UNAVAILABLE')
        remaining=15 if self.deadline is None else self.deadline-self.monotonic()
        if remaining<=0:raise Unverified('READ_DEADLINE')
        if self.last_request is not None:
            pause=max(0,.15-(self.monotonic()-self.last_request))
            if pause>=remaining:raise Unverified('READ_DEADLINE')
            if pause:self.sleep(pause)  # Only the passive worker can wait here.
        self.last_request=self.monotonic()
        start=self.clock();mono=self.monotonic()
        headers={'Content-Type':'application/json','language':'en-US'}
        if path!=TICKER:
            nonce=secrets.token_hex(16);stamp=str(int(start*1000))
            canonical=''.join(k+str(params[k]) for k in sorted(params))
            first=hashlib.sha256((nonce+stamp+self._key+canonical).encode()).hexdigest()
            headers.update({'api-key':self._key,'nonce':nonce,'timestamp':stamp,
                'sign':hashlib.sha256((first+self._secret).encode()).hexdigest()})
        try:
            response=self._http.get(ORIGIN+path,params=params,headers=headers,
                timeout=(min(2,remaining/2),min(3,remaining/2)),allow_redirects=False)
            end=self.clock()
            if abs((end-start)-(self.monotonic()-mono))>1:raise Unverified('LOCAL_CLOCK_JUMP')
            if self.deadline is not None and self.monotonic()>self.deadline:raise Unverified('READ_DEADLINE')
            if response.status_code!=200:raise Unverified('HTTP_UNAVAILABLE')
            if len(response.content)>1024*1024:raise Unverified('RESPONSE_TOO_LARGE')
            server=parsedate_to_datetime(response.headers['Date']).timestamp()
            if abs(server-end)>5:raise Unverified('EXCHANGE_TIME_UNVERIFIED')
            value=response.json()
            if not isinstance(value,dict) or type(value.get('code')) is not int or value['code']!=0 or 'data' not in value:
                raise Unverified('API_AUTH_OR_SCHEMA_UNVERIFIED')
            self.evidence.append(dict(path=path,params=dict(params),requested_at=start,received_at=end,
                exchange_time=server,http_status=200,response_sha256=hashlib.sha256(response.content).hexdigest()))
            return value['data']
        except Unverified:raise
        except Exception:raise Unverified('READ_UNAVAILABLE') from None

    def position_rows(self):
        data,total=rows(self.get(POSITIONS,{'includeSubAccounts':'false'}),'positionList')
        if total is not None and total!=len(data):raise Unverified('POSITIONS_INCOMPLETE')
        positions(data)  # Whole response, never pick the first side or silently drop assets.
        return data

    def order_rows(self,symbols,path=TPSL):
        result=[]
        for name in sorted(symbols):
            expected=None;pages=[];complete=False
            for skip in range(0,1000,100):
                page,total=rows(self.get(path,dict(symbol=name,limit=100,skip=skip)),'orderList')
                if len(page)>100:raise Unverified('ORDERS_INCOMPLETE')
                if total is not None:
                    if expected is not None and expected!=total:raise Unverified('ORDERS_CHANGED')
                    expected=total
                    if total<skip+len(page):raise Unverified('ORDERS_TOTAL_INVALID')
                if any(not isinstance(row,dict) or row.get('symbol')!=name for row in page):raise Unverified('ORDER_ASSET_SCOPE')
                pages+=page
                if len(page)<100 or (expected is not None and expected==len(pages)):
                    complete=expected is None or len(pages)==expected;break
            if not complete:raise Unverified('ORDERS_INCOMPLETE')
            result+=pages
            if len(result)>500:raise Unverified('ORDERS_SNAPSHOT_TOO_LARGE')
        return result

    def collect(self):
        self.deadline=self.monotonic()+15;self.evidence=[];start=self.clock()
        acc1=self.get(ACCOUNT,{'marginCoin':'USDT'});a1=account(acc1)
        raw=self.position_rows();parsed=positions(raw);assets={p['symbol'] for p in parsed}|{'BTCUSDT'}
        quotes=self.get(TICKER,{'symbols':','.join(sorted(assets))})
        orders1=self.order_rows(assets)
        regular1=self.order_rows(assets,REGULAR)
        after=self.position_rows()
        # Require stable identity, size, modes, entry, realized costs and margin.
        def shape(data):
            return [{k:v for k,v in p.items() if k not in ('unrealized','liquidation')} for p in positions(data)]
        if shape(raw)!=shape(after):raise Unverified('POSITIONS_CHANGED_DURING_READ')
        orders2=self.order_rows(assets)
        regular2=self.order_rows(assets,REGULAR)
        canonical_orders=lambda data:sorted(data,key=lambda row:str(row.get('id','')))
        if fingerprint(canonical_orders(orders1))!=fingerprint(canonical_orders(orders2)):raise Unverified('ORDERS_CHANGED_DURING_READ')
        by_id=lambda data:sorted(data,key=lambda row:str(row.get('orderId','')))
        if fingerprint(by_id(regular1))!=fingerprint(by_id(regular2)):raise Unverified('ORDERS_CHANGED_DURING_READ')
        acc2=self.get(ACCOUNT,{'marginCoin':'USDT'});a2=account(acc2)
        for k in ('available','frozen','margin','bonus','position_mode'):
            if a1[k]!=a2[k]:raise Unverified('ACCOUNT_CHANGED_DURING_READ')
        # Value exposure and SL triggers with a NEW quote after the second
        # positions/orders/account read. HTTP Date is not a market event time.
        final_quotes=self.get(TICKER,{'symbols':','.join(sorted(assets))})
        complete=self.clock()
        if not 0<=complete-start<=15:raise Unverified('READ_DEADLINE')
        result=build_view(after,acc2,orders2,final_quotes,started_at=start,completed_at=complete,regular_orders=regular2)
        result['evidence']=list(self.evidence);result['source_hash']=fingerprint(self.evidence)
        result['observed_at']=min(row['requested_at'] for row in self.evidence)
        result['component_times']={name:{k:next(row for row in reversed(self.evidence) if row['path']==path)[k]
            for k in ('requested_at','received_at','exchange_time')} for name,path in
            (('ticker',TICKER),('positions',POSITIONS),('account',ACCOUNT),('tpsl',TPSL),('regular_orders',REGULAR))}
        result['ticker_event_time_verified']=False
        result['ticker_changed_during_read']=fingerprint(quotes)!=fingerprint(final_quotes)
        result['account_pnl_changed_during_read']=any(a1[k]!=a2[k] for k in ('crossUnrealizedPNL','isolationUnrealizedPNL'))
        return result
