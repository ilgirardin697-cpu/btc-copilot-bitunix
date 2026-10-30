"""One-shot local preview: NO scheduler, Telegram or exchange execution."""
import argparse
import json
import time
from .core import generate_plan, telegram_text
from .market import public_market


def main():
    parser=argparse.ArgumentParser(description='Read-only I-GOD daily plan preview (not a signal or executor)')
    parser.add_argument('--from-json',help='File containing asof_ms and Binance-format closed candle arrays')
    parser.add_argument('--live-public',action='store_true',help='GET Binance USD-M public candles, never account API')
    parser.add_argument('--paper-equity',type=float,default=140.0)
    parser.add_argument('--out',help='Optional output JSON file')
    args=parser.parse_args()
    if bool(args.from_json)==bool(args.live_public):
        parser.error('Choose exactly one of --from-json or --live-public')
    if args.from_json:
        with open(args.from_json,encoding='utf-8') as file:data=json.load(file)
        asof=data['asof_ms'];market=data['candles']
    else:
        asof=int(time.time()*1000)
        try:market=public_market(asof)
        except Exception as e:
            print('DATOS NO DISPONIBLES: '+str(e)+'\nNO OPERAR. No hay niveles verificados.')
            return 2
    plan=generate_plan(market,asof,args.paper_equity,live_public=args.live_public)
    print(telegram_text(plan))
    if args.out:
        with open(args.out,'w',encoding='utf-8') as f:json.dump(plan,f,ensure_ascii=False,indent=2,allow_nan=False)
    return 0 if plan['bias']!='UNKNOWN' else 2

if __name__=='__main__':raise SystemExit(main())
