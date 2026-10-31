"""Render the ENTIRE fixed 72h excerpt plus explicitly artificial controls.

No rankings, returns, stops/targets reached, PnL or selection by outcome.
"""
from datetime import date, datetime, timezone
import json
from pathlib import Path
from .chart import svg_chart
from .data import json_text, read_csv, sha
from .model import observe


def main():
    # Control fixtures belong only to offline verification, never model logic.
    from .test_prototype import fixture
    here = Path(__file__).resolve().parent
    out = here/'examples'
    csv_path = out/'BTCUSDT_USDM_1h_20260901_03.csv'
    manifest = json.loads((out/'data_manifest.json').read_text(encoding='utf-8'))
    if (manifest['excerpt_sha256'] != sha(csv_path)
            or manifest['symbol'] != 'BTCUSDT' or manifest['venue'] != 'BINANCE_USDM_PERPETUAL'):
        raise ValueError('PUBLIC_EXCERPT_PROVENANCE_MISMATCH')
    bars = read_csv(csv_path)
    cutoff = int(datetime(2026,9,4,tzinfo=timezone.utc).timestamp()*1000)
    cards, checks = [], []
    for d in (date(2026,9,1),date(2026,9,2),date(2026,9,3)):
        r = observe(bars,d,cutoff)
        name = d.isoformat()
        (out/f'{name}.svg').write_text(svg_chart(bars,r,f'BTCUSDT USD-M | {name} | GEOMETRY CHECK ONLY'),encoding='utf-8',newline='\n')
        (out/f'{name}.json').write_text(json_text(r),encoding='utf-8',newline='\n')
        checks.append(dict(day=name,status=r['status'],reason=r.get('reason'),
                           plan_status=r['plan'] and r['plan']['status']))
        cards.append(f'<h2>{name} — {r["status"]}</h2><a href="{name}.json">Observation JSON</a><img src="{name}.svg" alt="BTCUSDT geometry check {name}">')
    for side in ('UP','DOWN'):
        b,d,t = fixture(side)
        from .model import HOUR
        r = observe(b,d,t+HOUR)
        name = f'synthetic_{side.lower()}'
        (out/f'{name}.svg').write_text(svg_chart(b,r,f'SYNTHETIC {side} CONTROL — NOT BTC — NOT HISTORICAL EVIDENCE'),encoding='utf-8',newline='\n')
        (out/f'{name}.json').write_text(json_text(r),encoding='utf-8',newline='\n')
        cards.append(f'<h2>SYNTHETIC {side} — NOT BTC / NOT EVIDENCE</h2><img src="{name}.svg" alt="Synthetic control {side}">')
    (out/'visual_checks.json').write_text(json_text(dict(
        input_sha256=sha(csv_path),all_complete_session_pairs_in_fixed_excerpt_shown=True,
        real_days=checks,performance_evaluation=False,synthetic_not_independent_evidence=True)),encoding='utf-8',newline='\n')
    (out/'index.html').write_text('<!doctype html><html lang="es"><meta charset="utf-8"><title>Single-segment geometry V1</title><style>body{background:#101824;color:#edf1f7;font:16px Arial;margin:20px}img{width:100%;max-width:1400px}a{color:#5ad8ec}</style><h1>Kill Zones — one segment and one translated copy</h1><p>Historical visual checks, no performance evaluation. Hypothesis: the original measurement extended is the trigger line; NOT exact video parity.</p><p>ALL three session pairs in the fixed excerpt are retained, including ambiguous/rejected cases. SHADOW ONLY. TRADE AUTHORITY: NONE.</p>'+''.join(cards)+'</html>\n',encoding='utf-8',newline='\n')
    print(json_text(checks))


if __name__ == '__main__':
    main()
