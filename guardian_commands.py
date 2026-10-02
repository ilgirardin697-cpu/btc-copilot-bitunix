"""Opt-in, owner-only Telegram queries. Receives copied data, never a client/store."""
import copy
import json
import math
import threading
import time
import requests
from guardian_telegram import _price, render_risk

COMMANDS = ('/status', '/why', '/position', '/risk', '/levels', '/help')
NO_DATA = '⚫❓ SIN DATOS SUFICIENTES — NO OPERAR'
STALE = '⚠️ DATOS DESACTUALIZADOS — NO TOMAR DECISIÓN'
HELP = ('🤖 I-GOD MANUAL COPILOT\n\n/status — qué hago ahora\n/why — por qué\n'
        '/position — mi operación\n/risk — riesgo/liquidación\n/levels — niveles importantes\n'
        '/help — ayuda\n\nGuardian nunca abre operaciones desde Telegram.')


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


def _position(snapshot):
    if not snapshot['position_verified']:
        return '💼 Posición no verificable con datos actuales'
    p = snapshot['position']
    if p is None:
        return '💼 Sin posición BTCUSDT abierta'
    risk = snapshot['risk'] or {}
    expected = 'LONG_ALLOWED' if p['side'] == 'LONG' else 'SHORT_ALLOWED'
    opposite = 'SHORT_ALLOWED' if p['side'] == 'LONG' else 'LONG_ALLOWED'
    bias = snapshot['data'].get('bias')
    relationship = ('✅ Alineada con el bias' if bias == expected else
                    '⚠️ CONTRA TENDENCIA — NO AÑADIR; considerar reducir/cerrar manualmente' if bias == opposite
                    else '⚪ Bias sin confirmación')
    pct, multiple = risk.get('distance_pct'), risk.get('distance_atr')
    return (f'💼 {p["side"]} BTCUSDT\nEntrada: {_price(p["entry"])}\nMark: {_price(snapshot["mark"])}'
            f'\nQty BTC: {p["qty"]:g}\nLeverage: {p["leverage"]:g}x\nPnL: {_price(p["pnl"])}'
            f'\nLiquidación: {_price(p["liq"])}') + (
            f'\nDistancia: {pct:.2%}' if pct is not None else '\nDistancia: Sin datos') + (
            f'\nDistancia ATR: {multiple:.2f}' if multiple is not None else '\nDistancia ATR: Sin datos') + '\n' + relationship


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
    bias = data.get('bias', 'UNKNOWN')
    if command == '/status':
        blocks = snapshot['human_snapshot'].split('\n\n')
        wanted = ('🧭 TENDENCIA', '🧠 ML RSI', '💧 FLUJO', '🏗 ESTRUCTURA', '🌪 VOLATILIDAD', '🎯 ENTRADA')
        text = blocks[0] + '\n\nBTC: ' + _price(snapshot['mark'])
        text += '\n\n' + '\n\n'.join(block for block in blocks if block.startswith(wanted))
        text += '\n\n' + _position(snapshot)
        text += '\n\n' + render_risk(snapshot['risk']).split('\n')[0] + '\n\n' + snapshot['protection']
    elif command == '/position':
        text = _position(snapshot)
    elif command == '/risk':
        text = render_risk(snapshot['risk'], snapshot['sl_status'], snapshot['stop_target'])
        text += '\n\n' + snapshot['protection']
    elif command == '/levels':
        lines = ['🏗 NIVELES CONFIRMADOS']
        for key, label in (('support', 'Soporte'), ('resistance', 'Resistencia'),
                           ('entry_level', 'Reclaim'), ('breakout_level', 'Breakout')):
            value = data.get(key)
            if isinstance(value, (int, float)) and math.isfinite(value) and value > 0:
                lines.append(label + ': ' + _price(value))
        if len(lines) == 1:
            lines.append('Sin niveles confirmados disponibles')
        if data.get('entry_level') and bias in ('LONG_ALLOWED', 'SHORT_ALLOWED'):
            lines.append('Invalidación del reclaim: cierre 15m ' + ('bajo' if bias == 'LONG_ALLOWED' else 'sobre')
                         + ' ' + _price(data['entry_level']) + '; reevaluar el setup')
        else:
            lines.append('Esperar alineación 4H/1H y estructura confirmada')
        text = '\n'.join(lines)
    else:
        human = snapshot['human_snapshot']
        conclusion = human.split('🎯 CONCLUSIÓN\n')[-1].split('\n\n')[0]
        expected = human.split('👀 QUÉ ESPERAMOS\n')[-1].split('\n\n')[0]
        lines = ['🧭 POR QUÉ', conclusion, '🎯 Entrada: ' + data.get('entry_quality', 'CAUTION')]
        if bias in ('LONG_ALLOWED', 'SHORT_ALLOWED'):
            side = 'LONG' if bias == 'LONG_ALLOWED' else 'SHORT'
            lines.append('🚫 Por qué no ' + ('SHORT' if side == 'LONG' else 'LONG')
                         + ': tendencia 4H/1H apoya ' + side)
            momentum = 'GREEN' if side == 'LONG' else 'RED'
            structure = 'BULLISH' if side == 'LONG' else 'BEARISH'
            if data.get('momentum') != momentum:
                lines.append('Falta ML RSI ' + momentum)
            ratio = data.get('taker_buy')
            if ratio is None or (ratio < .55 if side == 'LONG' else ratio > .45):
                lines.append('Falta flujo taker a favor')
            if data.get('structure') != structure:
                lines.append('Falta estructura 15m a favor')
        else:
            lines.append('🚫 Ni LONG ni SHORT: falta alineación o confirmación verificable')
        text = '\n'.join(lines) + '\n\n👀 QUÉ ESPERAMOS\n' + expected
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
