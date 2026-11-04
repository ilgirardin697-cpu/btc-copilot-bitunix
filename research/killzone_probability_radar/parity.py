"""Independent TradingView comparison needs ACTUAL logs. Local arithmetic is labeled separately."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import numpy as np
from .data import CACHE
from .dataset import NY
from .journal import parse_logs


def pine_arithmetic(model, vector):
    # Literal scalar arithmetic order emitted into Pine; NOT an executed Pine runtime.
    z = list(model['weights'][0])
    for j, feature in enumerate(model['indices']):
        value = max(-8, min(8, (float(vector[feature])-model['mean'][j])/model['scale'][j]))
        for k in range(3): z[k] += value*model['weights'][j+1][k]
    largest = max(z); e = [math.exp(v-largest) for v in z]
    return [v/sum(e) for v in e]


def compare(logs, dataset):
    a = np.load(dataset); lookup = {day: i for i, day in enumerate(a['days'])}; rows = []
    for p in parse_logs(logs):
        day = datetime.fromtimestamp(p['available_at']/1000, timezone.utc).astimezone(NY).date().isoformat()
        if day not in lookup:
            rows.append(dict(available_at=p['available_at'], status='NO_OFFLINE_REFERENCE_CYCLE')); continue
        expected = a['X'][lookup[day], p['minute']]
        actual = np.array(p['features']); error = abs(actual-expected)
        rows.append(dict(available_at=p['available_at'], status='PASS' if np.allclose(actual, expected, rtol=1e-8, atol=1e-8) else 'MISMATCH',
                         absolute_error_per_feature=error.tolist(), max_absolute_error=float(error.max())))
    return dict(actual_tradingview_records=len(rows), records=rows,
                status='NO_ACTUAL_TRADINGVIEW_RECORDS' if not rows else 'PASS' if all(r['status']=='PASS' for r in rows) else 'REVIEW_REQUIRED',
                probability_runtime_parity='NOT_AVAILABLE_PUBLICATION_GATE_CLOSED')


def main():
    p = argparse.ArgumentParser(); p.add_argument('logs'); p.add_argument('--out', required=True); args = p.parse_args()
    r = compare(Path(args.logs).read_text(encoding='utf-8-sig'), CACHE/'dataset.npz')
    Path(args.out).write_text(json.dumps(r, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in r.items() if k != 'records'}))


if __name__ == '__main__':
    main()
