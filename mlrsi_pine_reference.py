# Derived from the user-supplied BackQuant Pine source; MPL-2.0, © BackQuant.
"""Independent, literal oracle for the author's supplied Pine v5 source.

No production imports, numpy or network. Preserve constructors' initial NA slots,
persistent VAR centroids, NA comparisons inside IF, and BREAK before assignment.
UNKNOWN during invalid warmup is the observer's explicit display safeguard.
"""
import math


def reference_percentile(values, p):
    ordered = sorted(x for x in values if x is not None)
    if not ordered:
        return None
    index = (len(ordered) - 1) * p / 100.0
    lower, upper = int(math.floor(index)), int(math.ceil(index))
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def reference_arrays_equal(left, right):
    if len(left) != len(right):
        return False
    all_equal = True
    for index in range(len(left)):
        # In Pine v5, NA != value is NA; IF(NA) does not enter its body.
        unequal = None if left[index] is None or right[index] is None else left[index] != right[index]
        if unequal:
            all_equal = False
            break
    return all_equal


def reference_clusters(samples, max_iter=1000, centroids=None):
    centers = [None] * 3 if centroids is None else list(centroids)
    if len(samples) > 3:
        for index, percentile in enumerate((25, 50, 75)):
            centers[index] = reference_percentile(samples, percentile)
    for attempt in range(max_iter + 1):  # Pine inclusive for bound
        groups = [[], [], []]
        for value in samples:
            distances = [None] * 3  # array.new_float(3), not an empty array
            for center in centers:
                distances.append(None if value is None or center is None else abs(value - center))
            finite = [x for x in distances if x is not None]
            smallest = min(finite) if finite else None
            index = distances.index(smallest)  # FIRST matching slot
            if index == 0:
                groups[0].append(value)
            elif index == 1:
                groups[1].append(value)
            else:
                groups[2].append(value)
        updated = [None] * 3
        for group in groups:
            finite = [x for x in group if x is not None]
            updated.append(sum(finite) / len(finite) if finite else None)
        if reference_arrays_equal(updated, centers):
            return centers, attempt + 1, True  # BREAK precedes assignment
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
    centers = [None] * 3  # VAR: persists across historical/realtime candles
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
        centers, iterations, converged = reference_clusters(rsi_values, max_iter, centers)
        valid = raw is not None and len(rsi_values) > 3 and all(c is not None and math.isfinite(c) for c in centers[:3])
        color = ('GREEN' if smooth > centers[2] else 'RED' if smooth < centers[0] else 'NEUTRAL') if valid else 'UNKNOWN'
        output.append(dict(mlrsi_raw=raw, mlrsi_smoothed=smooth if raw is not None else None,
                           lower_threshold=centers[0], middle_centroid=centers[1], upper_threshold=centers[2],
                           threshold_sample_count=len(rsi_values), window_count=len(rsi_values),
                           valid=valid, color=color, converged=converged, iterations=iterations))
    return output
