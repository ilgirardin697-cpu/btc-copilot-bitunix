"""Outbound sendMessage only. No chat polling. Telegram failure is nonfatal."""
import requests
import queue
import threading
import math
import time
from datetime import datetime, timezone


DECISION_PREFIXES = ('🟢📈', '🔴📉', '🟠📈', '🟠📉', '🟡⏳', '⚫❓', '🛡️')


def _number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _price(value):
    value = _number(value)
    return f'{value:,.2f}' if value is not None else 'Sin datos'


def protection_status(config, private_ready=False):
    """Actual triple arm plus credentials; never render the phrase or credentials."""
    if config.mode == 'SHADOW':
        return '👁️ GUARDIAN: SHADOW\n🔒 Protección automática DESARMADA'
    sl = private_ready and config.armed('SL')
    close = private_ready and config.armed('CLOSE')
    title = '🛡️🚨 GUARDIAN: PROTECT CAPITAL' if sl and close else '🛡️ GUARDIAN: PROTECT'
    lines = [title, '✅ SL catastrófico ARMADO' if sl else '❌ SL catastrófico desarmado',
             '✅ Cierre emergencia ARMADO' if close else '❌ Auto-cierre desarmado']
    if not sl and not close:
        lines.append('🔒 Protección automática DESARMADA')
    return '\n'.join(lines)


def render_risk(details, statuses=None, target=None):
    details = details or {}
    labels = {
        'NORMAL': '🛡️🟢 RIESGO: NORMAL',
        'WARNING': '🛡️🟡 RIESGO: WARNING\n⚠️ La liquidación empieza a estar demasiado cerca',
        'DANGER': '🛡️🟠 RIESGO: DANGER\n🚨 Riesgo serio de capital\n🚫 NO AÑADIR',
        'EMERGENCY': '🛡️🔴🚨 EMERGENCIA DE LIQUIDACIÓN 🚨🔴\n💥 Liquidación demasiado cerca\n🛑 Protección de capital requerida',
    }
    lines = [labels.get(details.get('state'), '🛡️⚫ RIESGO: SIN DATOS VERIFICADOS')]
    if not details:
        return lines[0]
    pct, multiple = _number(details.get('distance_pct')), _number(details.get('distance_atr'))
    lines += ['Liquidación: ' + _price(details.get('liq')),
              f'Distancia: {pct:.2%}' if pct is not None else 'Distancia %: Sin datos',
              'ATR1H USDT: ' + _price(details.get('atr')),
              f'Distancia ATR: {multiple:.2f}' if multiple is not None else 'Distancia ATR: Sin datos']
    atr_pct = _number(details.get('atr_pct'))
    if atr_pct is not None:
        lines.append(f'ATR1H: {atr_pct:.2%}')
    stop_labels = {
        'EXISTING_SAFER_SL_UNTOUCHED': '✅ SL existente más protector; se respeta',
        'EXISTING_SL_CLOSER_TO_LIQUIDATION_OR_UNVERIFIED': '⚠️ SL más cercano a liquidación o protección no verificable; no se reemplaza',
        'EXISTING_TP_OR_UNKNOWN_UNTOUCHED': '⚠️ TP/SL sin stop protector verificado; no se reemplaza',
        'MISSING_SL': '⚠️ Sin SL catastrófico verificado',
        'STOP_TARGET_UNAVAILABLE_OR_INVALID': '⚠️ SL catastrófico no verificable',
    }
    lines.extend(stop_labels.get(code, '⚠️ SL no verificable') for code in (statuses or ['STOP_TARGET_UNAVAILABLE_OR_INVALID']))
    if _number(target) is not None:
        lines.append('SL catastrófico objetivo: ' + _price(target))
    return '\n'.join(lines)


def render_copilot(data, config, position=None, details=None, statuses=None, target=None, private_ready=False):
    """Pure presentation with explicit fields; never interpolate arbitrary API text."""
    bias = data.get('bias')
    quality = data.get('entry_quality', 'CAUTION')
    if quality not in ('GOOD', 'CAUTION', 'POOR'):
        quality = 'CAUTION'
    long, short = bias == 'LONG_ALLOWED', bias == 'SHORT_ALLOWED'
    side = 'LONG' if long else 'SHORT'
    if (long or short) and quality == 'GOOD':
        banner = '🟢📈 LONG — PUEDES BUSCAR ENTRADA' if long else '🔴📉 SHORT — PUEDES BUSCAR ENTRADA'
        decision = f'✅ Dirección: {side}\n✅ Puedes buscar entrada {side}\n🚫 {"SHORT" if long else "LONG"}: NO recomendado ahora'
    elif long or short:
        banner = '🟠📈 BIAS LONG — ESPERA MEJOR ENTRADA' if long else '🟠📉 BIAS SHORT — ESPERA MEJOR ENTRADA'
        decision = f'✅ Bias: {side}\n🚫 NO ENTRAR AHORA\n⏳ Esperar pullback o breakout + reclaim'
    elif bias == 'WAIT':
        banner = '🟡⏳ NO OPERAR — ESPERAR'
        decision = '🚫 No LONG\n🚫 No SHORT\n⏳ Esperar nueva confirmación'
    else:
        banner = '⚫❓ SIN DATOS SUFICIENTES — NO OPERAR'
        decision = '🚫 No abrir LONG\n🚫 No abrir SHORT\nNo se puede verificar el mercado con datos frescos.'
    trends = {'BULL': '🟢 BULL', 'BEAR': '🔴 BEAR'}
    momenta = {'GREEN': '🟢 GREEN', 'NEUTRAL': '⚪ NEUTRAL', 'RED': '🔴 RED'}
    structures = {'BULLISH': '🟢 Alcista', 'BEARISH': '🔴 Bajista', 'MIXED': '⚪ Mixta'}
    volatilities = {'NORMAL': '🟢 NORMAL', 'ELEVATED': '🟠 ELEVATED', 'HIGH': '🔴 HIGH'}
    ratio = _number(data.get('taker_buy'))
    flow = '⚪ Compras taker: Sin datos'
    if ratio is not None and 0 <= ratio <= 1:
        color = '🟢' if ratio >= .55 else '🔴' if ratio <= .45 else '⚪'
        flow = f'{color} Compras taker: {ratio:.1%}'
    entry_labels = {
        'GOOD': '🟢 ENTRADA: BUENA ZONA\n✅ Se permite buscar entrada según las reglas',
        'CAUTION': '🟠 ENTRADA: PRECAUCIÓN\n⚠️ Dirección válida, pero la entrada no es limpia\n⏳ Mejor esperar confirmación / pullback / reclaim',
        'POOR': '🔴 ENTRADA: NO PERSEGUIR PRECIO\n🚫 NO ENTRAR AHORA\n❌ El punto de entrada es malo',
    }
    reason = data.get('entry_reason')
    if long or short:
        conclusions = {
            'EXTENDED': f'Bias {side}, pero el precio está demasiado extendido. No perseguir.',
            'NEAR_RESISTANCE': 'Bias LONG, pero el precio está junto a resistencia confirmada. No perseguir.',
            'NEAR_SUPPORT': 'Bias SHORT, pero el precio está junto a soporte confirmado. No perseguir.',
        }
        conclusion = (f'Tendencia, confirmaciones y reclaim apoyan buscar {side}.' if quality == 'GOOD'
                      else conclusions.get(reason, f'Bias {side}; esperar una entrada confirmada.'))
    elif bias == 'WAIT':
        conclusion = ('4H y 1H no están alineados. No operar.' if data.get('trend4') != data.get('trend1')
                      else 'Faltan confirmaciones de momentum, flujo o estructura. No operar.')
    else:
        conclusion = 'Datos insuficientes o no frescos. No operar.'
    expected = []
    if long or short:
        opposing = data.get('resistance') if long else data.get('support')
        if quality == 'POOR' and reason in ('NEAR_RESISTANCE', 'NEAR_SUPPORT') and _number(opposing) is not None:
            expected.append('Breakout + reclaim de ' + _price(opposing))
        elif quality != 'GOOD' and _number(data.get('entry_level')) is not None:
            expected.append('Pullback y reclaim del nivel confirmado ' + _price(data['entry_level']))
        if data.get('momentum') != ('GREEN' if long else 'RED'):
            expected.append('ML RSI vuelva a ' + ('GREEN' if long else 'RED'))
        if data.get('structure') != ('BULLISH' if long else 'BEARISH'):
            expected.append('Estructura 15m confirme ' + ('alcista' if long else 'bajista'))
        expected = expected or ['Mantener reclaim / estructura confirmada.' if quality == 'GOOD' else 'Esperar un reclaim con datos cerrados suficientes.']
    elif bias == 'WAIT':
        if data.get('trend4') != data.get('trend1'):
            expected.append('4H y 1H vuelvan a alinearse')
            if data.get('trend4') == 'BULL' and data.get('trend1') == 'BEAR':
                expected.append('1H recupere SMA200')
        else:
            expected.append('Nueva confirmación de momentum, flujo y estructura')
    else:
        expected.append('Recuperar datos cerrados y frescos del mercado')
    # Non-directional states never claim a GOOD entry from a stray input field.
    if not (long or short):
        quality = 'CAUTION'
    entry_text = entry_labels[quality] if long or short else '🟠 ENTRADA: PRECAUCIÓN\n⏳ Sin confirmación para entrar'
    momentum_text = momenta.get(data.get('momentum'), '⚪ Sin datos')
    if data.get('green_event') is True:
        momentum_text += '\n🟢 Nuevo evento GREEN'
    if data.get('red_event') is True:
        momentum_text += '\n🔴 Nuevo evento RED'
    lines = [banner, 'I-GOD TRADE GUARDIAN + MANUAL COPILOT', decision,
             '🧭 TENDENCIA\n4H: ' + trends.get(data.get('trend4'), '⚪ Sin datos')
             + '\n1H: ' + trends.get(data.get('trend1'), '⚪ Sin datos'),
             '🧠 ML RSI 27 LOW EMA4\nEstado: ' + momentum_text,
             '💧 FLUJO\n' + flow,
             '🏗 ESTRUCTURA 15m\n' + structures.get(data.get('structure'), '⚪ Sin datos'),
             '🌪 VOLATILIDAD\n' + volatilities.get(data.get('volatility'), '⚪ Sin datos'),
             '🎯 ENTRADA\n' + entry_text,
             '🎯 CONCLUSIÓN\n' + conclusion, '👀 QUÉ ESPERAMOS\n' + '\n'.join(expected)]
    if position is not None and details:
        aligned = bias == ('LONG_ALLOWED' if position.side == 'LONG' else 'SHORT_ALLOWED')
        counter = bias == ('SHORT_ALLOWED' if position.side == 'LONG' else 'LONG_ALLOWED')
        status = ('✅ POSICIÓN ALINEADA CON EL BIAS' if aligned else
                  '⚠️⚠️ POSICIÓN CONTRA TENDENCIA ⚠️⚠️\n🚫 NO AÑADIR POSICIÓN\n🟠 Considerar reducir/cerrar manualmente si la tesis ya no es válida\nCierre automático por dirección: NO' if counter else
                  '⚪ No hay bias confirmado para comparar la posición')
        icon = '📈' if position.side == 'LONG' else '📉'
        lines.append(f'💼 TU POSICIÓN\n{icon} {position.side} BTCUSDT\nEntrada: {_price(position.entry)}\n'
                     f'Mark: {_price(details.get("mark"))}\nLeverage: {_price(position.leverage)}x\n'
                     f'Tamaño BTC: {position.qty:g}\nPnL: {_price(position.pnl)}\n' + status)
    if details:
        lines.append(render_risk(details, statuses, target))
    stamp = _number(data.get('last_closed_1h'))
    if stamp is not None:
        try:
            lines.append('Última 1H cerrada: ' + datetime.fromtimestamp(stamp / 1000, timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))
        except (ValueError, OverflowError, OSError):
            pass
    lines.append(protection_status(config, private_ready))
    return '\n\n'.join(lines)


class Telegram:
    def __init__(self, token='', chat_id='', transport=None, alert_chat_id=''):
        self._token = token.strip()
        owner = str(chat_id).strip()
        self._owner = owner
        extras = [value.strip() for value in alert_chat_id.split(',') if value.strip()]
        self._recipients = []
        for recipient in [owner] + extras:
            if recipient and recipient not in self._recipients:
                self._recipients.append(recipient)
        self._http = transport or requests.Session()
        self._queue = None
        self._worker = None
        self._start_lock = threading.Lock()

    @staticmethod
    def _diagnostic(code):
        try:
            print(code, flush=True)
        except Exception:
            pass  # a broken log stream must not affect the risk loop

    def send(self, text):
        return self._enqueue(text, tuple(self._recipients))

    def send_owner(self, text):
        """Command replies go only to the configured owner, never alert recipients."""
        return self._enqueue(text, (self._owner,) if self._owner else ())

    def _enqueue(self, text, recipients):
        if not self._token:
            self._diagnostic('TELEGRAM_DISABLED_NO_TOKEN')
            return False
        if not recipients:
            self._diagnostic('TELEGRAM_DISABLED_NO_RECIPIENT')
            return False
        try:
            with self._start_lock:
                if self._queue is None:
                    self._queue = queue.Queue(maxsize=100)
                    self._worker = threading.Thread(target=self._run, daemon=True, name='guardian-telegram')
                    try:
                        self._worker.start()
                    except Exception:
                        self._queue, self._worker = None, None
                        self._diagnostic('TELEGRAM_SEND_NOT_OK')
                        return False
            self._queue.put_nowait((text[:4000], recipients))
            return True
        except queue.Full:
            self._diagnostic('TELEGRAM_QUEUE_FULL')
            return False
        except Exception:
            self._diagnostic('TELEGRAM_SEND_NOT_OK')
            return False

    def _deliver(self, recipient, text):
        """At most three attempts per recipient, all on the outbound worker."""
        for attempt in range(3):
            try:
                response = self._http.post('https://api.telegram.org/bot' + self._token + '/sendMessage',
                                          json={'chat_id': recipient, 'text': text},
                                          timeout=(1, 2), allow_redirects=False)
                if response.status_code != 200:
                    code = 'TELEGRAM_SEND_HTTP_ERROR'
                else:
                    payload = response.json()
                    if isinstance(payload, dict) and payload.get('ok') is True:
                        self._diagnostic('TELEGRAM_SEND_OK')
                        return True
                    code = 'TELEGRAM_SEND_NOT_OK'
            except requests.Timeout:
                code = 'TELEGRAM_SEND_TIMEOUT'
            except requests.RequestException:
                code = 'TELEGRAM_SEND_HTTP_ERROR'
            except Exception:
                code = 'TELEGRAM_SEND_NOT_OK'
            self._diagnostic(code)
            if attempt < 2:
                time.sleep(.2 * (attempt + 1))
        return False

    def _run(self):
        while True:
            text, recipients = self._queue.get()
            try:
                for recipient in recipients:
                    self._deliver(recipient, text)
            except Exception:
                self._diagnostic('TELEGRAM_SEND_NOT_OK')
            finally:
                self._queue.task_done()
