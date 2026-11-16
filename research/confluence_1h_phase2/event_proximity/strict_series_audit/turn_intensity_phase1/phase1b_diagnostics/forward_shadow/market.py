"""Strict input receipts only. No HTTP client, credentials or market requests."""
from dataclasses import dataclass
import hashlib,json
from decimal import Decimal,InvalidOperation
from types import MappingProxyType
import numpy as np

HOUR=3600000
VENUE='BINANCE_USDM_PERPETUAL'


def decode(raw):
    return json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


@dataclass(frozen=True)
class Receipt:
    body:bytes
    url:str
    query:dict
    request_started_ms:int
    received_at_ms:int
    exchange_time_ms:int
    status:int=200

    def __post_init__(self):object.__setattr__(self,'query',MappingProxyType(dict(self.query)))

    def validate(self,kind):
        endpoint='klines' if kind=='KLINES' else 'fundingRate'
        if self.url!='https://fapi.binance.com/fapi/v1/'+endpoint or self.status!=200:raise ValueError('UNAPPROVED_PUBLIC_SOURCE')
        if not self.request_started_ms<=self.received_at_ms or self.exchange_time_ms>self.received_at_ms+2000:raise ValueError('SOURCE_CLOCK_INVALID')
        if len(self.body)>2000000:raise ValueError('PUBLIC_BODY_TOO_LARGE')
        allowed={'symbol','startTime','endTime','limit'}|({'interval'} if kind=='KLINES' else set())
        if set(self.query)!=allowed or self.query['symbol']!='BTCUSDT':raise ValueError('PUBLIC_QUERY_INVALID')
        if type(self.query['limit']) is not int:raise ValueError('PUBLIC_LIMIT_INTEGER')
        if kind=='KLINES' and (self.query['interval']!='1h' or not 1<=self.query['limit']<=1500):raise ValueError('PUBLIC_H1_ONLY')
        if kind!='KLINES' and self.query['limit']!=1000:raise ValueError('FUNDING_COMPLETENESS_LIMIT')
        if type(self.query['startTime']) is not int or type(self.query['endTime']) is not int or self.query['startTime']>self.query['endTime']:
            raise ValueError('PUBLIC_RANGE_INVALID')
        rows=decode(self.body)
        if not isinstance(rows,list) or len(rows)>self.query['limit']:raise ValueError('PUBLIC_SCHEMA_INVALID')
        return rows

    def metadata(self):
        return dict(url=self.url,query=dict(self.query),request_started_ms=self.request_started_ms,
                    received_at_ms=self.received_at_ms,exchange_time_ms=self.exchange_time_ms,status=self.status,
                    sha256=hashlib.sha256(self.body).hexdigest(),bytes=len(self.body),venue=VENUE)


def klines(receipt):
    rows=receipt.validate('KLINES');a=[]
    if not rows:raise ValueError('PUBLIC_NO_CLOSED_ROWS')
    for row in rows:
        if not isinstance(row,list) or len(row)!=12 or type(row[0]) is not int or type(row[6]) is not int:raise ValueError('KLINE12_REQUIRED')
        t=row[0]
        if t%HOUR or row[6]!=t+HOUR-1 or t+HOUR>min(receipt.exchange_time_ms,receipt.received_at_ms):raise ValueError('OPEN_OR_INVALID_CANDLE')
        if not receipt.query['startTime']<=t<=receipt.query['endTime']:raise ValueError('CANDLE_OUTSIDE_QUERY')
        try:
            vals=[Decimal(str(row[k])) for k in (1,2,3,4,5,9)]
            auxiliary=[Decimal(str(row[k])) for k in (7,10,11)]
        except (InvalidOperation,ValueError):raise ValueError('INVALID_OHLCV_NUMBER') from None
        if not all(v.is_finite() for v in vals+auxiliary):raise ValueError('NONFINITE_OHLCV')
        if min(auxiliary)<0 or type(row[8]) is not int or row[8]<0:raise ValueError('INVALID_PUBLIC_VOLUME_TRADES')
        o,h,l,c,v,taker=vals
        if min(o,h,l,c)<=0 or min(v,taker)<0 or taker>v or h<max(o,l,c) or l>min(o,h,c):raise ValueError('INVALID_OHLCV')
        a.append([t,*map(float,vals[:5])])
    a=np.asarray(a,float).reshape((-1,6))
    if len(a)>1 and not (np.diff(a[:,0])==HOUR).all():raise ValueError('PUBLIC_CANDLE_GAP_OR_DUPLICATE')
    return a


def candle_key(row):
    # Detect numeric revisions below float64 precision without treating formatting
    # differences (100.0 vs100.00) as a different market value.
    normalized=[str(Decimal(str(v)).normalize()) for v in row]
    return hashlib.sha256(json.dumps(normalized,separators=(',',':')).encode()).hexdigest()


def funding(receipt):
    rows=receipt.validate('FUNDING')
    if len(rows)>=1000 or receipt.query['endTime']>min(receipt.exchange_time_ms,receipt.received_at_ms):raise ValueError('INCOMPLETE_OR_FUTURE_FUNDING')
    out=[]
    for row in rows:
        if (not isinstance(row,dict) or set(row)-{'symbol','fundingTime','fundingRate','markPrice'} or
            not {'symbol','fundingTime','fundingRate'}<=set(row)):raise ValueError('FUNDING_SCHEMA_INVALID')
        if row['symbol']!='BTCUSDT' or type(row['fundingTime']) is not int:raise ValueError('FUNDING_SYMBOL_TIME_INVALID')
        try:
            t=row['fundingTime'];rate=Decimal(str(row['fundingRate']));mark=Decimal(str(row['markPrice'])) if row.get('markPrice') else None
        except (InvalidOperation,ValueError,KeyError):raise ValueError('INVALID_FUNDING_NUMBER') from None
        if not receipt.query['startTime']<=t<=receipt.query['endTime'] or not rate.is_finite() or (mark is not None and (not mark.is_finite() or mark<=0)):
            raise ValueError('INVALID_FUNDING')
        out.append(dict(time=t,rate=float(rate),mark=float(mark) if mark is not None else None))
    if any(y['time']<=x['time'] for x,y in zip(out,out[1:])):raise ValueError('DUPLICATE_FUNDING')
    return out
