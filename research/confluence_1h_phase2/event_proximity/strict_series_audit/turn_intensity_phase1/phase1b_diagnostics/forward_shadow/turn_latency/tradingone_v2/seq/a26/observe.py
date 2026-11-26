"""Export observations only; missing confirmations remain explicitly unspecified."""
from .run import load,H,CUT,START,HERE,csvwrite,dump
from .member import observe
def execute():
    dest=HERE/'out/member.csv'
    if dest.exists():raise ValueError('DO_NOT_OVERWRITE_OBSERVATIONS')
    frames,_=load();rows=[]
    for row in frames['1h'].records:
        when=row['available_at']
        if START<=when<=CUT:rows.append(observe({k:f.at(when) for k,f in frames.items()}))
    csvwrite(dest,rows);dump(HERE/'out/member_latest.json',rows[-1])
    print('OBSERVATIONS_ONLY',len(rows),'NO_SIGNALS_NO_OUTCOMES')
if __name__=='__main__':execute()
