"""Read-only public Binance USD-M closed OHLCV, no credential use or fallback."""
import time
import requests
from .core import HISTORIES, STEPS, PlanDataError, normalize

BASE='https://fapi.binance.com/fapi/v1/klines'


def public_klines(tf, asof_ms, count, *, session=None):
    if tf not in HISTORIES or count != HISTORIES[tf]:
        raise PlanDataError('PUBLIC_REQUEST_DENIED')
    sess = session if session is not None else requests.Session()
    sess.trust_env=False
    sess.auth=None
    sess.headers.clear()
    # Official endpoint returns latest klines when start/end are omitted. An
    # explicit as-of bound prevents treating later candles as historical data.
    # Fetch a few extras to tolerate last open/partial candle.
    try:
        response=sess.get(BASE,params={'symbol':'BTCUSDT','interval':tf,'limit':count+2,'endTime':asof_ms-1},
                          timeout=(3,10),allow_redirects=False)
        if response.status_code != 200:
            raise PlanDataError('PUBLIC_HTTP_'+str(response.status_code))
        rows=response.json()
    except PlanDataError:
        raise
    except (requests.RequestException,ValueError) as exc:
        raise PlanDataError('PUBLIC_DATA_UNAVAILABLE') from exc
    if not isinstance(rows,list):raise PlanDataError('PUBLIC_NOT_A_KLINE_LIST')
    parsed=normalize(rows,tf,asof_ms,count)
    if len(parsed)>count:
        rows=[r for r in rows if r[6]<asof_ms][-count:]
        normalize(rows,tf,asof_ms,count)
    else:
        rows=[r for r in rows if r[6]<asof_ms][-count:]
    return rows


def public_market(asof_ms=None, *, session=None):
    asof_ms = asof_ms if asof_ms is not None else int(time.time()*1000)
    return {tf:public_klines(tf,asof_ms,count,session=session) for tf,count in HISTORIES.items()}
