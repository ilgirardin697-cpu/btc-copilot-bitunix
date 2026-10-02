"""Opt-in, owner-only Telegram queries. Receives copied data, never a client/store."""
import copy
import json
import math
import threading
import time
import requests
from guardian_telegram import _price, _number, render_risk, direction_label, position_relationship

COMMANDS = ('/status', '/why', '/position', '/risk', '/levels', '/help')
NO_DATA = '⚫❓ SIN DATOS SUFICIENTES — NO OPERAR'
STALE = '⚠️ DATOS DESACTUALIZADOS — NO TOMAR DECISIÓN'
HELP = ('🤖 I-GOD MANUAL COPILOT\n\n/status\n→ resumen de qué ve ahora\n\n'
        '/why\n→ por qué espera o favorece LONG/SHORT\n\n'
        '/position\n→ tu posición real de Bitunix\n\n/risk\n→ riesgo y liquidación\n\n'
        '/levels\n→ soportes, resistencias y niveles a vigilar\n\n/help\n→ ayuda\n\n'
        '🔒 Estos comandos son solo consulta.\nNunca abren ni cierran operaciones.')


class SnapshotCache:
    """Copy boundary: command consumers cannot mutate Guardian objects or arming."""
    def __init__(self):
        self._lock = threading.Lock()
        self._value = None

    def publish(self, value):
        with self._lock:
            self._value = copy.deepcopy(value)

    def read(self):
        with self._lock:
            return copy.deepcopy(self._value)


def _position(snapshot, compact=False):
    if not snapshot['position_verified']:
        return '💼 Posición no verificable con datos actuales'
    p = snapshot['position']
    if p is None:
        return '💼 Sin posición BTCUSDT abierta'
    risk = snapshot['risk'] or {}
    bias = snapshot['data'].get('bias')
    relationship = position_relationship(p['side'], bias)
    pct, multiple = risk.get('distance_pct'), risk.get('distance_atr')
    pnl = _number(p['pnl'])
    pnl_text = ('+' if pnl is not None and pnl >= 0 else '') + _price(pnl)
    icon = '📈' if p['side'] == 'LONG' else '📉'
    if compact:
        return (f'💼 POSICIÓN\n{icon} {p["side"]} BTCUSDT\nEntrada: {_price(p["entry"])}\n'
                f'PnL: {pnl_text}\nLeverage: {p["leverage"]:g}x\n' + relationship)
    return (f'💼 TU POSICIÓN\n\n{icon} {p["side"]} BTCUSDT\nEntrada: {_price(p["entry"])}\nMark: {_price(snapshot["mark"])}'
            f'\nQty BTC: {p["qty"]:g}\nPnL: {pnl_text}\nLeverage: {p["leverage"]:g}x'
            f'\nLiquidación: {_price(p["liq"])}') + (
            f'\n\n📏 Distancia liquidación:\nDistancia: {pct:.2%}' if pct is not None else '\nDistancia: Sin datos') + (
            f'\nDistancia ATR: {multiple:.2f} ATR' if multiple is not None else '\nDistancia ATR: Sin datos') + (
            '\n\n🧭 DIRECCIÓN DEL COPILOT\n' + direction_label(bias) + '\n' + relationship
            + '\n\n' + render_risk(risk).split('\n')[0])


def _levels(data, compact=False, mark=None):
    """Only the independent closed/pivot-verified level field; no guessed levels."""
    levels = data.get('market_levels') or {}
    reference = _number(levels.get('reference_price'))
    support, resistance = _number(levels.get('support')), _number(levels.get('resistance'))
    if reference is None or reference <= 0 or levels.get('status') != 'AVAILABLE':
        support = resistance = None
    else:
        if support is None or not 0 < support < reference:
            support = None
        if resistance is None or not resistance > reference:
            resistance = None
    if compact:
        if support is None and resistance is None:
            return ''
        return '\n'.join(['🏗 NIVELES'] + (['🔴 R: ' + _price(resistance)] if resistance else [])
                         + (['🟢 S: ' + _price(support)] if support else []))
    lines = ['🏗 NIVELES DEL MERCADO', 'BTC: ' + _price(mark),
             'Referencia 15m cerrada: ' + _price(reference)]
    for value, label, sign in ((resistance, '🔴 Resistencia 15m', '+'),
                                (support, '🟢 Soporte 15m', '-')):
        if value is None:
            lines.append('\n' + label + ': Sin pivote confirmado disponible')
            continue
        lines.append('\n' + label + ': ' + _price(value))
        lines.append(f'Distancia: {sign}{abs(value - reference) / reference:.2%}')
        atr = _number(levels.get('atr_1h'))
        if atr is not None and atr > 0:
            lines.append(f'{abs(value - reference) / atr:.2f} ATR1H (Binance cerrado)')
    if support is None and resistance is None:
        lines.append('Sin niveles confirmados suficientes')
    lines += ['\n🧭 DIRECCIÓN', direction_label(data.get('bias')), '\n👀 QUÉ VIGILAR']
    if resistance is not None:
        lines.append('⬆️ Cierre 15m por encima de ' + _price(resistance)
                     + '\n→ podría mejorar escenario LONG\n→ todavía necesita momentum/flow/estructura')
    if support is not None:
        lines.append('⬇️ Cierre 15m por debajo de ' + _price(support)
                     + '\n→ podría mejorar escenario SHORT\n→ todavía necesita momentum/flow/estructura')
    if support is None and resistance is None:
        lines.append('Esperar nuevos pivotes 15m confirmados; no hay niveles verificables')
    level = _number(data.get('entry_level'))
    bias = data.get('bias')
    if level is not None and level > 0 and bias in ('LONG_ALLOWED', 'SHORT_ALLOWED'):
        lines += ['\n🎯 Reclaim relevante: ' + _price(level),
                  '🛑 Invalidación técnica: cierre 15m ' + ('bajo' if bias == 'LONG_ALLOWED' else 'sobre')
                  + ' ' + _price(level) + '; reevaluar el setup']
    lines.append('\n🚫 Estos niveles NO son una señal de entrada.')
    return '\n'.join(lines)


def _why(data):
    trends = {'BULL': '🟢 BULL', 'BEAR': '🔴 BEAR'}
    momenta = {'GREEN': '🟢 GREEN', 'RED': '🔴 RED', 'NEUTRAL': '⚪ NEUTRAL'}
    structures = {'BULLISH': '🟢 ALCISTA', 'BEARISH': '🔴 BAJISTA', 'MIXED': '⚪ MIXTA'}
    trend4, trend1 = data.get('trend4'), data.get('trend1')
    momentum, structure = data.get('momentum'), data.get('structure')
    bias = data.get('bias')
    aligned = trend4 == trend1 and trend4 in ('BULL', 'BEAR')
    side = 'LONG' if trend4 == 'BULL' else 'SHORT'
    desired_momentum = 'GREEN' if side == 'LONG' else 'RED'
    desired_structure = 'BULLISH' if side == 'LONG' else 'BEARISH'
    ratio = _number(data.get('taker_buy'))
    valid_flow = ratio is not None and 0 <= ratio <= 1
    flow_supports = valid_flow and (ratio >= .55 if side == 'LONG' else ratio <= .45)
    flow_label = ('comprador' if ratio >= .55 else 'vendedor' if ratio <= .45 else 'neutral') if valid_flow else 'sin datos'
    lines = ['🧭 POR QUÉ ESPERAMOS' if bias == 'WAIT' else '🧭 POR QUÉ', '\nTendencia:',
             '4H ' + trends.get(trend4, '⚫ Sin datos'), '1H ' + trends.get(trend1, '⚫ Sin datos'),
             '\nMomentum:', momenta.get(momentum, '⚫ Sin datos')]
    if aligned and momentum != desired_momentum:
        lines.append('→ falta impulso ' + side)
    lines += ['\nFlow:', (f'{ratio:.1%}' if valid_flow else 'Sin datos') + '\n→ ' + flow_label,
              '\nEstructura:', structures.get(structure, '⚫ Sin datos')]
    if structure == 'MIXED':
        lines.append('→ falta estructura 15m alcista/bajista')
    lines += ['\nRESULTADO:', direction_label(bias), '🎯 Entrada: ' + (
        data.get('entry_quality') if data.get('entry_quality') in ('GOOD', 'CAUTION', 'POOR') else 'CAUTION')]
    if aligned:
        lines.append('🚫 Por qué no ' + ('SHORT' if side == 'LONG' else 'LONG') + ': 4H/1H apoyan ' + side)
    else:
        lines.append('🚫 Ni LONG ni SHORT: 4H/1H deben estar alineados y verificables')
    lines.append('\n👀 QUÉ ESPERAMOS / QUÉ CAMBIARÍA LA DECISIÓN')
    if bias == 'UNKNOWN':
        lines.append('Recuperar datos cerrados y frescos del mercado')
    elif not aligned:
        lines.append('4H y 1H vuelvan a alinearse')
        if trend4 == 'BULL' and trend1 == 'BEAR':
            lines.append('1H recupere SMA200')
        elif trend4 == 'BEAR' and trend1 == 'BULL':
            lines.append('1H cierre bajo SMA200')
    else:
        missing = []
        if momentum != desired_momentum:
            missing.append('ML RSI vuelva a ' + desired_momentum)
        if not flow_supports:
            missing.append('Flujo taker ' + ('comprador' if side == 'LONG' else 'vendedor') + ' ≥55%')
        if structure != desired_structure:
            missing.append('Estructura 15m confirme ' + ('alcista' if side == 'LONG' else 'bajista'))
        lines += missing or ['Mantener las confirmaciones verificadas']
        lines.append('Reglas: ambas tendencias alineadas y al menos 2 de 3 confirmaciones')
        level = _number(data.get('entry_level'))
        if data.get('entry_quality') != 'GOOD' and level is not None and level > 0:
            lines.append('Esperar pullback + reclaim confirmado de ' + _price(level))
        elif data.get('entry_quality') != 'GOOD':
            lines.append('Esperar una entrada confirmada; no perseguir precio')
    return '\n'.join(lines)


def render_command(command, snapshot, now):
    if command not in COMMANDS or command == '/help':
        return HELP
    if not snapshot:
        return NO_DATA
    age = now - snapshot['timestamp']
    if not math.isfinite(age) or age < 0:
        return NO_DATA
    footer = f'\n\nActualizado hace: {age:.0f} s'
    warning = STALE + '\n\n' if age > 30 else ''
    data = snapshot['data']
    if command == '/status':
        blocks = snapshot['human_snapshot'].split('\n\n')
        wanted = ('🧭 DIRECCIÓN', '🧭 TENDENCIA', '🧠 ML RSI', '💧 FLUJO', '🏗 ESTRUCTURA', '🌪 VOLATILIDAD', '🎯 ENTRADA')
        text = blocks[0] + '\n\nBTC: ' + _price(snapshot['mark'])
        text += '\n\n' + '\n\n'.join(block for block in blocks if block.startswith(wanted))
        levels = _levels(data, compact=True)
        if levels:
            text += '\n\n' + levels
        text += '\n\n' + _position(snapshot, compact=True)
        text += '\n\n' + render_risk(snapshot['risk']).split('\n')[0] + '\n\n' + snapshot['protection']
    elif command == '/position':
        text = _position(snapshot)
    elif command == '/risk':
        text = '🛡️ RIESGO DE TU POSICIÓN\n\n' + render_risk(snapshot['risk'], snapshot['sl_status'], snapshot['stop_target'])
        text += '\n\n' + snapshot['protection']
        if snapshot.get('mode') == 'SHADOW':
            text += '\nGuardian NO colocará este stop automáticamente.'
    elif command == '/levels':
        text = _levels(data, mark=snapshot['mark'])
    else:
        text = _why(data)
    return warning + text + footer


class TelegramCommands:
    """No Bitunix, Guardian, environment writer, disk store or mutation callback."""
    def __init__(self, token, owner, cache, reply, enabled=False, transport=None, clock=time.time):
        self._token, self._owner = token.strip(), str(owner).strip()
        self._cache, self._reply = cache, reply
        self.enabled = enabled is True
        self._http = transport or requests.Session()
        self._clock = clock
        self._offset = 0
        self._stop = threading.Event()
        self._worker = None

    def process(self, update):
        if not self.enabled or not self._token or not self._owner or not isinstance(update, dict):
            return False
        message = update.get('message')
        if not isinstance(message, dict) or not isinstance(message.get('chat'), dict):
            return False
        if str(message['chat'].get('id', '')) != self._owner:
            return False
        text = message.get('text')
        if not isinstance(text, str) or not text.startswith('/'):
            return False
        command = text.split(maxsplit=1)[0].split('@')[0]
        try:
            return bool(self._reply(render_command(command, self._cache.read(), self._clock())))
        except Exception:
            return False  # never log incoming content, response payload or credentials

    def poll_once(self):
        if not self.enabled or not self._token or not self._owner:
            return False
        try:
            response = self._http.get('https://api.telegram.org/bot' + self._token + '/getUpdates',
                                      params={'offset': self._offset, 'limit': 25, 'timeout': 10,
                                              'allowed_updates': json.dumps(['message'])},
                                      timeout=(2, 12), allow_redirects=False)
            if response.status_code != 200:
                return False
            payload = response.json()
            if not isinstance(payload, dict) or payload.get('ok') is not True or not isinstance(payload.get('result'), list):
                return False
            for update in payload['result']:
                if not isinstance(update, dict):
                    continue
                identifier = update.get('update_id')
                if type(identifier) is not int or identifier < self._offset:
                    continue
                self._offset = identifier + 1
                self.process(update)
            return True
        except Exception:
            return False

    def start(self):
        if not self.enabled or not self._token or not self._owner or self._worker is not None:
            return False
        try:
            self._worker = threading.Thread(target=self._run, daemon=True, name='guardian-readonly-commands')
            self._worker.start()
            return True
        except Exception:
            self._worker = None
            return False

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            self.poll_once()
            self._stop.wait(1)
