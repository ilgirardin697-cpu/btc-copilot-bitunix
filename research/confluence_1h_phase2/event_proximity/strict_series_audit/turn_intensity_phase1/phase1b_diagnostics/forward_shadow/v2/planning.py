"""Reproduce development-noise planning; cannot overwrite the sealed power file."""
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from ....detect import features,HOUR
from ....outcomes import outcome
from .registry import ROOT
from .statistics import freeze_power

EXPECTED_DATA='5b2544c9bf353cedb77a07781ffe9e6202b12513c0c10f3d25bca67756a4825a'

def reproduce(path,out):
    if Path(out).resolve()==(ROOT/'power.json').resolve():raise ValueError('SEALED_POWER_FILE_CANNOT_BE_OVERWRITTEN')
    sha=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if sha!=EXPECTED_DATA:raise ValueError('AUDITED_INPUT_CHECKSUM_REQUIRED')
    first=int(datetime(2022,11,1,tzinfo=timezone.utc).timestamp()*1000);end=int(datetime(2025,1,1,tzinfo=timezone.utc).timestamp()*1000)
    with np.load(path,allow_pickle=False) as z:a=z['bars'][z['bars'][:,0]<end];fund=z['funding'][z['funding'][:,0]<end]
    f=features(a);y=[];cells=[];lookup={}
    for i in range(len(a)-14):
        if a[i,0]+HOUR<first or not np.isfinite([f['atr'][i],f['vol_rank'][i],f['regime4h'][i]]).all():continue
        lo,hi=a[i+1,0],a[i+13,0];small=fund[np.searchsorted(fund[:,0],lo,'left'):np.searchsorted(fund[:,0],hi,'right')]
        values=[outcome(a,small,i,s,f['atr'][i],12)['net_fraction'] for s in (1,-1)]
        if not np.isfinite(values).all():continue
        month=datetime.fromtimestamp((a[i,0]+HOUR)/1000,timezone.utc).strftime('%Y-%m');cell=(month,float(f['regime4h'][i]),min(2,int(f['vol_rank'][i]*3)))
        cells.append(lookup.setdefault(cell,len(lookup)));y.append(values)
    result=freeze_power(y,cells,dict(dataset_sha256=sha,warmup_first_open=int(a[0,0]),sample_start='2022-11-01T00:00:00Z',
               sample_end_exclusive='2025-01-01T00:00:00Z',last_open=int(a[-1,0]),hours=len(y),
               role='DEVELOPMENT_NOISE_PLANNING_ONLY; no signal ranking, no outcomes2025+',venue='BINANCE_USDM_PERPETUAL'))
    Path(out).write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--npz',required=True);p.add_argument('--out',required=True);a=p.parse_args();print(json.dumps(reproduce(a.npz,a.out)))
