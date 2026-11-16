"""Disabled-by-default offline-prepared core. No network loop or service hook."""
import hashlib,json,time,copy
import numpy as np
from ...evaluate import clean
from ...outcomes import outcome
from . import protocol
from .journal import Journal,JournalError,digest
from .market import Receipt,klines,funding,candle_key,decode,HOUR,VENUE
from .models import Engine,feature_sets,PROFILES
from .observations import Facts


def receipt_from(meta,raw):
    return Receipt(raw,meta['url'],meta['query'],meta['request_started_ms'],meta['received_at_ms'],meta['exchange_time_ms'],meta['status'])


def passive_inputs(a,f):
    view=a.view();view.flags.writeable=False;copied={}
    for k,v in f.items():
        x=v.view();x.flags.writeable=False;copied[k]=x
    return view,copied


class Observer:
    def __init__(self,root,enabled=False,mode='OFFLINE_TEST',authorization_ref=None,source_sha=None,clock=None,sidecar=None):
        self.enabled=enabled;self.root=root;self.mode=mode;self.authorization=authorization_ref;self.source_sha=source_sha
        self.clock=clock or (lambda:int(time.time()*1000));self.store=None;self.status='DISABLED';self.a=np.empty((0,6));self.observations={}
        self.sources={};self.candle_keys={};self.coverage=[];self.funding_rows={};self.completed=set();self.engines={p:Engine(p) for p in PROFILES}
        self.facts=sidecar or Facts();self.start_record=None;self.pending_gap=None
        if not enabled:return
        if mode not in ('OFFLINE_TEST','FORWARD_SHADOW'):raise ValueError('UNKNOWN_OBSERVER_MODE')
        if mode=='FORWARD_SHADOW' and (not authorization_ref or not source_sha or len(source_sha)!=40 or any(c not in '0123456789abcdef' for c in source_sha)):raise ValueError('SEPARATE_ACTIVATION_APPROVAL_REQUIRED')
        self.registry=protocol.verify();self.cfg=protocol.config();self.store=Journal(root,self.registry)
        try:self._replay()
        except Exception:self.store.close();raise
        self.status='PREPARED' if not self.start_record else self.status

    def _now(self):return int(self.clock())

    def _source(self,r,kind,write):
        rows=klines(r) if kind=='KLINES' else funding(r);meta=r.metadata();key=digest(meta)
        if r.received_at_ms>self._now():raise ValueError('RECEIPT_FROM_FUTURE')
        if write:
            blob=self.store.blob(r.body)
            self.store.append('PUBLIC_SOURCE','SOURCE:'+key,dict(source_kind=kind,blob=blob,metadata=meta),self._now())
        self.sources[key]=(r,rows);return key,rows

    def start(self,seed_receipts):
        if not self.enabled:return 'DISABLED'
        if self.start_record:raise ValueError('SESSION_ALREADY_STARTED')
        chunks=[];refs=[]
        for r in seed_receipts:
            a=klines(r)
            if r.received_at_ms>self._now():raise ValueError('SEED_FROM_FUTURE')
            chunks.append(a);refs.append(dict(blob=hashlib.sha256(r.body).hexdigest(),metadata=r.metadata()))
        a=np.concatenate(chunks) if chunks else np.empty((0,6))
        if len(a)<self.cfg['collection']['minimum_seed_hours'] or not (np.diff(a[:,0])==HOUR).all():raise ValueError('BOOTSTRAP_INCOMPLETE')
        now=self._now()
        if a[-1,0]+HOUR>now:raise ValueError('OPEN_BOOTSTRAP')
        for r in seed_receipts:self.store.blob(r.body)
        payload=dict(mode=self.mode,authorization_ref=self.authorization,source_sha=self.source_sha,activated_at_ms=now,
                     first_eligible_open_ms=(now//HOUR+1)*HOUR,seed=refs,seed_sha256=digest(a.tolist()),
                     historical_events_imported=0,hypothesis='HYPOTHESIS_FOR_FORWARD_OBSERVATION',trade_authority='NONE')
        self.store.append('SESSION_START','START:'+self.registry,clean(payload),now)
        self._initialize(payload);self.start_record=payload;self.status='HEALTHY'
        return 'HEALTHY'

    def _initialize(self,payload):
        chunks=[]
        for ref in payload['seed']:
            raw=self.store.read_blob(ref['blob']);chunks.append(klines(receipt_from(ref['metadata'],raw)))
            self.candle_keys.update({int(row[0]):candle_key(row) for row in decode(raw)})
        a=np.concatenate(chunks)
        if (digest(a.tolist())!=payload['seed_sha256'] or len(a)<6000 or not (np.diff(a[:,0])==HOUR).all() or
            a[-1,0]+HOUR>payload['activated_at_ms'] or payload['historical_events_imported']!=0 or payload['trade_authority']!='NONE'):
            raise JournalError('BOOTSTRAP_INVALID')
        self.a=a;sets=feature_sets(a)
        for p,e in self.engines.items():e.warm(a,sets[p])
        self.facts.warm(*passive_inputs(a,sets['TURN22_FORWARD_V1']));self.start_record=payload

    def _snapshot(self,row,receipt,recorded,comparative_override=None):
        a=np.concatenate([self.a,np.asarray([row],float)]);i=len(a)-1;sets=feature_sets(a);profiles={};claims=[]
        for p,e in self.engines.items():
            events,audit,attempts=e.step(i,a,sets[p]);out=[]
            for event in events:
                event=dict(event);event['event_id']=p+':'+event['event_id'];event['protocol_version']=p
                event['duplicate_group_id']=str(event['side'])+':'+str(int(row[0]))
                vertex=event['tokens']['ao']-e.n
                event['episode_anchor_id']=str(event['side'])+':'+str(int(a[vertex,0]+HOUR))
                event['comparison_anchor_id']=event['pattern']+':'+event['episode_anchor_id']
                event['has_pre_activation_tokens']=any(a[j,0]<self.start_record['first_eligible_open_ms'] for j in event['tokens'].values())
                claims.append(event);out.append(event)
            profiles[p]=dict(events=out,audit=audit,attempts=attempts)
        f=sets['TURN22_FORWARD_V1']
        if comparative_override is not None:extra=comparative_override
        else:
            backup=copy.deepcopy(self.facts)
            try:extra=self.facts.step(i,*passive_inputs(a,f))
            except Exception:self.facts=backup;extra=dict(status='COMPARATIVE_UNAVAILABLE',events=[],watch=None)
        values={name:clean(f[key][i]) for name,key in [('ADX','adx'),('DI_PLUS','plus_di'),('DI_MINUS','minus_di'),('AO','ao'),('PECECILLOS','minnows'),('RED_EMA15_TENDENCIA','kon_signal'),('BBWP','bbwp'),('ATR14','atr')]}
        slopes={name:clean(f[key][i]-f[key][i-1]) for name,key in [('ADX','adx'),('AO','ao'),('PECECILLOS','minnows'),('RED_EMA15_TENDENCIA','kon_signal'),('BBWP','bbwp')]}
        available=int(row[0]+HOUR);lag=recorded-available;on_time=0<=lag<=self.cfg['collection']['on_time_lag_ms']
        from datetime import datetime
        first,last=self.cfg['cohort']['planned_22_window']
        bounds=[int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()*1000) for s in (first,last)]
        in_window=bounds[0]<=available<bounds[1]
        oid=f'{VENUE}:BTCUSDT:H1:{int(row[0])}'
        rank=f['vol_rank'][i]
        duplicates={}
        for e in claims:duplicates.setdefault(e['duplicate_group_id'],[]).append(e['event_id'])
        payload=dict(observation_id=oid,open_time=int(row[0]),available_at_ms=available,recorded_at_ms=recorded,
                     source_received_at_ms=receipt.received_at_ms,capture_delay_ms=lag,on_time=on_time,
                     forward_eligible=bool(self.mode=='FORWARD_SHADOW' and on_time and in_window and row[0]>=self.start_record['first_eligible_open_ms']),
                     collection_class='ON_TIME' if on_time else 'LATE_RECOVERY',mode=self.mode,
                     candle=list(row),candle_hash=digest(list(row)),values=values,slopes=slopes,
                     regime_4h=clean(f['regime4h'][i]),volatility_tercile=int(min(2,int(rank*3))) if np.isfinite(rank) else None,
                     profiles=profiles,duplicate_groups=duplicates,unique_model_claims=len(duplicates),
                     comparative=extra,bootstrap_block_7d=int(row[0]//(168*HOUR)),trade_authority='NONE')
        return clean(payload),a

    def ingest(self,receipt):
        if not self.enabled:return 'DISABLED'
        if not self.start_record:raise ValueError('SESSION_NOT_STARTED')
        if self.status=='DEGRADED':raise ValueError('OBSERVER_DEGRADED_REVIEW_REQUIRED')
        try:key,rows=self._source(receipt,'KLINES',True)
        except ValueError:
            self.note_failure('PUBLIC_HTTP_ERROR' if receipt.status!=200 else 'PUBLIC_SCHEMA_INVALID');raise
        raw_rows=decode(receipt.body)
        for index,row in enumerate(rows):
            t=int(row[0]);old=np.flatnonzero(self.a[:,0]==t);raw_key=candle_key(raw_rows[index])
            if len(old):
                if self.candle_keys[t]!=raw_key:
                    self.store.append('SOURCE_REVISION','REVISION:'+str(t)+':'+raw_key,dict(open_time=t,source=key,old_candle_hash=self.candle_keys[t],new_candle_hash=raw_key),self._now());self.status='DEGRADED';return 'DEGRADED'
                continue
            expected=int(self.a[-1,0]+HOUR)
            if t!=expected:
                rid='GAP:'+str(expected)+':'+str(t)
                if rid not in self.store.ids:self.store.append('DATA_GAP',rid,dict(expected=expected,received=t,source=key),self._now())
                self.pending_gap=max(t,self.pending_gap or t);self.status='GAP_PENDING';return 'MISSING_HOUR'
            recorded=self._now()
            try:
                payload,a=self._snapshot(row.tolist(),receipt,recorded);payload['source']=key;payload['source_row']=index
                payload['raw_candle_hash']=raw_key
                self.store.append('CANDLE','CANDLE:'+str(t),payload,recorded)
            except Exception:
                # A detector may have advanced in memory. Never retry it before
                # reopening and replaying the last durable prefix.
                self.status='DEGRADED';raise
            self.a=a;self.observations[payload['observation_id']]=payload
            self.candle_keys[t]=raw_key
            if self.pending_gap is not None and t>=self.pending_gap:self.pending_gap=None
            self.status='GAP_PENDING' if self.pending_gap is not None else 'HEALTHY'
            self._mature()
        self._mature();return self.status

    def note_failure(self,code):
        if not self.enabled:return 'DISABLED'
        if not self.start_record:raise ValueError('SESSION_NOT_STARTED')
        if code not in {'PUBLIC_HTTP_ERROR','PUBLIC_TIMEOUT','PUBLIC_SCHEMA_INVALID','CLOCK_UNCERTAIN','COLLECTOR_UNAVAILABLE'}:raise ValueError('STATIC_FAILURE_CODE_ONLY')
        t=int(self.a[-1,0]+HOUR);rid='FAILURE:'+str(t)+':'+code
        if rid not in self.store.ids:self.store.append('COLLECTION_FAILURE',rid,dict(expected_open=t,code=code),self._now())
        return code

    def mature(self):
        if not self.enabled:return 'DISABLED'
        if not self.start_record or self.status=='DEGRADED':raise ValueError('SESSION_UNAVAILABLE')
        self._mature();return self.status

    def ingest_funding(self,receipt):
        if not self.enabled:return 'DISABLED'
        if not self.start_record or self.status=='DEGRADED':raise ValueError('SESSION_UNAVAILABLE')
        key,rows=self._source(receipt,'FUNDING',True)
        for row in rows:
            if row['time'] in self.funding_rows and self.funding_rows[row['time']]!=row:
                self.store.append('FUNDING_REVISION','FUND_REV:'+key,dict(source=key),self._now());self.status='DEGRADED';return 'DEGRADED'
        p=dict(source=key,start=receipt.query['startTime'],end=receipt.query['endTime'],settlements=rows)
        self.store.append('FUNDING_COVERAGE','FUNDING:'+key,p,self._now());self.coverage.append((p['start'],p['end']))
        self.funding_rows.update({r['time']:r for r in rows});self._mature();return 'HEALTHY'

    def _covered(self,start,end):
        cursor=start
        for lo,hi in sorted(self.coverage):
            if lo>cursor:continue
            if hi>=cursor:cursor=max(cursor,hi+1)
            if cursor>end:return True
        return False

    def _result(self,obs,h,side,costed):
        i=int(np.searchsorted(self.a[:,0],obs['open_time']));j=i+1+h
        if j>=len(self.a) or obs['values']['ATR14'] is None:return None
        entry_at=int(self.a[i+1,0]);exit_at=int(self.a[j,0]);fund=[]
        if costed:
            if not self._covered(entry_at,exit_at):return None
            used=[r for t,r in self.funding_rows.items() if entry_at<=t<=exit_at]
            if any(r['mark'] is None for r in used):return None
            fund=np.asarray([[r['time'],r['rate'],r['mark'],0,r['mark'],r['mark']] for r in sorted(used,key=lambda r:r['time'])],float).reshape((-1,6))
        r=outcome(self.a,np.asarray(fund,float).reshape((-1,6)),i,side,obs['values']['ATR14'],h)
        raw=side*(self.a[j,1]-self.a[i+1,1])/self.a[i+1,1]
        result=dict(observation_id=obs['observation_id'],horizon_h=h,side=side,reference_at_ms=entry_at,
                    reference_price=float(self.a[i+1,1]),endpoint_at_ms=exit_at,endpoint_price=float(self.a[j,1]),
                    data_available_at_ms=int(self.a[j,0]+HOUR),reference_precedes_recording=entry_at<obs['recorded_at_ms'],
                    measurement='HYPOTHETICAL_NEXT_OPEN_NOT_A_FILL',raw_price_fraction=float(raw),
                    direction_result='FAVORED' if raw>0 else 'OPPOSED_OR_FLAT',
                    net_fraction=r['net_fraction'] if costed else None,net_optimistic=r['optimistic_fraction'] if costed else None,
                    exact_net=r['exact_net_fraction'] if costed else None,net_atr=r['net_atr'] if costed else None,
                    funding_status='COVERED_WITH_BOUNDARY_BOUNDS' if costed else 'PENDING_NOT_ZERO',
                    boundary_settlements=r['boundary_settlements'] if costed else None,
                    observational_fact_ids=[e['fact_id'] for e in obs['comparative'].get('events',[])],
                    model_event_ids=[e['event_id'] for p in obs['profiles'].values() for e in p['events']])
        return clean(result)

    def _mature(self):
        for obs in self.observations.values():
            for h in (4,12,24):
                for side in (1,-1):
                    for costed in (False,True):
                        rid=f'{"COST" if costed else "PRICE"}:{obs["observation_id"]}:H{h}:{side}'
                        if rid in self.completed:continue
                        result=self._result(obs,h,side,costed)
                        if result is not None:
                            self.store.append('COSTED_OUTCOME' if costed else 'PRICE_OUTCOME',rid,result,self._now());self.completed.add(rid)

    def _replay(self):
        for record in self.store.records:
            kind,p=record['kind'],record['payload']
            if self.status=='DEGRADED' and kind not in ('COLLECTION_FAILURE',):raise JournalError('CAPTURE_AFTER_REVISION_INVALID')
            if kind=='SESSION_START':
                if (self.start_record or p['mode']!=self.mode or p['activated_at_ms']!=record['created_at_ms'] or
                    p['first_eligible_open_ms']!=(p['activated_at_ms']//HOUR+1)*HOUR or
                    p['source_sha']!=self.source_sha or p['authorization_ref']!=self.authorization):raise JournalError('SESSION_IDENTITY_INVALID')
                if any(s['metadata']['received_at_ms']>p['activated_at_ms'] for s in p['seed']):raise JournalError('SEED_AFTER_ACTIVATION')
                self._initialize(p);self.status='HEALTHY'
            elif kind=='PUBLIC_SOURCE':
                r=receipt_from(p['metadata'],self.store.read_blob(p['blob']));self._source(r,p['source_kind'],False)
            elif kind=='CANDLE':
                r,rows=self.sources[p['source']];row=rows[p['source_row']].tolist()
                if row[0]!=self.a[-1,0]+HOUR:raise JournalError('REPLAY_MISSING_HOUR')
                override=p['comparative'] if p['comparative'].get('status')=='COMPARATIVE_UNAVAILABLE' else None
                expected,a=self._snapshot(row,r,record['created_at_ms'],override);expected.update(source=p['source'],source_row=p['source_row'])
                expected['raw_candle_hash']=candle_key(decode(r.body)[p['source_row']])
                if expected!=p:raise JournalError('SEMANTIC_REPLAY_DIFFERENCE')
                self.a=a;self.observations[p['observation_id']]=p
                self.candle_keys[int(row[0])]=p['raw_candle_hash']
                if self.pending_gap is not None and row[0]>=self.pending_gap:self.pending_gap=None;self.status='HEALTHY'
            elif kind=='FUNDING_COVERAGE':
                r,rows=self.sources[p['source']]
                if rows!=p['settlements'] or (r.query['startTime'],r.query['endTime'])!=(p['start'],p['end']):raise JournalError('FUNDING_REPLAY_INVALID')
                self.coverage.append((p['start'],p['end']));self.funding_rows.update({r['time']:r for r in rows})
            elif kind in ('PRICE_OUTCOME','COSTED_OUTCOME'):
                expected=self._result(self.observations[p['observation_id']],p['horizon_h'],p['side'],kind=='COSTED_OUTCOME')
                if expected!=p or record['created_at_ms']<p['data_available_at_ms']:raise JournalError('EARLY_OR_CHANGED_OUTCOME')
                self.completed.add(record['record_id'])
            elif kind in ('SOURCE_REVISION','FUNDING_REVISION'):self.status='DEGRADED'
            elif kind=='DATA_GAP':self.pending_gap=max(p['received'],self.pending_gap or p['received']);self.status='GAP_PENDING'
            elif kind!='COLLECTION_FAILURE':raise JournalError('UNKNOWN_JOURNAL_RECORD')

    def close(self):
        if self.store:self.store.close()
