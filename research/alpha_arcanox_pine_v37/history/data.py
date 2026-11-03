"""Public Spot archive reader. Explicit microsecond -> millisecond normalization."""
import csv
from dataclasses import dataclass
from datetime import datetime,timezone
import hashlib
import io
import json
import math
from pathlib import Path
from zipfile import ZipFile
from ..core import Candle,HOUR

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
CACHE=ROOT/'research/cache/killzone_owner_b_history_v1'
MINUTE=60_000


def ts(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()*1000)
def iso(t):return datetime.fromtimestamp(t/1000,timezone.utc).isoformat().replace('+00:00','Z')
def spec():return json.loads((HERE/'specification.json').read_text(encoding='utf-8'))


@dataclass(frozen=True)
class Minute:
    open_time:int
    open:float
    high:float
    low:float
    close:float

    @property
    def available_at(self):return self.open_time+MINUTE


def read_archive(path,interval):
    step=HOUR if interval=='1h' else MINUTE
    out=[]
    with ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=1 or not names[0].endswith('.csv'):raise ValueError('ARCHIVE_SCHEMA')
        with z.open(names[0]) as f:
            reader=csv.reader(io.TextIOWrapper(f,encoding='utf-8-sig',newline=''))
            for r in reader:
                if len(r)!=12:raise ValueError('KLINE_SCHEMA_NOT_12')
                opened=int(r[0]);closed=int(r[6])
                if opened<10**14 or opened%1000:raise ValueError('EXPECTED_SPOT_MICROSECONDS')
                t=opened//1000
                if t%step or closed!=(t+step)*1000-1:raise ValueError('KLINE_TIME_MISMATCH')
                values=[float(r[i]) for i in (1,2,3,4)]
                o,h,l,c=values
                if (any(not math.isfinite(v) or v<=0 for v in values)
                        or not l<=min(o,c)<=max(o,c)<=h):raise ValueError('OHLC_INVALID')
                base,taker=float(r[5]),float(r[9])
                if (not math.isfinite(base) or not math.isfinite(taker)
                        or not 0<=taker<=base):raise ValueError('VOLUME_INVALID')
                cls=Candle if interval=='1h' else Minute
                out.append(cls(t,*values))
    if any(b.open_time-a.open_time!=step for a,b in zip(out,out[1:])):
        raise ValueError('ARCHIVE_GAP_OR_DUPLICATE')
    return out


def load_interval(interval,cache=CACHE):
    manifest=json.loads((cache/f'manifest_{interval}.json').read_text(encoding='utf-8'))
    if manifest.get('status')!='COMPLETE':raise ValueError('DATASET_INCOMPLETE')
    bars=[]
    for record in manifest['archives']:
        path=cache/record['file']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
            raise ValueError('ARCHIVE_HASH_CHANGED')
        bars.extend(read_archive(path,interval))
    step=HOUR if interval=='1h' else MINUTE
    if any(b.open_time-a.open_time!=step for a,b in zip(bars,bars[1:])):
        raise ValueError('DATASET_GAP_OR_DUPLICATE')
    return bars,manifest


def verify_aggregation(hours,minutes):
    mapped={b.open_time:b for b in hours}
    if len(minutes)%60:raise ValueError('PARTIAL_HOUR')
    for i in range(0,len(minutes),60):
        rows=minutes[i:i+60];t=rows[0].open_time
        if t not in mapped or any(b.open_time!=t+j*MINUTE for j,b in enumerate(rows)):
            raise ValueError('INTRABAR_COVERAGE_GAP')
        values=(rows[0].open,max(b.high for b in rows),min(b.low for b in rows),rows[-1].close)
        h=mapped[t]
        if values!=(h.open,h.high,h.low,h.close):raise ValueError('SPOT_H1_1M_MISMATCH')
    return len(minutes)//60
