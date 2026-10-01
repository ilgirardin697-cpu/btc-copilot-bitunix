"""Shared process exclusion for V8 worker and the V7 entry endpoint."""
from functools import wraps
import os
from pathlib import Path


def lock_directory():
    return Path(os.getenv("V8_EXECUTION_LOCK_DIR", os.getenv("RAILWAY_VOLUME_MOUNT_PATH", ".")))


class ExecutionLease:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else lock_directory()
        self.stream = None

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        stream = (self.directory / "igod_execution.lock").open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                if stream.seek(0, 2) == 0:
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            raise RuntimeError("Execution locked: V8/V7 worker already active") from None
        self.stream = stream
        return self

    @property
    def held(self):
        return self.stream is not None and not self.stream.closed

    def __exit__(self, *args):
        if self.held:
            if os.name == "nt":
                import msvcrt
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
            self.stream.close()


def v7_entry_guard(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        if os.getenv("V8_LIVE_EXECUTION", "false").lower() == "true":
            raise RuntimeError("V7 entry disabled while V8 REAL is selected")
        # Held through the HTTP call: V8 cannot start while a V7 entry is in flight.
        with ExecutionLease():
            return function(*args, **kwargs)
    return guarded


def v7_mutation_guard(function):
    @wraps(function)
    def guarded(self, method, *args, **kwargs):
        if method == "GET":
            return function(self, method, *args, **kwargs)
        return v7_entry_guard(function)(self, method, *args, **kwargs)
    return guarded
