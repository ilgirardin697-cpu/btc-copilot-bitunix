"""Local sequential replay. No network, environment, credentials or live loop."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,csv,gzip,hashlib,json
import numpy as np
from ..backquant import OriginalMLRSI
from .maths import Frame,fortnight,concordance,H,M
from .engine import Ledger,Engine
from .paper import Paper

HERE=Path(__file__).resolve().parent
START=1794960000000  # 2026-11-18 00:00 UTC
END=1795510800000    # 2026-11-24 09:00 UTC


def dump(path,obj):
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')


def load(data):
    manifest=json.loads((data/'manifest.json').read_text('utf-8'))
    if manifest['venue']!='BINANCE_SPOT' or manifest['symbol']!='BTCUSDT' or manifest['cutoff']!=END:
        raise ValueError('INPUT_PROVENANCE')
    frames={}
    for name,meta in manifest['frames'].items():
        path=data/(name+'.csv.gz')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:
            raise ValueError('INPUT_HASH')
        with gzip.open(path,'rt') as f:
            bars=np.loadtxt(f,delimiter=',',skiprows=1,ndmin=2)
        if len(bars)!=meta['rows']:
            raise ValueError('INPUT_ROWS')
        frames[name]=Frame(bars,name,END)
    for r in manifest['receipts']:
        if hashlib.sha256((data/r['file']).read_bytes()).hexdigest()!=r['sha256']:
            raise ValueError('HTTP_BYTES_CHANGED')
    frames['2w']=Frame(fortnight(frames['1w'].a),'2w',END)
    return frames,manifest


def replay(frames,start=START,end=END):
    ledger=Ledger()
    engine=Engine(ledger)
    broker=Paper(ledger)
    base=frames['15m'].a
    for row in base:
        if row[0]<start or row[0]+M>end:
            continue
        # Old decisions execute at this opening; this closing cannot affect them.
        old=frames['1h'].at(int(row[0]))
        broker.step(row,old['atr'])
        context={k:f.at(int(row[0]+M)) for k,f in frames.items()}
        for plan in engine.consume(context):
            broker.enqueue(plan)
    return ledger,engine,broker


def csvwrite(path,rows):
    rows=list(rows)
    columns=sorted({k for row in rows for k in row})
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,columns,lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,sort_keys=True,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})


def rsi_reconstruction(frame):
    # Exact source profile, fixed initial load anchor and no OPT substitution.
    ml=OriginalMLRSI(len(frame.a)-1)
    rows=[]
    prev=None
    for bar in frame.a:
        r=ml.push(float(bar[3]))
        available=int(bar[0]+H)
        text=datetime.fromtimestamp(available/1000,timezone.utc).isoformat()
        day=text[:10]
        if r['color']!=prev or day in ('2026-11-05','2026-11-22'):
            rows.append(dict(open_time=int(bar[0]),available_at=available,available_utc=text,
                color=r['color'],value=r['value'],lower=r['lower'],upper=r['upper'],
                is_transition=r['color']!=prev,close=float(bar[4]),
                venue='BINANCE_SPOT',matches_private_Bitman_RSI='NOT_VERIFIED',
                historical_emission='MODELED_SOURCE_REPLAY_NOT_ORIGINAL_LIVE_LOG'))
        prev=r['color']
    return rows


def claim_checks(frames):
    """User dossier claims checked against fresh public data, not indicator identity."""
    claims=[
        ('2026-11-18T12:00:00+00:00','1h','close',64231.52,'19Nov dossier; 13:00 Madrid'),
        ('2026-11-19T10:00:00+00:00','1h','close',63857.89,'19Nov dossier; 11:00 Madrid'),
        ('2026-11-23T04:00:00+00:00','4h','ao',-716.44,'23Nov dossier; 05:00 Madrid'),
        ('2026-11-23T12:00:00+00:00','4h','ao',-219.79,'23Nov dossier; 13:00 Madrid'),
        ('2026-11-23T16:00:00+00:00','4h','ao',200.90,'23Nov dossier; 17:00 Madrid'),
        ('2026-11-24T08:00:00+00:00','4h','ao',412.35,'24Nov dossier; 09:00 Madrid'),
        ('2026-11-24T08:00:00+00:00','1h','ao',-961.99,'24Nov dossier; 09:00 Madrid'),
        ('2026-11-24T08:30:00+00:00','15m','close',60108.75,'24Nov dossier; 09:30 Madrid'),
    ]
    out=[]
    for text,frame,key,expected,label in claims:
        stamp=int(datetime.fromisoformat(text).timestamp()*1000)
        r=frames[frame].at(stamp)
        value=r[key] if r['available_at']==stamp else None
        out.append(dict(claim=label,available_at=stamp,frame=frame,field=key,
            reported=expected,replayed=value,difference=value-expected if value is not None else None,
            matches_rounded_2dp=abs(value-expected)<=.00500001 if value is not None else False,
            evidence='DERIVED_REPORT_VS_PUBLIC_MARKET_NOT_ORIGINAL_PLATFORM_PARITY'))
    return out


def execute(data,out):
    if out.exists():
        raise ValueError('NEVER_OVERWRITE_REPLAY')
    frames,manifest=load(data)
    cross=concordance(frames)
    ledger,engine,broker=replay(frames)
    assert Ledger.verify(ledger.rows)==ledger.tip
    out.mkdir(parents=True)
    with gzip.open(out/'ledger.gz','wt',encoding='utf-8') as f:
        for row in ledger.rows:
            f.write(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')
    events=[r for r in ledger.rows if r['kind'] not in ('FRAME','SIM_MARK','WATCH_PROGRESS')]
    csvwrite(out/'events.csv',events)
    csvwrite(out/'trades.csv',broker.trades)
    csvwrite(out/'equity.csv',broker.curve)
    csvwrite(out/'rsi.csv',rsi_reconstruction(frames['1h']))
    csvwrite(out/'claims.csv',claim_checks(frames))
    for frame,f in frames.items():
        csvwrite(out/(frame+'.csv'),[r for r in f.records if START<=r['available_at']<=END])
    from collections import Counter
    counts=dict(Counter(r['kind'] for r in ledger.rows))
    summary=dict(version='IGOD_SEQUENTIAL_SHADOW_V0',source_base='0017faf74f3b157aa5d2789e073a819854108a89',
        declaration_commit='daa8673',source_addendum_commit='19a2f57',
        window_start=START,end_exclusive=END,base_bars=len(broker.curve),
        venue='BINANCE_SPOT',concordance=cross,records=len(ledger.rows),ledger_tip=ledger.tip,
        events=counts,simulation=broker.summary(),
        source_parity='NOT_CERTIFIED; user transcript/group derived reports, no original platform output',
        result='ENGINEERING_PROTOTYPE_ONLY; ECONOMIC_EDGE_NOT_TESTED',
        independent_validation='PENDING; no new held-out evaluation or automatic capture',
        two_week_anchor='1970-01-05 UTC; not platform certified',
        two_week_full_bbwp=frames['2w'].records[-1]['bbwp'] is not None,
        source_snapshot_2w=frames['2w'].records[-1],V8_LIVE_EXECUTION=False,trade_authority='NONE',
        deployment='NONE; flag above is local assertion, not independent Railway value',
        market_hashes={k:v['sha256'] for k,v in manifest['frames'].items()})
    dump(out/'summary.json',summary)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--data',type=Path,default=HERE/'d')
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    s=execute(args.data,args.out)
    print(json.dumps({k:s[k] for k in ('records','events','result')}))
