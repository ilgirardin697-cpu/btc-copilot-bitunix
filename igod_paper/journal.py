"""Append-only, hash chained state commits; no silent repair or truncation."""
import json
import os
from pathlib import Path

from .market import digest


class JournalError(RuntimeError):
    pass


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


class Journal:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = (self.directory / 'paper.lock').open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.lock.seek(0)
                self.lock.write(b'0')
                self.lock.flush()
                self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            raise JournalError('PAPER_ALREADY_RUNNING') from None
        self.path = self.directory / 'paper_v0.jsonl'
        self.records = []
        self.ids = set()
        self.failed = False
        try:
            self._replay()
        except Exception:
            self.close()
            raise

    def _replay(self):
        if not self.path.exists():
            return
        previous = '0' * 64
        try:
            with self.path.open('r', encoding='utf-8') as stream:
                for line in stream:
                    if not line.endswith('\n'):
                        raise ValueError
                    row = json.loads(line)
                    recorded = row.pop('record_hash')
                    if row['previous_hash'] != previous or row['sequence'] != len(self.records) + 1 or row['id'] in self.ids or digest(row) != recorded:
                        raise ValueError
                    if row['type'] not in ('FORWARD_START', 'SIGNAL_OBSERVED', 'CLOSED_BAR_PROCESSED') or type(row['observed_at']) is not int:
                        raise ValueError
                    state = row['state_after']
                    if state['mode'] != 'SHADOW_ONLY' or state['trade_authority'] != 'NONE':
                        raise ValueError
                    if not self.records:
                        if row['type'] != 'FORWARD_START' or row['id'] != 'START':
                            raise ValueError
                    elif row['type'] == 'FORWARD_START':
                        raise ValueError
                    else:
                        prior_bar = self.records[-1]['state_after']['last_bar']
                        if row['type'] == 'CLOSED_BAR_PROCESSED':
                            stamp = row['payload']['candle'][0]
                            if state['last_bar'] != prior_bar + 300_000 or stamp != state['last_bar'] or row['id'] != 'BAR:' + str(stamp) or row['observed_at'] < stamp + 300_000:
                                raise ValueError
                        elif state['last_bar'] != prior_bar or row['id'] != 'SIGNAL:' + str(row['payload']['context']['signal_close']):
                            raise ValueError
                    row['record_hash'] = recorded
                    previous = recorded
                    self.records.append(row)
                    self.ids.add(row['id'])
        except (ValueError, KeyError, TypeError):
            raise JournalError('PAPER_JOURNAL_INVALID') from None

    def append(self, identity, kind, payload, state, observed_at):
        if self.failed:
            raise JournalError('PAPER_STORAGE_UNCERTAIN_RESTART_REQUIRED')
        if identity in self.ids:
            return False
        row = dict(id=identity, type=kind, sequence=len(self.records) + 1,
                   observed_at=observed_at, payload=payload, state_after=state,
                   previous_hash=self.records[-1]['record_hash'] if self.records else '0' * 64)
        row = json.loads(json.dumps(row, allow_nan=False))
        row['record_hash'] = digest(row)
        try:
            with self.path.open('a', encoding='utf-8', newline='\n') as stream:
                stream.write(json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            self.failed = True
            raise JournalError('PAPER_STORAGE_UNCERTAIN_RESTART_REQUIRED') from None
        self.records.append(row)
        self.ids.add(identity)
        # The journal is already authoritative if this derived write fails.
        try:
            atomic_json(self.directory / 'paper_state.json', state)
        except OSError:
            pass
        return True

    def close(self):
        if not self.lock.closed:
            if os.name == 'nt':
                import msvcrt
                self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_UNLCK, 1)
            self.lock.close()
