"""Explicit safe checkpoint codec. No executable deserialization."""
from collections import deque
import io,json,math,gzip
import numpy as np
from ..journal import canonical,digest
from ..models import Engine
from ..observations import Facts
from .incremental import Incremental,Indicator,MTF,Tape,Rank,Smoother

CLASSES={c.__name__:c for c in (Incremental,Indicator,MTF,Tape,Rank,Smoother,Engine,Facts)}

def pack(state):
    arrays={}
    def encode(x):
        if isinstance(x,np.ndarray):
            if x.dtype!=np.dtype('float64'):raise ValueError('CHECKPOINT_FLOAT64_ONLY')
            key='a'+str(len(arrays));arrays[key]=x;return {'array':key}
        if isinstance(x,(np.integer,np.bool_)):return x.item()
        if isinstance(x,(float,np.floating)):
            return float(x) if np.isfinite(x) else {'float':'nan' if np.isnan(x) else 'inf' if x>0 else '-inf'}
        if x is None or isinstance(x,(str,int,bool)):return x
        if isinstance(x,dict):return {'map':[[encode(k),encode(v)] for k,v in x.items()]}
        if isinstance(x,deque):return {'deque':[encode(v) for v in x],'maxlen':x.maxlen}
        if isinstance(x,(tuple,list,set)):
            values=[encode(v) for v in x]
            if isinstance(x,set):values.sort(key=lambda v:canonical(v))
            return {type(x).__name__:values}
        if type(x).__name__ in CLASSES and type(x) is CLASSES[type(x).__name__]:
            return {'class':type(x).__name__,'attrs':encode(vars(x))}
        raise ValueError('CHECKPOINT_TYPE_NOT_ALLOWED')
    meta=gzip.compress(canonical(encode(state)),mtime=0);buffer=io.BytesIO();np.savez_compressed(buffer,**arrays)
    return meta,buffer.getvalue()

def unpack(meta,raw):
    with np.load(io.BytesIO(raw),allow_pickle=False) as archive:arrays={k:archive[k] for k in archive.files}
    if any(v.dtype!=np.dtype('float64') for v in arrays.values()):raise ValueError('INVALID_ARRAY_DTYPE')
    def decode(x):
        if not isinstance(x,dict):return x
        if 'array' in x:return arrays[x['array']].copy()
        if 'float' in x:return float(x['float'])
        if 'map' in x:return {decode(k):decode(v) for k,v in x['map']}
        if 'deque' in x:return deque((decode(v) for v in x['deque']),maxlen=x['maxlen'])
        for kind,constructor in [('list',list),('tuple',tuple),('set',set)]:
            if kind in x:return constructor(decode(v) for v in x[kind])
        if x.get('class') in CLASSES:
            instance=CLASSES[x['class']].__new__(CLASSES[x['class']]);instance.__dict__.update(decode(x['attrs']));return instance
        raise ValueError('INVALID_CHECKPOINT_TAG')
    return decode(json.loads(gzip.decompress(meta)))

def state_digest(state):
    meta,raw=pack(state);return digest(dict(meta=__import__('hashlib').sha256(meta).hexdigest(),arrays=__import__('hashlib').sha256(raw).hexdigest()))
