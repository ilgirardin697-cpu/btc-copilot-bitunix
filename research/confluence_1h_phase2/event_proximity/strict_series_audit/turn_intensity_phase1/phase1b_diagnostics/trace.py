"""Read-only instrumentation of the actual frozen function, never a variant."""
import copy
import hashlib
import inspect
import sys
import numpy as np
from .. import detect as frozen

EXPECTED_SOURCE='5f3bba638bf262ab286f02832545f2ef131eecaa4bc4eb9120c3286ba6b374c1'


def source_lines():
    raw=inspect.getsourcefile(frozen.detect)
    with open(raw,'rb') as stream:
        source=stream.read().replace(b'\r\n',b'\n')
    if hashlib.sha256(source).hexdigest()!=EXPECTED_SOURCE:
        raise ValueError('UNRECOGNIZED_FROZEN_SOURCE')
    lines=source.decode().splitlines()
    def line(fragment):
        found=[i+1 for i,s in enumerate(lines) if fragment in s]
        if len(found)!=1:raise ValueError('AMBIGUOUS_DIAGNOSTIC_LOCATION')
        return found[0]
    return line("if tokens and i-min(t['i']"),line('if needed.issubset(tokens)')


def instrument(bars, features):
    before_line,complete_line=source_lines()
    saved={};rows=[]
    def observe(frame,event,arg):
        if frame.f_code is not frozen.detect.__code__:
            return None
        if event!='line':return observe
        z=frame.f_locals
        if frame.f_lineno==before_line:
            saved.clear();saved.update(copy.deepcopy(z['tokens']))
        elif frame.f_lineno==complete_line:
            i,p,side=z['i'],z['p'],z['side'];f=z['f'];ao=z['ao']
            ao_sign_ok=bool(side*ao[i]<0) if p==frozen.PATTERNS[0] else bool(side*ao[i]>0) if p==frozen.PATTERNS[2] else True
            dmi=bool(f['plus_di'][i]>f['minus_di'][i]) if side==1 else bool(f['minus_di'][i]>f['plus_di'][i])
            adx_ok=bool(f['adx'][i]<f['adx'][i-1]) if p==frozen.PATTERNS[0] else bool(f['adx'][i]>f['adx'][i-1]) if p==frozen.PATTERNS[1] else True
            post=copy.deepcopy(z['tokens']);need=z['needed']
            r=dict(i=i,pattern=p,side=side,pre_tokens=copy.deepcopy(saved),post_tokens=post,
                   raw_ao22=bool(z['turns']['ao',side][i]),raw_pece22=bool(z['turns']['pece',side][i]),
                   qualified_ao_event=bool(z['ao_event']),adx_event=bool(z['adx_event']),
                   ao_sign_ok=ao_sign_ok,ao_slope_ok=bool(side*(ao[i]-ao[i-1])>0),
                   pece_slope_ok=bool(z['pece_ok']),adx_slope_ok=adx_ok,
                   dmi_ok=dmi if p==frozen.PATTERNS[1] else True,
                   complete_tokens=bool(need.issubset(post)),current_alignment=bool(z['pece_ok'] and z['ao_ok'] and z['adx_ok']),
                   cooldown=bool(i-z['last'][p,side]<25),
                   missing_tokens=sorted(need-set(post)))
            r['failed_flags']=[name for name in ('ao_sign_ok','ao_slope_ok','pece_slope_ok','adx_slope_ok','dmi_ok') if not r[name]]
            rows.append(r)
        return observe
    previous=sys.gettrace()
    try:
        sys.settrace(observe)
        events,audit=frozen.detect(bars,features)
    finally:
        sys.settrace(previous)
    event_lookup={(e['i'],e['pattern'],e['side']):e for e in events}
    statuses={}
    for a in audit:statuses.setdefault((a['i'],a['pattern'],a['side']),[]).append(a['status'])
    for row in rows:
        key=(row['i'],row['pattern'],row['side'])
        row['actual_status']=statuses.get(key,[])
        e=event_lookup.get(key);row['actual_event_id']=e['event_id'] if e else None
        row['strata']=e['strata'] if e else []
    return events,audit,rows


def simple_turn(values,side):
    x=np.asarray(values,float);d=x-frozen.lag(x)
    return (side*d>0)&(side*frozen.lag(d)<0)


def funnel(bars, f, events, audit, rows, windows):
    """Static opportunities and actual state counts are deliberately separate."""
    output=[];opportunities=[]
    for stage,(start,end) in windows.items():
        stop=end-25
        for p in frozen.PATTERNS:
            for side in (1,-1):
                series=[r for r in rows if r['pattern']==p and r['side']==side]
                by={r['i']:r for r in series}
                mask=np.arange(len(bars));mask=(mask>=start)&(mask<stop)
                adx_side=-1 if p==frozen.PATTERNS[0] else 1
                ao22=frozen.two_turn(f['ao'],side);pece22=frozen.two_turn(f['minnows'],side)
                adx22=frozen.two_turn(f['adx'],adx_side)
                required=('ao','pece') if p==frozen.PATTERNS[2] else ('ao','pece','adx')
                raw={'ao':ao22,'pece':pece22,'adx':adx22}
                last={};candidates=[]
                for i in range(len(bars)):
                    for n in required:
                        if raw[n][i]:last[n]=i
                    if set(required).issubset(last) and i-max(last.values())==0 and i-min(last.values())<=2 and i in by and start<=i<stop:
                        row=dict(stage=stage,pattern=p,side=side,i=i,raw_window_tokens=dict(last),
                                 original_event=by[i]['actual_event_id'],**{k:by[i][k] for k in ('ao_sign_ok','ao_slope_ok','pece_slope_ok','adx_slope_ok','dmi_ok')})
                        row['ao_event_sign_ok']=by[last['ao']]['qualified_ao_event'] if last['ao'] in by else False
                        opportunities.append(row);candidates.append(row)
                count=dict(stage=stage,pattern=p,side=side,hours=int(mask.sum()),
                           adx_required=p!=frozen.PATTERNS[2],
                           individual_adx_simple=int(simple_turn(f['adx'],adx_side)[mask].sum()),
                           individual_adx22=int(adx22[mask].sum()),
                           individual_adx22_peak=int(frozen.two_turn(f['adx'],-1)[mask].sum()),
                           individual_adx22_trough=int(frozen.two_turn(f['adx'],1)[mask].sum()),
                           individual_adx_simple_peak=int(simple_turn(f['adx'],-1)[mask].sum()),
                           individual_adx_simple_trough=int(simple_turn(f['adx'],1)[mask].sum()),
                           individual_ao_simple=int(simple_turn(f['ao'],side)[mask].sum()),
                           individual_ao22=int(ao22[mask].sum()),
                           individual_pece_simple=int(simple_turn(f['minnows'],side)[mask].sum()),
                           individual_pece22=int(pece22[mask].sum()),
                           simultaneous22=int(np.logical_and.reduce([raw[n] for n in required])[mask].sum()),
                           within2h_raw=len(candidates))
                kept=candidates
                for gate in ('ao_sign_ok','ao_event_sign_ok','ao_slope_ok','pece_slope_ok','adx_slope_ok','dmi_ok'):
                    count['nonexclusive_'+gate+'_fail']=sum(not r[gate] for r in candidates)
                    after=[r for r in kept if r[gate]]
                    count['ordered_drop_'+gate]=len(kept)-len(after);count['after_'+gate]=len(after);kept=after
                current=[r for r in series if start<=r['i']<stop]
                for kind in ('EXPIRED','ALIGNMENT_INVALIDATED','COOLDOWN','DATA_INVALIDATED'):
                    count[kind.lower()]=sum(kind in r['actual_status'] for r in current)
                count['complete_stateful_before_cooldown']=sum(r['complete_tokens'] and r['current_alignment'] for r in current)
                valid=[e for e in events if e['pattern']==p and e['side']==side and start<=e['i']<stop]
                for s in ('ALL','Q75','Q90'):count[s]=sum(s in e['strata'] for e in valid)
                count['ordered_drop_stateful_tokens']=len(kept)-count['complete_stateful_before_cooldown']
                count['drop_ALL_to_Q75']=count['ALL']-count['Q75'];count['drop_Q75_to_Q90']=count['Q75']-count['Q90']
                output.append(count)
    return output,opportunities
