"""Single-process lock, atomic state, fsync journal; corruption fails closed."""
import json
import os
from pathlib import Path
from guardian_risk import SafetyError


class Store:
    def __init__(self, directory):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = (self.root / 'guardian.lock').open('a+b')
        self._lock.seek(0)
        self._lock.write(b'0')
        self._lock.flush()
        self._lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lock.close()
            raise SafetyError('STORE_ALREADY_LOCKED') from None
        try:
            path = self.root / 'state.json'
            self.state = json.loads(path.read_text('utf-8')) if path.exists() else {}
            if not isinstance(self.state, dict):
                raise ValueError()
            self.actions = self.read('actions')
        except Exception:
            self.close()
            raise SafetyError('STATE_OR_JOURNAL_CORRUPT') from None

    def close(self):
        if not self._lock.closed:
            self._lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_UNLCK, 1)
            self._lock.close()

    def read(self, name):
        path = self.root / (name + '.jsonl')
        if not path.exists():
            return []
        content = path.read_text('utf-8')
        if content and not content.endswith('\n'):
            raise SafetyError('TORN_JOURNAL')
        rows = [json.loads(line) for line in content.splitlines()]
        if any(not isinstance(row, dict) for row in rows):
            raise SafetyError('JOURNAL_INVALID')
        return rows

    def append(self, name, row):
        if name not in ('actions', 'positions', 'bias', 'alerts'):
            raise SafetyError('JOURNAL_NAME_INVALID')
        payload = json.dumps(row, separators=(',', ':'), allow_nan=False)
        with (self.root / (name + '.jsonl')).open('a', encoding='utf-8') as stream:
            stream.write(payload + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        if name == 'actions':
            self.actions.append(row)

    def save(self):
        temp = self.root / 'state.json.tmp'
        with temp.open('w', encoding='utf-8') as stream:
            json.dump(self.state, stream, allow_nan=False, separators=(',', ':'))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, self.root / 'state.json')
        if os.name != 'nt':
            fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def pending(self):
        latest = {}
        for row in self.actions:
            latest[row['key']] = row
        return [row for row in latest.values() if row['status'] != 'CONFIRMED']

    def attempted(self, action, position_id):
        return any(row['action'] == action and row['positionId'] == position_id for row in self.actions)
