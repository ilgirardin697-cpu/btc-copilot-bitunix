"""Only unauthenticated official Binance Spot GETs, no configurable host/proxy."""
import json
import urllib.error
import urllib.parse
import urllib.request
import numpy as np

from .features import HOUR, MINUTE, require_rows
from .journal import EvidenceError

BASE='https://api.binance.com'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PublicSpot:
    def __init__(self, store, clock, opener=None):
        self.store,self.clock=store,clock
        self.opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())

    def get(self, path, params):
        if path not in ('/api/v3/time','/api/v3/klines'):
            raise EvidenceError('PUBLIC_PATH_REJECTED')
        if path=='/api/v3/time' and params:
            raise EvidenceError('PUBLIC_PARAMETERS_REJECTED')
        if path.endswith('klines'):
            if (set(params)!={'symbol','interval','startTime','endTime','limit'} or params['symbol']!='BTCUSDT'
                or params['interval'] not in ('1h','1m') or type(params['limit']) is not int
                or not 1<=params['limit']<=1000 or type(params['startTime']) is not int
                or type(params['endTime']) is not int or params['endTime']>=self.clock.now_ms()
                or params['startTime']>params['endTime']):
                raise EvidenceError('PUBLIC_PARAMETERS_REJECTED')
        request=urllib.request.Request(BASE+path+('?' + urllib.parse.urlencode(params) if params else ''),
                                       headers={'User-Agent':'IGOD-Price-Research/1','Accept':'application/json'},method='GET')
        started=self.clock.now_ms(); mono=self.clock.monotonic_ms()
        try:
            response=self.opener.open(request,timeout=10)
            with response:
                status=response.status; content_type=response.headers.get('Content-Type','')
                raw=response.read(2_097_153)
        except urllib.error.HTTPError as e:
            status=e.code; content_type=e.headers.get('Content-Type',''); raw=e.read(2_097_153)
        except (OSError,TimeoutError,urllib.error.URLError):
            raise EvidenceError('PUBLIC_NETWORK_UNAVAILABLE') from None
        received=self.clock.now_ms(); elapsed=self.clock.monotonic_ms()-mono
        if len(raw)>2_097_152:
            raise EvidenceError('PUBLIC_RESPONSE_TOO_LARGE')
        sha=self.store.archive(raw)
        meta=dict(path=path,params=params,status=status,content_type=content_type,
                  requested_at=started,received_at=received,elapsed_ms=elapsed,
                  monotonic_received_ms=self.clock.monotonic_ms(),raw_sha256=sha,bytes=len(raw))
        if status!=200:
            error=EvidenceError('PUBLIC_HTTP_'+str(status)); error.meta=meta
            raise error
        try:
            value=json.loads(raw)
        except (ValueError,UnicodeError):
            error=EvidenceError('PUBLIC_JSON_INVALID');error.meta=meta
            raise error from None
        return value,meta

    def clock_check(self):
        value,meta=self.get('/api/v3/time',{})
        server=value.get('serverTime') if isinstance(value,dict) else None
        if type(server) is not int:
            error=EvidenceError('PUBLIC_CLOCK_SCHEMA');error.meta=meta
            raise error
        midpoint=(meta['requested_at']+meta['received_at'])/2
        skew=server-midpoint
        if meta['elapsed_ms']>5000 or abs(skew)>2000 or meta['received_at']<meta['requested_at']:
            error=EvidenceError('CLOCK_UNVERIFIED');error.meta=meta
            raise error
        return dict(meta,server_time=server,midpoint_skew_ms=skew)

    def klines(self, start, end, interval):
        step=HOUR if interval=='1h' else MINUTE
        n=(end-start)//step
        if end<=start or (end-start)%step or not 1<=n<=1000 or start%step:
            raise EvidenceError('PUBLIC_RANGE_REJECTED')
        value,meta=self.get('/api/v3/klines',dict(symbol='BTCUSDT',interval=interval,startTime=start,endTime=end-1,limit=n))
        try:
            arr=decode_klines(value,start,end,step)
        except EvidenceError as error:
            error.meta=meta
            raise
        return arr,meta


def decode_klines(value,start,end,step):
    if not isinstance(value,list):
        raise EvidenceError('PUBLIC_KLINES_NOT_LIST')
    out=[]
    for row in value:
        if (not isinstance(row,list) or len(row)!=12 or type(row[0]) is not int or type(row[6]) is not int
            or row[6]!=row[0]+step-1 or row[0]%step):
            raise EvidenceError('PUBLIC_KLINE_SCHEMA_OR_TIME')
        try:
            vals=[float(v) for v in row[1:5]]
            base,taker=float(row[5]),float(row[9])
        except (TypeError,ValueError):
            raise EvidenceError('PUBLIC_NUMERIC_SCHEMA') from None
        if not np.isfinite([base,taker]).all() or not 0<=taker<=base:
            raise EvidenceError('PUBLIC_VOLUME_INVALID')
        out.append([row[0],*vals])
    arr=np.array(out,float).reshape(-1,5)
    try:
        require_rows(arr,start,end,step)
    except ValueError:
        raise EvidenceError('PUBLIC_GAP_DUPLICATE_OR_OHLC') from None
    return arr
