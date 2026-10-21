"""Exact private USD-M transport; a single complete closed week per GET."""
from decimal import Decimal
import json
import urllib.request as http
from urllib.parse import urlencode
from .protocol import HOUR, WEEK, MONDAY, digest

PRIVATE_URL='http://bitman-market-data.railway.internal:8080/fapi/v1/klines'
MAX_BYTES=262144


class NoRedirect(http.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def validate_url(url):
    if type(url) is not str or url!=PRIVATE_URL:
        raise ValueError('INVALID_WEEKLY_MARKET_URL')
    return url


def aggregate(rows,opening,now):
    if type(opening) is not int or (opening-MONDAY)%WEEK or opening+WEEK>int(now):
        raise ValueError('WEEK_NOT_CLOSED')
    if type(rows) is not list or len(rows)!=168:
        raise ValueError('WEEK_REQUIRES_168_CLOSED_HOURS')
    for i,row in enumerate(rows):
        if type(row) is not list or len(row)!=12 or type(row[0]) is not int or type(row[6]) is not int:
            raise ValueError('HOURLY_SCHEMA')
        if row[0]!=opening+i*HOUR or row[6]!=row[0]+HOUR-1 or row[6]>=now:
            raise ValueError('HOURLY_GAP_DUPLICATE_OR_OPEN')
        try:
            o,h,l,c,v,b=(Decimal(str(row[j])) for j in (1,2,3,4,5,9))
            if not all(x.is_finite() for x in (o,h,l,c,v,b)) or min(o,h,l,c)<=0 or h<max(o,c) or l>min(o,c) or not 0<=b<=v:
                raise ValueError
        except Exception:
            raise ValueError('HOURLY_OHLCV') from None
    candle=dict(open_time=opening,open=str(rows[0][1]),high=str(max(Decimal(str(r[2])) for r in rows)),
                low=str(min(Decimal(str(r[3])) for r in rows)),close=str(rows[-1][4]))
    return candle,digest(rows)


def fetch_week(opening,now,url):
    validate_url(url)
    if opening+WEEK>now:
        raise ValueError('WEEK_NOT_CLOSED')
    params=dict(symbol='BTCUSDT',interval='1h',startTime=opening,endTime=opening+WEEK-1,limit=168)
    opener=http.build_opener(http.ProxyHandler({}),NoRedirect())
    request=http.Request(url+'?'+urlencode(params),method='GET')
    with opener.open(request,timeout=8) as response:
        if response.status!=200:
            raise ValueError('WEEKLY_MARKET_UNAVAILABLE')
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:
        raise ValueError('WEEKLY_MARKET_OVERSIZE')
    return aggregate(json.loads(raw),opening,now)
