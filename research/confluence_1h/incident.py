"""Separate post-hoc incident audit. No parameter changes or immature outcomes."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import requests

from .data import HERE,HOUR,stamp,iso,decode_klines
from .indicators import calculate,signals
from .evaluate import csv_write,json_write


def acquire(venue,cache):
    host,path=('https://fapi.binance.com','/fapi/v1/') if venue=='BINANCE_USDM_PERPETUAL' else ('https://api.binance.com','/api/v3/')
    folder=cache/venue;folder.mkdir(parents=True,exist_ok=True);sources=[]
    with requests.Session() as s:
        s.trust_env=False
        def get(endpoint,params,name):
            url=host+path+endpoint;p=folder/name;reused=p.exists()
            if reused:
                raw=p.read_bytes();status=None
            else:
                r=s.get(url,params=params,timeout=20,allow_redirects=False);raw=r.content;status=r.status_code
                with p.open('xb') as f:f.write(raw)
            sources.append(dict(url=url,params=params,status=status,raw_sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
                received_at=None if reused else datetime.now(timezone.utc).isoformat(),file=name,
                reused_original_response=reused,recovery_read_at=datetime.now(timezone.utc).isoformat() if reused else None,
                historical_receipt_attested=False))
            if status not in (200,None):raise ValueError('PUBLIC_INCIDENT_HTTP_'+str(status))
            return json.loads(raw)
        clock=get('time',{},'server_time.json');end=int(clock['serverTime'])//HOUR*HOUR
        start=stamp('2026-09-01T00:00:00Z');cursor=start;allrows=[]
        for page in range(4):
            if cursor>=end:break
            row=get('klines',dict(symbol='BTCUSDT',interval='1h',startTime=cursor,endTime=end-1,limit=1000),f'page_{page}.json')
            if not isinstance(row,list) or not row:raise ValueError('INCIDENT_DATA_INCOMPLETE')
            allrows.extend(row);cursor=int(row[-1][0])+HOUR
        bars=decode_klines(allrows)
        if not np.array_equal(bars[:,0],np.arange(start,end,HOUR)):raise ValueError('INCIDENT_HISTORY_GAP')
        json_write(folder/'manifest.json',dict(venue=venue,symbol='BTCUSDT',end_exclusive=iso(end),sources=sources))
        return bars,dict(venue=venue,symbol='BTCUSDT',end_exclusive=iso(end),sources=sources)


def run(cache='research/cache/confluence_incident_20261115'):
    cache=Path(cache);out=HERE/'artifacts';out.mkdir(exist_ok=True);records=[];statuses=[]
    for venue in ('BINANCE_USDM_PERPETUAL','BINANCE_SPOT'):
        try:
            folder=cache/venue
            if (folder/'manifest.json').exists():
                manifest=json.loads((folder/'manifest.json').read_text());rows=[]
                for r in manifest['sources']:
                    raw=(folder/r['file']).read_bytes()
                    if hashlib.sha256(raw).hexdigest()!=r['raw_sha256']:raise ValueError('INCIDENT_RAW_CHANGED')
                    if r['file'].startswith('page_'):rows.extend(json.loads(raw))
                bars=decode_klines(rows)
            else:bars,manifest=acquire(venue,cache)
            f=calculate(bars);s=signals(f)
            for i in range(len(bars)):
                if not stamp('2026-11-14T18:00:00Z')<=bars[i,0]<stamp('2026-11-15T08:00:00Z'):continue
                row=dict(venue=venue,open_utc=iso(bars[i,0]),available_at_utc=iso(bars[i,0]+HOUR),
                    available_at_madrid=datetime.fromtimestamp((bars[i,0]+HOUR)/1000,ZoneInfo('Europe/Madrid')).isoformat(),
                    open=bars[i,1],high=bars[i,2],low=bars[i,3],close=bars[i,4])
                for key in ('kon_trend','kon_signal','ao','ao_slope','adx','adx_slope','plus_di','minus_di','bbwp','atr'):
                    row[key]=float(f[key][i]) if np.isfinite(f[key][i]) else None
                row.update({k:bool(v[i]) for k,v in s.items()});records.append(row)
            statuses.append(dict(venue=venue,status='REAL_PUBLIC_CLOSED_BARS',**{k:v for k,v in manifest.items() if k!='venue'}))
            chart(bars,f,s,venue,out)
        except Exception as e:
            statuses.append(dict(venue=venue,status='BLOCKED',error_type=type(e).__name__,code=str(e)[:160]))
    csv_write(out/'incident_20261115.csv',records)
    json_write(out/'incident_20261115_sources.json',dict(
        label='POST_HOC_OBSERVATION_NOT_IN_VALIDATION',
        requested_time='2026-11-15T02:00:00+01:00',utc='2026-11-15T01:00:00Z',
        no_retuning=True,full24h_outcome='NOT_EVALUATED_IMMATURE',venues=statuses,
        full_signal_rows=[r for r in records if r['long'] or r['short']]))
    print(json.dumps([dict(venue=r['venue'],status=r['status']) for r in statuses]))


def chart(bars,f,s,venue,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.dates import DateFormatter
    mask=(bars[:,0]>=stamp('2026-11-14T00:00:00Z'));a=bars[mask]
    times=[datetime.fromtimestamp((t+HOUR)/1000,timezone.utc) for t in a[:,0]]
    fig,ax=plt.subplots(4,1,figsize=(13,10),sharex=True)
    ax[0].plot(times,a[:,4],label=venue+' closed H1')
    for axis in ax:axis.axvline(datetime.fromtimestamp(stamp('2026-11-15T01:00:00Z')/1000,timezone.utc),color='purple',ls=':',label='02:00 Madrid')
    for key in ('kon_trend','kon_signal'):ax[1].plot(times,f[key][mask],label=key)
    for key in ('adx','plus_di','minus_di'):ax[2].plot(times,f[key][mask],label=key)
    ax[3].plot(times,f['ao'][mask],label='AO');other=ax[3].twinx();other.plot(times,f['bbwp'][mask],color='orange',label='BBWP')
    for axis in ax:axis.legend(fontsize=7);axis.grid(alpha=.2)
    ax[-1].xaxis.set_major_formatter(DateFormatter('%m-%d %H:%M',tz=timezone.utc))
    fig.suptitle('POST-HOC INCIDENT — x = AVAILABLE AT (UTC candle close), not candle open; no24h outcome')
    fig.tight_layout();fig.savefig(out/('incident_'+venue+'.png'),dpi=150);plt.close(fig)


if __name__=='__main__':run()
