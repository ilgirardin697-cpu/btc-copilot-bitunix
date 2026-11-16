"""Synthetic census/semantic checks; no market return study is run here."""
import copy,json,unittest
from unittest.mock import patch
try:
    import numpy as np
except ImportError as error:
    raise unittest.SkipTest('Research tests require NumPy') from error
from . import protocol
from .journal import canonical,digest,JournalError
from .models import Engine,PROFILES
from .report import summarize
from .observer import Observer
from .test_forward import ACT,HOUR,receipt,features_fixture
from . import test_forward as support
from ... import detect as old
from ...evaluate import clean


def census():
    records=[]
    for i in range(4):
        oid=str(i);event=dict(event_id='event'+oid,episode_anchor_id='anchor',comparison_anchor_id='same-turn',
                            pattern='P1',side=-1,strata=['ALL','Q75'])
        profiles={'TURN22_FORWARD_V1':dict(events=[event] if i==1 else [],attempts=[dict(emitted=i==1)],audit=[]),
                  'TURN11_EXPLORATORY_V1':dict(events=[dict(event,event_id='eleven')] if i==1 else [],attempts=[dict(emitted=i==1)],audit=[])}
        obs=dict(observation_id=oid,available_at_ms=ACT+i*HOUR,recorded_at_ms=ACT+i*HOUR+1000,
                 open_time=ACT+(i-1)*HOUR,capture_delay_ms=1000,regime_4h=-1,volatility_tercile=1,
                 on_time=True,forward_eligible=True,mode='FORWARD_SHADOW',collection_class='ON_TIME',
                 profiles=profiles,comparative=dict(events=[dict(fact_id='fact'+oid,kind='AO_ADX_PAIR',side=-1,n=1)]),
                 duplicate_groups={'same-hour':['event1','eleven']} if i==1 else {})
        records.append(dict(kind='CANDLE',payload=obs,created_at_ms=ACT+i*HOUR+1000))
        for side in (-1,1):
            for h in (4,12,24):
                # Price values here are arbitrary test sentinels, not observations.
                r=dict(observation_id=oid,horizon_h=h,side=side,raw_price_fraction=side*i*.01,net_fraction=side*i*.01-.003)
                records.append(dict(kind='PRICE_OUTCOME',payload=r,created_at_ms=ACT+30*HOUR))
    return records


class CensusTests(unittest.TestCase):
    def test_baseline_keeps_event_hour_and_both_neighbors(self):
        r=summarize(census(),ACT+30*HOUR)
        self.assertEqual(r['forward_eligible'],4)
        for c in r['comparisons']:
            if c['metric']=='PRICE':
                self.assertEqual(c['inclusive_baseline_unique_hours'],4)
                self.assertEqual(c['unique_event_hours'],1)
                self.assertAlmostEqual(c['excess_mean'],.005)
    def test_deduplicates_claims_across_protocols_not_same_thing_as_two_events(self):
        r=summarize(census());self.assertEqual(r['unique_observations'],4)
        self.assertEqual(r['duplicate_claims_not_extra_samples'],1)
        self.assertEqual(r['unique_episode_anchors'],1);self.assertEqual(r['episodes_with_multiple_claims'],1)
        self.assertEqual(len(r['model_detection_comparisons']['same-turn']),2)
    def test_same_side_returns_and_all_three_horizons(self):
        r=summarize(census())
        self.assertEqual({c['side'] for c in r['comparisons']},{-1})
        self.assertEqual({c['horizon'] for c in r['comparisons']},{4,12,24})
        self.assertEqual({c['hypothetical_return_side'] for c in r['comparative_comparisons']},{1,-1})
    def test_late_and_offline_rows_never_promoted(self):
        rows=census()
        for r in rows:
            if r['kind']=='CANDLE':r['payload'].update(forward_eligible=False,mode='OFFLINE_TEST')
        r=summarize(rows,ACT+30*HOUR);self.assertEqual(r['forward_eligible'],0)
        self.assertEqual(r['comparisons'],[]);self.assertEqual(r['offline_test_rows'],4)
        self.assertEqual(r['on_time_forward_coverage'],0)
    def test_missing_hours_explicit_dates_not_shifted_by_activation(self):
        r=summarize(census(),ACT+30*HOUR)
        self.assertEqual(r['expected_cohort_hours'],31)
        self.assertEqual(r['missing_or_not_forward_hours'],27)
        self.assertFalse(r['validated']);self.assertFalse(r['collector_or_scheduler_included'])
    def test_failed_candidates_and_missing_net_visible(self):
        r=summarize(census())
        self.assertEqual(r['candidate_attempts'],8);self.assertEqual(r['failed_candidate_attempts'],6)
        self.assertTrue(all(c['matured']==0 and c['missing_or_pending']==1 for c in r['comparisons'] if c['metric']=='COSTED'))
    def test_no_new_inference_or_sigma_claim(self):
        c=protocol.config();self.assertEqual(c['cohort']['statistical_constants']['mde_net_fraction'],.001)
        self.assertIn('not a calibrated power guarantee',c['cohort']['sample_target'])
        self.assertFalse(c['cohort']['capture_running']);self.assertIsNone(c['cohort']['activation'])


class TemporalTests(unittest.TestCase):
    def test_cooldown_full25_hours_both_profiles(self):
        for p in PROFILES:
            a,f,i=features_fixture();a=np.tile(a,(3,1));a[:,0]=a[0,0]+np.arange(len(a))*HOUR
            f={k:np.tile(v,3) for k,v in f.items()}
            # Duplicate the exact turn at +20h: consumes it but must not emit.
            for k in ('ao','adx','minnows'):f[k][26:31]=f[k][6:11]
            e,audit=Engine(p).warm(a,f)
            events=[x for x in e if x['pattern']==old.PATTERNS[0] and x['side']==1]
            for x,y in zip(events,events[1:]):self.assertGreaterEqual(y['i']-x['i'],25)
            self.assertTrue(any(x['status']=='COOLDOWN' for x in audit))
    def test_no_resurrection_after_pending_expiry(self):
        for p in PROFILES:
            a,f,i=features_fixture();f['minnows']=np.arange(len(a),dtype=float)
            f['ao']*=100;f['ao'][i+1:]=f['ao'][i]+np.arange(1,len(a)-i)*2
            f['adx'][i+1:]=f['adx'][i]-np.arange(1,len(a)-i)*.5
            events,audit=Engine(p).warm(a,f)
            self.assertFalse(any(e['pattern']==old.PATTERNS[0] and e['side']==1 for e in events))
            self.assertTrue(any(x['status']=='EXPIRED' for x in audit))
    def test_sidecar_facts_are_prefix_invariant(self):
        from .observations import Facts
        a,f,i=features_fixture();x=Facts();left=[]
        for j in range(20):left.append(x.step(j,a[:20],{k:v[:20] for k,v in f.items()},False))
        y=Facts();right=[y.step(j,a,f,False) for j in range(len(a))]
        self.assertEqual(clean(left),clean(right[:20]))


# Subclass imports would repeat all base tests during discovery; bind only helpers.
class ReplayTests(unittest.TestCase):
    setUpClass=classmethod(support.ObserverTests.setUpClass.__func__)
    setUp=support.ObserverTests.setUp
    tearDown=support.ObserverTests.tearDown
    start=support.ObserverTests.start
    feed=support.ObserverTests.feed
    def test_semantic_replay_rejects_edited_indicator_even_rehashed_chain(self):
        o=self.start();self.feed(6000);rows=copy.deepcopy(o.store.records);path=o.store.path;o.close()
        rows[-1]['payload']['values']['AO']=123456
        previous='0'*64
        for r in rows:
            r.pop('record_hash',None);r['prev_hash']=previous;r['record_hash']=digest(r);previous=r['record_hash']
        raw=b''.join(canonical(r)+b'\n' for r in rows);path.write_bytes(raw)
        with self.assertRaisesRegex(JournalError,'SEMANTIC_REPLAY'):Observer(self.root,True,clock=lambda:self.now)
        self.assertEqual(path.read_bytes(),raw)
    def test_writes_interrupted_after_candle_recovered_no_duplicate_outcome(self):
        o=self.start()
        for j in range(6000,6005):self.feed(j)
        original=o.store.append
        def interrupt(kind,*args,**kw):
            if kind=='PRICE_OUTCOME':raise OSError('synthetic interruption before outcome write')
            return original(kind,*args,**kw)
        with patch.object(o.store,'append',side_effect=interrupt):
            with self.assertRaises(OSError):self.feed(6005)
        o.close();self.o=Observer(self.root,True,clock=lambda:self.now);self.o.mature()
        self.assertEqual(sum(r['kind']=='PRICE_OUTCOME' for r in self.o.store.records),2)
        n=len(self.o.store.records);self.o.mature();self.assertEqual(len(self.o.store.records),n)
    def test_source_raw_tamper_prevents_replay_not_repaired(self):
        o=self.start();ref=o.start_record['seed'][0]['blob'];path=o.store.blobs/(ref+'.json');o.close()
        path.write_bytes(b'[]')
        with self.assertRaisesRegex(JournalError,'PUBLIC_BLOB_TAMPERED'):Observer(self.root,True,clock=lambda:self.now)
        self.assertEqual(path.read_bytes(),b'[]')


if __name__=='__main__':unittest.main()
