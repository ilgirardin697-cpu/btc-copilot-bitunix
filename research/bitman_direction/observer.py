"""Unstarted file-fed telemetry/dedupe; no sender and no operational dependency."""
import copy
import hashlib
import json
from pathlib import Path
from research.bitman_real.storage import append,atomic
from . import core
from .spec import VERSION,HOUR
from .telegram import render
from .confirmed import confirmed_cache


class DirectionObserver:
    shadow_only=True
    trade_authority=False

    def __init__(self,directory):
        self.root=Path(directory).resolve()
        if any(x.lower() in ('guardian','mlrsi','copilot_audit','early_breakout','v8','bitman_real') for x in self.root.parts):
            raise ValueError('SEPARATE_DIRECTION_RESEARCH_STORAGE_REQUIRED')
        self.root.mkdir(parents=True,exist_ok=True);self.path=self.root/'direction_state.json';self.journal=self.root/'direction_events.jsonl'
        self.state=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}
        if self.state and self.state.get('version')!=VERSION:raise ValueError('STATE_VERSION_INVALID')
        self.keys=set()
        if self.journal.exists():
            with self.journal.open(encoding='utf-8') as stream:
                for line in stream:self.keys.add(json.loads(line)['dedupe_key'])
        self.failed=False;self.first=True

    def cycle(self,hourly,now_ms,confirmed=None):
        try:return self._cycle(hourly,now_ms,confirmed)
        except Exception:
            self.failed=True
            return dict(status='DIRECTION_OBSERVATION_FAILED',messages=[],trade_authority=False)

    def _cycle(self,hourly,now,confirmed):
        data=core.prepare(hourly,now);stamp=int(data['times'][-1]);old=self.state
        if stamp!=now//HOUR*HOUR:raise ValueError('STALE_PUBLIC_HISTORY')
        if old and stamp<old['timestamp']:raise ValueError('TIME_REGRESSION')
        if old and stamp==old['timestamp'] and not self.failed:
            self.first=False;return dict(snapshot=copy.deepcopy(old['snapshot']),messages=[],trade_authority=False)
        ml=confirmed_cache(confirmed or {},now)
        s=core.snapshot(data,len(data['times'])-1,ml)
        signature='|'.join(str(s[k]) for k in ('state','detail','strength','evidence_grade'))
        recovery=self.first or self.failed or not old or stamp-old['timestamp']>HOUR
        changed=bool(old and old['signature']!=signature)
        episode=dict(old.get('episode',{})) if old else {}
        if not episode or old['snapshot']['state']!=s['state']:
            episode=dict(state=s['state'],started_at=stamp,reference=s['reference_price'],direction=s['direction'],mfe=0.,mae=0.)
        elif s['state'] in ('UP','DOWN'):
            new=data['bars'][(data['bars'][:,0]>=old['timestamp'])&(data['bars'][:,0]+HOUR<=stamp)]
            if len(new):
                ref=episode['reference'];side=episode['direction']
                favorable=new[:,2]/ref-1 if side==1 else 1-new[:,3]/ref
                adverse=new[:,3]/ref-1 if side==1 else 1-new[:,2]/ref
                episode['mfe']=max(episode['mfe'],float(max(favorable)));episode['mae']=min(episode['mae'],float(min(adverse)))
        s['extension_tracker']=dict(status='REACHED_OBSERVED' if episode['mfe']>=.10 else 'TRACKING' if s['state'] in ('UP','DOWN') else 'NO_DIRECTIONAL_EPISODE',
            episode_started_at=episode['started_at'],mfe=episode['mfe'],mae=episode['mae'])
        key=hashlib.sha256(f'{VERSION}|{stamp}|{signature}'.encode()).hexdigest()
        notify=changed and not recovery and key not in self.keys
        if notify:
            append(self.journal,dict(snapshot=s,dedupe_key=key,source='FORWARD_SIMULATED_FILE_FEED',trade_authority=False));self.keys.add(key)
        state=dict(version=VERSION,timestamp=stamp,signature=signature,snapshot=s,episode=episode)
        atomic(self.path,state);self.state=state;self.failed=False;self.first=False
        return dict(snapshot=copy.deepcopy(s),messages=[render(s)] if notify else [],current_status_only=bool(recovery),trade_authority=False)
