"""Reproduce local closed-market diagnostics; no return/outcome analysis."""
import csv
import json
from pathlib import Path
from .compare import load_market
from .semantics import HOUR, descriptive_rows

HERE = Path(__file__).resolve().parent


def build():
    outputs = {}
    (HERE / 'artifacts').mkdir(exist_ok=True)
    # Cover BOTH interpretations of 01:00--05:00 Madrid: candle labels and closes.
    start = 1794697200000  # 2026-11-14 23:00 UTC; opens at 00:00 CET
    end = start + 6 * HOUR  # last open 04:00 UTC; available 05:00 UTC / 06:00 CET
    for venue in ('BINANCE_SPOT', 'BINANCE_USDM_PERPETUAL'):
        manifest = json.loads((HERE / 'fixtures' / (venue + '.json')).read_text())
        a = load_market(HERE / 'fixtures' / (venue + '.csv.gz'), manifest)
        rows = [dict(venue=venue, **r) for r in descriptive_rows(a) if start <= r['open_time_ms'] < end]
        output = HERE / 'artifacts' / (venue + '_focus.csv')
        with output.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
        outputs[venue] = rows
    return outputs


def chart():
    # Optional plotting dependency, never required by numerical/test entry points.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from datetime import datetime
    from zoneinfo import ZoneInfo
    figures = []
    for venue in ('BINANCE_SPOT', 'BINANCE_USDM_PERPETUAL'):
        m = json.loads((HERE / 'fixtures' / (venue + '.json')).read_text())
        a = load_market(HERE / 'fixtures' / (venue + '.csv.gz'), m)
        all_rows = descriptive_rows(a)
        rows = all_rows[-18:]
        x = [datetime.fromisoformat(r['close_utc'].replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Madrid')) for r in rows]
        fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)
        for key, color in [('pececillos', '#178545'), ('tendencia', '#946332'),
                           ('tiburones', '#2269a9'), ('ma_trend', '#d33d3d')]:
            axes[0].plot(x, [r[key] for r in rows], marker='.', label=key, color=color)
        axes[0].axhline(0, color='grey', linewidth=.7)
        axes[0].set_ylabel('Koncorde components')
        for key, color in [('adx', '#d33d3d'), ('plus_di', '#178545'), ('minus_di', '#7755aa')]:
            axes[1].plot(x, [r[key] for r in rows], marker='.', label=key, color=color)
        axes[1].set_ylabel('ADX / DMI 14/14')
        axes[2].bar(x, [r['ao'] for r in rows], width=.025,
                    color=['#178545' if r['ao_slope'] > 0 else '#d33d3d' for r in rows])
        axes[2].set_ylabel('AO (color = slope)')
        axes[3].plot(x, a[-len(rows):, 4], marker='.', color='#324c76', label='Closed BTC price')
        axes[3].set_ylabel('BTCUSDT close')
        for ax in axes:
            ax.grid(alpha=.2)
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                ax.legend(loc='upper left', fontsize=8)
        import matplotlib.dates as mdates
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%d %H:%M', tz=ZoneInfo('Europe/Madrid')))
        axes[-1].set_xlabel('Earliest availability at H1 close, Europe/Madrid (UTC+1); actual receipt unknown')
        fig.suptitle(venue + '\nLOCAL PUBLIC-MARKET REPLAY, NOT A TradingOne EXPORT / NO VISUAL PARITY', fontsize=12)
        fig.tight_layout(rect=(0, 0, 1, .95))
        path = HERE / 'artifacts' / (venue + '_series.png')
        fig.savefig(path, dpi=145)
        plt.close(fig)
        figures.append(path.name)
    return figures


if __name__ == '__main__':
    build()
    print(json.dumps(dict(descriptive_only=True, chart_files=chart(), new_backtests=0)))
