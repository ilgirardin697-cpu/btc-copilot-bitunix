"""Unique-observation census, inclusive regime baseline, no automatic validation."""
import hashlib,json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from .journal import canonical,digest,JournalError
from .protocol import config


def read_records(path,registry):
    raw=Path(path).read_bytes()
    if raw and not raw.endswith(b'\n'):raise JournalError('TRUNCATED_JOURNAL')
    rows=[];seen=set();previous='0'*64
    for line in raw.splitlines():
        r=json.loads(line);checksum=r.pop('record_hash',None)
        if r['registry_hash']!=registry or r['prev_hash']!=previous or digest(r)!=checksum or r['record_id'] in seen:raise JournalError('INVALID_JOURNAL')
        seen.add(r['record_id']);r['record_hash']=checksum;rows.append(r);previous=checksum
    return rows


def summarize(records,as_of_ms=None):
    observations={r['payload']['observation_id']:r['payload'] for r in records if r['kind']=='CANDLE'}
    outcomes={(r['payload']['observation_id'],r['payload']['horizon_h'],r['payload']['side'],r['kind']):r['payload']
              for r in records if r['kind'] in ('PRICE_OUTCOME','COSTED_OUTCOME')}
    groups=defaultdict(list);events=defaultdict(set);comparative=defaultdict(set);duplicates=0;episodes=defaultdict(list);anchors=defaultdict(dict)
    def cell(obs):
        month=datetime.fromtimestamp(obs['available_at_ms']/1000,timezone.utc).strftime('%Y-%m')
        return (month,obs['regime_4h'],obs['volatility_tercile'],obs['collection_class'],obs['mode'])
    for oid,obs in observations.items():
        if not obs['forward_eligible']:continue
        groups[cell(obs)].append(oid)  # all hours, INCLUDING events and neighbors
        for profile,p in obs['profiles'].items():
            for e in p['events']:
                episodes[e['episode_anchor_id']].append(e['event_id'])
                anchors[e['comparison_anchor_id']][profile]=dict(available_at_ms=obs['available_at_ms'],recorded_at_ms=obs['recorded_at_ms'],event_id=e['event_id'])
                for stratum in e['strata']:events[profile,e['pattern'],e['side'],stratum].add(oid)
        duplicates+=sum(max(0,len(v)-1) for v in obs['duplicate_groups'].values())
        for e in obs['comparative'].get('events',[]):
            comparative[(e['kind'],e.get('series'),e.get('n'),e.get('side'),e.get('label'))].add(oid)
    comparisons=[]
    for key,ids in sorted(events.items()):
        p,pattern,side,stratum=key
        for h in (4,12,24):
            for metric,kind,field in [('PRICE','PRICE_OUTCOME','raw_price_fraction'),('COSTED','COSTED_OUTCOME','net_fraction')]:
                vals=[];excess=[];baselines=set();missing=0
                for oid in sorted(ids):
                    result=outcomes.get((oid,h,side,kind))
                    if result is None:missing+=1;continue
                    pool=[(other,outcomes.get((other,h,side,kind))) for other in groups[cell(observations[oid])]]
                    pool=[(other,o) for other,o in pool if o is not None and o[field] is not None]
                    if not pool:missing+=1;continue
                    val=result[field];base=sum(o[field] for _,o in pool)/len(pool)
                    vals.append(val);excess.append(val-base);baselines.update(other for other,_ in pool)
                comparisons.append(dict(profile=p,pattern=pattern,side=side,stratum=stratum,horizon=h,metric=metric,
                                        unique_event_hours=len(ids),matured=len(vals),missing_or_pending=missing,
                                        inclusive_baseline_unique_hours=len(baselines),event_mean=sum(vals)/len(vals) if vals else None,
                                        excess_mean=sum(excess)/len(excess) if excess else None,
                                        baseline_excludes_event_neighbors=False,status='DESCRIPTIVE_ONLY_NOT_VALIDATED'))
    comparative_rows=[]
    for key,ids in sorted(comparative.items(),key=lambda kv:str(kv[0])):
        for h in (4,12,24):
            for side in (1,-1):  # ADX up/down is not price direction; always show both
                vals=[];diffs=[]
                for oid in ids:
                    r=outcomes.get((oid,h,side,'PRICE_OUTCOME'))
                    pool=[outcomes.get((other,h,side,'PRICE_OUTCOME')) for other in groups[cell(observations[oid])]]
                    pool=[o for o in pool if o is not None]
                    if r is not None and pool:
                        vals.append(r['raw_price_fraction']);diffs.append(r['raw_price_fraction']-sum(o['raw_price_fraction'] for o in pool)/len(pool))
                comparative_rows.append(dict(kind=key[0],series=key[1],n=key[2],fact_direction=key[3],watch=key[4],
                                             hypothetical_return_side=side,horizon=h,unique_hours=len(ids),matured=len(vals),
                                             mean_price_fraction=sum(vals)/len(vals) if vals else None,
                                             inclusive_regime_excess=sum(diffs)/len(diffs) if diffs else None,
                                             mean_capture_delay_ms=sum(observations[i]['capture_delay_ms'] for i in ids)/len(ids),
                                             status='EXPLORATORY_NO_WINNER_SELECTION'))
    as_of_ms=as_of_ms if as_of_ms is not None else max((r.get('created_at_ms',0) for r in records),default=0)
    start,end=[int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()*1000) for s in config()['cohort']['planned_22_window']]
    cutoff=min(as_of_ms+1,end);expected=max(0,(cutoff-start-1)//3600000+1)
    eligible=sum(o['forward_eligible'] for o in observations.values())
    return dict(unique_observations=len(observations),forward_eligible=eligible,
                coverage_as_of_ms=as_of_ms,expected_cohort_hours=expected,
                missing_or_not_forward_hours=max(0,expected-eligible),
                on_time_forward_coverage=eligible/expected if expected else None,
                offline_test_rows=sum(o['mode']=='OFFLINE_TEST' for o in observations.values()),
                late_rows=sum(not o['on_time'] for o in observations.values()),
                duplicate_claims_not_extra_samples=duplicates,unique_episode_anchors=len(episodes),
                episodes_with_multiple_claims=sum(len(v)>1 for v in episodes.values()),
                model_detection_comparisons=dict(anchors),comparative_comparisons=comparative_rows,
                outcomes={str(h):len({oid for oid,hh,side,k in outcomes if hh==h and k=='PRICE_OUTCOME'}) for h in (4,12,24)},
                collection_failures=sum(r['kind'] in ('COLLECTION_FAILURE','DATA_GAP') for r in records),
                candidate_attempts=sum(len(p['attempts']) for o in observations.values() for p in o['profiles'].values()),
                failed_candidate_attempts=sum(not a['emitted'] for o in observations.values() for p in o['profiles'].values() for a in p['attempts']),
                model_audit_counts={s:sum(a['status']==s for o in observations.values() for p in o['profiles'].values() for a in p['audit'])
                                    for s in ('EXPIRED','ALIGNMENT_INVALIDATED','COOLDOWN','DATA_INVALIDATED','EPISODE')},
                source_revisions=sum(r['kind'] in ('SOURCE_REVISION','FUNDING_REVISION') for r in records),
                comparisons=comparisons,validated=False,collector_or_scheduler_included=False,
                note='No automatic edge classification. Late/offline rows and absent funding are not silently promoted into primary evidence.')
