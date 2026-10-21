"""Audit the original worker's GET attempts; never replace its computation."""
import os
import sys
from urllib.parse import parse_qsl,urlsplit
from bitman_weekly_forward.protocol import HOUR,WEEK,MONDAY

FETCH_PREFIX='BITMAN_WEEKLY_FORWARD_FETCH='


def request_week(event,args):
    if event!='urllib.Request' or type(args) is not tuple or len(args)!=4:return None
    url,data,headers,method=args
    if type(url) is not str or method!='GET' or data is not None:return None
    parts=urlsplit(url)
    if (parts.scheme!='http' or parts.netloc!='bitman-market-data.railway.internal:8080'
        or parts.path!='/fapi/v1/klines' or parts.fragment):return None
    items=parse_qsl(parts.query,strict_parsing=True)
    params=dict(items)
    if len(items)!=5 or set(params)!={'symbol','interval','startTime','endTime','limit'}:return None
    if params['symbol']!='BTCUSDT' or params['interval']!='1h' or params['limit']!='168':return None
    for key in ('startTime','endTime'):
        if not params[key].isascii() or not params[key].isdigit() or len(params[key])>16:return None
    opening,end=int(params['startTime']),int(params['endTime'])
    return opening if (opening-MONDAY)%WEEK==0 and end==opening+WEEK-1 else None


def audit_request(event,args):
    try:
        opening=request_week(event,args)
        if opening is not None:os.write(2,(FETCH_PREFIX+str(opening)+'\n').encode('ascii'))
    except Exception:pass


def main():
    # Worker-local Python audit hook fires in OpenerDirector.open before GET.
    # Markers travel through its existing stderr pipe; parent forwards only
    # validated markers after completion, never raw stderr or other text.
    try:sys.addaudithook(audit_request)
    except Exception:pass
    from bitman_weekly_forward.worker import main as original_main
    original_main()


if __name__=='__main__':main()
