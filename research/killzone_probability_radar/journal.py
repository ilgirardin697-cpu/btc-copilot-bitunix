"""Optional OFFLINE capture of user-supplied realtime Pine Logs; no remote receiver."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import os
from .dataset import NY

PREFIX = 'IGOD_KILLZONE_RADAR_V1='


def digest(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_prediction(p):
    allowed = {'version', 'available_at', 'emitted_at', 'minute', 'status', 'features', 'probabilities'}
    if set(p) != allowed:
        raise ValueError('UNEXPECTED_LOG_FIELDS')
    if type(p['available_at']) is not int or type(p['emitted_at']) is not int or p['emitted_at'] < p['available_at']:
        raise ValueError('TIME_NOT_CAUSAL')
    t = datetime.fromtimestamp(p['available_at']/1000, timezone.utc).astimezone(NY)
    if t.hour != 5 or t.second or t.microsecond or p['minute'] != t.minute:
        raise ValueError('OUTSIDE_FORECAST_WINDOW')
    if len(p['features']) != 14 or not all(isinstance(x, (int, float)) for x in p['features']):
        raise ValueError('FEATURE_SCHEMA')
    # This release never publishes validated probabilities; do not accept forged percentages.
    if p['probabilities'] is not None or p['status'] not in ('NO VALIDADO', 'EXPERIMENTAL'):
        raise ValueError('PUBLICATION_GATE_CLOSED')
    digest(p)
    return p


def read(path):
    path = Path(path)
    if not path.exists(): return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('CAPTURE_JOURNAL_INVALID_NO_REPAIR')
    result = []; previous = '0'*64; ids = set()
    for line in raw.splitlines():
        r = json.loads(line); expected = r.pop('record_hash')
        if r['prev_hash'] != previous or digest(r) != expected or r['record_id'] in ids:
            raise ValueError('CAPTURE_JOURNAL_INVALID_NO_REPAIR')
        validate_prediction(r['prediction'])
        r['record_hash'] = expected; result.append(r); ids.add(r['record_id']); previous = expected
    return result


def append(path, prediction):
    p = validate_prediction(prediction); records = read(path)
    rid = f"{p['version']}:{p['available_at']}"
    for row in records:
        if row['record_id'] == rid:
            if row['prediction'] != p:
                raise ValueError('CONFLICTING_EXISTING_PREDICTION_NO_REWRITE')
            return False
    if records and p['available_at'] <= records[-1]['prediction']['available_at']:
        raise ValueError('NONCHRONOLOGICAL_CAPTURE')
    row = dict(record_id=rid, prediction=p, captured_at=datetime.now(timezone.utc).isoformat(),
               origin='USER_SUPPLIED_TRADINGVIEW_LOG_NOT_INDEPENDENT_LIVE_ATTESTATION',
               prev_hash=records[-1]['record_hash'] if records else '0'*64)
    row['record_hash'] = digest(row)
    with Path(path).open('ab') as f:
        f.write(json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()+b'\n')
        f.flush(); os.fsync(f.fileno())
    return True


def parse_logs(text):
    for line in text.splitlines():
        if PREFIX in line:
            yield validate_prediction(json.loads(line.split(PREFIX, 1)[1]))


def main():
    p = argparse.ArgumentParser(); p.add_argument('logs'); p.add_argument('--journal', required=True); args = p.parse_args()
    destination = Path(args.journal).resolve()
    # Experimental capture belongs in this checkout's ignored cache, never the production volume.
    safe_root = Path(__file__).resolve().parents[1]/'cache'
    if not destination.is_relative_to(safe_root.resolve()):
        raise ValueError('CAPTURE_ONLY_RESEARCH_CACHE')
    destination.parent.mkdir(parents=True, exist_ok=True)
    added = sum(append(destination, r) for r in parse_logs(Path(args.logs).read_text(encoding='utf-8-sig')))
    print(json.dumps(dict(added=added, verified_records=len(read(destination)))))


if __name__ == '__main__':
    main()
