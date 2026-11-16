"""Synthetic technical evidence only; never profitability or forward records."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
try:import numpy as np
except ImportError as error:raise unittest.SkipTest('Research CI installs NumPy') from error
from ..test_forward import bars,receipt,funding_receipt,ACT,HOUR
from ..models import Engine,feature_sets,PROFILES
from ..observations import mtf
from ..journal import JournalError,digest,canonical
from . import registry,codec,statistics,integrity
from .incremental import Incremental
from .ledger import Ledger
from .core import Observer
import subprocess,sys

class NumericalTests(unittest.TestCase):
    def test_exact_all_fields_both_profiles_and_prefixes(self):
        a=bars(1500);c=Incremental()
        for row in a:c.step(row)
        _,actual=c.tape.views();expected=feature_sets(a)
        for p in PROFILES:
            for k,v in expected[p].items():np.testing.assert_array_equal(actual[p][k],v,strict=True)
        self.assertEqual(c.contexts,mtf(a))
        for p in PROFILES:self.assertEqual(codec.pack(Engine(p))[0],codec.pack(codec.unpack(*codec.pack(Engine(p))))[0])
    def test_checkpoint_array_bits_and_future_prefix(self):
        a=bars(1100);c=Incremental()
        for row in a[:1000]:c.step(row)
        before=codec.state_digest(c);restored=codec.unpack(*codec.pack(c));self.assertEqual(before,codec.state_digest(restored))
        for row in a[1000:]:c.step(row);restored.step(row)
        self.assertEqual(codec.state_digest(c),codec.state_digest(restored))
        _,f=c.tape.views();prefix=feature_sets(a[:1000])
        for p in PROFILES:
            for k in prefix[p]:np.testing.assert_array_equal(f[p][k][:1000],prefix[p][k])
    def test_unsafe_codec_types_rejected(self):
        with self.assertRaises(ValueError):codec.pack(object())
        with self.assertRaises(ValueError):codec.pack(np.array([object()],object))

class PolicyTests(unittest.TestCase):
    def test_old_window_and_new_pending_window(self):
        from ..protocol import config,verify,EXPECTED
        self.assertEqual(verify(),EXPECTED);self.assertEqual(EXPECTED,'6619b8ad176737de7b75c8d297ae7ab14b771879b8ad969161ba6b155ad325b9')
        self.assertEqual(config()['cohort']['planned_22_window'][0],'2026-11-17T00:00:00Z')
        self.assertIsNone(registry.policy()['cohort_start'])
    def test_sealed_future_cohort_cannot_shift(self):
        c=registry.cohort(ACT,ACT-1,'REVIEW','a'*40,'writer');self.assertEqual(registry.validate_cohort(c),c)
        changed=dict(c,start_ms=ACT+HOUR)
        with self.assertRaises(ValueError):registry.validate_cohort(changed)
        with self.assertRaises(ValueError):registry.cohort(ACT,ACT+1,'REVIEW','a'*40,'writer')
    def test_close_based_coverage_no_hidden_open_offset(self):
        c=registry.cohort(ACT,ACT-HOUR,'REVIEW','a'*40,'w')
        self.assertTrue(registry.eligible(ACT,ACT+60000,ACT-HOUR,c,mode='FORWARD_SHADOW'))
        self.assertFalse(registry.eligible(ACT,ACT+300001,ACT-HOUR,c,mode='FORWARD_SHADOW'))
        self.assertFalse(registry.eligible(ACT,ACT+1,ACT-HOUR,c,pre_tokens=True,mode='FORWARD_SHADOW'))
        self.assertFalse(registry.eligible(ACT,ACT+1,ACT-HOUR,c))
    def test_real_activation_not_granted_by_technical_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):Observer(tmp,True,'FORWARD_SHADOW',registry.cohort(ACT,ACT-HOUR,'R','a'*40,'w'))
            root=Path(tmp)/'disabled';o=Observer(root);self.assertFalse(root.exists());self.assertEqual(o.ingest(None),'DISABLED')
    def test_local_export_cannot_impersonate_external_ack(self):
        c=registry.cohort(ACT,ACT-HOUR,'R','a'*40,'w')
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(registry,'qualified_environment',return_value=True):
                with self.assertRaisesRegex(ValueError,'LOCAL_EXPORT'):
                    Observer(tmp,True,'FORWARD_SHADOW',c,anchor=dict(anchor_status='EXPORT_ONLY',cohort_hash=c['cohort_hash']),volume_proof={'verified_real_volume':True})
    def test_forward_rejects_non_pinned_environment(self):
        with patch.object(registry,'qualified_environment',return_value=False):
            with self.assertRaisesRegex(ValueError,'PINNED_NUMERICAL'):registry.verify(check_environment=True)
    def test_expired_external_ack_rejected_before_storage(self):
        c=registry.cohort(ACT,ACT-HOUR,'R','a'*40,'w')
        anchor=dict(anchor_status='INDEPENDENT_STORE_ACK',external_store_id='FIXTURE',cohort_hash=c['cohort_hash'],acknowledged_at_ms=ACT-25*HOUR)
        with tempfile.TemporaryDirectory() as tmp,patch.object(registry,'qualified_environment',return_value=True):
            with self.assertRaisesRegex(ValueError,'EXTERNAL_ANCHOR_EXPIRED'):
                Observer(Path(tmp)/'unused',True,'FORWARD_SHADOW',c,clock=lambda:ACT,anchor=anchor,volume_proof={'verified_real_volume':True})
            self.assertFalse((Path(tmp)/'unused').exists())

class DurableTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_partial_uncommitted_blob_quarantined_auditably(self):
        l=Ledger(self.root/'data','r','w');raw=b'complete';sha=hashlib.sha256(raw).hexdigest();(l.blobs/sha).write_bytes(b'comp')
        self.assertEqual(l.put(raw,1),sha);self.assertEqual(l.read_blob(sha),raw)
        self.assertEqual(list(l.records())[0]['kind'],'UNCOMMITTED_BLOB_QUARANTINED');self.assertEqual(len(list(l.quarantine.iterdir())),1);l.close()
    def test_referenced_corrupt_blob_never_repaired(self):
        l=Ledger(self.root/'data','r','w');sha=l.put(b'public',1);l.append('REF','one',{},1,[sha]);l.close()
        path=self.root/'data/blobs'/sha;path.write_bytes(b'bad')
        with self.assertRaises(JournalError):Ledger(self.root/'data','r','w')
        self.assertEqual(path.read_bytes(),b'bad')
    def test_truncation_tamper_tail_loss_and_independent_restore(self):
        l=Ledger(self.root/'data','r','w');sha=l.put(b'public',1);l.append('REF','one',{},1,[sha]);l.append('REF','two',{},2,[sha])
        anchor=integrity.backup(l,self.root/'outside',3);raw=(self.root/'outside'/anchor['snapshot_name']).read_bytes();path=l.path;l.close()
        original=path.read_bytes();path.write_bytes(original[:-1])
        with self.assertRaises(JournalError):Ledger(self.root/'data','r','w')
        self.assertEqual(path.read_bytes(),original[:-1]);integrity.restore(raw,anchor,self.root/'restored')
        restored=Ledger(self.root/'restored','r','w');self.assertTrue(restored.verify_anchor(anchor));restored.close()
        path.write_bytes(original.splitlines()[0]+b'\n');l=Ledger(self.root/'data','r','w')
        with self.assertRaises(JournalError):l.verify_anchor(anchor)
        l.close()
        with self.assertRaises(JournalError):integrity.verify_archive(raw[:-1],anchor)
    def test_second_writer_and_wrong_identity(self):
        l=Ledger(self.root/'data','r','authorized');l.append('A','a',{},1)
        with self.assertRaises((OSError,JournalError)):Ledger(self.root/'data','r','authorized')
        l.close()
        with self.assertRaises(JournalError):Ledger(self.root/'data','r','intruder')
    def test_fsync_failure_requires_reopen(self):
        l=Ledger(self.root/'data','r','w')
        with patch('os.fsync',side_effect=OSError('synthetic')):
            with self.assertRaises(JournalError):l.append('A','a',{},1)
        with self.assertRaises(JournalError):l.append('B','b',{},2)
        l.close();l=Ledger(self.root/'data','r','w');self.assertEqual(l.count,1);l.close()
    def test_uncommitted_part_is_quarantined_not_deleted(self):
        l=Ledger(self.root/'data','r','w');name='a'*64+'.part.fixture';(l.blobs/name).write_bytes(b'partial')
        l.quarantine_uncommitted_temps(1);self.assertEqual((l.quarantine/name).read_bytes(),b'partial')
        self.assertEqual(list(l.records())[-1]['kind'],'UNCOMMITTED_TEMP_QUARANTINED');l.close()
    def test_two_separate_processes_on_local_filesystem(self):
        from .volume_probe import probe
        report=probe(self.root/'probe','LOCAL_TEMP_TEST_ONLY')
        self.assertTrue(report['second_process_excluded']);self.assertTrue(report['acquired_after_release']);self.assertFalse(report['verified_real_volume'])

class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.a=bars(6100);cls.seed=[receipt(cls.a[j:j+1500],ACT) for j in range(0,6000,1500)]
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.now=ACT;self.o=Observer(self.root/'s',True,clock=lambda:self.now);self.o.bootstrap(self.seed)
    def tearDown(self):self.o.close();self.tmp.cleanup()
    def feed(self,start,end):
        self.now=int(self.a[end-1,0]+HOUR+60000);return self.o.ingest(receipt(self.a[start:end],self.now))
    def test_checkpoint_and_full_replay_equivalent(self):
        self.feed(6000,6008);self.o.checkpoint();self.feed(6008,6011);before=codec.state_digest(self.o.state());self.o.close()
        self.o=Observer(self.root/'s',True,clock=lambda:self.now);self.assertEqual(codec.state_digest(self.o.state()),before)
    def test_funding_terminal_not_indefinitely_recalculated(self):
        self.feed(6000,6100);self.assertGreater(self.o.counts['unknown'],0)
        self.assertLessEqual(len(self.o.jobs),3*75);self.assertLessEqual(self.o.counts['cost_attempts'],self.o.counts['price'])
        self.assertFalse(any(r['kind']=='COSTED_OUTCOME' for r in self.o.store.records()))
    def test_candle_revision_original_and_reviewed_child(self):
        self.feed(6000,6001);raw=json.loads(receipt(self.a[6000:6001],self.now).body);raw[0][4]=str(float(raw[0][4])+.1)
        self.assertEqual(self.o.ingest(receipt(self.a[6000:6001],self.now,raw=raw)),'QUARANTINED')
        record=list(self.o.store.records())[-1];self.assertEqual(record['kind'],'CANDLE_REVISION');self.assertTrue(record['payload']['differences'])
        child=self.o.child(self.root/'child','INDEPENDENT_REVIEW')
        self.assertEqual(child.counts['hours'],0);self.assertEqual(child.cohort,self.o.cohort);self.assertNotEqual(child.session,self.o.session)
        self.assertEqual(list(child.store.records())[0]['payload']['parent']['tip'],self.o.store.tip);child.close()
    def test_missing_funding_mark_completion_not_false_revision(self):
        self.feed(6000,6010);self.now=ACT+12*HOUR
        rows=[dict(symbol='BTCUSDT',fundingTime=ACT+2*HOUR,fundingRate='.001')]
        self.o.ingest_funding(funding_receipt(ACT,ACT+10*HOUR,rows,self.now));before=self.o.counts['net']
        affected=[r for r in self.o.store.records() if r['kind']=='COSTED_OUTCOME' and r['payload']['entry_reference']<=ACT+2*HOUR<=r['payload']['endpoint_reference']]
        self.assertEqual(affected,[])
        rows[0]['markPrice']='70000';self.o.ingest_funding(funding_receipt(ACT,ACT+10*HOUR,rows,self.now))
        self.assertGreater(self.o.counts['net'],before);self.assertNotEqual(self.o.status,'QUARANTINED')
        rows[0]['fundingRate']='.002';self.assertEqual(self.o.ingest_funding(funding_receipt(ACT,ACT+10*HOUR,rows,self.now)),'QUARANTINED')
        last=list(self.o.store.records())[-1];self.assertEqual(last['payload']['differences'][0]['field'],'rate');self.assertIn('original_receipt',last['payload'])
    def test_full_replay_without_checkpoint(self):
        self.feed(6000,6008);before=codec.state_digest(self.o.state());self.o.close()
        self.o=Observer(self.root/'s',True,clock=lambda:self.now);self.assertEqual(codec.state_digest(self.o.state()),before)
    def test_regular_rate_type_preserves_original_bytes(self):
        rows=[dict(symbol='BTCUSDT',fundingTime=ACT,fundingRate='.001',rateType='Regular',markPrice='70000')]
        self.now=ACT+HOUR;r=funding_receipt(ACT,ACT,rows,self.now);self.o.ingest_funding(r)
        source=next(r for r in self.o.store.records() if r['kind']=='PUBLIC_SOURCE')
        self.assertIn(b'"rateType"',self.o.store.read_blob(source['payload']['blob']))
    def test_uncommitted_hour_requires_replay(self):
        original=self.o.store.append
        def fail(kind,*a,**kw):
            if kind=='HOUR':raise JournalError('SYNTHETIC_FAILURE')
            return original(kind,*a,**kw)
        with patch.object(self.o.store,'append',side_effect=fail):
            with self.assertRaises(JournalError):self.feed(6000,6001)
        self.assertEqual(self.o.status,'REPLAY_REQUIRED')
        with self.assertRaises(ValueError):self.feed(6000,6001)
    def test_checkpoint_cannot_bypass_original_cohort_identity(self):
        self.feed(6000,6001);self.o.checkpoint();self.o.close()
        changed=registry.cohort(ACT+24*HOUR,ACT,'R','a'*40,'OFFLINE_TEST')
        with self.assertRaisesRegex(JournalError,'COHORT_IDENTITY'):
            Observer(self.root/'s',True,cohort=changed,clock=lambda:self.now)

class StatisticsTests(unittest.TestCase):
    def test_inclusive_event_neighbors_both_sides(self):
        y=np.c_[np.arange(4)*.01,-np.arange(4)*.01];labels=np.zeros((4,6),bool);labels[1,0]=True
        effect,_=statistics.contrasts(y,labels,np.zeros(4,int));self.assertAlmostEqual(effect[0],-.005)
    def test_no_testable_and_holm_family_never_shrinks(self):
        rng=np.random.default_rng(53);n=24*180;y=rng.normal(0,.01,(n,2));events=np.zeros((n,6),bool);events[::200,:]=True
        r=statistics.assess(y,events,np.zeros(n,int),np.arange(n)//24,0,179,16751,coverage=1,all_primary_auditable=True,replicates=80)
        self.assertEqual(len(r['primary']),6);self.assertTrue(all(x['classification']=='NO TESTABLE' and x['holm_adjusted_p']==1 for x in r['primary']))
    def test_joint_bootstrap_deterministic_overlap_and_power(self):
        n=24*160;x=np.sin(np.arange(n)/50)*.02;y=np.c_[x,-x];events=np.zeros((n,6),bool);events[::25,:]=True
        args=(y,events,np.zeros(n,int),np.arange(n)//24,0,159,16751)
        a=statistics.assess(*args,coverage=1,all_primary_auditable=True,replicates=80);b=statistics.assess(*args,coverage=1,all_primary_auditable=True,replicates=80)
        self.assertEqual(a,b);self.assertTrue(all(r['effective_n']<=r['n'] for r in a['primary']))
        self.assertGreater(statistics.required_effective_n(.04),statistics.required_effective_n(.02))
    def test_power_cannot_be_relaxed_and_twelve_months_not_confirmatory(self):
        with self.assertRaises(ValueError):statistics.assess(np.zeros((1,2)),np.zeros((1,6)),[0],[0],0,1,1)
        p=json.loads((registry.ROOT/'power.json').read_text())
        self.assertGreater(p['conditional_required_effective_n'],p['theoretical_annual_event_limit_per_contrast'])
        self.assertFalse(p['confirmatory_power_feasible_in_fixed_12months'])
    def test_offline_hours_never_become_forward_evidence(self):
        from .ledger import Ledger
        with tempfile.TemporaryDirectory() as tmp:
            l=Ledger(tmp,registry.EXPECTED,'w');c=registry.cohort(ACT,ACT-1,'R','a'*40,'w')
            r=statistics.evaluate_ledgers([l],c,c['end_exclusive_ms']+74*HOUR,replicates=10)
            self.assertEqual(r['prospective_samples'],0);self.assertEqual(r['status'],'NO TESTABLE');l.close()
    def test_evaluation_cannot_mix_or_relabel_cohorts(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=registry.cohort(ACT,ACT-1,'R','a'*40,'w');l=Ledger(tmp,registry.EXPECTED,'w')
            l.append('SESSION_START','s',dict(cohort=dict(c,start_ms=ACT+HOUR)),ACT)
            with self.assertRaisesRegex(ValueError,'COHORT_MISMATCH'):statistics.evaluate_ledgers([l],c,ACT+HOUR)
            l.close()

class SourceGuards(unittest.TestCase):
    def test_only_new_v2_files_and_all_old_sources_unchanged(self):
        root=registry.ROOT.parents[7];prefix=registry.ROOT.relative_to(root).as_posix()+'/'
        changes=subprocess.check_output(['git','diff','9f307fd9feda6279253c0a0813d49b47d3f1d9b2','--name-status'],cwd=root,text=True).splitlines()
        for line in changes:
            status,name=line.split('\t',1);self.assertEqual(status,'A');self.assertTrue(name.startswith(prefix))
        self.assertEqual(registry.verify(),registry.EXPECTED)
    def test_no_runtime_dependency_or_network_client(self):
        root=registry.ROOT.parents[7]
        for path in registry.ROOT.glob('*.py'):
            if path.name.startswith('test_') or path.name=='volume_probe.py':continue
            text=path.read_text()
            for token in ('import requests','import socket','import http','guardian_bitunix','trade_guardian','live_auto','os.environ'):
                self.assertNotIn(token,text)
        names=subprocess.check_output(['git','ls-files','--','*.py'],cwd=root,text=True).splitlines()
        for name in names:
            if name.startswith('research/') or Path(name).name.startswith('test_'):continue
            self.assertNotIn('IGOD_H1_FORWARD_AUDIT_V2',(root/name).read_text('utf-8-sig'))

if __name__=='__main__':unittest.main()
