"""Local public OHLC CSV only; no downloader or authenticated adapter."""
import csv
import hashlib
import json
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from pathlib import Path
from .model import Bar

COLUMNS = ('open_time', 'open', 'high', 'low', 'close', 'base_volume')


def read_csv(path):
    with Path(path).open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError('CSV_SCHEMA_INVALID')
        return tuple(Bar(int(r['open_time']), *(Decimal(r[k]) for k in COLUMNS[1:])) for r in reader)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    if is_dataclass(value):
        return {k: encoded(v) for k, v in asdict(value).items()}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: encoded(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [encoded(v) for v in value]
    return value


def json_text(value):
    return json.dumps(encoded(value), ensure_ascii=False, indent=2, sort_keys=True) + '\n'
