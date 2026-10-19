"""Lazy manual request host. No poller, sender, account client or auto work."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from .render import render, unavailable
from .transport import MARKET_DATA_ENV, OFFICIAL_URL, validate_market_url

TIMEOUT_SECONDS = 25
CACHE_SECONDS = 30
ROOT = Path(__file__).resolve().parents[1]


def state_path():
    from mlrsi_guardian_host import storage_directory
    return storage_directory() / 'igod_mlrsi_state.json'


class BitmanHost:
    shadow_only = True
    trade_authority = False

    def __init__(self, *, resolve_state=state_path, clock=time.monotonic, wall=time.time):
        self._resolve_state, self._clock, self._wall = resolve_state, clock, wall
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self._busy = False
        self._process = None
        self._cache = None
        self._cache_at = 0

    def request(self, reply):
        with self._lock:
            if self._closed.is_set():
                return False
            if self._busy:
                busy = True
            else:
                busy = False
                self._busy = True
        if busy:
            return bool(reply(unavailable()))
        try:
            threading.Thread(target=self._run, args=(reply,), daemon=True, name='bitman-manual-request').start()
            return True
        except Exception:
            with self._lock:
                self._busy = False
            return bool(reply(unavailable()))

    def _run(self, reply):
        text = unavailable()
        process = None
        try:
            now = self._clock()
            with self._lock:
                cached = copy.deepcopy(self._cache) if (self._cache is not None and 0 <= now - self._cache_at < CACHE_SECONDS
                    and self._cache['timestamp'] == int(self._wall()) // 3600 * 3600000) else None
            market_url = validate_market_url(os.environ.get(MARKET_DATA_ENV, OFFICIAL_URL))
            request = dict(mlrsi_state_path=str(self._resolve_state()), public_cache=cached, market_data_url=market_url)
            # The child inherits only runtime/OS paths, never the parent's credentials.
            env = {key: os.environ[key] for key in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP') if key in os.environ}
            env.update(PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            with self._lock:
                if self._closed.is_set():
                    return
                process = subprocess.Popen([sys.executable, '-m', 'bitman_manual.worker'], cwd=ROOT, env=env,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
                    creationflags=flags)
                self._process = process
            output, _ = process.communicate(json.dumps(request, allow_nan=False), timeout=TIMEOUT_SECONDS)
            if process.returncode != 0 or len(output) > 200000:
                raise ValueError
            result = json.loads(output)
            if result.get('ok') is not True:
                raise ValueError
            snapshot = result['snapshot']
            if (snapshot.get('shadow_only') is not True or snapshot.get('trade_authority') is not False
                    or snapshot.get('not_trade_signal') is not True or snapshot.get('symbol') != 'BTCUSDT'
                    or set(snapshot.get('components', {})) != {'1H', '4H', '1D'}):
                raise ValueError
            candidate = render(result['snapshot'])
            if candidate == unavailable() or not isinstance(result['public_cache'], dict):
                raise ValueError
            text = candidate
            with self._lock:
                self._cache = copy.deepcopy(result['public_cache'])
                self._cache_at = self._clock()
        except Exception:
            if process is not None and process.poll() is None:
                try:
                    process.kill()
                    process.communicate(timeout=2)
                except Exception:
                    pass
        finally:
            with self._lock:
                self._busy = False
                self._process = None
            if not self._closed.is_set():
                try:
                    reply(text)  # exactly one response to this authorized manual request
                except Exception:
                    pass

    def stop(self):
        self._closed.set()
        with self._lock:
            process = self._process
        if process is not None and process.poll() is None:
            try:
                process.kill()
            except Exception:
                pass
