"""Optional file-fed passive observer. Never started/deployed by the research run.

The input is an exported/public hourly CSV, not an account feed. No Telegram
consumer or HTTP transport: rendered transition messages go only to stdout or a
caller-supplied plain-text callback. Journals are separate from existing stores.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import time
import numpy as np
from . import core
from .data import HOUR
from .run import make_candidate
from .telegram import render


def atomic(path,value):
    tmp=path.with_suffix('.tmp')
    with tmp.open('w',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,allow_nan=False); stream.flush(); os.fsync(stream.fileno())
    os.replace(tmp,path)


def append(path,value):
    with path.open('a',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def load_csv(path,now_ms):
    rows=[]
    with Path(path).open(encoding='utf-8',newline='') as stream:
        for row in csv.DictReader(stream):
            rows.append([float(row[k]) for k in ('time','open','high','low','close','volume','taker_buy')])
    bars=np.asarray(rows,float).reshape(-1,7)
    bars=bars[bars[:,0]+HOUR<=now_ms]
    if len(bars)<1320 or np.any(~np.isfinite(bars)) or np.any(np.diff(bars[:,0])!=HOUR) or np.any(bars[:,0]%HOUR):
        raise ValueError('PUBLIC_HOURLY_INPUT_INVALID')
    if (np.any(bars[:,3]<=0) or np.any(bars[:,2]<np.maximum(bars[:,1],bars[:,4]))
            or np.any(bars[:,3]>np.minimum(bars[:,1],bars[:,4])) or np.any(bars[:,6]<0)
            or np.any(bars[:,6]>bars[:,5])):
        raise ValueError('PUBLIC_HOURLY_INPUT_INVALID')
    if now_ms-(bars[-1,0]+HOUR)>HOUR: raise ValueError('PUBLIC_HOURLY_INPUT_STALE')
    return bars


class ShadowObserver:
    trade_authority=False
    def __init__(self,directory,selection,send=None):
        self.root=Path(directory).resolve()
        if any(p.lower() in ('guardian','mlrsi','copilot_audit','early_breakout','v8') for p in self.root.parts):
            raise ValueError('SEPARATE_BITMAN_STORAGE_REQUIRED')
        self.root.mkdir(parents=True,exist_ok=True)
        self.selection=selection; self.send=send
        self.state_path=self.root/'bitman_state.json'; self.journal=self.root/'bitman_signals.jsonl'
        self.state=json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        self.keys=set()
        if self.journal.exists():
            for line in self.journal.read_text().splitlines(): self.keys.add(json.loads(line)['event_id'])
        self.selection_hash=hashlib.sha256(json.dumps(selection,sort_keys=True).encode()).hexdigest()

    def cycle(self,bars,now_ms):
        try: return self._cycle(bars,now_ms)
        except Exception:
            print('BITMAN_SHADOW_OBSERVATION_ERROR',flush=True)
            return dict(state='DATA_RISK_ERROR',shadow_only=True,trade_authority=False)

    def _cycle(self,bars,now_ms):
        bars=np.asarray(bars,float); bars=bars[bars[:,0]+HOUR<=now_ms]
        if len(bars)<1320 or now_ms-(bars[-1,0]+HOUR)>HOUR: raise ValueError('STALE')
        stamp=int(bars[-1,0]+HOUR)
        if (np.any(np.diff(bars[:,0])!=HOUR) or np.any(~np.isfinite(bars))
                or np.any(bars[:,0]%HOUR) or np.any(bars[:,3]<=0)
                or np.any(bars[:,2]<np.maximum(bars[:,1],bars[:,4]))
                or np.any(bars[:,3]>np.minimum(bars[:,1],bars[:,4]))
                or np.any((bars[:,6]<0)|(bars[:,6]>bars[:,5]))): raise ValueError('GAP_OR_SCHEMA')
        if self.state.get('closed_timestamp')==stamp: return self.state.get('snapshot')
        base=core.base_features(bars); cache={}; observations={}
        for side in (1,-1):
            p=make_candidate(self.selection[str(side)]['selected'])
            # The Phase2 frozen FUSION selected no additions. Future MLRSI
            # configurations require an explicit separately supplied observational
            # feature cache, never silently fabricated GREEN values.
            if any(x.startswith('MLRSI') for x in p.fusion): raise ValueError('MLRSI_OBSERVATION_CACHE_REQUIRED')
            f=core.candidate_features(bars,base,p,cache); groups=core.blocks(f,p,side)
            active={k:bool(v[-1]) for k,v in groups.items()
                    if k not in p.disabled and not (k=='STRUCTURE' and p.structure=='none')
                    and not (k=='VOLATILITY' and p.volatility=='none')}
            observations[side]=(p,f,active,all(active.values()))
        ready=[s for s,(_,_,_,good) in observations.items() if good]
        side=ready[0] if len(ready)==1 else max(observations,key=lambda s:sum(observations[s][2].values()))
        p,f,conditions,_=observations[side]
        status='LONG' if ready==[1] else 'SHORT' if ready==[-1] else 'BLOCKED' if len(ready)>1 else 'SETUP_FORMING' if conditions.get('TREND') and conditions.get('RSI_CLOUD') else 'WAIT'
        bb=f['bbwp'][-1]
        if not np.isfinite(bb) or not np.isfinite(f['adx'][-1]) or not np.isfinite(f['cloud_fast'][-1]): raise ValueError('WARMUP')
        snapshot=dict(state=status,entry=float(bars[-1,4]),atr=float(f['atr'][-1]),stop_atr=p.stop_atr,trail_atr=p.trail_atr,
            trend={'1H':'BULL' if f['ema_fast'][-1]>f['ema_slow'][-1] else 'BEAR',
                   '4H':'UNKNOWN' if not np.isfinite(f['h4_trend'][-1]) else 'BULL' if f['h4_trend'][-1]>0 else 'BEAR',
                   '1D':'UNKNOWN' if not np.isfinite(f['day_trend'][-1]) else 'BULL' if f['day_trend'][-1]>0 else 'BEAR'},
            cloud='BULLISH' if f['cloud_fast'][-1]>f['cloud_slow'][-1] else 'BEARISH',
            adx=float(f['adx'][-1]),adx_arrow='↑' if f['adx_slope'][-1]>0 else '↓',
            momentum='POSITIVE' if f['ao' if p.oscillator=='AO' else 'sqz'][-1]>0 else 'NEGATIVE',
            bbwp=float(bb),bbwp_state='COMPRESSION' if bb<15 else 'EXTREME' if bb>=90 else 'EXPANSION' if f['bbwp_rising'][-1] else 'NORMAL',
            structure='BULLISH' if f['bull'][-1] else 'BEARISH' if f['bear'][-1] else 'MIXED',
            vpoc='SUPPORTING' if (bars[-1,4]-f['vpoc'][-1])*side>0 else 'NOT SUPPORTING',
            mlrsi='UNAVAILABLE',conditions=conditions,shadow_only=True,trade_authority=False)
        first=not self.state or self.state.get('selection_hash')!=self.selection_hash
        recovery=not first and stamp-self.state.get('closed_timestamp',stamp)>HOUR
        changed=status!=self.state.get('status')
        if not first and not recovery and changed and status in ('LONG','SHORT'):
            identity=hashlib.sha256(f'{self.selection_hash}|{stamp}|{status}'.encode()).hexdigest()
            if identity not in self.keys:
                record=dict(event_id=identity,source='FORWARD_LIVE',software_version='BITMAN_PUBLIC_PROXY_V1',
                    variant='CLASSIC_OR_IDENTICAL_FUSION',signal_time=int(now_ms),closed_1h_time=stamp,
                    reference_price=float(bars[-1,4]),side=status,configuration=p.name,
                    selection_hash=self.selection_hash,shadow_only=True,trade_authority=False)
                append(self.journal,record);self.keys.add(identity)
        append(self.root/'bitman_snapshots.jsonl',dict(snapshot,recorded_at=int(now_ms),closed_1h_time=stamp))
        new_state=dict(status=status,closed_timestamp=stamp,selection_hash=self.selection_hash,snapshot=snapshot)
        atomic(self.state_path,new_state)
        self.state=new_state
        if (first or changed) and not recovery and self.send:
            try: self.send(render(snapshot))
            except Exception: print('BITMAN_SHADOW_DELIVERY_FAILED',flush=True)
        return snapshot


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-csv',required=True);parser.add_argument('--state-dir',required=True)
    parser.add_argument('--selection',default=str(Path(__file__).parent/'artifacts/selection_lock.json'))
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args();lock=json.loads(Path(args.selection).read_text())
    observer=ShadowObserver(args.state_dir,lock['fusion'],send=print)
    while True:
        try:
            now=int(time.time()*1000);observer.cycle(load_csv(args.input_csv,now),now)
        except Exception: print('BITMAN_SHADOW_PUBLIC_INPUT_UNAVAILABLE',flush=True)
        if args.once: return
        time.sleep(60)


if __name__=='__main__': main()
