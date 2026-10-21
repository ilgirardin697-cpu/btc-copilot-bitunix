"""Journal-authoritative passive replay; historical warmup is never forward evidence."""
import math
from . import protocol as p
from .features import load_bootstrap, golden_check, calculate, snapshot, validate_week
from .models import calculate_models
from .outcomes import outcomes, causal_range
from .market import fetch_week, validate_url
from .journal import Journal, JournalInvalid, identifier

MAX_WEEKS_PER_RUN=4


def plain(value):
    import numpy as np
    if isinstance(value,dict): return {k:plain(v) for k,v in value.items()}
    if isinstance(value,(tuple,list,np.ndarray)): return [plain(v) for v in value]
    if isinstance(value,(bool,np.bool_)): return bool(value)
    if isinstance(value,(int,np.integer)): return int(value)
    if isinstance(value,(float,np.floating)): return float(value) if math.isfinite(value) else None
    return value


def context(rows,manifest):
    f=calculate(rows,manifest)
    models=calculate_models(f)
    return f,models,snapshot(f,models)


def event_payload(name,event,f,observed_at):
    i=event['index'];a=event['activation_index']
    high,low=causal_range(f['frame'],i,4)
    return dict(model=name,kind=event['kind'],side=event['side'],activation_week=int(f['frame'][a,0]),
        confirmation_week=int(f['frame'][i,0]),actual_lag=event['lag'],pullback_weeks=event['pullback_weeks'],
        ao=float(f['ao'][i]),ao_slope=float(f['ao_slope'][i]),ao_sign=str(f['sign'][i]),ao_color=str(f['color'][i]),
        bbwp=float(f['bbwp'][i]),bbwp_slope=float(f['bbwp_slope'][i]),
        frozen_range=dict(high=high,low=low,weeks=4),confirmation_close=float(f['frame'][i,4]),atr=float(f['atr'][i]),
        observed_at=observed_at,prospective=observed_at<int(f['available_at'][i])+p.WEEK,
        observation_class='PROSPECTIVE' if observed_at<int(f['available_at'][i])+p.WEEK else 'LATE_RECOVERY_NOT_PROSPECTIVE')


class Engine:
    def __init__(self,journal,bootstrap,manifest,now):
        self.journal=journal;self.bootstrap=bootstrap;self.manifest=manifest;self.now=now
        self.rows=list(bootstrap);self.observations={};self.events={};self.start=None
        self.f,self.models,self.current=context(self.rows,manifest)
        self.replay()

    def replay(self):
        bootstrapped=False
        for record in self.journal.records:
            kind,body=record['record_type'],record['payload']
            if record['created_at']>self.now:
                raise JournalInvalid()
            if kind=='FORWARD_OBSERVATION_START':
                if (self.start is not None or body.get('bootstrap_hash')!=self.manifest['sha256'] or body.get('known_close')!=self.manifest['available_at']
                    or body.get('activated_at')!=record['created_at'] or record['week_open']!=self.bootstrap[-1]['open_time']
                    or record['available_at']!=self.manifest['available_at']
                    or set(body)!={'deployment_source_sha','bootstrap_hash','known_close','activated_at','hypothesis'}
                    or type(body['deployment_source_sha']) is not str or len(body['deployment_source_sha'])!=40
                    or any(c not in '0123456789abcdef' for c in body['deployment_source_sha'])
                    or body['hypothesis']!='HYPOTHESIS FOR FORWARD OBSERVATION'
                    or record['source_hash']!=self.manifest['sha256']
                    or record['weekly_candle_hash']!=p.digest(self.bootstrap[-1])):
                    raise JournalInvalid()
                self.start=record
            elif kind=='BOOTSTRAP':
                if (self.start is None or bootstrapped or body!=dict(bootstrap_hash=self.manifest['sha256'],snapshot=self.current)
                    or any(record[k]!=self.start[k] for k in ('week_open','available_at','source_hash','weekly_candle_hash'))):
                    raise JournalInvalid()
                bootstrapped=True
            elif kind=='WEEK_SNAPSHOT' or kind=='RECOVERY':
                if not bootstrapped or body.get('role') not in ('FORWARD_WEEK','PRE_ACTIVATION_WARMUP'):
                    raise JournalInvalid()
                row=body.get('candle')
                try: validate_week(row)
                except Exception: raise JournalInvalid() from None
                if (row['open_time']!=self.rows[-1]['open_time']+p.WEEK or record['week_open']!=row['open_time']
                    or record['available_at']!=row['open_time']+p.WEEK or record['weekly_candle_hash']!=p.digest(row)):
                    raise JournalInvalid()
                warmup=record['available_at']<=self.start['created_at']
                if (set(body)!={'role','candle','snapshot','recovery_late'} or warmup!=(kind=='RECOVERY')
                    or body['role']!=('PRE_ACTIVATION_WARMUP' if warmup else 'FORWARD_WEEK')
                    or body['recovery_late']!=(record['created_at']>=record['available_at']+p.WEEK)):
                    raise JournalInvalid()
                self.rows.append(row)
                self.f,self.models,self.current=context(self.rows,self.manifest)
                if body['snapshot']!=self.current:
                    raise JournalInvalid()
                self.observations[record['week_open']]=record
            elif kind=='MODEL_EVENT':
                expected=self.expected_events().get(record['record_id'])
                source=self.observations.get(record['week_open'],{})
                if (expected is None or body!=expected or record['week_open']!=body['confirmation_week']
                    or record['available_at']!=body['confirmation_week']+p.WEEK
                    or any(record[k]!=source.get(k) for k in ('source_hash','weekly_candle_hash'))):
                    raise JournalInvalid()
                self.events[record['record_id']]=record
            elif kind=='OUTCOME':
                expected=self.expected_outcome(body.get('event_id'),body.get('horizon'))
                source=self.observations.get(record['week_open'],{})
                if (expected is None or body!=expected or record['available_at']!=body['matured_at']
                    or record['week_open']!=body['matured_at']-p.WEEK
                    or any(record[k]!=source.get(k) for k in ('source_hash','weekly_candle_hash'))):
                    raise JournalInvalid()

    def expected_events(self):
        result={}
        if self.start is None: return result
        for name,model in self.models.items():
            for event in model['events']:
                i=event['index'];a=event['activation_index']
                week=int(self.f['frame'][i,0]);observation=self.observations.get(week)
                if observation is None or self.f['available_at'][a]<=self.start['created_at']:
                    continue  # warmup activations are never promoted to forward events
                body=event_payload(name,event,self.f,observation['created_at'])
                result[identifier('MODEL_EVENT',week,body)]=body
        return result

    def expected_outcome(self,event_id,horizon):
        if event_id not in self.events or type(horizon) is not int or horizon not in (1,2,3,4): return None
        event=self.events[event_id]['payload']
        index=next((i for i,r in enumerate(self.rows) if r['open_time']==event['confirmation_week']),None)
        if index is None or index+horizon>=len(self.rows): return None
        matured=int(self.f['available_at'][index])+horizon*p.WEEK
        if matured>self.now: return None
        values=outcomes(self.f,4,horizon)
        measured=plain({k:v[index] for k,v in values.items()})
        measured['signed']=measured['forward']*event['side']
        return dict(event_id=event_id,horizon=horizon,matured_at=matured,prospective=event['prospective'],metrics=measured)

    def complete(self,now):
        for rid,body in self.expected_events().items():
            week=body['confirmation_week'];source=self.observations[week]
            self.journal.append('MODEL_EVENT',week,week+p.WEEK,body,now,source['source_hash'],source['weekly_candle_hash'])
            self.events[rid]=next(r for r in self.journal.records if r['record_id']==rid)
        for event_id,record in self.events.items():
            for h in (1,2,3,4):
                body=self.expected_outcome(event_id,h)
                if body is not None:
                    week=body['matured_at']-p.WEEK
                    observation=self.observations[week]
                    self.journal.append('OUTCOME',week,body['matured_at'],body,now,observation['source_hash'],observation['weekly_candle_hash'])

    def append_week(self,candle,source_hash,now):
        if candle['open_time']!=self.rows[-1]['open_time']+p.WEEK: raise ValueError('MISSING_WEEK')
        validate_week(candle)
        if candle['open_time']+p.WEEK>now: raise ValueError('WEEK_NOT_CLOSED')
        rows=self.rows+[candle]
        f,models,current=context(rows,self.manifest)
        available=candle['open_time']+p.WEEK
        warmup=available<=self.start['created_at']
        kind='RECOVERY' if warmup else 'WEEK_SNAPSHOT'
        body=dict(role='PRE_ACTIVATION_WARMUP' if warmup else 'FORWARD_WEEK',candle=candle,snapshot=current,
                  recovery_late=now>=available+p.WEEK)
        self.journal.append(kind,candle['open_time'],available,body,now,source_hash,p.digest(candle))
        self.rows,self.f,self.models,self.current=rows,f,models,current
        self.observations[candle['open_time']]=self.journal.records[-1]
        self.complete(now)

    def view(self,status='HEALTHY'):
        prospective={rid:r for rid,r in self.events.items() if r['payload']['prospective']}
        horizons={str(h):sum(r['record_type']=='OUTCOME' and r['payload']['horizon']==h and r['payload']['prospective']
                               for r in self.journal.records) for h in (1,2,3,4)}
        matured=horizons['4']
        recent=max(prospective.values(),key=lambda r:(r['payload']['confirmation_week'],r['payload']['model']))['payload'] if prospective else None
        return dict(status=status,week_open=self.rows[-1]['open_time'],snapshot=self.current,
                    forward_events=len(prospective),active=len(prospective)-matured,matured=matured,
                    horizons=horizons,late_recovery_events=len(self.events)-len(prospective),latest_event=recent,
                    evidence='INSUFFICIENT',next_due=self.rows[-1]['open_time']+2*p.WEEK+p.MARGIN,
                    journal_records=len(self.journal.records),journal_tip=self.journal.records[-1]['record_hash'])


def run(folder,url,source_sha,now,fetch=fetch_week):
    p.verify();validate_url(url)
    if type(source_sha) is not str or len(source_sha)!=40 or any(c not in '0123456789abcdef' for c in source_sha):
        raise ValueError('DEPLOYMENT_SOURCE_UNAVAILABLE')
    bootstrap,manifest=load_bootstrap();gold=golden_check(bootstrap,manifest)
    if now<manifest['available_at']: raise ValueError('BOOTSTRAP_NOT_AVAILABLE')
    with Journal(folder) as journal:
        if not journal.records:
            body=dict(deployment_source_sha=source_sha,bootstrap_hash=manifest['sha256'],known_close=manifest['available_at'],
                      activated_at=now,hypothesis='HYPOTHESIS FOR FORWARD OBSERVATION')
            journal.append('FORWARD_OBSERVATION_START',bootstrap[-1]['open_time'],manifest['available_at'],body,
                           now,manifest['sha256'],p.digest(bootstrap[-1]))
        if not any(r['record_type']=='BOOTSTRAP' for r in journal.records):
            if len(journal.records)!=1:
                raise JournalInvalid()
            Engine(journal,bootstrap,manifest,now)  # verify a valid START-only crash prefix before appending
            journal.append('BOOTSTRAP',bootstrap[-1]['open_time'],manifest['available_at'],
                dict(bootstrap_hash=manifest['sha256'],snapshot=gold),now,manifest['sha256'],p.digest(bootstrap[-1]))
        engine=Engine(journal,bootstrap,manifest,now)
        engine.complete(now)
        count=0
        try:
            while engine.rows[-1]['open_time']+2*p.WEEK+p.MARGIN<=now and count<MAX_WEEKS_PER_RUN:
                opening=engine.rows[-1]['open_time']+p.WEEK
                candle,source_hash=fetch(opening,now,url)
                engine.append_week(candle,source_hash,now);count+=1
        except Exception:
            if journal.poisoned: raise
            view=engine.view('DEGRADED');view['next_due']=now+60000
        else:
            gap=engine.rows[-1]['open_time']+2*p.WEEK+p.MARGIN<=now
            view=engine.view('DEGRADED' if gap else 'HEALTHY')
            if gap: view['next_due']=now+60000
        view['updated_at']=now
        journal.save_state(view)
        return view
