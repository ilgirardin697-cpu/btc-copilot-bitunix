"""Exact frozen PRICE inference and a predeclared three-bucket price reference."""
import hashlib
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ANCHORS = [0,15,30,45,59]
CLASSES = ['SUPERIOR_FIRST','INFERIOR_FIRST','NEITHER']


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def read_json(name):
    return json.loads((HERE/name).read_text(encoding='utf-8'))


def verify_freeze():
    m=read_json('freeze_manifest.json')
    if hashlib.sha256(canonical(read_json('frozen_PRICE.json'))).hexdigest()!=m['model_sha256']:
        raise ValueError('PRICE_MODEL_CHANGED')
    if hashlib.sha256(canonical(read_json('frozen_PRIOR.json'))).hexdigest()!=m['prior_sha256']:
        raise ValueError('PRIOR_CHANGED')
    if hashlib.sha256((HERE/'protocol.json').read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=m['protocol_sha256']:
        raise ValueError('PROTOCOL_CHANGED')
    return m


def predict(x):
    verify_freeze(); m=read_json('frozen_PRICE.json'); x=np.asarray(x,float)
    if x.shape[-1]!=6 or not np.isfinite(x).all():
        raise ValueError('PRICE_SIX_FINITE_FEATURES_REQUIRED')
    z=np.clip((x-m['mean'])/m['scale'],-8,8)
    z=np.concatenate([np.ones((*x.shape[:-1],1)),z],axis=-1)@np.array(m['weights'])
    e=np.exp(z-z.max(axis=-1,keepdims=True))
    return e/e.sum(axis=-1,keepdims=True)


def fit_structure(x,y):
    """Training ONLY, fixed thirds. Minute weights are fractions of a cycle."""
    prior=np.array(read_json('frozen_PRIOR.json')); x=np.asarray(x); y=np.asarray(y)
    if x.shape[1:]!=(60,6) or len(x)!=len(y):raise ValueError('TRAIN_SHAPE')
    buckets=np.minimum(2,np.searchsorted([1/3,2/3],x[:,:,1],side='right'))
    rows=[]
    for k in range(3):
        mask=buckets==k
        counts=np.array([np.sum(mask*(y[:,None]==c))/60 for c in range(3)])
        p=(counts+20*prior)/(counts.sum()+20)
        rows.append(dict(bucket=k,cycle_equivalent_counts=counts.tolist(),probabilities=p.tolist()))
    return dict(protocol='FIXED_POSITION_THIRDS_TRAIN_ONLY_V1',thresholds=[1/3,2/3],
                smoothing_cycle_equivalents=20,training_cycles=len(y),rows=rows)


def structure_predict(x,model):
    i=np.searchsorted(model['thresholds'],np.asarray(x)[...,1],side='right')
    return np.array([r['probabilities'] for r in model['rows']])[i]


def scores(p,y):
    p=np.asarray(p);y=np.asarray(y)
    onehot=np.eye(3)[y]
    while onehot.ndim<p.ndim:onehot=np.expand_dims(onehot,-2)
    brier=((p-onehot)**2).sum(axis=-1)
    ll=-np.log(np.maximum(np.sum(p*onehot,axis=-1),1e-15))
    return brier,ll


def block_indices(n,replicates=2000):
    rng=np.random.default_rng(20261104)
    starts=rng.integers(0,n,(replicates,(n+6)//7))
    return ((starts[:,:,None]+np.arange(7))%n).reshape(replicates,-1)[:,:n]


def interval(a,confidence=.95):
    a=np.asarray(a,float)
    if not len(a):return None
    means=a[block_indices(len(a))].mean(axis=1);q=(1-confidence)/2
    return np.quantile(means,[q,1-q]).tolist()


def class_calibration(p,y):
    p=np.asarray(p);y=np.asarray(y); pred=p.reshape(-1,3)
    labels=np.repeat(np.eye(3)[y],p.shape[1],axis=0)
    bins=[];ece=[]
    for c in range(3):
        total=0
        for b in range(10):
            m=(pred[:,c]>=b/10)&(pred[:,c]<(b+1)/10 if b<9 else pred[:,c]<=1)
            n=int(m.sum());prob=float(pred[m,c].mean()) if n else None
            rate=float(labels[m,c].mean()) if n else None
            if n:total+=n/len(pred)*abs(prob-rate)
            bins.append(dict(class_name=CLASSES[c],bin=b,rows=n,probability=prob,observed=rate))
        ece.append(total)
    return dict(class_ece=ece,macro_ece=float(np.mean(ece)),bins=bins)


def ece_upper(p,y):
    """Bootstrap whole cycles, not 60 allegedly independent minute observations."""
    p=np.asarray(p);y=np.asarray(y);n=len(y);idx=block_indices(n)
    # Per-cycle bin counts/sums give the same ECE as explicit resampling, much faster.
    values=[]
    for c in range(3):
        counts=[];difference=[]
        for b in range(10):
            mask=(p[:,:,c]>=b/10)&(p[:,:,c]<(b+1)/10 if b<9 else p[:,:,c]<=1)
            counts.append(mask.sum(axis=1));difference.append(((p[:,:,c]-(y[:,None]==c))*mask).sum(axis=1))
        counts=np.array(counts).T;difference=np.array(difference).T
        eces=np.abs(difference[idx].sum(axis=1)).sum(axis=1)/(n*p.shape[1])
        values.append(float(np.quantile(eces,.95)))
    return values
