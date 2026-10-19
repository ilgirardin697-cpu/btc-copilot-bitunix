"""Exact, non-secret transport selection; no configurable upstream hosts."""

OFFICIAL_URL = 'https://fapi.binance.com/fapi/v1/klines'
PRIVATE_URL = 'http://bitman-market-data.railway.internal:8080/fapi/v1/klines'
MARKET_DATA_ENV = 'BITMAN_MARKET_DATA_URL'


def validate_market_url(value):
    if not isinstance(value, str) or value not in (OFFICIAL_URL, PRIVATE_URL):
        raise ValueError('INVALID_MARKET_DATA_URL')
    return value
