"""Small deterministic multinomial models; fit/selection never see test outcomes."""
import json
import numpy as np
from .data import CACHE, HERE, protocol_hash

MODELS = {'PRICE': list(range(6)), 'PRICE_MOMENTUM': list(range(11)),
          'PRICE_BBWP': list(range(6))+[11, 12], 'PRICE_4H': list(range(6))+[13]}


def softmax(z):
    z = z-np.max(z, axis=-1, keepdims=True)
    e = np.exp(z)
    return e/e.sum(axis=-1, keepdims=True)


def fit(X, Y, indices):
    x = X[:, :, indices].reshape(-1, len(indices)); y = np.repeat(Y, 60)
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale < 1e-12] = 1
    x = np.column_stack([np.ones(len(x)), np.clip((x-mean)/scale, -8, 8)])
    target = np.eye(3)[y]; w = np.zeros((x.shape[1], 3)); m = np.zeros_like(w); v = np.zeros_like(w)
    gradient = float('inf')
    for step in range(1, 3001):
        p = softmax(x@w)
        g = x.T@(p-target)/len(x); g[1:] += .01*w[1:]
        gradient = float(abs(g).max())
        if gradient < 1e-7:
            break
        m = .9*m+.1*g; v = .999*v+.001*g*g
        w -= .03*(m/(1-.9**step))/(np.sqrt(v/(1-.999**step))+1e-8)
    return dict(indices=indices, mean=mean.tolist(), scale=scale.tolist(), weights=w.tolist(),
                iterations=step, gradient=gradient, converged=gradient < 1e-7)


def predict(model, X):
    x = X[:, :, model['indices']]
    x = np.clip((x-np.array(model['mean']))/np.array(model['scale']), -8, 8)
    return softmax(np.concatenate([np.ones((*x.shape[:-1], 1)), x], axis=-1)@np.array(model['weights']))


def losses(p, y):
    target = np.eye(3)[y][:, None, :]
    brier = ((p-target)**2).sum(axis=-1)
    logloss = -np.log(np.clip(np.take_along_axis(p, y[:, None, None], axis=2)[:, :, 0], 1e-15, 1))
    return brier, logloss


def calibration(p, y):
    target = np.repeat(np.eye(3)[y], 60, axis=0); pp = p.reshape(-1, 3)
    rows = []; eces = []
    for k in range(3):
        ece = 0
        for bucket in range(10):
            mask = (pp[:, k] >= bucket/10) & (pp[:, k] < (bucket+1)/10 if bucket < 9 else pp[:, k] <= 1)
            n = int(mask.sum())
            conf = float(pp[mask, k].mean()) if n else None
            freq = float(target[mask, k].mean()) if n else None
            if n: ece += n/len(pp)*abs(conf-freq)
            rows.append(dict(class_index=k, lower=bucket/10, rows=n, mean_probability=conf, frequency=freq))
        eces.append(ece)
    return dict(macro_ece=float(np.mean(eces)), bins=rows)


def ci(difference, seed=20261104):
    # One value per cycle, then circular seven-cycle blocks. Never resample minutes independently.
    a = np.asarray(difference); n = len(a); rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(2000, (n+6)//7))
    idx = (starts[:, :, None]+np.arange(7)) % n
    values = a[idx.reshape(2000, -1)[:, :n]].mean(axis=1)
    return [float(x) for x in np.quantile(values, [.025, .975])]


def metrics(p, y):
    b, l = losses(p, y)
    return dict(cycles=len(y), predictions=len(y)*60, brier=float(b.mean()),
                logloss=float(l.mean()), class_counts=np.bincount(y, minlength=3).tolist(),
                calibration=calibration(p, y))


def main():
    a = np.load(CACHE/'dataset.npz'); X, y, days = a['X'], a['Y'], a['days']
    train = (days <= '2023-12-30'); val = (days >= '2024-01-01') & (days <= '2024-12-30'); test = days >= '2025-01-01'
    prior = (np.bincount(y[train], minlength=3)+1)/(train.sum()+3)
    fitted = {}; probabilities = {'PRIOR': np.broadcast_to(prior, (len(y), 60, 3)).copy()}
    for name, indices in MODELS.items():
        fitted[name] = fit(X[train], y[train], indices)
        probabilities[name] = predict(fitted[name], X)
        print(json.dumps(dict(model=name, fit=fitted[name]['converged'], iterations=fitted[name]['iterations'],
                              gradient=fitted[name]['gradient'])), flush=True)
    selected = min(MODELS, key=lambda name: losses(probabilities[name][val], y[val])[0].mean())
    report = dict(protocol_hash=protocol_hash(), selected_on_validation=selected, prior=prior.tolist(),
                  models=fitted, partitions={}, eras={}, gate_failures=[], model_status='NO VALIDADO',
                  independent_tradingview_parity='PENDING_ACTUAL_PINE_EXECUTION', visible_probabilities_allowed=False)
    for part, mask in [('train', train), ('validation', val), ('test', test)]:
        report['partitions'][part] = {}
        for name, p in probabilities.items():
            r = metrics(p[mask], y[mask]); ref = losses(probabilities['PRIOR'][mask], y[mask])[0].mean(axis=1)
            own = losses(p[mask], y[mask])[0].mean(axis=1)
            r['brier_gain_vs_prior'] = float(np.mean(ref-own)); r['brier_gain_ci95'] = ci(ref-own)
            if name != 'PRIOR':
                price = losses(probabilities['PRICE'][mask], y[mask])[0].mean(axis=1)
                r['gain_vs_price'] = float(np.mean(price-own)); r['gain_vs_price_ci95'] = ci(price-own)
            report['partitions'][part][name] = r
    for part in ('validation', 'test'):
        r = report['partitions'][part][selected]; base = report['partitions'][part]['PRIOR']
        if min(r['class_counts']) < 30: report['gate_failures'].append(part+':CLASS_N_LT30')
        if r['brier_gain_ci95'][0] <= 0: report['gate_failures'].append(part+':NO_SIGNIFICANT_PRIOR_GAIN')
        if r['logloss'] > base['logloss']: report['gate_failures'].append(part+':LOGLOSS_WORSE')
        if r['calibration']['macro_ece'] > .07: report['gate_failures'].append(part+':CALIBRATION')
        if selected != 'PRICE' and r['gain_vs_price_ci95'][0] <= 0:
            report['gate_failures'].append(part+':NO_INCREMENTAL_PRICE_GAIN')
    monthly = []
    for month in sorted(set(s[:7] for s in days)):
        mask = np.array([s.startswith(month) for s in days])
        for name, p in probabilities.items():
            r = metrics(p[mask], y[mask]); r.pop('calibration')
            monthly.append(dict(month=month, model=name, **r))
    for era, left, right in [('2025H1', '2025-01-01', '2025-06-30'),
                             ('2025H2', '2025-07-01', '2025-12-31'),
                             ('2026JAN_OCT', '2026-01-01', '2026-10-31')]:
        mask = (days >= left) & (days <= right)
        gain = float((losses(probabilities['PRIOR'][mask], y[mask])[0]-losses(probabilities[selected][mask], y[mask])[0]).mean())
        report['eras'][era] = dict(cycles=int(mask.sum()), brier_gain_vs_prior=gain)
        if gain <= 0: report['gate_failures'].append(era+':NONPOSITIVE_GAIN')
    positive_months = 0; test_months = sorted(set(s[:7] for s in days[test]))
    for month in test_months:
        rows = {r['model']: r for r in monthly if r['month'] == month}
        positive_months += rows[selected]['brier'] < rows['PRIOR']['brier']
    report['positive_test_months'] = int(positive_months); report['test_months'] = len(test_months)
    if positive_months < .6*len(test_months): report['gate_failures'].append('MONTHLY_STABILITY')
    if not fitted[selected]['converged']: report['gate_failures'].append('OPTIMIZER_NOT_CONVERGED')
    report['historical_gate_passed'] = not report['gate_failures']
    report['monthly'] = monthly
    report['per_minute'] = []
    for name, p in probabilities.items():
        b, l = losses(p[test], y[test])
        for minute in range(60):
            report['per_minute'].append(dict(model=name, minute=minute, cycles=int(test.sum()),
                                              brier=float(b[:, minute].mean()), logloss=float(l[:, minute].mean())))
    report['model_status'] = 'EXPERIMENTAL' if report['historical_gate_passed'] else 'NO VALIDADO'
    (CACHE/'training_results.json').write_text(json.dumps(report, indent=2)+'\n')
    np.savez_compressed(CACHE/'predictions.npz', days=days, y=y, **probabilities)
    print(json.dumps(dict(selected=selected, historical_gate=report['historical_gate_passed'], failures=report['gate_failures'])))


if __name__ == '__main__':
    main()
