"""Public-data research only. No credentials, private API, orders or executor imports.

Run: python -m research.v8_bear_backtest --download --as-of 2026-10-01T14:02:56+00:00
Then offline: python -m research.v8_bear_backtest
Requires the repository's existing numpy and requests dependencies.
"""
from __future__ import annotations

import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import time
from urllib.parse import urlparse
import zipfile

import numpy as np
import requests

ROOT = Path(__file__).resolve().parent
H4 = 14_400_000
DAY = 6 * H4
YEAR_BARS = 365.25 * 6
COST = 0.001
TRAIN_END = int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
START = int(datetime(2018, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
PERP_START = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
ALLOWED = {"data.binance.vision": None,
           "data-api.binance.vision": {"/api/v3/klines"},
           "fapi.binance.com": {"/fapi/v1/klines", "/fapi/v1/fundingRate"},
           "api.exchange.coinbase.com": {"/products/BTC-USD/candles"}}


def public_get(url, params=None):
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED or
            (ALLOWED[parsed.hostname] is not None and parsed.path not in ALLOWED[parsed.hostname]) or
            (parsed.hostname == "data.binance.vision" and not parsed.path.startswith("/data/"))):
        raise ValueError("Only allowlisted public market-data endpoints are permitted")
    for attempt in range(3):
        response = requests.get(url, params=params, timeout=25)
        if response.status_code not in (429, 500, 502, 503, 504):
            break
        time.sleep(1 + attempt)
    return response


def timestamp_ms(value):
    timestamp = int(value)
    return timestamp // 1000 if timestamp > 100_000_000_000_000 else timestamp


def months(first, as_of):
    current = datetime.fromisoformat(first).replace(tzinfo=timezone.utc)
    end = datetime.fromtimestamp(as_of / 1000, timezone.utc)
    while (current.year, current.month) <= (end.year, end.month):
        following = datetime(current.year + (current.month == 12), current.month % 12 + 1, 1,
                             tzinfo=timezone.utc)
        yield current.strftime("%Y-%m"), int(current.timestamp() * 1000), int(following.timestamp() * 1000)
        current = following


def fetch_month(kind, month, start, end, as_of):
    """Checksum-verified ZIP when published; otherwise public REST for that month."""
    cache = ROOT / "cache"
    cache.mkdir(exist_ok=True)
    local = cache / f"{kind}-{month}.zip"
    if kind == "spot":
        prefix = "spot/monthly/klines/BTCUSDT/4h/BTCUSDT-4h"
        rest = "https://data-api.binance.vision/api/v3/klines"
    elif kind == "perp":
        prefix = "futures/um/monthly/klines/BTCUSDT/4h/BTCUSDT-4h"
        rest = "https://fapi.binance.com/fapi/v1/klines"
    else:
        prefix = "futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate"
        rest = "https://fapi.binance.com/fapi/v1/fundingRate"
    url = f"https://data.binance.vision/data/{prefix}-{month}.zip"
    if local.exists():
        blob = local.read_bytes()
    else:
        response = public_get(url)
        if response.status_code == 200:
            blob = response.content
            local.write_bytes(blob)
        elif response.status_code == 404:
            blob = None
        else:
            response.raise_for_status()
    if blob is not None:
        checksum_path = local.with_suffix(".checksum")
        if checksum_path.exists():
            checksum = checksum_path.read_text().split()[0]
        else:
            response = public_get(url + ".CHECKSUM")
            response.raise_for_status()
            checksum = response.text.split()[0]
            checksum_path.write_text(response.text)
        digest = hashlib.sha256(blob).hexdigest()
        if checksum != digest:
            raise ValueError(f"Checksum mismatch: {url}")
        archive = zipfile.ZipFile(io.BytesIO(blob))
        rows = list(csv.reader(io.StringIO(archive.read(archive.namelist()[0]).decode())))
        if rows and not rows[0][0].isdigit():
            rows = rows[1:]
        manifest = {"kind": kind, "month": month, "url": url, "sha256": digest,
                    "official_checksum_verified": True, "rows": len(rows)}
    else:
        params = {"symbol": "BTCUSDT", "startTime": start, "endTime": min(end - 1, as_of - 1), "limit": 1000}
        if kind != "funding":
            params["interval"] = "4h"
        cache_json = cache / f"{kind}-{month}-{as_of}.json"
        if cache_json.exists():
            data = json.loads(cache_json.read_text())
        else:
            response = public_get(rest, params)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list) or len(data) >= 1000:
                raise ValueError("Unexpected/truncated public REST data")
            cache_json.write_text(json.dumps(data))
        if kind == "funding":
            rows = [[r["fundingTime"], 8, r["fundingRate"]] for r in data]
        else:
            rows = data
        manifest = {"kind": kind, "month": month, "url": rest, "params": params,
                    "sha256": hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest(),
                    "official_checksum_verified": False, "rows": len(rows)}
    return rows, manifest


def validate_bars(rows, as_of):
    unique = {}
    for row in rows:
        timestamp = timestamp_ms(row[0])
        close_time = timestamp_ms(row[6])
        if close_time >= as_of or timestamp + H4 > as_of:
            continue
        bar = (timestamp, *map(float, row[1:6]))
        if timestamp % H4 or close_time != timestamp + H4 - 1:
            raise ValueError("Not a completely closed UTC 4H candle")
        _, opened, high, low, close, volume = bar
        if (not all(math.isfinite(v) for v in bar[1:]) or min(opened, high, low, close) <= 0 or
                low > min(opened, close) or high < max(opened, close) or volume < 0):
            raise ValueError("Invalid OHLCV candle")
        if timestamp in unique and unique[timestamp] != bar:
            raise ValueError("Conflicting duplicate candle")
        unique[timestamp] = bar
    ordered = [unique[k] for k in sorted(unique)]
    times = np.array([r[0] for r in ordered], dtype=np.int64)
    if len(times) < 1000:
        raise ValueError("Insufficient history")
    gaps = [(int(a), int(b)) for a, b in zip(times[:-1], times[1:]) if b - a != H4]
    if gaps:
        raise ValueError(f"Missing 4H data, cannot silently impute: {gaps[:10]}")
    return np.array(ordered, dtype=float)


def write_gzip(path, text):
    with path.open("wb") as stream, gzip.GzipFile(fileobj=stream, mode="wb", mtime=0) as compressed:
        compressed.write(text.encode())


def coinbase_history(as_of):
    start = int(datetime(2017, 8, 1, tzinfo=timezone.utc).timestamp() * 1000)
    hour = H4 // 4
    end = as_of // hour * hour
    ranges = [(begin, min(begin + 288 * hour, end)) for begin in range(start, end, 288 * hour)]
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
    def fetch(bounds):
        begin, finish = bounds
        params = {"start": datetime.fromtimestamp(begin / 1000, timezone.utc).isoformat(),
                  "end": datetime.fromtimestamp(finish / 1000, timezone.utc).isoformat(), "granularity": 3600}
        path = ROOT / "cache" / f"coinbase-{begin}-{finish}.json"
        if path.exists():
            rows = json.loads(path.read_text())
        else:
            response = public_get(url, params)
            response.raise_for_status()
            rows = response.json()
            path.write_text(json.dumps(rows))
        if not isinstance(rows, list) or len(rows) > 300:
            raise ValueError("Unexpected Coinbase response")
        selected = [r for r in rows if begin <= int(r[0]) * 1000 < finish]
        return selected, {"kind": "coinbase", "url": url, "params": params, "rows": len(selected),
                          "sha256": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()}
    hours, manifest = {}, []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for count, (rows, provenance) in enumerate(pool.map(fetch, ranges), 1):
            manifest.append(provenance)
            for row in rows:
                timestamp = int(row[0]) * 1000
                if timestamp in hours and hours[timestamp] != row:
                    raise ValueError("Conflicting Coinbase hour")
                hours[timestamp] = row
            if count % 40 == 0:
                print(f"Coinbase public downloads {count}/{len(ranges)}", flush=True)
    bars = []
    missing = [t for t in range(start, end, hour) if t not in hours]
    if missing:
        dates = [datetime.fromtimestamp(t / 1000, timezone.utc).isoformat() for t in missing]
        raise ValueError(f"Coinbase missing {len(missing)} hourly candles; first={dates[:5]}, last={dates[-5:]}")
    for timestamp in range(start, as_of // H4 * H4, H4):
        bucket = [hours.get(timestamp + i * hour) for i in range(4)]
        if any(row is None for row in bucket):
            raise ValueError(f"Missing Coinbase hour in 4H bucket {timestamp}")
        bars.append([timestamp, bucket[0][3], max(r[2] for r in bucket), min(r[1] for r in bucket),
                     bucket[-1][4], sum(r[5] for r in bucket), timestamp + H4 - 1])
    return validate_bars(bars, as_of), manifest


def download(as_of):
    jobs = [(kind, month, start, end, as_of) for kind, first in (
        ("spot", "2017-08-01"), ("perp", "2019-09-01"), ("funding", "2020-01-01"))
            for month, start, end in months(first, as_of)]
    grouped = {kind: [] for kind in ("spot", "perp", "funding")}
    manifest = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for count, (rows, provenance) in enumerate(pool.map(lambda args: fetch_month(*args), jobs), 1):
            grouped[provenance["kind"]].extend(rows)
            manifest.append(provenance)
            if count % 30 == 0:
                print(f"Public downloads {count}/{len(jobs)}", flush=True)
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    audit = {}
    source = "Binance BTCUSDT spot"
    try:
        primary = validate_bars(grouped["spot"], as_of)
    except ValueError as exc:
        audit["binance_spot_rejected"] = str(exc)
        audit["binance_spot_nonstandard_close_times"] = sum(
            timestamp_ms(r[6]) != timestamp_ms(r[0]) + H4 - 1 for r in grouped["spot"])
        spot_times = sorted(set(timestamp_ms(r[0]) for r in grouped["spot"]))
        audit["binance_spot_gaps"] = [[a, b] for a, b in zip(spot_times, spot_times[1:]) if b - a != H4]
        print("Binance spot audit failed; checking Coinbase BTCUSD fallback", flush=True)
        try:
            primary, extra = coinbase_history(as_of)
            manifest.extend(extra)
            source = "Coinbase BTCUSD spot (4H aggregated from four complete 1H candles)"
        except ValueError as fallback_error:
            audit["coinbase_rejected"] = str(fallback_error)
            primary = validate_bars(grouped["perp"], as_of)
            source = "Binance BTCUSDT perpetual (minimum 2020-2026; no imputed pre-launch data)"
    for kind in ("spot", "perp"):
        data = primary if kind == "spot" else validate_bars(grouped[kind], as_of)
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(["time", "open", "high", "low", "close", "volume"])
        for row in data:
            writer.writerow([int(row[0]), *row[1:]])
        write_gzip(artifacts / f"{'primary' if kind == 'spot' else kind}_4h.csv.gz", buffer.getvalue())
        print(f"{kind}: {len(data)} closed continuous 4H bars", flush=True)
    funding = {}
    for row in grouped["funding"]:
        timestamp, hours, rate = int(row[0]), int(row[1]), float(row[2])
        if timestamp >= as_of:
            continue
        if hours != 8 or not math.isfinite(rate):
            raise ValueError("Unexpected funding interval/rate")
        # Binance calc_time can be a few milliseconds after settlement. Audit 8H slots.
        slot = round(timestamp / (2 * H4)) * 2 * H4
        if abs(slot - timestamp) > 60_000:
            raise ValueError("Funding settlement timestamp not on an 8H slot")
        if slot in funding and funding[slot] != rate:
            raise ValueError("Conflicting funding records")
        funding[slot] = rate
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["settlement_time", "rate"])
    writer.writerows(sorted(funding.items()))
    write_gzip(artifacts / "funding.csv.gz", buffer.getvalue())
    summary = {"as_of_utc": datetime.fromtimestamp(as_of / 1000, timezone.utc).isoformat(),
               "as_of_ms": as_of, "primary_source": source, "data_audit": audit,
               "downloads": manifest, "funding_records": len(funding),
               "artifacts": {name: hashlib.sha256((artifacts / name).read_bytes()).hexdigest()
                             for name in ("primary_4h.csv.gz", "perp_4h.csv.gz", "funding.csv.gz")}}
    (artifacts / "data_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def sma(values, window):
    result = np.full(len(values), np.nan)
    if len(values) >= window:
        cumulative = np.r_[0.0, np.cumsum(values)]
        result[window - 1:] = (cumulative[window:] - cumulative[:-window]) / window
    return result


def ema(values, window):
    result = np.full(len(values), np.nan)
    if len(values) < window:
        return result
    result[window - 1] = np.mean(values[:window])
    alpha = 2 / (window + 1)
    for i in range(window, len(values)):
        result[i] = alpha * values[i] + (1 - alpha) * result[i - 1]
    return result


def previous_extreme(values, window, minimum):
    """Current candle is explicitly excluded from both Donchian channels."""
    result = np.full(len(values), np.nan)
    queue = deque()
    for i, value in enumerate(values):
        while queue and queue[0] < i - window:
            queue.popleft()
        if i >= window:
            result[i] = values[queue[0]]
        while queue and (values[queue[-1]] >= value if minimum else values[queue[-1]] <= value):
            queue.pop()
        queue.append(i)
    return result


def daily_short(data, window=50):
    times = data[:, 0].astype(np.int64)
    closing = {}
    for timestamp, close in zip(times, data[:, 4]):
        if timestamp % DAY == DAY - H4:
            closing[timestamp // DAY] = close
    days = sorted(closing)
    values = np.array([closing[d] for d in days])
    averages = sma(values, window)
    lookup = {day: bool(values[i] < averages[i]) for i, day in enumerate(days)}
    signals = np.zeros(len(data), dtype=bool)
    for i, timestamp in enumerate(times):
        # Only at the 20:00-24:00 candle close is today's daily close known.
        known_day = (timestamp + H4) // DAY - 1
        signals[i] = lookup.get(known_day, False)
    return signals


def short_signal(data, family, entry=20, exit=10, slope=10, daily=50):
    close = data[:, 4]
    avg = sma(close, 200)
    below = close < avg
    descending = np.zeros(len(close), dtype=bool)
    descending[slope:] = avg[slope:] < avg[:-slope]
    if family == "A":
        return below
    if family == "B":
        return below & descending
    if family in ("C", "D"):
        lower = previous_extreme(data[:, 3], entry, True)
        upper = previous_extreme(data[:, 2], exit, False)
        regime = below & descending if family == "C" else below
        result = np.zeros(len(close), dtype=bool)
        active = False
        for i in range(len(close)):
            # The regime filters entry only. Exit follows the requested channel rule.
            if active and close[i] > upper[i]:
                active = False
            elif not active and regime[i] and close[i] < lower[i]:
                active = True
            result[i] = active
        return result
    if family == "E":
        fast, slow = ema(close, 50), ema(close, 200)
        return (fast < slow) & (close < fast)
    if family == "F":
        result = np.zeros(len(close), dtype=bool)
        result[504:] = close[504:] < close[:-504]
        return result
    if family == "G":
        return daily_short(data, daily)
    raise ValueError("Unknown short family")


def signals(data):
    short = {name: short_signal(data, name, entry=55 if name == "D" else 20,
                                exit=20 if name == "D" else 10) for name in "ABCDEFG"}
    long = data[:, 4] > sma(data[:, 4], 200)
    return long, short


def lag_target(target):
    """Decision at candle t close is applied only at candle t+1 open."""
    return np.r_[0.0, np.asarray(target, dtype=float)[:-1]]


def backtest(data, target, start=START, cost=COST, short_funding_apr=0.0, funding=None):
    if not 0 <= cost < 1 or short_funding_apr < 0:
        raise ValueError("Invalid research costs")
    target = np.asarray(target, dtype=float)
    if len(target) != len(data) or np.any(~np.isfinite(target)) or np.max(np.abs(target)) > 1:
        raise ValueError("Invalid target exposure")
    all_weights = lag_target(target)
    mask = data[:, 0] >= start
    bars = data[mask]
    weights = all_weights[mask]
    # Next open exit includes every inter-bar price gap; final bar marked at its closed close.
    ends = np.r_[bars[1:, 1], bars[-1, 4]]
    asset_returns = ends / bars[:, 1] - 1
    equity = 1.0
    previous = 0.0
    curve, net_returns, turnover, costs, fund_costs = [], [], [], [], []
    trades = []
    active = None
    for i, (bar, weight, asset_return) in enumerate(zip(bars, weights, asset_returns)):
        timestamp = int(bar[0])
        before = equity
        churn = abs(weight - previous)
        charge = before * cost * churn
        # Funding settles BEFORE the same-timestamp order; previous weight owns that payment.
        paid_funding = before * previous * (funding.get(timestamp, 0.0) if funding else 0.0)
        conservative = before * max(-weight, 0.0) * short_funding_apr / YEAR_BARS
        if weight != previous:
            closed_equity = before - before * cost * abs(previous) - paid_funding
            if active is not None:
                active.update(exit_time=timestamp, net_return=closed_equity / active["entry_equity"] - 1,
                              net_pnl=closed_equity - active["entry_equity"], closed=True)
                trades.append(active)
                active = None
            if weight:
                active = {"entry_time": timestamp, "direction": "LONG" if weight > 0 else "SHORT",
                          "exposure": abs(float(weight)), "entry_equity": closed_equity,
                          "entry_price": float(bar[1])}
        equity = (before - charge - paid_funding - conservative) * (1 + weight * asset_return)
        if equity <= 0 or not math.isfinite(equity):
            raise ValueError("Research portfolio insolvency")
        curve.append(equity)
        net_returns.append(equity / before - 1)
        turnover.append(churn)
        costs.append(charge)
        fund_costs.append(paid_funding + conservative)
        previous = weight
    if active is not None:
        active.update(exit_time=int(bars[-1, 0]) + H4, net_return=equity / active["entry_equity"] - 1,
                      net_pnl=equity - active["entry_equity"], closed=False)
        trades.append(active)
    return {"times": bars[:, 0].astype(np.int64), "returns": np.array(net_returns),
            "equity": np.array(curve), "weights": weights, "turnover": np.array(turnover),
            "costs": np.array(costs), "funding_costs": np.array(fund_costs), "trades": trades}


def metrics(run, start=None, end=None):
    mask = np.ones(len(run["times"]), dtype=bool)
    if start is not None:
        mask &= run["times"] >= start
    if end is not None:
        mask &= run["times"] < end
    timestamps = run["times"][mask]
    if not len(timestamps):
        return {}
    returns = run["returns"][mask]
    normalized = np.r_[1.0, np.cumprod(1 + returns)]
    years = (int(timestamps[-1]) + H4 - int(timestamps[0])) / (365.25 * DAY)
    cagr = normalized[-1] ** (1 / years) - 1
    std = np.std(returns, ddof=1)
    sharpe = np.mean(returns) / std * math.sqrt(YEAR_BARS) if std else 0.0
    downside = math.sqrt(np.mean(np.minimum(returns, 0) ** 2))
    sortino = np.mean(returns) / downside * math.sqrt(YEAR_BARS) if downside else None
    drawdown = normalized / np.maximum.accumulate(normalized) - 1
    mdd = float(np.min(drawdown))
    trade_rows = [t for t in run["trades"] if t["closed"] and
                  t["entry_time"] >= int(timestamps[0]) and t["exit_time"] <= int(timestamps[-1]) + H4]
    winners = [t["net_return"] for t in trade_rows if t["net_return"] > 0]
    losers = [t["net_return"] for t in trade_rows if t["net_return"] <= 0]
    profits = sum(t["net_pnl"] for t in trade_rows if t["net_pnl"] > 0)
    losses = -sum(t["net_pnl"] for t in trade_rows if t["net_pnl"] < 0)
    return {"cagr": float(cagr), "total_return": float(normalized[-1] - 1), "sharpe": float(sharpe),
            "sortino": float(sortino) if sortino is not None else None, "max_drawdown": mdd,
            "calmar": float(cagr / abs(mdd)) if mdd else None, "trades": len(trade_rows),
            "win_rate": len(winners) / len(trade_rows) if trade_rows else None,
            "average_winner": float(np.mean(winners)) if winners else None,
            "average_loser": float(np.mean(losers)) if losers else None,
            "profit_factor": profits / losses if losses else None,
            "time_long": float(np.mean(run["weights"][mask] > 0)),
            "time_short": float(np.mean(run["weights"][mask] < 0)),
            "turnover": float(np.sum(run["turnover"][mask])),
            "cost_total_initial_equity": float(np.sum(run["costs"][mask])),
            "funding_net_paid_initial_equity": float(np.sum(run["funding_costs"][mask])),
            "open_trades": sum(not t["closed"] for t in run["trades"]), "years": years}


def portfolios(long, shorts):
    yield "V8_LONG_FLAT", long.astype(float)
    for family, short in shorts.items():
        yield f"SHORT_{family}", -short.astype(float)
        for exposure in (0.25, 0.50, 1.0):
            yield f"COMBO_{family}_{exposure:.2f}", np.where(long, 1.0, np.where(short, -exposure, 0.0))


def analyze(data, start=START, short_funding_apr=0.0, funding=None):
    long, shorts = signals(data)
    runs, rows = {}, []
    for name, target in portfolios(long, shorts):
        run = backtest(data, target, start, short_funding_apr=short_funding_apr, funding=funding)
        runs[name] = run
        row = {"system": name, "full": metrics(run), "train": metrics(run, end=TRAIN_END),
               "test": metrics(run, start=TRAIN_END), "annual": {}}
        for year in range(2018, 2027):
            begin = int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
            end = int(datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
            annual = metrics(run, begin, end)
            row["annual"][str(year)] = annual.get("total_return")
        rows.append(row)
    return rows, runs


def select_train(rows):
    """Frozen rule: 0.25x combo TRAIN Sharpe gain + half Calmar gain. Never sees TEST."""
    lookup = {r["system"]: r for r in rows}
    baseline = lookup["V8_LONG_FLAT"]["train"]
    ranked = []
    for family in "ABCDEFG":
        candidate = lookup[f"COMBO_{family}_0.25"]["train"]
        score = candidate["sharpe"] - baseline["sharpe"] + 0.5 * (candidate["calmar"] - baseline["calmar"])
        ranked.append((score, family))
    return [family for _, family in sorted(ranked, reverse=True)[:2]], ranked


def variants(family):
    if family in ("C", "D"):
        for entry, exit in ((15, 7), (20, 10), (30, 15), (55, 20)):
            yield f"{family}_donchian_{entry}_{exit}", {"entry": entry, "exit": exit}
        if family == "C":
            for slope in (5, 20):
                yield f"{family}_slope_{slope}", {"slope": slope}
    elif family in ("A", "B"):
        # A has no slope parameter: these are declared structural filters, not A retuning.
        for slope in (5, 10, 20):
            yield f"{family}_slope_{slope}", {"family_override": "B", "slope": slope}
    elif family == "G":
        for daily in (40, 50, 60):
            yield f"G_daily_{daily}", {"daily": daily}
    elif family == "F":
        # Keep momentum 504 fixed. Only the explicitly authorized SMA slope filters
        # are examined as structural sensitivity; these are not momentum retuning.
        for slope in (5, 10, 20):
            yield f"F_504_plus_sma_slope_{slope}", {"slope_filter": slope}
    # E has no neighborhood authorized by this request; do not invent an EMA grid.


def robustness(data, candidates, start=START, funding=None):
    long, _ = signals(data)
    result = []
    for family in candidates:
        for name, kwargs in variants(family):
            override = kwargs.pop("family_override", family)
            slope_filter = kwargs.pop("slope_filter", None)
            short = short_signal(data, override, **kwargs)
            if slope_filter is not None:
                average = sma(data[:, 4], 200)
                descending = np.zeros(len(data), dtype=bool)
                descending[slope_filter:] = average[slope_filter:] < average[:-slope_filter]
                short &= descending
            for exposure in (0.25, 0.50, 1.0):
                target = np.where(long, 1.0, np.where(short, -exposure, 0.0))
                run = backtest(data, target, start, funding=funding)
                isolated = backtest(data, -short.astype(float), start, funding=funding)
                result.append({"candidate": family, "variant": name, "short_exposure": exposure,
                               "full": metrics(run), "train": metrics(run, end=TRAIN_END),
                               "test": metrics(run, start=TRAIN_END), "isolated_full": metrics(isolated),
                               "isolated_test": metrics(isolated, start=TRAIN_END)})
    return result


def read_bars(name):
    with gzip.open(ROOT / "artifacts" / f"{name}_4h.csv.gz", "rt") as stream:
        return np.loadtxt(stream, delimiter=",", skiprows=1)


def read_funding(data):
    with gzip.open(ROOT / "artifacts" / "funding.csv.gz", "rt") as stream:
        funding = {int(row[0]): float(row[1]) for row in list(csv.reader(stream))[1:]}
    end = int(data[-1, 0]) + H4
    expected = list(range(PERP_START, end, 2 * H4))
    missing = [timestamp for timestamp in expected if timestamp not in funding]
    return funding, {"expected_settlements": len(expected), "available_settlements": len(expected) - len(missing),
                     "missing_settlements": len(missing), "missing_first": missing[:10]}


def paired_test_bootstrap(runs, candidates, draws=1000):
    """Fixed seven-day moving blocks; conditional uncertainty, not a new holdout."""
    rng = np.random.default_rng(8)
    mask = runs["V8_LONG_FLAT"]["times"] >= TRAIN_END
    baseline = runs["V8_LONG_FLAT"]["returns"][mask]
    block = 42
    result = {}
    for family in candidates:
        candidate = runs[f"COMBO_{family}_0.25"]["returns"][mask]
        excess = np.log1p(candidate) - np.log1p(baseline)
        samples = []
        for _ in range(draws):
            starts = rng.integers(0, len(excess) - block + 1, size=math.ceil(len(excess) / block))
            indices = (starts[:, None] + np.arange(block)[None, :]).ravel()[:len(excess)]
            samples.append(float(np.expm1(np.mean(excess[indices]) * YEAR_BARS)))
        low, high = np.quantile(samples, [0.025, 0.975])
        result[family] = {"annual_relative_growth": float(np.expm1(np.mean(excess) * YEAR_BARS)),
                          "ci95_low": float(low), "ci95_high": float(high),
                          "probability_positive": float(np.mean(np.array(samples) > 0)),
                          "draws": draws, "block_bars": block, "seed": 8}
    return result


def interpretation(bundle):
    """Promotion audit uses original configurations, never the best TEST neighbor."""
    if bundle["metadata"]["as_of_utc"] != "2026-10-01T14:02:56+00:00":
        return ["## Interpretación pendiente", "",
                "Snapshot distinto del revisado el 2026-10-01. Las tablas se recalculan, pero la conclusión "
                "de promoción requiere una nueva revisión humana; no se extrapola automáticamente el rechazo anterior.", ""]
    lookup = {r["system"]: r for r in bundle["principal"]}
    base = lookup["V8_LONG_FLAT"]
    c = lookup["COMBO_C_0.25"]
    isolated = lookup["SHORT_C"]
    f = lookup["COMBO_F_0.25"]
    f_short = lookup["SHORT_F"]
    a = lookup["COMBO_A_0.25"]
    ci = bundle["paired_test_bootstrap"].get("C")
    lines = ["## Conclusión y criterio de promoción", "",
             "**C) REJECT SHORT ENGINE — las reglas A–G actuales no justifican promoción a SHADOW.**", "",
             "No se rechaza la posibilidad de investigar otras hipótesis bajistas; se rechaza promover este conjunto "
             "con la evidencia disponible. La selección TRAIN y los parámetros base se mantienen aunque una variante "
             "haya obtenido más CAGR después de mirar TEST.", "",
             f"Baseline neto de turnover y funding real: CAGR **{pct(base['full']['cagr'])}**, "
             f"Sharpe **{number(base['full']['sharpe'])}**, DD **{pct(base['full']['max_drawdown'])}**. "
             f"Sin funding: CAGR {pct(bundle['primary_no_funding'][0]['full']['cagr'])}. Esto explica por qué no "
             "deben mezclarse simulaciones de precio con resultados de perpetual financiado.", "",
             f"El espejo A a 0.25x reduce CAGR a {pct(a['full']['cagr'])}, Sharpe a {number(a['full']['sharpe'])} "
             f"y DD a {pct(a['full']['max_drawdown'])}; por tanto no aporta una mejora robusta.", "",
             f"C 20/10 con slope 10, combinado 0.25x, es el caso más cercano: CAGR {pct(c['full']['cagr'])}, "
             f"Sharpe {number(c['full']['sharpe'])}, DD {pct(c['full']['max_drawdown'])}. "
             f"SHORT_C aislado solo devuelve {pct(isolated['full']['total_return'])} acumulado y "
             f"{pct(isolated['test']['total_return'])} en TEST. El combinado TEST pasa de CAGR "
             f"{pct(base['test']['cagr'])} a {pct(c['test']['cagr'])}; Sharpe de {number(base['test']['sharpe'])} "
             f"a {number(c['test']['sharpe'])}. Es una ventaja pequeña, no un ganador por CAGR.", ""]
    if ci:
        lines += [f"Bootstrap pareado TEST, 1.000 muestras y bloques fijos de siete días: crecimiento anual relativo "
                  f"C/baseline {pct(ci['annual_relative_growth'])}, IC95% [{pct(ci['ci95_low'])}, "
                  f"{pct(ci['ci95_high'])}]; frecuencia positiva {pct(ci['probability_positive'])}. "
                  "El intervalo incluye cero: no demuestra una contribución robusta. Es un diagnóstico condicional "
                  "sobre el mismo TEST, no otro periodo independiente ni corrección completa por múltiples pruebas.", ""]
    neighbors = [r for r in bundle["robustness"] if r["candidate"] == "C" and r["short_exposure"] == 0.25]
    if neighbors:
        beats = sum(r["test"]["cagr"] > base["test"]["cagr"] for r in neighbors)
        standalone = sum(r["isolated_test"]["total_return"] > 0 for r in neighbors)
        lines += [f"Vecinos C a 0.25x: {beats}/{len(neighbors)} superan el CAGR TEST del baseline; "
                  f"{standalone}/{len(neighbors)} SHORT aislados son positivos en TEST. "
                  "No se escoge retrospectivamente el vecino más favorable.", ""]
    removed = bundle["concentration"]["C"]["combo_without_best_2022_short"]
    lines += [f"Quitando el mejor trade SHORT de 2022 del combinado C, CAGR {pct(removed['cagr'])} y "
              f"Sharpe {number(removed['sharpe'])}, frente a {pct(base['full']['cagr'])} y "
              f"{number(base['full']['sharpe'])} del baseline: la ventaja de CAGR desaparece. "
              f"SHORT_C gana {pct(isolated['annual']['2022'])} en 2022, pero eso no basta para el TEST posterior.", "",
              f"F fue primero en la selección TRAIN conservadora, pero su SHORT aislado pierde "
              f"{pct(f_short['full']['total_return'])} acumulado. El combinado F 0.25x tiene CAGR TEST "
              f"{pct(f['test']['cagr'])} frente a {pct(base['test']['cagr'])}; DD TEST "
              f"{pct(f['test']['max_drawdown'])} frente a {pct(base['test']['max_drawdown'])}. "
              "La reducción de drawdown no demuestra una contribución positiva suficiente para compensar "
              "menor rentabilidad y Sharpe. Los filtros slope son sensibilidad estructural, no validación "
              "de vecinos del momentum 504.", ""]
    stress = {r["system"]: r for r in bundle["primary_short_apr25"]}["COMBO_C_0.25"]
    lines += [f"Con funding adverso ADICIONAL de 25% APR sobre SHORT, C 0.25x queda en CAGR "
              f"{pct(stress['full']['cagr'])} y CAGR TEST {pct(stress['test']['cagr'])}. "
              "La ventaja tampoco es estable ante ese estrés; no se trata de una predicción de funding futuro.", "",
              "Los seis requisitos no se cumplen conjuntamente: standalone/contribución marginal, mejora combinada "
              "pequeña con DD global peor, TEST no concluyente, vecinos débiles y dependencia de una operación "
              "de 2022 para el incremento de CAGR. El requisito de no usar leverage alto sí se cumple: todo <=1x. "
              "No se añade código SHADOW nuevo ni ejecución SHORT, y no se promociona ningún parámetro.", ""]
    return lines


def pct(value):
    return "—" if value is None else f"{100 * value:.2f}%"


def number(value):
    return "—" if value is None else f"{value:.2f}"


def table(rows, split):
    header = "| Sistema | CAGR | Retorno | Sharpe | Sortino | Max DD | Calmar | Trades | Win | Avg win | Avg loss | PF | % LONG | % SHORT | Turnover | Coste / equity inicial |"
    lines = [header, "|" + "---|" * 16]
    # Descriptive ordering; selection was frozen using TRAIN before reading TEST.
    for row in sorted(rows, key=lambda r: r[split]["sharpe"], reverse=True):
        m = row[split]
        values = [row["system"], pct(m["cagr"]), pct(m["total_return"]), number(m["sharpe"]), number(m["sortino"]),
                  pct(m["max_drawdown"]), number(m["calmar"]), str(m["trades"]), pct(m["win_rate"]),
                  pct(m["average_winner"]), pct(m["average_loser"]), number(m["profit_factor"]),
                  pct(m["time_long"]), pct(m["time_short"]), number(m["turnover"]), number(m["cost_total_initial_equity"])]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_report(bundle):
    rows = bundle["principal"]
    selected = bundle["selected_using_train"]
    metadata = bundle["metadata"]
    output = ["# V8 BEAR ENGINE — investigación independiente", "",
              "Solo research/backtest. Sin ejecución, API privada ni cambios V8 REAL/Railway.", "",
              "## Datos y diseño", "",
              f"Snapshot UTC: {metadata['as_of_utc']}. Principal: {metadata['primary_source']}: {metadata['spot_start']} a {metadata['spot_end']}. "
              f"Perpetual: {metadata['perp_start']} a {metadata['perp_end']}. "
              "TRAIN hasta 2022-12-31; TEST desde 2023-01-01. Velas 4H UTC cerradas, sin huecos ni imputación. "
              "Indicadores precalentados con datos anteriores al inicio de evaluación.", "",
              "Se reproduce exactamente la regla de señal del baseline SMA200 LONG/FLAT. No hay una curva ni cifras "
              "del backtest anterior incluidas en main con las que certificar coincidencia numérica. El control sin "
              "funding permite comparar resultados de precio; el principal incorpora financiación real.", "",
              f"Auditoría y fallback: {metadata['data_audit']}. No se inventan velas para ampliar el histórico.", "",
              "Fuente: [Binance public data](https://github.com/binance/binance-public-data), "
              "[klines públicas](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints), "
              "[funding público](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History). "
              "[Coinbase candles públicas](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles). "
              "ZIP comprobados contra SHA256 oficial; REST para meses aún sin publicar. Manifest y snapshots gzip incluidos.", "",
              "Señal al cierre t, aplicación al open t+1. Retorno de open a siguiente open; último periodo se marca al close cerrado. "
              "Coste = 0.001 * abs(cambio de exposición), descontado antes del retorno. Reverse LONG/SHORT paga ambas unidades. "
              "HOLD no paga turnover. Cartera académica con pesos objetivo por periodo; no reproduce fills, borrow, liquidación, "
              "market impact ni costes de rebalanceo por deriva dentro de HOLD. Exposición máxima 1x, sin apalancamiento alto. "
              "La fórmula de pesos difiere ligeramente del sizing financiado de SHADOW: 1-c frente a 1/(1+c) en entrada.", "",
              "Principal: incluye funding real cuando hay cobertura completa del mercado perpetual, como en esta ejecución. "
              "Control: mismas velas sin funding. Sensibilidad adversa: SHORT paga un coste ADICIONAL de 10% y 25% APR "
              "prorrateados sobre su exposición, sin modificar las tasas históricas. LONG paga funding positivo; SHORT lo recibe. "
              "La liquidación de funding en frontera 8H se aplica a la exposición previa a la orden de ese instante.", "",
              f"Cobertura funding perpetual 2020+: {bundle['funding_coverage']}.", "",
              "Sharpe/Sortino sobre retornos 4H, anualización sqrt(365.25*6), libre de riesgo cero. "
              "Max DD al cierre de periodo (no intrabar). Trades cerrados íntegramente dentro de cada segmento para win/PF; "
              "las curvas TRAIN/TEST conservan exposición, no fuerzan cierre en la frontera. Coste acumulado en unidades "
              "de equity inicial, no porcentaje fijo del equity final. Trades abiertos se marcan en equity pero se excluyen de win/PF.", "",
              "C usa slope de 10 velas y Donchian 20/10; D Donchian 55/20. Los canales usan low/high de velas anteriores, "
              "excluyendo la actual. En C/D el régimen filtra la entrada; la salida sigue exclusivamente el canal superior. "
              "G agrega cierres diarios UTC: señal de un día solo disponible tras 24:00 y aplicada al periodo 4H siguiente.", "",
              "## Selección congelada antes de TEST", "",
              f"Dos candidatos elegidos por TRAIN: **{', '.join(selected)}**. Regla fija: mejora de Sharpe + "
              "0.5 * mejora de Calmar del combinado SHORT 0.25x frente al baseline, en TRAIN de precios+turnover SIN créditos funding. "
              "Es una selección conservadora independiente de créditos de financiación. No se usa CAGR máximo ni TEST para escoger parámetros. "
              "Los vecindarios autorizados se muestran completos; ninguna variante sustituye retrospectivamente la configuración base.", "",
              "F conserva siempre momentum 504: no se autorizó un grid de lookbacks momentum. Se muestran únicamente filtros "
              "estructurales adicionales slope SMA200 5/10/20; no se presentan como prueba de vecindad del parámetro 504. "
              "E tampoco recibe parámetros inventados.", "",
              "## Tabla final — principal, histórico completo", "", table(rows, "full"), "",
              "## TRAIN", "", table(rows, "train"), "", "## TEST 2023–2026", "", table(rows, "test"), "",
              "## Años 2021–2026 YTD", "",
              "| Sistema | 2021 | 2022 bear | 2023 | 2024 | 2025 | 2026 YTD |", "|" + "---|" * 7]
    for row in sorted(rows, key=lambda r: r["test"]["sharpe"], reverse=True):
        output.append("| " + " | ".join([row["system"], *[pct(row["annual"].get(str(y))) for y in range(2021, 2027)]]) + " |")
    output += ["", "## Vecindarios pequeños — candidatos TRAIN", "",
               "| Candidato | Variante | SHORT x | CAGR total | Sharpe total | DD total | CAGR TEST | Sharpe TEST | DD TEST | SHORT aislado retorno TEST |",
               "|" + "---|" * 10]
    for row in bundle["robustness"]:
        output.append("| " + " | ".join([row["candidate"], row["variant"], str(row["short_exposure"]),
                      pct(row["full"]["cagr"]), number(row["full"]["sharpe"]), pct(row["full"]["max_drawdown"]),
                      pct(row["test"]["cagr"]), number(row["test"]["sharpe"]), pct(row["test"]["max_drawdown"]),
                      pct(row["isolated_test"]["total_return"])]) + " |")
    output += ["", "## Sensibilidad funding y mercado perpetual", "",
               "| Sistema | CAGR sin fund | Retorno TEST sin fund | CAGR +extra SHORT 10% APR | Retorno TEST +10% | CAGR +extra SHORT 25% APR | Retorno TEST +25% | CAGR perp+fund real | Retorno TEST perp+fund real |",
               "|" + "---|" * 9]
    maps = [{r["system"]: r for r in bundle[key]} for key in ("primary_no_funding", "primary_short_apr10", "primary_short_apr25", "perp_actual_funding")]
    for name in maps[0]:
        values = [name]
        for lookup in maps:
            row = lookup.get(name)
            values += [pct(row["full"]["cagr"]) if row else "N/A", pct(row["test"]["total_return"]) if row else "N/A"]
        output.append("| " + " | ".join(values) + " |")
    output += ["", "## Concentración y contribución SHORT", "",
               "| SHORT | Retorno total aislado | Retorno TEST aislado | 2022 aislado | Mayor trade / ganancias positivas | CAGR combinado 0.25x sin mejor trade SHORT de 2022 |",
               "|" + "---|" * 6]
    for family, row in bundle["concentration"].items():
        output.append("| " + " | ".join([family, pct(row["isolated_return"]), pct(row["isolated_test"]),
                      pct(row["return_2022"]), pct(row["largest_trade_positive_share"]),
                      pct(row["combo_without_best_2022_short"]["cagr"])]) + " |")
    output += ["", *interpretation(bundle)]
    output += ["", "## Reproducibilidad", "", "```sh",
               "python -m research.v8_bear_backtest",
               "python -m unittest discover -s research -p 'test_*.py' -v", "```", "",
               "Resultados íntegros, métricas por segmento/año y sensibilidades en artifacts/results.json y metrics.csv. "
              "Ledger de trades del principal en artifacts/trades.csv.gz. Datos congelados y SHA256 en data_manifest.json. "
               "Los reruns usan snapshots locales; --download consulta exclusivamente endpoints públicos. "
               "La conclusión editorial pertenece exclusivamente al snapshot fechado anterior y exige nueva revisión al actualizar datos."]
    (ROOT / "V8_BEAR_RESULTS.md").write_text("\n".join(output) + "\n", encoding="utf-8")


def study():
    artifacts = ROOT / "artifacts"
    manifest = json.loads((artifacts / "data_manifest.json").read_text())
    for name, digest in manifest["artifacts"].items():
        if hashlib.sha256((artifacts / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Snapshot integrity mismatch: {name}")
    spot, perp = read_bars("primary"), read_bars("perp")
    primary_start = PERP_START if "minimum 2020" in manifest["primary_source"] else START
    main_rows, main_runs = analyze(spot, primary_start)
    selected, ranking = select_train(main_rows)
    funding, coverage = read_funding(perp)
    if coverage["missing_settlements"]:
        funded_rows = []  # never silently replace missing funding with zero
    else:
        funded_rows, funded_runs = analyze(perp, PERP_START, funding=funding)
    principal_funding = funding if funded_rows and "minimum 2020" in manifest["primary_source"] else None
    if principal_funding is not None:
        principal_rows, principal_runs = funded_rows, funded_runs
    else:
        principal_rows, principal_runs = main_rows, main_runs
    stress10, _ = analyze(spot, primary_start, short_funding_apr=0.10, funding=principal_funding)
    stress25, _ = analyze(spot, primary_start, short_funding_apr=0.25, funding=principal_funding)
    concentration = {}
    lookup = {r["system"]: r for r in principal_rows}
    long, short = signals(spot)
    for family in "ABCDEFG":
        trades = principal_runs[f"SHORT_{family}"]["trades"]
        positive_pnl = sum(max(t["net_pnl"], 0) for t in trades if t["closed"])
        largest = max([max(t["net_pnl"], 0) for t in trades if t["closed"]], default=0)
        combo = principal_runs[f"COMBO_{family}_0.25"]
        bear_trades = [t for t in combo["trades"] if t["closed"] and t["direction"] == "SHORT" and
                       datetime.fromtimestamp(t["entry_time"] / 1000, timezone.utc).year == 2022]
        altered = np.where(long, 1.0, np.where(short[family], -0.25, 0.0))
        if bear_trades:
            best = max(bear_trades, key=lambda t: t["net_pnl"])
            # Executed weights derive from previous signal, so remove those signal timestamps.
            cut = (spot[:, 0] >= best["entry_time"] - H4) & (spot[:, 0] < best["exit_time"] - H4)
            altered[cut] = np.where(long[cut], 1.0, 0.0)
        stripped = backtest(spot, altered, primary_start, funding=principal_funding)
        isolated = lookup[f"SHORT_{family}"]
        concentration[family] = {"isolated_return": isolated["full"]["total_return"],
                                 "isolated_test": isolated["test"]["total_return"],
                                 "return_2022": isolated["annual"]["2022"],
                                 "largest_trade_positive_share": largest / positive_pnl if positive_pnl else None,
                                 "combo_without_best_2022_short": metrics(stripped)}
    iso = lambda t: datetime.fromtimestamp(int(t) / 1000, timezone.utc).isoformat()
    bundle = {"metadata": {"as_of_utc": manifest["as_of_utc"], "spot_start": iso(primary_start),
                            "primary_source": manifest["primary_source"], "data_audit": manifest["data_audit"],
                            "spot_end": iso(spot[-1, 0] + H4), "perp_start": iso(PERP_START),
                            "perp_end": iso(perp[-1, 0] + H4)},
              "principal": principal_rows, "primary_no_funding": main_rows,
              "primary_short_apr10": stress10, "primary_short_apr25": stress25,
              "perp_actual_funding": funded_rows, "funding_coverage": coverage,
              "selected_using_train": selected, "train_ranking": sorted(ranking, reverse=True),
              "robustness": robustness(spot, selected, primary_start, principal_funding), "concentration": concentration}
    bundle["paired_test_bootstrap"] = paired_test_bootstrap(principal_runs, selected)
    (artifacts / "results.json").write_text(json.dumps(bundle, indent=2, allow_nan=False), encoding="utf-8")
    with (artifacts / "metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ["scenario", "system", "segment", *main_rows[0]["full"]]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for key in ("principal", "primary_no_funding", "primary_short_apr10", "primary_short_apr25", "perp_actual_funding"):
            for row in bundle[key]:
                for split in ("full", "train", "test"):
                    writer.writerow({"scenario": key, "system": row["system"], "segment": split, **row[split]})
    buffer = io.StringIO()
    fields = ["system", "entry_time", "exit_time", "direction", "exposure", "entry_equity", "entry_price", "net_return", "net_pnl", "closed"]
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for name, run in principal_runs.items():
        for trade in run["trades"]:
            writer.writerow({"system": name, **trade})
    write_gzip(artifacts / "trades.csv.gz", buffer.getvalue())
    write_report(bundle)
    print(json.dumps({"baseline": principal_rows[0], "selected_train": selected,
                      "funding_coverage": coverage, "train_ranking": bundle["train_ranking"]}, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--as-of", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()
    if args.download:
        download(int(datetime.fromisoformat(args.as_of).timestamp() * 1000))
    study()


if __name__ == "__main__":
    main()
