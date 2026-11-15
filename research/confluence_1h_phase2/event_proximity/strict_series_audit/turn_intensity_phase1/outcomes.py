"""No-stop event study: next-open entries, percentage and ATR units only."""
import numpy as np


def outcome(bars, funding, i, side, atr, hours=12, fee=.001, slip=.0005):
    a, f = np.asarray(bars, float), np.asarray(funding, float)
    if side not in (-1, 1) or hours not in (4, 12, 24) or not np.isfinite(atr) or atr <= 0:
        raise ValueError('FIXED_PHASE1_PARAMETERS_REQUIRED')
    entry_i, exit_i = int(i)+1, int(i)+1+hours
    if exit_i >= len(a):
        return None
    if not np.isfinite(a[i:exit_i+1]).all() or (np.diff(a[i:exit_i+1, 0]) != 3600000).any():
        return None
    entry = float(a[entry_i, 1]*(1+side*slip))
    exit_price = float(a[exit_i, 1]*(1-side*slip))
    gross = side*(exit_price-entry)
    fees = fee*(entry+exit_price)
    low_cost, high_cost, missing, boundary = 0., 0., 0, 0
    if f.size:
        if f.ndim != 2 or f.shape[1] != 6:
            raise ValueError('FUNDING_SIX_FIELDS')
        for row in f[(f[:,0] >= a[entry_i,0]) & (f[:,0] <= a[exit_i,0])]:
            t, rate, mark = row[:3]
            if np.isfinite(mark):
                vals = [side*rate*mark]
            else:
                if not np.isfinite(row[4:6]).all():
                    return None
                missing += 1
                vals = [side*rate*x for x in row[4:6]]
            if t in (a[entry_i,0], a[exit_i,0]):
                boundary += 1
                vals.append(0.)  # exact entry/settlement ordering not observed
            low_cost += min(vals); high_cost += max(vals)
    lo, hi = gross-fees-high_cost, gross-fees-low_cost
    held = a[entry_i:exit_i]
    favorable = max(0., float(held[:,2].max()-entry) if side == 1 else float(entry-held[:,3].min()))
    adverse = max(0., float(entry-held[:,3].min()) if side == 1 else float(held[:,2].max()-entry))
    return dict(entry_i=entry_i, exit_i=exit_i, entry_at=int(a[entry_i,0]), exit_at=int(a[exit_i,0]),
                entry_reference=float(a[entry_i,1]), entry=entry, exit=exit_price, hours=hours,
                gross_fraction=float(gross/entry), net_fraction=float(lo/entry), net_percent=float(100*lo/entry),
                optimistic_fraction=float(hi/entry), exact_net_fraction=float(lo/entry) if not (missing or boundary) else None,
                net_atr=float(lo/atr), missing_marks=missing, boundary_settlements=boundary,
                funding_low_per_btc=float(low_cost), funding_high_per_btc=float(high_cost),
                fees_per_btc=float(fees), mfe_fraction=favorable/entry, mae_fraction=adverse/entry)
