"""Separate process, separate storage, no production service integration."""
import json
import os
from pathlib import Path
import time

from guardian_signals import atr14
from .engine import Engine
from .journal import Journal, JournalError
from .market import DataError, PublicMarket, STEPS, digest
from .report import build, publish
from .signals import columns, confirmed_context


def environment_guard(environment):
    # This process must be launched without trading/account/messaging secrets.
    if any(value and any(word in name.upper() for word in ('BITUNIX', 'TELEGRAM', 'API_KEY', 'SECRET', 'ACCESS_TOKEN', 'PRIVATE_KEY', 'LIVE_EXECUTION'))
           for name, value in environment.items()):
        raise RuntimeError('PAPER_FORBIDDEN_ENVIRONMENT')


class Service:
    def __init__(self, directory, market=None, clock=time.time):
        directory = Path(directory).resolve()
        if directory == Path('/data').resolve() or Path('/data').resolve() in directory.parents:
            raise RuntimeError('PAPER_PRODUCTION_STORAGE_DENIED')
        self.directory, self.clock = directory, clock
        self.market = market or PublicMarket(clock=clock)
        self.journal = Journal(directory)
        self.engine = Engine(self.journal, int(clock() * 1000))
        self.status, self.error = 'STARTING', None

    def cycle(self):
        try:
            now = int(self.clock() * 1000)
            end = (now - 3000) // STEPS['5m'] * STEPS['5m']
            start = self.engine.state['last_bar'] + STEPS['5m']
            if start < end:
                bars = self.market.candles('5m', start, end)
                for row in bars:
                    pending = self.engine.state['pending']
                    needs_funding = self.engine.state['position'] or (pending and pending['entry_open'] <= row[0])
                    funding = self.market.funding(row[0], row[0] + STEPS['5m']) if needs_funding else []
                    self.engine.process_bar(row, funding, int(self.clock() * 1000))
            current = int(self.clock() * 1000)
            cutoff = (current - 3000) // 900_000 * 900_000
            if self.engine.state['last_signal'] is None or cutoff > self.engine.state['last_signal']:
                context = confirmed_context(self.market, cutoff)
                atr_rows = self.market.history('5m', 220, cutoff)
                atr = atr14(columns(atr_rows))
                context.update(atr_input_sha256=digest(atr_rows), paper_stop_atr_timeframe='5m')
                self.engine.observe(context, atr, int(self.clock() * 1000))
            self.status, self.error = 'HEALTHY', None
        except JournalError:
            self.status, self.error = 'HALTED', 'PAPER_JOURNAL_OR_STORAGE_INVALID'
            raise
        except (DataError, ValueError, TypeError, OSError, RuntimeError) as error:
            self.status = 'DEGRADED'
            self.error = str(error) if str(error).replace('_', '').isalnum() and len(str(error)) <= 80 and str(error).upper() == str(error) else 'PAPER_PUBLIC_DATA_UNAVAILABLE'
        except Exception:
            self.status, self.error = 'DEGRADED', 'PAPER_PUBLIC_DATA_UNAVAILABLE'
        report = build(self.journal, self.status, self.error, int(self.clock() * 1000))
        publish(self.directory, report)
        print('IGOD_PAPER_STATUS=' + json.dumps({k: report[k] for k in (
            'status', 'error_code', 'started_at', 'last_closed_bar', 'closed_trades', 'wins', 'losses',
            'realized_equity', 'equity_after_estimated_exit_cost', 'max_marked_drawdown_pct',
            'fees', 'funding_paid_net', 'journal_records')}, separators=(',', ':')), flush=True)
        return report
