"""The single authorized substitution; original indicators and red EMA retained."""
from research.confluence_1h.indicators import signals

VARIANTS = ('BASE', 'PECECILLOS')


def flags(features, variant):
    if variant not in VARIANTS:
        raise ValueError('ONLY_TWO_PREDECLARED_VARIANTS')
    if variant == 'BASE':
        return signals(features)
    view = dict(features)
    view['kon_trend'] = features['minnows']
    return signals(view)
