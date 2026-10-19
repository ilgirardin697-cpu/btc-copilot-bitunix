"""One manual public-data calculation in a killable, credential-free child."""
import copy
import json
import sys
import time
from .frozen import core
from .frozen.constants import HOUR
from .confirmed import read_current
from .public import fetch_closed
from .transport import OFFICIAL_URL, validate_market_url


def calculate(request, now_ms=None, transport=None):
    now = int(time.time() * 1000) if now_ms is None else now_ms
    required = {'mlrsi_state_path', 'public_cache'}
    if (not isinstance(request, dict) or not required <= set(request)
            or set(request) - required - {'market_data_url'}):
        raise ValueError('INVALID_MANUAL_REQUEST')
    market_url = validate_market_url(request.get('market_data_url', OFFICIAL_URL))
    cached = request['public_cache']
    if cached is None:
        data = core.prepare(fetch_closed(now, transport, url=market_url), now)
        public = core.snapshot(data, len(data['times']) - 1)
    else:
        public = copy.deepcopy(cached)
    current = int(time.time() * 1000) if now_ms is None else now_ms
    if (public['timestamp'] != current // HOUR * HOUR or public['venue'] != 'BINANCE_USDM_PERPETUAL'
            or public['version'] != core.VERSION):
        raise ValueError('PUBLIC_CONTEXT_NOT_CURRENT')
    ml, display = read_current(request['mlrsi_state_path'], current)
    snapshot = copy.deepcopy(public)
    snapshot.update(core.decide(public['components'], public['structure'], ml))
    snapshot.update(confirmed_mlrsi=ml, display_mlrsi=display)
    return dict(ok=True, snapshot=snapshot, public_cache=public)


def main():
    try:
        raw = sys.stdin.read(200001)
        if len(raw) > 200000:
            raise ValueError
        result = calculate(json.loads(raw))
        print(json.dumps(result, allow_nan=False, separators=(',', ':')))
    except Exception:
        print('{"ok":false}')  # never emit API payloads, paths, exceptions or credentials


if __name__ == '__main__':
    main()
