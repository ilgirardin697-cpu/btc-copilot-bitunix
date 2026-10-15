"""Read-only bridge to the accepted forward auditor; original importer unchanged."""
import argparse
from collections import Counter
import json
from pathlib import Path
from research.import_forward_journals import load_market, milliseconds, sha, summarize


def run(input_dir,output_dir,as_of,market_csv=None):
    root=Path(input_dir).resolve(strict=True);out=Path(output_dir).resolve()
    if root.is_relative_to(out) or out.is_relative_to(root): raise ValueError('OUTPUT_MUST_BE_SEPARATE')
    path=root/'bitman_signals.jsonl';before=sha(path)
    events=[];issues=Counter();seen=set()
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            if not line.endswith('\n'): issues['TORN_ROW_IGNORED']+=1;continue
            try:
                r=json.loads(line)
                if r.get('source')!='FORWARD_LIVE' or r.get('shadow_only') is not True or r.get('trade_authority') is not False:
                    issues['NOT_FORWARD_SHADOW']+=1;continue
                if r['side'] not in ('LONG','SHORT') or r['reference_price']<=0 or r['signal_time']<r['closed_1h_time']:
                    raise ValueError
                if r['event_id'] in seen: issues['DUPLICATE']+=1;continue
                seen.add(r['event_id'])
                if r['signal_time']>as_of: continue
                events.append(dict(system='bitman',identity=r['event_id'],observed_at=r['signal_time'],
                    reference=r['reference_price'],side=r['side'],event=r['side'],quality='NA',timeframe='1h',
                    version=r['software_version']+'_'+r['selection_hash']))
            except (ValueError,KeyError,TypeError): issues['INVALID_ROW']+=1
    market=load_market(market_csv) if market_csv else None
    result=dict(source='FORWARD_LIVE_EXPORTED_COPY',source_sha256=before,as_of=as_of,
                cohorts=summarize(events,market,as_of),issues=dict(issues),signal_reconstruction=False,
                trade_authority=False,note='Signal statistics only, not fills/account PnL. No historical study is modified.')
    if sha(path)!=before: raise ValueError('INPUT_CHANGED')
    out.mkdir(parents=True,exist_ok=True)
    (out/'bitman_forward_report.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-dir',required=True)
    p.add_argument('--output-dir',required=True);p.add_argument('--as-of',required=True);p.add_argument('--market-csv')
    a=p.parse_args();run(a.input_dir,a.output_dir,milliseconds(a.as_of),a.market_csv)
