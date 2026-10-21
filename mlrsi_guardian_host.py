"""Non-blocking passive host. Public data and outbound text only, no guard client.

The command layer receives only StatusCache.read, never this host or observer.
Heavy imports, disk recovery, calculations and downloads run outside Guardian.
"""
import copy
import os
from pathlib import Path
import threading

UNAVAILABLE = ('🧠 ML RSI MTF STATUS\nBTCUSDT\n15m ⚫ UNKNOWN\n1H ⚫ UNKNOWN\n4H ⚫ UNKNOWN'
               '\nObserver: OFF / no disponible\n👀 SHADOW ONLY\n🚫 TRADE AUTHORITY: NONE')


def plain_text(text):
    # Guardian sends plain text. Preserve the validated renderer without literal HTML.
    return text.replace('<b>', '').replace('</b>', '')


def storage_directory(environ=None):
    env = os.environ if environ is None else environ
    explicit = str(env.get('MLRSI_STATE_DIR', '')).strip()
    volume = str(env.get('RAILWAY_VOLUME_MOUNT_PATH', '')).strip()
    if explicit:
        target = Path(explicit)
    elif volume:
        target = Path(volume) / 'mlrsi'
    elif Path('/data').is_dir():
        target = Path('/data/mlrsi')
    else:
        target = Path('mlrsi_observations')
    resolved = target.resolve()
    # Configuration may not place observational files in another module's namespace.
    for key, default in (('GUARDIAN_STATE_DIR', '/data/guardian'),
                         ('COPILOT_AUDIT_STATE_DIR', '/data/copilot_audit'),
                         ('EARLY_BREAKOUT_STATE_DIR', '/data/early_breakout')):
        other = Path(env.get(key) or default).resolve()
        if resolved == other or other in resolved.parents:
            raise ValueError('MLRSI_STATE_DIR_NOT_SEPARATE')
    if resolved == Path.cwd().resolve() or resolved == Path('/data').resolve() or (volume and resolved == Path(volume).resolve()):
        raise ValueError('MLRSI_STATE_DIR_NOT_SEPARATE')
    return target


class StatusCache:
    """Contains only copied text and enabled flag; no observer/Guardian reference."""
    def __init__(self):
        self._lock = threading.Lock()
        self._value = dict(text=UNAVAILABLE, enabled=False)

    def publish(self, text, enabled):
        with self._lock:
            self._value = dict(text=plain_text(text), enabled=enabled is True)

    def read(self):
        with self._lock:
            return copy.deepcopy(self._value)


class MLRSIHost:
    """Only a directory, outbound send callback and static logger are accepted."""
    def __init__(self, storage_dir=None, *, send=None, logger=print):
        # No filesystem/import/recovery in the capital-protection caller.
        self.folder = Path(storage_dir) if storage_dir is not None else None
        self._send, self._logger = send, logger
        self.status_cache = StatusCache()
        self._stop = threading.Event()
        self._thread = None
        self._observer = None

    def _log(self, code):
        try:
            self._logger(code)
        except Exception:
            pass

    def _send_text(self, text):
        return self._send(plain_text(text)) if self._send is not None else False

    def start(self):
        if self._thread is not None or self._stop.is_set():
            return
        self._thread = threading.Thread(target=self._run, name='guardian-mlrsi-host', daemon=True)
        self._thread.start()  # main catches a thread-start failure; never joins

    def stop(self):
        self._stop.set()
        self._stop_observer()

    def _stop_observer(self):
        try:
            if self._observer is not None:
                self._observer.stop()
        except Exception:
            self._log('MLRSI_STOP_FAILED_IGNORED')

    def _run(self):
        try:
            env = dict(os.environ)
            if self.folder is not None:
                env['MLRSI_STATE_DIR'] = str(self.folder)
            self.folder = storage_directory(env)
            from mlrsi_observer import MLRSIObserver
            self._observer = MLRSIObserver(self.folder, send=self._send_text, logger=self._log)
            if self._stop.is_set():
                return
            self._observer.start()
            while not self._stop.is_set():
                try:
                    self.status_cache.publish(self._observer.status_text(), self._observer.config.enabled)
                except Exception:
                    self.status_cache.publish(UNAVAILABLE, False)
                    self._log('MLRSI_STATUS_FAILED_IGNORED')
                self._stop.wait(1)  # cache publisher, not a Telegram consumer or risk loop
        except Exception:
            self.status_cache.publish(UNAVAILABLE, False)
            self._log('MLRSI_HOST_FAILED_IGNORED')
        finally:
            self._stop_observer()
