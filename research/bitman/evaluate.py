"""JSON scalar export adapter; frozen strategy/engine/run files unchanged.

The initial TEST attempt stopped at json.dumps(trade) on np.int64 hold_hours.
This wrapper only normalizes NumPy scalars, never reselects or changes math.
"""
import json
from types import SimpleNamespace
import numpy as np
from . import run
from .data import digest


def native_scalar(value):
    if isinstance(value,np.generic): return value.item()
    raise TypeError('NON_JSON_RESEARCH_VALUE')


def dumps(value,**kwargs):
    return json.dumps(value,default=native_scalar,**kwargs)


def main():
    original=run.json
    art=run.ART
    receipt=dict(reason='Initial TEST export TypeError: Object of type int64 is not JSON serializable',
        scope='JSON scalar normalization only; no strategy/engine source changes',
        code_sha256=run.code_hash(),selection_sha256=digest(art/'selection_lock.json'),
        preregistered_sha256=digest(art/'preregistered.json'),selection_repeated=False)
    lock=json.loads((art/'selection_lock.json').read_text())
    if run.code_hash()!=lock['code_sha256']: raise ValueError('FROZEN_STRATEGY_CHANGED')
    path=art/'serialization_receipt.json'
    if not path.exists(): path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
    run.json=SimpleNamespace(dumps=dumps,loads=json.loads)
    try: run.evaluate()
    finally: run.json=original


if __name__=='__main__': main()
