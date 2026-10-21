"""Only explicit non-secret request fields; no parent environment configuration."""
import json
from pathlib import Path
import sys
import time
from .observer import run
from .journal import JournalInvalid


def handle(request,now=None):
    if type(request) is not dict or set(request)!={'storage_path','market_data_url','source_sha'}:
        raise ValueError('INVALID_WEEKLY_REQUEST')
    if type(request['storage_path']) is not str or not Path(request['storage_path']).is_absolute():
        raise ValueError('INVALID_WEEKLY_STORAGE')
    return run(request['storage_path'],request['market_data_url'],request['source_sha'],
               int(time.time()*1000) if now is None else now)


def main():
    try:
        raw=sys.stdin.read(8193)
        if len(raw)>8192:raise ValueError
        result=handle(json.loads(raw))
    except JournalInvalid:
        result=dict(status='OBSERVER_JOURNAL_INVALID')
    except Exception:
        result=dict(status='DEGRADED')
    print(json.dumps(result,ensure_ascii=True,allow_nan=False,separators=(',',':')))


if __name__=='__main__':main()
