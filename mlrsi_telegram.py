"""Read-only HTML presentation; no command polling or operational state."""
from datetime import datetime, timezone
from mlrsi_math import CAPTURED_CONFIG, TIMEFRAMES

ICONS = {'GREEN': '🟢', 'RED': '🔴', 'NEUTRAL': '⚪', 'UNKNOWN': '⚫'}
LABELS = {'15m': '15m', '1h': '1H', '4h': '4H'}
PRESET_LABEL = f"Source: LOW | RSI: Wilder {CAPTURED_CONFIG['rsi_length']} | Smooth: EMA4"


def utc(stamp):
    return datetime.fromtimestamp(stamp / 1000, timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if stamp is not None else 'no disponible'


def number(value):
    return f'{value:.2f}' if value is not None else 'no disponible'


def matrix(snapshot):
    return '\n'.join(f"{LABELS[tf]} {ICONS[snapshot['timeframes'][tf]['confirmed_color']]} "
                     f"{snapshot['timeframes'][tf]['confirmed_color']}"
                     + (' (datos no actuales)' if not snapshot['timeframes'][tf]['fresh'] else '')
                     for tf in TIMEFRAMES)


def status(snapshot):
    if snapshot is None:
        return '🧠 ML RSI MTF Observer: OFF / no disponible\n👀 SHADOW ONLY\n🚫 TRADE AUTHORITY: NONE'
    lines = ['🧠 <b>ML RSI MTF STATUS</b>', 'BTCUSDT — Binance spot public',
             'Precio público: ' + number(snapshot.get('price')),
             'Exact BackQuant TradingView parity is NOT proven.']
    for tf in TIMEFRAMES:
        p = snapshot['timeframes'][tf]
        c, o = p['latest_confirmed_values'], p['latest_provisional_values']
        lines += ['', '<b>' + LABELS[tf] + '</b>',
                  f"Confirmed: {ICONS[p['confirmed_color']]} {p['confirmed_color']}",
                  'ML RSI: ' + number(c.get('mlrsi_smoothed')),
                  'Upper: ' + number(c.get('upper_threshold')) + ' | Middle: ' + number(c.get('middle_centroid')),
                  'Lower: ' + number(c.get('lower_threshold')),
                  'Último cierre: ' + utc(p['last_closed_timestamp']),
                  'Último evento: ' + (p['last_confirmed_event'] or 'none'),
                  'Actualización pública: ' + (str(p['public_read_age_seconds']) + ' s' if p.get('public_read_age_seconds') is not None else 'no disponible'),
                  'Open candle — NOT CONFIRMED:',
                  f"Provisional: {ICONS[o.get('color', 'UNKNOWN')]} {o.get('color', 'UNKNOWN')}",
                  'ML RSI provisional: ' + number(o.get('mlrsi_smoothed')),
                  'Approaching: ' + ('🟡 ' if p['approaching_state'] != 'NO' else '') + p['approaching_state'],
                  'Distance GREEN: ' + number(o.get('distance_to_green')) + ' | RED: ' + number(o.get('distance_to_red'))]
        if not p['fresh']:
            lines += ['⚠️ Datos no actuales / insuficientes; no nueva confirmación.']
    green = sum(p['fresh'] and p['confirmed_color'] == 'GREEN' for p in snapshot['timeframes'].values())
    red = sum(p['fresh'] and p['confirmed_color'] == 'RED' for p in snapshot['timeframes'].values())
    lines += ['', '<b>CONFLUENCIA</b>', f'GREEN confirmed: {green}/3', f'RED confirmed: {red}/3', matrix(snapshot),
              '', PRESET_LABEL,
              'Max data: 3000 | Max clustering steps: 1000',
              'TV metadata: range 10–90 | step 5 | memory 10 | ALMA sigma 1',
              '(Range/step/memory metadata; ALMA no afecta EMA.)',
              'Confirmed: CLOSED CANDLES ONLY',
              'Approaching: ' + ('ON' if snapshot['approaching_enabled'] else 'OFF'),
              'Observer: ' + ('ON' if snapshot['enabled'] else 'OFF'),
              '', '🟢 GREEN / 🔴 RED = confirmado al cierre',
              '⚪ NEUTRAL = entre thresholds',
              '🟡 APPROACHING = cerca del threshold, todavía no confirmado',
              '🟡 PROVISIONAL = cruce OPEN CANDLE pendiente de cierre',
              'GREEN_CROSS / RED_CROSS = cambio confirmado de color',
              'GREEN_RESUME / RED_RESUME = reanudación según definición research',
              '3/3 = tres TF confirmados en el mismo color',
              '👀 Todo ML RSI es SHADOW ONLY.', '🚫 TRADE AUTHORITY: NONE']
    return '\n'.join(lines)


def startup(snapshot):
    return ('🧠 <b>ML RSI MTF OBSERVER — CURRENT STATUS</b>\nBTCUSDT\n\n' + matrix(snapshot)
            + '\n\n' + PRESET_LABEL + '\nMax data: 3000 | Max clustering: 1000'
            + '\nApproaching: ' + ('ON' if snapshot['approaching_enabled'] else 'OFF')
            + '\nProvisional alerts: ' + ('ON' if snapshot['provisional_alerts'] else 'OFF')
            + '\nClosed candle confirmation: ON\nConsulta: /mlrsi'
            + '\nExact BackQuant TradingView parity is NOT proven.\n👀 SHADOW ONLY\n🚫 TRADE AUTHORITY: NONE')


def priority(event):
    return (0 if event.startswith('CONFLUENCE_') else 1 if event.endswith('_CROSS') else
            2 if event.endswith('_RESUME') else 3 if event == 'COLOR_CHANGE' else
            4 if event.startswith('PROVISIONAL_') else 5)


def alert(snapshot, records):
    ordered = sorted(records, key=lambda row: priority(row['event']))
    main = ordered[0]
    events = list(dict.fromkeys(row['event'] for row in ordered))
    headline = main['event']
    if headline.startswith('CONFLUENCE_'):
        color = headline.rsplit('_', 1)[-1]
        cross = next((e for e in events if e.endswith('_CROSS')), None)
        headline = (cross + ' + ' if cross else '') + '3/3 ' + color + ' CONFIRMED'
        icon = ICONS[color] * 3
    else:
        icon = '🟡' if priority(headline) >= 4 else ICONS[main['confirmed_color']]
        if headline == 'COLOR_CHANGE':
            headline = 'BACK TO NEUTRAL' if main['confirmed_color'] == 'NEUTRAL' else main['confirmed_color'] + ' CONFIRMED'
    lines = [icon + ' <b>ML RSI — ' + headline + ' ' + LABELS.get(main['timeframe'], 'MTF') + '</b>',
             'BTCUSDT', matrix(snapshot)]
    for row in ordered:
        if row['event'] == 'COLOR_CHANGE' and any(r['timeframe'] == row['timeframe'] and r['event'].endswith('_CROSS') for r in ordered):
            continue
        lines += ['', LABELS.get(row['timeframe'], 'MTF') + ' Event: ' + row['event'],
                  'ML RSI: ' + number(row['mlrsi_smoothed']),
                  'Upper: ' + number(row['upper_threshold']) + ' | Middle: ' + number(row['middle_centroid']),
                  'Lower: ' + number(row['lower_threshold']), 'Close: ' + number(row['close'])]
        if row['candle_complete']:
            lines += ['✅ CLOSED CANDLE — ' + row['candle_timestamp_utc']]
        else:
            lines += ['🟡 ' + row['provisional_color'] + ' provisional',
                      '⚠️ OPEN CANDLE — NOT CONFIRMED — PROVISIONAL',
                      '⏳ Waiting candle close. Puede desaparecer antes del cierre.']
    lines += ['👀 SHADOW ONLY', '🚫 TRADE AUTHORITY: NONE — NO AUTO TRADE']
    # Telegram hard limit; never split a single close into multiple notifications.
    if sum(len(line) + 1 for line in lines) > 3900:
        lines = lines[:3] + [matrix(snapshot), 'Eventos: ' + ', '.join(events),
                            'Detalle: /mlrsi', '👀 SHADOW ONLY', '🚫 TRADE AUTHORITY: NONE']
    return '\n'.join(lines)
