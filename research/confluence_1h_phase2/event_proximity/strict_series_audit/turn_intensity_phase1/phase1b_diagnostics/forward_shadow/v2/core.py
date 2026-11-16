"""Receipt-driven isolated V2 observer. Disabled default, no transport or service."""
import hashlib,json,heapq,time,copy,sys
import numpy as np
from ..models import Engine,PROFILES
from ..observations import Facts
from ..market import klines,decode,candle_key,HOUR
from .market import funding
from ..journal import canonical,digest,JournalError
from ....evaluate import clean
from ....outcomes import outcome
from .incremental import Incremental
from .ledger import Ledger
from . import registry,codec


class Observer:
    def __init__(self,root,enabled=False,mode='OFFLINE_TEST',cohort=None,clock=None,anchor=None,volume_proof=None):
        self.enabled=enabled;self.mode=mode;self.clock=clock or (lambda:int(time.time()*1000));self.store=None;self.status='DISABLED';self.cohort=cohort
        if not enabled:return
        self.registry=registry.verify(check_environment=mode=='FORWARD_SHADOW')
        if mode not in ('OFFLINE_TEST','FORWARD_SHADOW'):raise ValueError('INVALID_MODE')
        if mode=='FORWARD_SHADOW':
            registry.validate_cohort(cohort)
            if not anchor or not volume_proof or volume_proof.get('verified_real_volume') is not True:raise ValueError('REAL_VOLUME_AND_EXTERNAL_INTEGRITY_REVIEW_REQUIRED')
            if anchor.get('anchor_status')!='INDEPENDENT_STORE_ACK' or not anchor.get('external_store_id'):
                raise ValueError('LOCAL_EXPORT_IS_NOT_AN_EXTERNAL_ACK')
            ack=anchor.get('acknowledged_at_ms')
            if type(ack) is not int or not 0<=self.now()-ack<=24*HOUR:raise ValueError('EXTERNAL_ANCHOR_EXPIRED_OR_FUTURE')
            if anchor.get('cohort_hash')!=cohort['cohort_hash']:raise ValueError('EXTERNAL_COHORT_SEAL_REQUIRED')
        self.trusted_anchor=anchor;self.writer=cohort['writer_id'] if cohort else 'OFFLINE_TEST'
        self.store=Ledger(root,self.registry,self.writer);self._empty()
        try:
            if anchor and (self.store.count or anchor['count']==0):self.store.verify_anchor(anchor)
            self._restore(anchor)
            self.store.quarantine_uncommitted_temps(self.now())
        except Exception:self.store.close();raise
    def _empty(self):
        self.inc=Incremental();self.engines={p:Engine(p) for p in PROFILES};self.facts=Facts();self.activation=None;self.session=None
        self.vintages={};self.sources={};self.source_refs={};self.funding_rows={};self.funding_vintages={};self.coverage=[];self.generation=0;self.jobs={};self.price_due=[]
        self.net_wait={};self.deadlines=[];self.corrections={};self.status='PREPARED';self.counts=dict(hours=0,events=0,price=0,net=0,unknown=0,cost_attempts=0)
    def now(self):return int(self.clock())
    def _integrity_ready(self):
        if self.mode!='FORWARD_SHADOW':return True
        ack=self.trusted_anchor['acknowledged_at_ms']
        if not 0<=self.now()-ack<=24*HOUR:
            self.status='INTEGRITY_ANCHOR_STALE';raise ValueError('EXTERNAL_ANCHOR_REFRESH_REQUIRED')
        if self.status=='INTEGRITY_ANCHOR_STALE':self.status='HEALTHY'
        return True
    def accept_anchor(self,anchor):
        if not self.enabled:return 'DISABLED'
        if (anchor.get('anchor_status')!='INDEPENDENT_STORE_ACK' or not anchor.get('external_store_id') or
            type(anchor.get('acknowledged_at_ms')) is not int or not 0<=self.now()-anchor['acknowledged_at_ms']<=24*HOUR or
            anchor.get('cohort_hash')!=(self.cohort['cohort_hash'] if self.cohort else None)):
            raise ValueError('INDEPENDENT_CURRENT_COHORT_ACK_REQUIRED')
        if self.trusted_anchor and anchor['count']<self.trusted_anchor['count']:raise ValueError('ANCHOR_ROLLBACK_REJECTED')
        self.store.verify_anchor(anchor)
        self.store.append('EXTERNAL_ANCHOR_ACK','ACK:'+anchor['tip'],anchor,self.now())
        self.trusted_anchor=anchor;self._integrity_ready();return self.status
    def state(self):
        names=('inc','engines','facts','activation','session','vintages','source_refs','funding_rows','funding_vintages','coverage','generation','jobs','price_due','net_wait','deadlines','corrections','status','counts')
        return {k:getattr(self,k) for k in names}
    def bootstrap(self,receipts,parent=None):
        if not self.enabled:return 'DISABLED'
        if self.activation is not None:raise ValueError('ALREADY_STARTED')
        if self.mode=='FORWARD_SHADOW' and self.trusted_anchor['count'] and (not parent or parent['tip']!=self.trusted_anchor['tip']):raise ValueError('CHILD_PARENT_PROOF_REQUIRED')
        chunks=[];refs=[]
        for receipt in receipts:
            if receipt.received_at_ms>self.now():raise ValueError('FUTURE_RECEIPT')
            chunks.append(klines(receipt));sha=self.store.put(receipt.body,self.now());refs.append(dict(blob=sha,metadata=receipt.metadata()))
        a=np.concatenate(chunks) if chunks else np.empty((0,6))
        if len(a)<6000 or not (np.diff(a[:,0])==HOUR).all() or a[-1,0]+HOUR>self.now():raise ValueError('INVALID_TECHNICAL_WARMUP')
        p=dict(mode=self.mode,activation=self.now(),cohort=self.cohort,parent=parent,seed=refs,seed_rows=len(a),historical_events_imported=0,
               numerical_environment=dict(python='.'.join(map(str,sys.version_info[:3])),numpy=np.__version__,qualified=registry.qualified_environment()),authority='NONE')
        p['session_id']=digest(p);self.store.append('SESSION_START','START',p,self.now(),[r['blob'] for r in refs]);self._initialize(p);return self.status
    def _initialize(self,p):
        if p['mode']!=self.mode or p['cohort']!=self.cohort or p['historical_events_imported']!=0:raise JournalError('SESSION_IDENTITY_CHANGED')
        original=dict(p);sid=original.pop('session_id')
        if digest(original)!=sid:raise JournalError('SESSION_SEAL_CHANGED')
        from ..observer import receipt_from
        self.activation=p['activation'];self.session=p['session_id']
        for ref in p['seed']:
            raw=self.store.read_blob(ref['blob']);r=receipt_from(ref['metadata'],raw)
            if r.received_at_ms>self.activation:raise JournalError('WARMUP_AFTER_ACTIVATION')
            rows=klines(r);original=decode(raw)
            for j,row in enumerate(rows):
                a,f=self.inc.step(row);i=len(a)-1
                for key,e in self.engines.items():e.step(i,a,f[key])
                self.facts.step(i,a,f['TURN22_FORWARD_V1'],False)
                self.vintages[int(row[0])]=dict(key=candle_key(original[j]),blob=ref['blob'],row=j)
        if self.inc.tape.n!=p['seed_rows'] or self.inc.tape.n<6000:raise JournalError('WARMUP_ROWS_CHANGED')
        self.status='HEALTHY_UNANCHORED' if self.mode=='OFFLINE_TEST' else 'HEALTHY'
    def _source(self,r,kind):
        if r.received_at_ms>self.now():raise ValueError('FUTURE_RECEIPT')
        rows=klines(r) if kind=='KLINES' else funding(r);sha=self.store.put(r.body,self.now());meta=json.loads(canonical(r.metadata()))
        key=digest(meta);self.store.append('PUBLIC_SOURCE','SOURCE:'+key,dict(kind=kind,metadata=meta,blob=sha),self.now(),[sha])
        self.sources[key]=(r,rows,sha);self.source_refs[key]=dict(metadata=meta,blob=sha);return key,rows,sha
    def _step(self,row,receipt,now):
        a,sets=self.inc.step(row);i=len(a)-1;profiles={};cutoff=max(self.activation,self.cohort['start_ms'] if self.cohort else self.activation)
        for p,e in self.engines.items():
            events,audit,attempts=e.step(i,a,sets[p]);enriched=[]
            for event in events:
                token_indices=list(event['tokens'].values())+[event['tokens']['ao']-e.n]
                prior=any(a[j,0]+HOUR<cutoff for j in token_indices)
                enriched.append(dict(clean(event),protocol=p,pre_activation_tokens=prior,primary_token_eligible=not prior))
            profiles[p]=dict(events=enriched,audit=audit,attempts=attempts)
        f=sets['TURN22_FORWARD_V1'];extra=self.facts.step(i,a,f,False);extra['mtf']=self.inc.contexts
        close=int(row[0]+HOUR);rank=f['vol_rank'][i]
        p=dict(index=i,open_ms=int(row[0]),close_ms=close,recorded_ms=now,received_ms=receipt.received_at_ms,
               eligible=registry.eligible(close,now,self.activation,self.cohort,mode=self.mode) if self.cohort else False,
               mode=self.mode,regime=clean(f['regime4h'][i]),volatility=int(min(2,int(rank*3))) if np.isfinite(rank) else None,
               values={k:clean(f[k][i]) for k in ('adx','plus_di','minus_di','ao','ao_slope','minnows','pece_slope','kon_signal','bbwp','bbwp_slope','atr')},
               profiles=profiles,comparative=clean(extra),snapshot_kind='OBSERVATION_NOT_A_TRADE')
        return clean(p)
    def ingest(self,r):
        if not self.enabled:return 'DISABLED'
        if self.activation is None or self.status in ('QUARANTINED','REPLAY_REQUIRED'):raise ValueError('SESSION_NOT_WRITABLE')
        self._integrity_ready()
        source,rows,blob=self._source(r,'KLINES');original=decode(r.body)
        for j,row in enumerate(rows):
            t=int(row[0]);key=candle_key(original[j]);old=self.vintages.get(t)
            if old:
                if old['key']!=key:
                    first=decode(self.store.read_blob(old['blob']))[old['row']]
                    differences=[dict(column=k,original=first[k],correction=original[j][k]) for k in range(12) if str(first[k])!=str(original[j][k])]
                    self.store.append('CANDLE_REVISION','REV:'+str(t)+':'+key,dict(open_ms=t,original=old,correction=dict(blob=blob,row=j,key=key),differences=differences,
                                      correction_received_ms=r.received_at_ms,dispute_from_close_ms=t+HOUR),self.now(),[old['blob'],blob])
                    self.corrections[t]=dict(blob=blob,row=j,key=key);self.status='QUARANTINED';return self.status
                continue
            expected=int(self.inc.tape.rows[self.inc.tape.n-1,0]+HOUR)
            if t!=expected:
                self.store.append('DATA_GAP','GAP:'+str(expected)+':'+str(t),dict(expected=expected,received=t),self.now());return 'MISSING_HOUR'
            try:
                p=self._step(row,r,self.now());stamp=self.now();p['recorded_ms']=stamp
                p['eligible']=registry.eligible(p['close_ms'],stamp,self.activation,self.cohort,mode=self.mode) if self.cohort else False
                p.update(source=source,blob=blob,row=j,raw_key=key)
                self.store.append('HOUR','HOUR:'+str(t),p,stamp,[blob])
            except Exception:self.status='REPLAY_REQUIRED';raise
            self.vintages[t]=dict(key=key,blob=blob,row=j);self._accept(p);self._mature()
        return self.status
    def _accept(self,p):
        self.counts['hours']+=1;self.counts['events']+=sum(len(x['events']) for x in p['profiles'].values())
        i=p['index']
        for h in (4,12,24):
            key=f'{p["open_ms"]}:H{h}';self.jobs[key]=dict(index=i,h=h,obs_open=p['open_ms'],atr=p['values']['atr'],eligible=p['eligible'])
            heapq.heappush(self.price_due,(i+1+h,key))
    def _covered(self,start,end):
        cur=start
        for lo,hi in sorted(self.coverage):
            if lo<=cur<=hi+1:cur=max(cur,hi+1)
            if cur>end:return True
        return False
    def _outcome(self,key,costed):
        job=self.jobs[key];a,_=self.inc.tape.views();i=job['index'];j=i+1+job['h'];entry=int(a[i+1,0]);end=int(a[j,0]);data_available=end+HOUR
        rows=[r for t,r in self.funding_rows.items() if entry<=t<=end]
        if costed and (not self._covered(entry,end) or any(r['mark'] is None for r in rows)):return None
        fund=np.asarray([[r['time'],r['rate'],r['mark'],0,r['mark'],r['mark']] for r in sorted(rows,key=lambda r:r['time'])],float).reshape((-1,6)) if costed else np.empty((0,6))
        sides={}
        for side in (1,-1):
            raw=side*(a[j,1]-a[i+1,1])/a[i+1,1]
            result=outcome(a,fund,i,side,job['atr'],job['h']) if costed else None
            sides[str(side)]=dict(price_fraction=float(raw),net_fraction=result['net_fraction'] if result else None,
                                  net_atr=result['net_atr'] if result else None,exact_net=result['exact_net_fraction'] if result else None,
                                  optimistic_net=result['optimistic_fraction'] if result else None)
        return clean(dict(open_ms=job['obs_open'],hours=job['h'],entry_reference=entry,endpoint_reference=end,available_at=data_available,
                          hypothetical_not_fill=True,sides=sides,funding_status='COVERED_WITH_BOUNDARY_BOUNDS' if costed else 'PENDING_NOT_ZERO'))
    def _mature(self):
        i=self.inc.tape.n-1
        while self.price_due and self.price_due[0][0]<=i:
            _,key=self.price_due[0];p=self._outcome(key,False)
            self.store.append('PRICE_OUTCOME','PRICE:'+key,p,self.now());heapq.heappop(self.price_due);self.counts['price']+=1
            deadline=p['available_at']+48*HOUR;self.net_wait[key]=dict(deadline=deadline,last_generation=-1);heapq.heappush(self.deadlines,(deadline,key))
        for key,w in list(self.net_wait.items()):
            if w['last_generation']==self.generation:continue
            self.counts['cost_attempts']+=1;p=self._outcome(key,True)
            if p is not None:
                self.store.append('COSTED_OUTCOME','NET:'+key,p,self.now());self.counts['net']+=1;self.net_wait.pop(key);self.jobs.pop(key)
            else:w['last_generation']=self.generation
        while self.deadlines and self.deadlines[0][0]<=self.now():
            _,key=self.deadlines[0]
            if key in self.net_wait:
                self.store.append('FUNDING_UNAVAILABLE','UNKNOWN:'+key,dict(open_ms=self.jobs[key]['obs_open'],hours=self.jobs[key]['h'],deadline=self.net_wait[key]['deadline'],terminal=True),self.now())
                self.net_wait.pop(key);self.jobs.pop(key);self.counts['unknown']+=1
            heapq.heappop(self.deadlines)
    def ingest_funding(self,r):
        if not self.enabled:return 'DISABLED'
        if self.activation is None or self.status in ('QUARANTINED','REPLAY_REQUIRED'):raise ValueError('SESSION_NOT_WRITABLE')
        self._integrity_ready()
        key,rows,blob=self._source(r,'FUNDING')
        for value in rows:
            old=self.funding_rows.get(value['time'])
            if old and old!=value:
                complete=old['rate']==value['rate'] and old['mark'] is None and value['mark'] is not None
                kind='FUNDING_COMPLETION' if complete else 'FUNDING_REVISION'
                differences=[dict(field=k,original=old[k],correction=value[k]) for k in ('rate','mark') if old[k]!=value[k]]
                self.store.append(kind,kind+':'+key+':'+str(value['time']),dict(original=old,original_receipt=self.funding_vintages[value['time']],
                                  correction=value,differences=differences,source=key,received_ms=r.received_at_ms),self.now(),[blob])
                if not complete:self.status='QUARANTINED';return self.status
            self.funding_rows[value['time']]=value
            self.funding_vintages[value['time']]=dict(source=key,received_ms=r.received_at_ms)
        p=dict(source=key,start=r.query['startTime'],end=r.query['endTime'],rows=rows)
        if self.store.append('FUNDING_COVERAGE','COVERAGE:'+key,p,self.now(),[blob]):
            self.coverage.append((p['start'],p['end']));self.generation+=1;self._mature()
        return self.status
    def checkpoint(self):
        if not self.enabled:return None
        meta,arrays=codec.pack(self.state());m=self.store.put(meta,self.now());a=self.store.put(arrays,self.now())
        p=dict(meta=m,arrays=a,state_hash=digest(dict(meta=m,arrays=a)),prefix_count=self.store.count,prefix_tip=self.store.tip,session=self.session)
        self.store.append('CHECKPOINT','CHECKPOINT:'+self.store.tip,p,self.now(),[m,a]);return p
    def _restore(self,anchor):
        checkpoint=None;session_header=None;quarantined=False
        for index,r in enumerate(self.store.records(),1):
            if r['kind']=='SESSION_START':
                if session_header is not None:raise JournalError('MULTIPLE_SESSION_STARTS')
                session_header=r['payload'];p=session_header;original=dict(p);sid=original.pop('session_id')
                if p['mode']!=self.mode or p['cohort']!=self.cohort or p['activation']!=r['created_at_ms'] or digest(original)!=sid:
                    raise JournalError('SESSION_OR_COHORT_IDENTITY_CHANGED')
            if r['kind'] in ('CANDLE_REVISION','FUNDING_REVISION'):quarantined=True
            if r['kind']=='CHECKPOINT':
                if r['payload']['prefix_count']!=index-1 or r['payload']['prefix_tip']!=r['prev_hash']:raise JournalError('CHECKPOINT_PREFIX_CHANGED')
                checkpoint=(r['record_id'],r['payload'],quarantined)
        start=False if checkpoint else True
        if checkpoint:
            rid,p,prior_quarantine=checkpoint
            if self.mode=='FORWARD_SHADOW' and (not anchor or anchor['count']<=p['prefix_count']):raise JournalError('UNANCHORED_CHECKPOINT')
            state=codec.unpack(self.store.read_blob(p['meta']),self.store.read_blob(p['arrays']))
            if digest(dict(meta=p['meta'],arrays=p['arrays']))!=p['state_hash']:raise JournalError('CHECKPOINT_HASH_INVALID')
            if (session_header is None or set(state)!=set(self.state()) or state['session']!=p['session'] or
                state['session']!=session_header['session_id'] or state['activation']!=session_header['activation'] or
                prior_quarantine and state['status']!='QUARANTINED'):raise JournalError('CHECKPOINT_STATE_SCOPE_INVALID')
            for k,v in state.items():setattr(self,k,v)
        from ..observer import receipt_from
        cursor=iter(self.store.records())
        for r in cursor:
            if not start:
                if r['record_id']==checkpoint[0]:start=True
                continue
            p=r['payload'];kind=r['kind']
            if kind=='SESSION_START':self._initialize(p)
            elif kind=='PUBLIC_SOURCE':
                receipt=receipt_from(p['metadata'],self.store.read_blob(p['blob']));rows=klines(receipt) if p['kind']=='KLINES' else funding(receipt)
                self.sources[r['record_id'][7:]]=(receipt,rows,p['blob']);self.source_refs[r['record_id'][7:]]=dict(metadata=p['metadata'],blob=p['blob'])
            elif kind=='HOUR':
                # Source can predate a checkpoint; self-contained refs remain verifiable.
                raw=self.store.read_blob(p['blob']);row=decode(raw)[p['row']]
                ref=self.source_refs[p['source']];receipt=receipt_from(ref['metadata'],self.store.read_blob(ref['blob']))
                expected=self._step(klines(receipt)[p['row']],receipt,r['created_at_ms']);expected.update(source=p['source'],blob=p['blob'],row=p['row'],raw_key=candle_key(row))
                if expected!=p:raise JournalError('REPLAY_SNAPSHOT_MISMATCH')
                self.vintages[p['open_ms']]=dict(key=p['raw_key'],blob=p['blob'],row=p['row']);self._accept(p);self._replay_mature(cursor,r['created_at_ms'])
            elif kind=='FUNDING_COVERAGE':
                ref=self.source_refs[p['source']];receipt=receipt_from(ref['metadata'],self.store.read_blob(ref['blob']));values=funding(receipt)
                if values!=p['rows']:raise JournalError('FUNDING_SOURCE_CHANGED')
                self.coverage.append((p['start'],p['end']));self.funding_rows.update({v['time']:v for v in values})
                self.funding_vintages.update({v['time']:dict(source=p['source'],received_ms=receipt.received_at_ms) for v in values})
                self.generation+=1;self._replay_mature(cursor,r['created_at_ms'])
            elif kind in ('PRICE_OUTCOME','COSTED_OUTCOME','FUNDING_UNAVAILABLE'):
                key=f'{p["open_ms"]}:H{p["hours"]}'
                if kind=='PRICE_OUTCOME':
                    expected=self._outcome(key,False)
                    if expected!=p or r['created_at_ms']<p['available_at']:raise JournalError('EARLY_OR_CHANGED_OUTCOME')
                    self.price_due=[v for v in self.price_due if v[1]!=key];heapq.heapify(self.price_due)
                    w=dict(deadline=p['available_at']+48*HOUR,last_generation=self.generation);self.net_wait[key]=w;heapq.heappush(self.deadlines,(w['deadline'],key));self.counts['price']+=1
                else:
                    if kind=='COSTED_OUTCOME' and self._outcome(key,True)!=p:raise JournalError('CHANGED_NET_OUTCOME')
                    if kind=='FUNDING_UNAVAILABLE' and r['created_at_ms']<p['deadline']:raise JournalError('EARLY_FUNDING_TIMEOUT')
                    self.net_wait.pop(key,None);self.jobs.pop(key,None);self.counts['net' if kind=='COSTED_OUTCOME' else 'unknown']+=1
            elif kind=='CANDLE_REVISION':self.corrections[p['open_ms']]=p['correction'];self.status='QUARANTINED'
            elif kind=='FUNDING_REVISION':self.status='QUARANTINED'
            elif kind not in ('FUNDING_COMPLETION','DATA_GAP','CHECKPOINT','UNCOMMITTED_BLOB_QUARANTINED','UNCOMMITTED_TEMP_QUARANTINED','EXTERNAL_ANCHOR_ACK'):
                raise JournalError('UNKNOWN_RECORD_TYPE')
    def _replay_mature(self,cursor,stamp):
        class EndOfCommittedPrefix(Exception):pass
        original_append=self.store.append;original_clock=self.clock
        def compare(kind,rid,payload,now,refs=()):
            try:expected=next(cursor)
            except StopIteration:raise EndOfCommittedPrefix
            if (expected['kind'],expected['record_id'],expected['payload'])!=(kind,rid,payload) or expected['created_at_ms']<now:raise JournalError('OUTCOME_REPLAY_DIFFERENCE')
            return True
        self.store.append=compare;self.clock=lambda:stamp
        try:self._mature()
        except EndOfCommittedPrefix:pass  # queues remain pending; never append during replay
        finally:self.store.append=original_append;self.clock=original_clock
    def child(self,destination,approval_ref,anchor=None):
        if self.status!='QUARANTINED' or not approval_ref:raise ValueError('REVIEWED_QUARANTINE_REQUIRED')
        if self.mode=='FORWARD_SHADOW':
            if anchor is None:raise ValueError('EXTERNAL_PARENT_ANCHOR_REQUIRED')
            self.store.verify_anchor(anchor)
            if anchor['count']!=self.store.count:raise ValueError('REVISION_MUST_BE_ANCHORED')
        from ..market import Receipt
        rows=[]
        for t,original in sorted(self.vintages.items()):
            ref=self.corrections.get(t,original);rows.append(decode(self.store.read_blob(ref['blob']))[ref['row']])
        receipts=[];now=self.now()
        for j in range(0,len(rows),1500):
            chunk=rows[j:j+1500];receipts.append(Receipt(canonical(chunk),'https://fapi.binance.com/fapi/v1/klines',
                dict(symbol='BTCUSDT',interval='1h',startTime=chunk[0][0],endTime=chunk[-1][6],limit=len(chunk)),now,now,now))
        child=Observer(destination,True,self.mode,self.cohort,self.clock,anchor=None if self.mode=='OFFLINE_TEST' else anchor,
                       volume_proof=None if self.mode=='OFFLINE_TEST' else {'verified_real_volume':True})
        child.bootstrap(receipts,parent=dict(session=self.session,tip=self.store.tip,count=self.store.count,
                                            review=approval_ref,corrections=clean(self.corrections),cohort_never_reset=True,
                                            cohort_hash=self.cohort['cohort_hash'] if self.cohort else None))
        return child
    def close(self):
        if self.store:self.store.close()
