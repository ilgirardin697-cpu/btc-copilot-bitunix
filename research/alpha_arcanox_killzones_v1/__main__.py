"""Offline local-CSV snapshot. Original level formulas intentionally unavailable."""
import argparse
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from .core import scan
from .data import json_text,read_csv,sha
from .render import command_preview,session_svg
from .risk import Costs


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--day',required=True)
    p.add_argument('--as-of',required=True,help='Explicit ISO UTC cutoff, no implicit live time')
    p.add_argument('--capital',type=Decimal,required=True,help='SIMULATED only, no account read')
    p.add_argument('--costs',type=Path,required=True,help='Explicit assumed rates, not account fees')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    m=json.loads(a.manifest.read_text(encoding='utf-8'))
    if m.get('symbol')!='BTCUSDT' or not m.get('venue') or m.get('sha256')!=sha(a.csv):
        raise ValueError('DATA_MANIFEST_OR_HASH_INVALID')
    stamp=datetime.fromisoformat(a.as_of.replace('Z','+00:00'))
    if stamp.utcoffset() is None or stamp.utcoffset().total_seconds()!=0:
        raise ValueError('AS_OF_MUST_BE_UTC')
    c=json.loads(a.costs.read_text(encoding='utf-8'))
    # Unknown fields, including any alleged 'verified'/'trade_authority', are rejected.
    expected={'entry_fee','exit_fee','entry_slippage','exit_slippage','funding_reserve_per_btc','provenance'}
    if set(c)!=expected:raise ValueError('COST_SCHEMA_INVALID')
    costs=Costs(**{k:(v if k=='provenance' else Decimal(str(v))) for k,v in c.items()})
    bars=read_csv(a.csv)
    snapshot=scan(bars,a.day,int(stamp.timestamp()*1000),costs,a.capital)
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'snapshot.json').write_text(json_text(dict(data=m,snapshot=snapshot)),encoding='utf-8',newline='\n')
    (a.out/'killzone_OFFLINE_preview.txt').write_text(command_preview(snapshot,f'{m["symbol"]} / {m["venue"]}'),encoding='utf-8',newline='\n')
    if snapshot['pair']:
        (a.out/'sessions.svg').write_text(session_svg(bars,snapshot,'BTCUSDT PUBLIC DATA — SESSION VALIDATION ONLY'),encoding='utf-8',newline='\n')
    print(json_text(dict(paper_decision=snapshot['paper_decision'],reason_codes=snapshot['reason_codes'],trade_authority='NONE')))


if __name__=='__main__':main()
