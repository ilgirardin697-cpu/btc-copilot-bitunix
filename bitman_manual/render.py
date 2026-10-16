"""Compact adaptation of the frozen research renderer; no transport or decisions."""
from datetime import datetime, timezone
import math

ICONS = {'UP': '🟢', 'DOWN': '🔴', 'TRANSITION': '🟡', 'UNCLEAR': '⚪', 'CONFLICT': '🛑',
         'UNKNOWN': '⚪', 'NEUTRAL': '⚪', 'GREEN': '🟢', 'RED': '🔴'}
FOOTER = ('⚠️ Directional research context — INCONCLUSIVE DIRECTION ENGINE\n'
          'EXACT BITMAN KONKORDE PARITY: NOT PROVEN\n'
          '👀 SHADOW ONLY · MANUAL ONLY · NO AUTO ALERTS\n'
          '🚫 NOT AN ORDER · TRADE AUTHORITY: NONE — NO AUTO TRADE')
KONKORDE = {'KONKORDE_REENTRY': 'REENTRY', 'KONKORDE_EXIT_CONTEXT': 'EXIT CONTEXT',
    'KONKORDE_BULLISH_ENTRY_CONTEXT': 'BULLISH ENTRY CONTEXT',
    'KONKORDE_BULLISH_INSIDE': 'BULLISH INSIDE', 'KONKORDE_BEARISH_CONTEXT': 'BEARISH CONTEXT',
    'KONKORDE_NEUTRAL': 'NEUTRAL'}


def number(value):
    return f'{value:,.2f}' if type(value) in (float, int) and math.isfinite(value) else 'UNKNOWN'


def slope(value):
    if type(value) not in (float, int) or not math.isfinite(value):
        return 'UNKNOWN'
    return 'RISING' if value > 0 else 'FALLING' if value < 0 else 'STABLE'


def unavailable():
    return '⚪ BITMAN: DATA TEMPORARILY UNAVAILABLE\n\n' + FOOTER


def render(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get('state') not in ('UP', 'DOWN', 'TRANSITION', 'UNCLEAR', 'CONFLICT'):
        return unavailable()
    if snapshot.get('strength') not in ('WEAK', 'BUILDING', 'STRONG'):
        return unavailable()
    parts = snapshot.get('components') or {}
    state = snapshot['state']
    lines = ['🧭 BITMAN — BTC DIRECTION', '', ICONS[state] + ' Direction: ' + state,
             '💪 Strength: ' + snapshot['strength'], '']
    for tf, role in (('1D', 'MACRO BIAS'), ('4H', 'SWING BIAS')):
        bias = parts.get(tf, {}).get('bias', 'UNKNOWN')
        bias = bias if bias in ('UP', 'DOWN', 'TRANSITION', 'NEUTRAL') else 'UNKNOWN'
        lines.append(tf + ' ' + ICONS[bias] + ' ' + bias + ' — ' + role)
    timer = snapshot.get('timing_state')
    timing = {'impulse_up': 'UP', 'impulse_down': 'DOWN', 'transition': 'TRANSITION', 'no_impulse': 'UNCLEAR'}.get(timer, 'UNKNOWN')
    if timer == 'pullback':
        timing = snapshot.get('pullback_direction', 'UNKNOWN')
        timing = timing if timing in ('UP', 'DOWN') else 'UNKNOWN'
    lines += ['1H ' + ICONS[timing] + ' ' + timing + ' — IMPULSE / TIMING' + (' (PULLBACK)' if timer == 'pullback' else ''), '']
    ao = []
    for tf in ('1D', '4H', '1H'):
        part = parts.get(tf, {})
        momentum = {'BULLISH_MOMENTUM': 'bullish', 'BEARISH_MOMENTUM': 'bearish', 'MIXED': 'mixed'}.get(part.get('momentum'), 'UNKNOWN')
        ao.append(tf + ' ' + number(part.get('ao')) + ' ' + (momentum if number(part.get('ao')) != 'UNKNOWN' else 'UNKNOWN'))
    swing = parts.get('4H', {})
    di = {'BULLISH': '+DI leads', 'BEARISH': '-DI leads', 'NEUTRAL': 'DI neutral'}.get(swing.get('di_direction'), 'UNKNOWN')
    if any(number(swing.get(key)) == 'UNKNOWN' for key in ('di_plus', 'di_minus')):
        di = 'UNKNOWN'
    k = KONKORDE.get(swing.get('konkorde'), 'UNKNOWN')
    if any(number(swing.get(key)) == 'UNKNOWN' for key in ('mountain', 'ma')):
        k = 'UNKNOWN'
    lines += ['AO: ' + ' | '.join(ao),
              'ADX/DI (4H): ' + number(swing.get('adx')) + ' ' + slope(swing.get('adx_slope'))
              + ' · ' + di + ' (ADX strength; DI direction)',
              'Konkorde (4H, PROXY): ' + k,
              'BBWP / volatility (4H): ' + number(swing.get('bbwp')) + ' · ' + slope(swing.get('bbwp_slope')),
              '', 'ML RSI confirmed (production SPOT):']
    ml = snapshot.get('display_mlrsi') or {}
    for tf in ('15m', '1H', '4H'):
        color = ml.get(tf, {}).get('color', 'UNKNOWN')
        color = color if color in ('GREEN', 'RED', 'NEUTRAL') else 'UNKNOWN'
        lines.append(tf + ' ' + ICONS[color] + ' ' + color)
    structure = snapshot.get('structure') or {}
    lines += ['', 'Support: ' + number(structure.get('nearest_support')),
              'Resistance: ' + number(structure.get('nearest_resistance'))]
    try:
        stamp = snapshot['timestamp']
        if type(stamp) not in (int, float) or not math.isfinite(stamp):
            raise ValueError
        closed = datetime.fromtimestamp(stamp / 1000, timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    except (KeyError, ValueError, OverflowError, OSError):
        closed = 'UNKNOWN'
    lines += ['Public USD-M · closed 1H reference: ' + closed, '', FOOTER]
    text = '\n'.join(lines)
    return text if len(text.encode('utf-16-le')) // 2 < 3900 else unavailable()
