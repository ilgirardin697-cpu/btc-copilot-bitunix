"""Source-schema adapter only; unchanged mathematical cashflow calculation."""
import json
from ..market import Receipt,funding as previous_funding
from ..journal import canonical

def funding(receipt):
    rows=receipt.validate('FUNDING')
    # Current official public documentation adds optional rateType. Preserve the
    # original bytes in the ledger. Only Regular applies to this BTC study;
    # never reinterpret Special/dividend cashflows as ordinary funding.
    for row in rows:
        if isinstance(row,dict) and row.get('rateType','Regular')!='Regular':raise ValueError('UNSUPPORTED_FUNDING_RATE_TYPE')
    projected=[{k:v for k,v in row.items() if k!='rateType'} if isinstance(row,dict) else row for row in rows]
    view=Receipt(canonical(projected),receipt.url,dict(receipt.query),receipt.request_started_ms,
                 receipt.received_at_ms,receipt.exchange_time_ms,receipt.status)
    return previous_funding(view)
