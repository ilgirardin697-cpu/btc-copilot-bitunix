"""Five genuine acquisition times per cycle. No historical prediction backfill."""
from datetime import date, datetime, timedelta
import json
import re
import uuid
import numpy as np

from .features import NY,HOUR,MINUTE,schedule,window,require_rows,atr_series,vector,reference_vectors,final_label
from .frozen import ANCHORS,predict,read_json,structure_predict
from .journal import EvidenceError,safe_error
from .market import decode_klines


def settings():
    from pathlib import Path
    return json.loads((Path(__file__).parent/'protocol.json').read_text(encoding='utf-8'))


def days(first,last):
    day=date.fromisoformat(first); end=date.fromisoformat(last)
    while day<=end:
        yield day
        day+=timedelta(days=1)


def valid_schedule(day):
    s=schedule(day)
    if (s['close']-s['london']!=4*HOUR or s['asia_end']-s['asia']!=4*HOUR
        or datetime.fromtimestamp(s['london']/1000,NY).hour!=2):
        raise EvidenceError('DST_INCOMPLETE_CYCLE')
    return s


def anchor_id(day,minute):
    return f'{day.isoformat()}:{minute:02d}'


class Observer:
    def __init__(self,store,market,clock,source_sha):
        self.store,self.market,self.clock=store,market,clock
        self.protocol=settings();self.status='HEALTHY';self.last_code=None
        self.clock_meta=None;self.context_cache={}
        if not re.fullmatch('[0-9a-f]{40}',source_sha):
            raise EvidenceError('REVIEWED_SOURCE_SHA_REQUIRED')
        if not store.rows:
            store.append('ACTIVATION','ACTIVATION',dict(source_sha=source_sha,
                cohort='IGOD_PRICE_BINANCE_FORWARD_V1',model_version=store.freeze['model_version'],
                hypothesis='HYPOTHESIS_FOR_FORWARD_OBSERVATION',trade_authority='NONE',
                first_cycle=self.protocol['first_cycle'],last_cycle=self.protocol['last_cycle']))
        else:
            store.append('RECOVERY','RECOVERY:'+uuid.uuid4().hex,
                         dict(source_sha=source_sha,previous_records=len(store.rows),
                              previous_tip=store.rows[-1]['record_hash'],predictions_not_backfilled=True))
        self.activation_at=store.by_id['ACTIVATION']['created_at']

    def verified_clock(self):
        now=self.clock.now_ms()
        if self.clock_meta is None or now-self.clock_meta['received_at']>10000 or now<self.clock_meta['received_at']:
            self.clock_meta=self.market.clock_check()
        return self.clock_meta

    def server_upper(self,meta):
        return meta['server_time']+meta['elapsed_ms']+max(0,self.clock.monotonic_ms()-meta['monotonic_received_ms'])

    def _context(self,day,s):
        rid='CONTEXT:'+day.isoformat()
        if rid not in self.store.by_id:
            h,meta=self.market.klines(s['radar']-1000*HOUR,s['radar'],'1h')
            self.store.append('CONTEXT',rid,dict(cycle=day.isoformat(),rows=1000,
                start=s['radar']-1000*HOUR,end=s['radar'],source=meta,raw_refs=[meta['raw_sha256']],
                purpose='CLOSED_INDICATOR_WARMUP_NOT_HISTORICAL_FORECASTS'))
        record=self.store.by_id[rid]
        if rid not in self.context_cache:
            raw=json.loads(self.store.read_raw(record['data']['source']['raw_sha256']))
            h=decode_klines(raw,s['radar']-1000*HOUR,s['radar'],HOUR)
            self.context_cache[rid]=h
        return rid,self.context_cache[rid]

    def _failure(self,rid,day,phase,error,attempt):
        code=safe_error(error)
        meta=getattr(error,'meta',None)
        data=dict(cycle=day.isoformat(),phase=phase,code=code,attempt=attempt,
                  raw_refs=[meta['raw_sha256']] if meta else [])
        if meta:data['source']=meta
        self.store.append('FAILURE',rid,data)
        self.status='DEGRADED';self.last_code=code

    def _miss(self,day,minute,reason):
        rid='MISSED:'+anchor_id(day,minute)
        if rid not in self.store.by_id:
            self.store.append('MISSED',rid,dict(cycle=day.isoformat(),minute=minute,reason=reason,
                                               reconstructed_prediction=False))

    def capture(self,day,minute,s):
        key=anchor_id(day,minute);pid='PREDICTION:'+key;receipt='DURABILITY:'+key
        if receipt in self.store.by_id or 'MISSED:'+key in self.store.by_id:return
        if pid in self.store.by_id:
            self._miss(day,minute,'PREDICTION_WITHOUT_DURABILITY_WITNESS');return
        available=s['radar']+minute*MINUTE
        deadline=min(available+120000,s['close']-1)
        attempts=[r for r in self.store.rows if r['record_type']=='ATTEMPT' and r['data'].get('anchor')==key]
        if len(attempts)>=3:
            self._miss(day,minute,'ACQUISITION_ATTEMPTS_EXHAUSTED');return
        if attempts and self.clock.now_ms()-attempts[-1]['created_at']<10000:return
        if self.clock.now_ms()>deadline:
            self._miss(day,minute,'DEADLINE_EXPIRED_NO_BACKFILL');return
        n=len(attempts)+1
        try:
            self.store.append('ATTEMPT',f'ATTEMPT:{key}:{n}',dict(cycle=day.isoformat(),anchor=key,attempt=n))
            cm=self.verified_clock()
            if cm['server_time']<available:
                raise EvidenceError('CLOCK_NOT_AT_ANCHOR')
            context_id,h=self._context(day,s)
            a=window(h,s['asia'],s['asia_end']); l=window(h,s['london'],s['radar'])
            require_rows(a,s['asia'],s['asia_end'],HOUR);require_rows(l,s['london'],s['radar'],HOUR)
            sources=[self.store.by_id[context_id]['data']['source']]
            prefix=np.empty((0,5))
            if minute:
                prefix,meta=self.market.klines(s['radar'],available,'1m');sources.append(meta)
            x=vector(a,l,prefix,float(atr_series(h)[-1]),minute)
            p=predict(x)
            emitted=self.clock.now_ms()
            if emitted>deadline or self.server_upper(cm)>deadline:
                self._miss(day,minute,'ACQUISITION_FINISHED_LATE');return
            self.store.append('PREDICTION',pid,dict(cycle=day.isoformat(),minute=minute,available_at=available,
                emitted_at=emitted,context_id=context_id,features=x.tolist(),probabilities=p.tolist(),
                prior=read_json('frozen_PRIOR.json'),structure=structure_predict(x,read_json('frozen_STRUCTURE.json')).tolist(),
                sources=sources,clock=cm,raw_refs=[m['raw_sha256'] for m in sources]+[cm['raw_sha256']],
                model_version=self.store.freeze['model_version'],status='EXPERIMENTAL_NOT_VALIDATED'))
            # The second record witnesses the REAL time AFTER prediction fsync.
            # A crash before this witness never manufactures a receipt on replay.
            durable=self.clock.now_ms()
            server_durable_upper=self.server_upper(cm)
            if durable>deadline or server_durable_upper>deadline:
                self._miss(day,minute,'PREDICTION_DURABILITY_LATE');return
            self.store.append('DURABILITY',receipt,dict(cycle=day.isoformat(),minute=minute,
                              prediction_id=pid,prediction_durable_at=durable,
                              server_utc_upper_at_fsync=server_durable_upper,eligible=True))
            self.status='HEALTHY';self.last_code=None
        except Exception as error:
            if self.store.poisoned:raise
            self._failure(f'FAILURE:{key}:{n}',day,'FORECAST',error,n)

    def settle(self,day,s):
        rid='OUTCOME:'+day.isoformat()
        if rid in self.store.by_id:return
        p=[r for r in self.store.rows if r['record_type']=='PREDICTION' and r['data']['cycle']==day.isoformat()]
        if not p:return
        local_today=datetime.fromtimestamp(self.clock.now_ms()/1000,NY).date().isoformat()
        attempts=[r for r in self.store.rows if r['record_type']=='ATTEMPT'
                  and r['data'].get('outcome')==day.isoformat() and r['data'].get('attempt_day')==local_today]
        if len(attempts)>=3:return
        if attempts and self.clock.now_ms()-attempts[-1]['created_at']<60000:return
        n=len(attempts)+1
        try:
            self.store.append('ATTEMPT',f'LABEL_ATTEMPT:{day}:{local_today}:{n}',dict(cycle=day.isoformat(),
                outcome=day.isoformat(),attempt_day=local_today,attempt=n))
            cm=self.verified_clock()
            if cm['server_time']<s['end']:
                raise EvidenceError('OUTCOME_NOT_MATURE_SERVER_CLOCK')
            h,hm=self.market.klines(s['asia'],s['end'],'1h')
            m,mm=self.market.klines(s['radar'],s['end'],'1m')
            result=final_label(day,h,m,self.clock.now_ms())
            _,context=self._context(day,s)
            context_same=np.array_equal(window(context,s['asia'],s['radar']),window(h,s['asia'],s['radar']))
            # ATR remains causal, from the original context, while the new H1 data
            # provides final London and outcomes. Revisions are flagged, not erased.
            joined=np.concatenate([context[context[:,0]<s['asia']],h])
            ref=reference_vectors(day,joined,m)
            comparison={r['record_id']:dict(max_feature_error=float(abs(ref[r['data']['minute']]-r['data']['features']).max()),
                 passed=bool(np.allclose(ref[r['data']['minute']],r['data']['features'],rtol=1e-8,atol=1e-8))) for r in p}
            stable=context_same and all(c['passed'] for c in comparison.values())
            self.store.append('OUTCOME',rid,dict(cycle=day.isoformat(),outcome=result,source_h1=hm,source_1m=mm,
                original_context_unchanged=context_same,feature_comparison=comparison,quality_pass=stable,
                data_revision_detected=not stable,raw_refs=[hm['raw_sha256'],mm['raw_sha256'],cm['raw_sha256']],
                role='OBSERVED_POST06_TARGET_FIRST_TOUCH_NOT_TRADING_RESULT'))
            self.status='HEALTHY';self.last_code=None
        except Exception as error:
            if self.store.poisoned:raise
            self._failure(f'LABEL_FAILURE:{day}:{local_today}:{n}',day,'OUTCOME',error,n)

    def tick(self):
        now=self.clock.now_ms(); completed=[]
        for day in days(self.protocol['first_cycle'],self.protocol['last_cycle']):
            rough=schedule(day)
            if now<rough['radar']:break
            for minute in ANCHORS:
                key=anchor_id(day,minute)
                if 'DURABILITY:'+key in self.store.by_id or 'MISSED:'+key in self.store.by_id:continue
                available=rough['radar']+minute*MINUTE
                if now<available+2000:continue
                # Even MISSED decisions require a verified clock. No data fetch
                # is needed when an anchor is already lost.
                try:
                    s=valid_schedule(day)
                except EvidenceError:
                    self.verified_clock()
                    self._miss(day,minute,'DST_INCOMPLETE_CYCLE');continue
                if available<self.activation_at:
                    self.verified_clock()
                    self._miss(day,minute,'NOT_ACTIVE_AT_ANCHOR');continue
                if self.clock.now_ms()>min(available+120000,s['close']-1):
                    self.verified_clock()
                self.capture(day,minute,s)
            try:
                s=valid_schedule(day)
            except EvidenceError:
                continue
            if now>=s['end']+2000 and 'OUTCOME:'+day.isoformat() not in self.store.by_id:
                if any(r['record_type']=='PREDICTION' and r['data']['cycle']==day.isoformat() for r in self.store.rows):
                    completed.append((day,s))
        # Bound restart label recovery so it cannot starve today's forecasts.
        for day,s in completed[:3]:self.settle(day,s)
