"""8760-hour synthetic load qualification, never a market/profitability study."""
import argparse,csv,hashlib,json,os,sys,time,tempfile,ctypes
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from ..models import feature_sets,Engine,PROFILES
from ..observations import mtf
from ..market import Receipt,HOUR
from ....detect import detect
from ....evaluate import clean
from . import codec,registry
from .core import Observer

def synthetic(n):
    rng=np.random.default_rng(5353);c=70000*np.exp(np.cumsum(rng.normal(0,.002,n)));o=np.r_[c[0],c[:-1]]
    return np.c_[1794873600000-6000*HOUR+np.arange(n)*HOUR,o,np.maximum(o,c)+25,np.minimum(o,c)-25,c,rng.uniform(1,10,n)]
def receipt(a,now):
    rows=[[int(t),str(o),str(h),str(l),str(c),str(v),int(t+HOUR-1),'100',12,str(v/2),'50','0'] for t,o,h,l,c,v in a]
    return Receipt(json.dumps(rows,separators=(',',':')).encode(),'https://fapi.binance.com/fapi/v1/klines',
                   dict(symbol='BTCUSDT',interval='1h',startTime=int(a[0,0]),endTime=int(a[-1,0]+HOUR-1),limit=len(a)),now-100,now,now)
def funding_receipt(start,end,now):
    return Receipt(b'[]','https://fapi.binance.com/fapi/v1/fundingRate',dict(symbol='BTCUSDT',startTime=start,endTime=end,limit=1000),now-100,now,now)
def rss():
    if os.name=='nt':
        class Counters(ctypes.Structure):
            _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong),('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
        c=Counters();c.cb=ctypes.sizeof(c)
        current=ctypes.windll.kernel32.GetCurrentProcess;current.restype=ctypes.c_void_p
        query=ctypes.windll.psapi.GetProcessMemoryInfo;query.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong];query.restype=ctypes.c_int
        if not query(current(),ctypes.byref(c),c.cb):raise OSError('PROCESS_MEMORY_MEASUREMENT_FAILED')
        return c.PeakWorkingSetSize
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)

def run(out,hours=8760):
    if hours<8760:raise ValueError('MINIMUM_8760_HOURS')
    registry.verify(check_environment=True);out=Path(out);out.mkdir(parents=True,exist_ok=True);a=synthetic(6000+hours);now=int(a[5999,0]+HOUR)
    if rss()<=0:raise OSError('INVALID_RSS_MEASUREMENT')
    started=datetime.now(timezone.utc).isoformat();wall=time.perf_counter();cpu=time.process_time();measurements=[];latencies=[];recoveries=[]
    with tempfile.TemporaryDirectory(prefix='f53load_') as folder:
        root=Path(folder);observer=Observer(root,True,clock=lambda:now)
        observer.bootstrap([receipt(a[j:j+1500],now) for j in range(0,6000,1500)])
        for step,row in enumerate(a[6000:],1):
            now=int(row[0]+HOUR+60000);tick=time.perf_counter();observer.ingest(receipt(np.asarray([row]),now));latencies.append(time.perf_counter()-tick)
            if step%24==0:observer.ingest_funding(funding_receipt(int(a[6000,0]),int(row[0]+HOUR-1),now))
            if step%168==0:observer.checkpoint()
            if step in (hours//4,hours//2,hours):
                observer.checkpoint();before=codec.state_digest(observer.state());count=observer.store.count;observer.close()
                tick=time.perf_counter();observer=Observer(root,True,clock=lambda:now);seconds=time.perf_counter()-tick
                equal=before==codec.state_digest(observer.state())
                if not equal:raise AssertionError('CHECKPOINT_RECOVERY_STATE_DIFFERENCE')
                recoveries.append(dict(hours=step,seconds=seconds,exact_state=True))
                measurements.append(dict(hours=step,wall_seconds=time.perf_counter()-wall,cpu_seconds=time.process_time()-cpu,
                    peak_rss_bytes=rss(),storage_bytes=sum(p.stat().st_size for p in root.rglob('*') if p.is_file()),
                    records=count,recovery_seconds=seconds,unresolved_jobs=len(observer.jobs),cost_attempts=observer.counts['cost_attempts']))
                print(json.dumps(dict(stage=step,measurement=measurements[-1])),flush=True)
        _,actual=observer.inc.tape.views();reference=feature_sets(a);checked=0
        for profile in PROFILES:
            for key,value in reference[profile].items():
                np.testing.assert_array_equal(actual[profile][key],value);checked+=1
        if observer.inc.contexts!=mtf(a):raise AssertionError('MTF_CONTEXT_DIFFERENCE')
        expected={p:clean(Engine(p).warm(a,reference[p])[0]) for p in PROFILES}
        expected22=clean(detect(a,reference['TURN22_FORWARD_V1'])[0])
        if expected22!=expected['TURN22_FORWARD_V1']:raise AssertionError('PR50_22_DIFFERENCE')
        emitted={p:[] for p in PROFILES}
        for record in observer.store.records():
            if record['kind']!='HOUR':continue
            for p,view in record['payload']['profiles'].items():
                for event in view['events']:emitted[p].append({k:v for k,v in event.items() if k not in ('protocol','pre_activation_tokens','primary_token_eligible')})
        for p in PROFILES:
            if emitted[p]!=[e for e in expected[p] if e['i']>=6000]:raise AssertionError('EMITTER_PARITY_DIFFERENCE')
        result=dict(technical_only=True,market_or_profitability_evidence=False,mode='OFFLINE_TEST',prospective_observations=0,
                    registry_hash=registry.EXPECTED,input_sha256=hashlib.sha256(a.tobytes()).hexdigest(),input_rows=len(a),hours=hours,
                    python=sys.version,numpy=np.__version__,started_at_utc=started,wall_seconds=time.perf_counter()-wall,cpu_seconds=time.process_time()-cpu,
                    peak_rss_bytes=rss(),measurements=measurements,recoveries=recoveries,
                    indicator_arrays_exact=checked,MTF_exact=True,TURN22_PR50_exact=True,TURN11_PR52_exact=True,
                    latency_seconds=dict(mean=float(np.mean(latencies)),p95=float(np.quantile(latencies,.95)),maximum=max(latencies)),counts=observer.counts)
        observer.close()
    (out/'load_8760.json').write_text(json.dumps(result,indent=2)+'\n',newline='\n')
    with (out/'load_8760.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=measurements[0]);writer.writeheader();writer.writerows(measurements)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();print(json.dumps(run(a.out)))
