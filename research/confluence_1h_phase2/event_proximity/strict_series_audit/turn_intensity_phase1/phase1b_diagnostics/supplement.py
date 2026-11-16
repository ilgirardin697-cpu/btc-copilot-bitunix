"""Complete only the last requested hour in a separate diagnostic dataset."""
import argparse,csv,gzip,hashlib,io,json
from pathlib import Path
import numpy as np
from .. import detect as frozen
from ..evaluate import clean,write_csv,write_json
from .replay import HERE,read_fixture,hourly,latency
from .trace import instrument


def generate(out):
    rows=[];delays=[];sources=[]
    for venue in ('SPOT','USDM'):
        path=HERE/'fixtures'/(venue+'_FULL.csv.gz');m=json.loads(path.with_suffix('').with_suffix('.json').read_text())
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=m['sha256']:raise ValueError('SUPPLEMENT_SOURCE_CHANGED')
        a=np.asarray(list(csv.reader(io.StringIO(gzip.decompress(raw).decode())))[1:],float)
        original,meta=read_fixture(venue)
        if len(a)!=len(original)+1 or not np.array_equal(a[:-1],original) or not (np.diff(a[:,0])==frozen.HOUR).all():
            raise ValueError('ORIGINAL_CAPTURE_NOT_PRESERVED')
        if int(a[-1,0]+frozen.HOUR)!=m['requested_last_close_ms']:raise ValueError('SUPPLEMENT_NOT_CLOSED')
        f=frozen.features(a);events,_,trace=instrument(a,f)
        expected,_=frozen.detect(original,frozen.features(original))
        if clean([e for e in events if e['i']<len(original)])!=clean(expected):raise ValueError('PAST_EVENTS_CHANGED')
        rows.extend(hourly(venue,a,f,events,trace));delays.extend(latency(venue,a,f,events));sources.append(m)
    out.mkdir(parents=True,exist_ok=True)
    write_csv(out/'november_full.csv',rows);write_csv(out/'delay_full.csv',delays)
    result=dict(rows=len(rows),rows_per_venue={v:sum(r['venue']==v for r in rows) for v in ('SPOT','USDM')},
                earlier_capture_preserved=True,old_events_preserved=True,last_close='2026-11-15T23:00:00Z',
                new_sources=sources,interpretation='LATER_HISTORICAL_COMPLETION_NOT_FORWARD',no_rule_change=True)
    write_json(out/'completion.json',result);print(json.dumps(dict(rows=len(rows),last_close=result['last_close'])))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=HERE/'artifacts');generate(p.parse_args().out)
