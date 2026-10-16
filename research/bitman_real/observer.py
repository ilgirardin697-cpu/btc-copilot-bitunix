"""Unstarted file-fed observer. No network, Telegram poller or account capability."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
from .config import Config,HOUR,TIMEFRAMES,VERSION
from .events import analyze
from .market import load_csv,validate
from .storage import append,atomic
from .telegram import render


class BitmanRealObserver:
    trade_authority=False
    def __init__(self,directory,reentry_max_bars,send=None):
        self.root=Path(directory).resolve()
        if any(x.lower() in ('guardian','mlrsi','copilot_audit','early_breakout','v8') for x in self.root.parts):
            raise ValueError('SEPARATE_OBSERVATIONAL_STORAGE_REQUIRED')
        self.root.mkdir(parents=True,exist_ok=True);self.config=Config(reentry_max_bars);self.send=send
        self.signature=hashlib.sha256(json.dumps(dict(version=VERSION,**asdict(self.config)),sort_keys=True).encode()).hexdigest()
        self.state_path=self.root/'bitman_real_state.json';self.journal=self.root/'bitman_real_events.jsonl'
        self.snapshot_path=self.root/'bitman_real_snapshots.jsonl'
        self.state=json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        self.keys=set();self.failed=set()
        if self.journal.exists():
            for line in self.journal.read_text(encoding='utf-8').splitlines():
                try:self.keys.add(json.loads(line)['dedupe_key'])
                except (ValueError,KeyError):raise ValueError('EVENT_JOURNAL_INVALID')

    def cycle(self,hourly,now_ms):
        try:validate(hourly)
        except Exception:
            self.failed=set(TIMEFRAMES);print('BITMAN_REAL_PUBLIC_DATA_INVALID',flush=True);return {}
        result={}
        for tf,interval in TIMEFRAMES.items():
            try:result[tf]=self._update(hourly,now_ms,tf,interval)
            except Exception:
                self.failed.add(tf);print('BITMAN_REAL_OBSERVATION_FAILED '+tf,flush=True)
        return result

    def _update(self,hourly,now,tf,interval):
        rows=analyze(hourly,tf,now,self.config)
        if not rows:raise ValueError('INSUFFICIENT_HISTORY')
        s=rows[-1];stamp=s['candle_close'];old=self.state.get(tf)
        if s['state']=='BLOCKED' and 'DATOS INSUFICIENTES' in s['reasons']:raise ValueError('WARMUP')
        if stamp!=now//interval*interval:raise ValueError('STALE_PUBLIC_FRAME')
        if old and stamp<old['candle_close']:raise ValueError('TIME_REGRESSION')
        if old and stamp==old['candle_close'] and tf not in self.failed and old.get('signature')==self.signature:return old['snapshot']
        first=not old or old.get('signature')!=self.signature
        recovery=bool(tf in self.failed or old and stamp-old['candle_close']>interval)
        changed=bool(old and s['state']!=old['snapshot']['state'])
        significant=bool(s['event'] or changed)
        key=hashlib.sha256(f'{self.signature}|{tf}|{stamp}|{s["event"]}|{s["state"]}'.encode()).hexdigest()
        notify=not first and not recovery and significant and key not in self.keys
        if notify:
            append(self.journal,dict(s,dedupe_key=key,source='FORWARD_LIVE',observed_at=int(now)))
            self.keys.add(key)
        append(self.snapshot_path,dict(s,source='FORWARD_LIVE_CONTEXT',observed_at=int(now),
                                      current_status_only=bool(first or recovery)))
        new=dict(self.state);new[tf]=dict(candle_close=stamp,snapshot=s,signature=self.signature)
        atomic(self.state_path,new);self.state=new;self.failed.discard(tf)
        if notify and self.send:
            try:self.send(render(s))
            except Exception:print('BITMAN_REAL_DELIVERY_FAILED',flush=True)
        return s


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-csv',required=True)
    p.add_argument('--state-dir',required=True);p.add_argument('--reentry-max-bars',required=True,type=int)
    p.add_argument('--once',action='store_true');a=p.parse_args()
    observer=BitmanRealObserver(a.state_dir,a.reentry_max_bars,send=print)
    while True:
        try:observer.cycle(load_csv(a.input_csv),int(time.time()*1000))
        except Exception:print('BITMAN_REAL_INPUT_UNAVAILABLE',flush=True)
        if a.once:return
        time.sleep(60)


if __name__=='__main__':main()
