"""Slow, independent test oracle for the specified three-centroid Pine contract.

No production imports, numpy or network. NOT an authenticated BackQuant source
translation: the accessible attributed copy has leading-NA constructor defects.
The explicit empty-cluster fail-safe matches the observer, not Pine color NA.
"""
import math


def reference_percentile(values, p):
    ordered = sorted(x for x in values if x is not None)
    if not ordered:
        return None
    index = (len(ordered) - 1) * p / 100.0
    lower, upper = int(math.floor(index)), int(math.ceil(index))
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def reference_clusters(samples, max_iter=1000):
    centers = [reference_percentile(samples, p) for p in (25, 50, 75)]
    data = [x for x in samples if x is not None]
    if not data:
        return centers, 0, False
    for attempt in range(max_iter + 1):  # Pine inclusive for bound
        groups = [[], [], []]
        for value in data:
            distances = [abs(value - center) for center in centers]
            index = distances.index(min(distances))
            groups[index].append(value)
        updated = [sum(group) / len(group) if group else None for group in groups]
        if any(value is None for value in updated):
            return updated, attempt + 1, False  # explicit pathological fail-safe
        if updated == centers:
            return updated, attempt + 1, True
        centers = updated
    return centers, max_iter + 1, False


def pine_reference_mlrsi(lows, last_bar_index=0, max_data=3000, max_iter=1000):
    """Every historical bar sees the supplied fixed last index; realtime grows.

    Processes all LOWs for RSI seed regardless of the array's inclusion gate.
    Supply last_bar_index=len(available_candles)-1, INCLUDING an open bar.
    Calling with more samples past that anchor models confirmed realtime bars.
    """
    gains, losses, rsi_values, output = [], [], [], []
    previous = up = down = smooth = None
    for index, low in enumerate(lows):
        raw = None
        if previous is not None:
            gains.append(max(low - previous, 0.0))
            losses.append(max(previous - low, 0.0))
            if len(gains) == 29:
                up, down = sum(gains) / 29, sum(losses) / 29
            elif len(gains) > 29:
                up = (1.0 / 29) * gains[-1] + (1.0 - 1.0 / 29) * up
                down = (1.0 / 29) * losses[-1] + (1.0 - 1.0 / 29) * down
            if up is not None and up + down:
                raw = 100.0 if down == 0 else 100.0 - 100.0 / (1.0 + up / down)
        previous = low
        if raw is not None:
            smooth = raw if smooth is None else 0.4 * raw + 0.6 * smooth
        if max(last_bar_index, index) - index <= max_data:
            rsi_values.append(smooth if raw is not None else None)
        centers, iterations, converged = [None, None, None], 0, False
        if raw is not None and len(rsi_values) > 3:
            centers, iterations, converged = reference_clusters(rsi_values, max_iter)
        valid = all(c is not None and math.isfinite(c) for c in centers)
        color = ('GREEN' if smooth > centers[2] else 'RED' if smooth < centers[0] else 'NEUTRAL') if valid else 'UNKNOWN'
        output.append(dict(mlrsi_raw=raw, mlrsi_smoothed=smooth if raw is not None else None,
                           lower_threshold=centers[0], middle_centroid=centers[1], upper_threshold=centers[2],
                           threshold_sample_count=len(rsi_values), window_count=len(rsi_values),
                           valid=valid, color=color, converged=converged, iterations=iterations))
    return output
