"""Private durable action history. Truncation/tampering never repaired automatically."""
import hashlib
import json
import os
from pathlib import Path
import time


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


class Journal:
    def __init__(self,path,clock=time.time):
        self.path=Path(path);self.clock=clock
        self.rows=[];self.ids=set();self.tip='0'*64;self.poisoned=False
        if self.path.exists():
            raw=self.path.read_bytes()
            if raw and not raw.endswith(b'\n'):raise ValueError('CAPITAL_JOURNAL_TORN')
            for line in raw.splitlines():
                row=json.loads(line);digest=row.pop('hash')
                if row['prev_hash']!=self.tip or hashlib.sha256(canonical(row)).hexdigest()!=digest or row['id'] in self.ids:
                    raise ValueError('CAPITAL_JOURNAL_INVALID')
                row['hash']=digest;self.rows.append(row);self.ids.add(row['id']);self.tip=digest

    def append(self,identifier,kind,payload):
        if self.poisoned:raise ValueError('CAPITAL_JOURNAL_LATCHED')
        if identifier in self.ids:return False
        row=dict(schema=1,id=identifier,kind=kind,observed_ms=int(self.clock()*1000),payload=payload,prev_hash=self.tip)
        row['hash']=hashlib.sha256(canonical(row)).hexdigest()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        try:
            with self.path.open('ab') as stream:
                stream.write(canonical(row)+b'\n');stream.flush();os.fsync(stream.fileno())
        except Exception:
            self.poisoned=True
            raise ValueError('CAPITAL_JOURNAL_WRITE_UNCERTAIN') from None
        self.rows.append(row);self.ids.add(identifier);self.tip=row['hash'];return True

    def latest(self,kind):
        return next((r['payload'] for r in reversed(self.rows) if r['kind']==kind),None)

    def pending(self):
        done={r['payload']['client_id'] for r in self.rows if r['kind']=='RECONCILED'}
        return next((r['payload'] for r in self.rows if r['kind']=='INTENT' and r['payload']['client_id'] not in done),None)

    def owned_stops(self):
        return {r['payload']['order_id']:r['payload'] for r in self.rows if r['kind']=='STOP_OWNED'}
