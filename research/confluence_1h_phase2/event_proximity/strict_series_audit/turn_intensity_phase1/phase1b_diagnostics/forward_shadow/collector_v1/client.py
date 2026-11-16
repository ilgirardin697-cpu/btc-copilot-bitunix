"""Unsigned GET-only USD-M client preparation. No daemon or observer connection."""
import http.client,ssl,time,json,sys
from urllib.parse import urlencode
from decimal import Decimal
import numpy as np
from ..market import Receipt,klines,HOUR

HOST='fapi.binance.com'
PATHS={'/fapi/v1/time','/fapi/v1/klines','/fapi/v1/fundingRate'}
MAX_BODY=2000000

class PublicFailure(RuntimeError):pass

class PublicClient:
    def __init__(self,spool=None,enabled=False,network_allowed=False,network_authorization_ref=None,fixture_connection=None,clock=None,monotonic=None):
        self.spool=spool;self.enabled=enabled;self.network_allowed=network_allowed;self.authorization=network_authorization_ref
        self.fixture=fixture_connection;self.clock=clock or (lambda:int(time.time()*1000));self.monotonic=monotonic or time.monotonic_ns
        if fixture_connection is not None and network_allowed:raise ValueError('FIXTURE_CANNOT_CERTIFY_LIVE_NETWORK')
    def _get(self,path,query,exchange_time=None,clock_receipt_hash=None):
        if not self.enabled:raise PublicFailure('COLLECTOR_DISABLED')
        if path not in PATHS:raise PublicFailure('PUBLIC_PATH_REJECTED')
        if path=='/fapi/v1/time':
            if query:raise PublicFailure('TIME_QUERY_REJECTED')
        else:
            expected={'symbol','startTime','endTime','limit'}|({'interval'} if path.endswith('klines') else set())
            if set(query)!=expected or query['symbol']!='BTCUSDT' or any(type(query[k]) is not int for k in ('startTime','endTime','limit')):raise PublicFailure('QUERY_REJECTED')
            if query['startTime']>query['endTime']:raise PublicFailure('QUERY_RANGE_REJECTED')
            if path.endswith('klines') and (query['interval']!='1h' or not 1<=query['limit']<=1500):raise PublicFailure('H1_LIMIT_REJECTED')
            if path.endswith('fundingRate') and (query['limit']!=1000 or query['endTime']-query['startTime']>7*24*HOUR):raise PublicFailure('FUNDING_WINDOW_REJECTED')
        if self.fixture is None:
            if not self.network_allowed or not self.authorization:raise PublicFailure('SEPARATE_PUBLIC_NETWORK_APPROVAL_REQUIRED')
            if sys.version_info[:3]!=(3,12,12) or np.__version__!='2.3.5':raise PublicFailure('PINNED_ENVIRONMENT_REQUIRED')
        if self.spool is None:raise PublicFailure('INDEPENDENT_STORAGE_REQUIRED')
        start=self.clock();mono=self.monotonic();conn=None;raw=b'';status=0;ctype=None
        origin='OFFLINE_FIXTURE' if self.fixture else 'LIVE_PUBLIC_HTTPS'
        try:
            conn=self.fixture() if self.fixture else http.client.HTTPSConnection(HOST,443,timeout=10,context=ssl.create_default_context())
            target=path+('?'+urlencode(query) if query else '')
            conn.request('GET',target,headers={'Accept':'application/json','User-Agent':'I-GOD-public-data-research'})
            response=conn.getresponse();status=int(response.status);ctype=response.getheader('Content-Type');raw=response.read(MAX_BODY+1)
        except Exception:
            self.spool.append(dict(kind='REQUEST_FAILURE',origin=origin,url='https://'+HOST+path,params=query,method='GET',
                                   request_started_ms=start,received_ms=self.clock(),status=status,error='PUBLIC_TRANSPORT_FAILURE'),raw[:MAX_BODY])
            raise PublicFailure('PUBLIC_TRANSPORT_FAILURE') from None
        finally:
            if conn:conn.close()
        received=self.clock();elapsed=self.monotonic()-mono
        meta=dict(kind='PUBLIC_HTTP',origin=origin,url='https://'+HOST+path,params=dict(query),method='GET',
                  request_started_ms=start,received_ms=received,elapsed_ns=elapsed,status=status,content_type=ctype,
                  exchange_time_ms=exchange_time,clock_receipt_hash=clock_receipt_hash,body_truncated=len(raw)>MAX_BODY,
                  numerical_environment=dict(python='.'.join(map(str,sys.version_info[:3])),numpy=np.__version__))
        receipt=self.spool.append(meta,raw)
        if len(raw)>MAX_BODY:raise PublicFailure('PUBLIC_BODY_TOO_LARGE')
        if received<start or elapsed<0 or abs((received-start)-elapsed/1000000)>2000:raise PublicFailure('CLOCK_DISCONTINUITY')
        if status!=200:raise PublicFailure('PUBLIC_HTTP_'+str(status))  # redirects never followed
        return receipt
    def _validated(self,record,code,exchange_time=None):
        self.spool.append(dict(kind='VALIDATION',source_record=record['record_hash'],code=code,exchange_time_ms=exchange_time,at_ms=self.clock()),b'')
    def server_time(self):
        r=self._get('/fapi/v1/time',{});data=json.loads(r['body']);meta=r['metadata']
        if not isinstance(data,dict) or set(data)!={'serverTime'} or type(data['serverTime']) is not int:raise PublicFailure('SERVER_TIME_SCHEMA')
        t=data['serverTime'];mid=(meta['request_started_ms']+meta['received_ms'])/2
        if abs(t-mid)>2000 or meta['received_ms']-meta['request_started_ms']>3000:raise PublicFailure('SERVER_CLOCK_UNCERTAIN')
        self._validated(r,'PUBLIC_CLOCK_OK',t);return t,r
    def closed_hours(self,start,end):
        if type(start) is not int or type(end) is not int or start%HOUR or (end+1)%HOUR or end<start:raise PublicFailure('CLOSED_H1_RANGE_REQUIRED')
        expected=(end-start+1)//HOUR
        if not 1<=expected<=1500:raise PublicFailure('PAGE_SIZE_REJECTED')
        exchange,clock_record=self.server_time()
        if end>=exchange:raise PublicFailure('OPEN_CANDLE_REQUEST_REJECTED')
        query=dict(symbol='BTCUSDT',interval='1h',startTime=start,endTime=end,limit=expected);r=self._get('/fapi/v1/klines',query,exchange,clock_record['record_hash']);meta=r['metadata']
        parsed=klines(Receipt(r['body'],meta['url'],query,meta['request_started_ms'],meta['received_ms'],exchange,meta['status']))
        if len(parsed)!=expected:raise PublicFailure('INCOMPLETE_CLOSED_PAGE')
        self._validated(r,'CLOSED_H1_COMPLETE',exchange)
        return dict(receipt=r,exchange_time_ms=exchange,clock_receipt_hash=clock_record['record_hash'],rows=parsed,
                    observation_or_prediction_emitted=False)
    def funding_history(self,start,end):
        if type(start) is not int or type(end) is not int or start>end or end-start>7*24*HOUR:raise PublicFailure('FUNDING_WINDOW_REJECTED')
        exchange,clock_record=self.server_time()
        if end>exchange:raise PublicFailure('FUTURE_FUNDING_REQUEST')
        query=dict(symbol='BTCUSDT',startTime=start,endTime=end,limit=1000);r=self._get('/fapi/v1/fundingRate',query,exchange,clock_record['record_hash']);data=json.loads(r['body'])
        if not isinstance(data,list) or len(data)>=1000:raise PublicFailure('FUNDING_COMPLETENESS_UNKNOWN')
        previous=None;complete=True
        for row in data:
            if not isinstance(row,dict) or set(row)-{'symbol','fundingTime','fundingRate','markPrice','rateType'}:raise PublicFailure('FUNDING_SCHEMA')
            if not {'symbol','fundingTime','fundingRate'}<=set(row) or row['symbol']!='BTCUSDT' or row.get('rateType','Regular')!='Regular':raise PublicFailure('FUNDING_SCHEMA')
            t=row['fundingTime'];rate=Decimal(str(row['fundingRate']));mark=Decimal(str(row['markPrice'])) if row.get('markPrice') else None
            if type(t) is not int or not start<=t<=end or previous is not None and t<=previous or not rate.is_finite():raise PublicFailure('FUNDING_TIME_OR_RATE')
            if mark is None:complete=False
            elif not mark.is_finite() or mark<=0:raise PublicFailure('FUNDING_MARK')
            previous=t
        self._validated(r,'FUNDING_VALIDATED' if complete else 'FUNDING_MARK_UNKNOWN',exchange)
        return dict(receipt=r,clock_receipt_hash=clock_record['record_hash'],exchange_time_ms=exchange,mark_complete=complete,rows=data,
                    observation_or_prediction_emitted=False)
