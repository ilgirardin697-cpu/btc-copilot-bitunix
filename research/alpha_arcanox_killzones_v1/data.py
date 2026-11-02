"""Local public OHLC only. No Binance/Bitunix/Telegram client."""
import csv
import hashlib
import json
from dataclasses import asdict,is_dataclass
from decimal import Decimal
from pathlib import Path
from .core import Bar


def read_csv(path):
    with Path(path).open(encoding='utf-8',newline='') as f:
        reader=csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != ('open_time','open','high','low','close','base_volume'):
            raise ValueError('CSV_SCHEMA_INVALID')
        return tuple(Bar(int(r['open_time']),*(Decimal(r[k]) for k in ('open','high','low','close','base_volume'))) for r in reader)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(x):
    if is_dataclass(x):return encoded(asdict(x))
    if isinstance(x,Decimal):return str(x)
    if isinstance(x,dict):return {k:encoded(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [encoded(v) for v in x]
    return x


def json_text(x):
    return json.dumps(encoded(x),ensure_ascii=False,sort_keys=True,indent=2)+'\n'
