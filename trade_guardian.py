"""Independent disarmed-by-default manual copilot and liquidation emergency guard."""
from dataclasses import asdict
import json
import os
import time
from uuid import uuid4
from guardian_bitunix import Bitunix
from guardian_market import Market
from guardian_risk import Config, SafetyError, risk, catastrophic_stop, assess_orders
from guardian_store import Store
from guardian_telegram import Telegram, render_copilot, render_risk, protection_status, DECISION_PREFIXES, TPSL_WARNING_TEXT
from koncorde_shadow import diagnostic
from guardian_signals import volatility_state, current_entry_quality
from guardian_commands import SnapshotCache, TelegramCommands


def _safe_order_number(value):
    try:
        number_value = float(value)
        return number_value if number_value > 0 and number_value < float('inf') else None
    except (TypeError, ValueError, OverflowError):
        return None


class Guardian:
    def __init__(self, client, store, market, telegram, clock=time.time):
        self.client, self.store, self.market, self.telegram = client, store, market, telegram
        self.config = client.config
        self.clock = clock
        self.bias = {'bias': 'UNKNOWN', 'why': 'Not loaded'}
        self._bias_due = 0
        self._snapshot_due = 0
        self._started = False
        self._startup_key = 'startup:' + uuid4().hex
        self._startup_position_checked = False
        self._failures = 0
        self.command_snapshot = SnapshotCache()

    def alert(self, key, text, cooldown=300):
        last = self.store.state.setdefault('alerts', {}).get(key, 0)
        if last and self.clock() - last < cooldown:
            return
        # Existing-order warnings belong to the dedicated transition/hourly
        # notice. Risk/context alerts retain stop status without repeating the
        # same warning every generic cooldown. Queries keep the full warning.
        warning_lines = set(TPSL_WARNING_TEXT.values())
        seen = set()
        lines = []
        for line in text.split('\n'):
            if line in warning_lines:
                if not key.startswith('tpsl:') or line in seen:
                    continue
                seen.add(line)
            lines.append(line)
        text = '\n'.join(lines)
        if 'GUARDIAN:' not in text:
            text += '\n\n' + protection_status(self.config, self.client.credentials_present)
        self.store.append('alerts', {'timestamp': self.clock(), 'key': key, 'text': text})
        self.store.state['alerts'][key] = self.clock()
        self.store.save()
        try:
            self.telegram.send(text if text.startswith(DECISION_PREFIXES) else 'I-GOD TRADE GUARDIAN\n' + text)
        except Exception:
            Telegram._diagnostic('TELEGRAM_SEND_NOT_OK')

    def _confirmed(self, row, result):
        confirmed = dict(row, status='CONFIRMED', timestamp=self.clock(), result=result)
        self.store.append('actions', confirmed)
        if row['action'] == 'CLOSE':
            until = self.clock() + self.config.lockout_minutes * 60
            self.store.state['lockout_until'] = until
            self.store.save()
            self.alert('closed:' + row['positionId'], 'EMERGENCY CLOSE CONFIRMED\nPosition: ' + row['positionId'])
        else:
            self.alert('confirmed:' + row['key'], 'GUARDIAN PROTECTION RECONCILED\nAction: SL')

    def reconcile(self):
        """No repeat POST for unresolved intent, even after a lost response/restart."""
        pending = self.store.pending()
        for row in pending:
            current = self.client.position()
            if current is None or current.position_id != row['positionId']:
                self._confirmed(row, 'POSITION_ABSENT')
                continue
            orders = self.client.orders(current.position_id)
            if row['action'] == 'SL' and orders:
                # Presence avoids duplicate placement; cannot claim ownership after lost response.
                self._confirmed(row, 'EXISTING_ORDER_RECONCILED_OWNERSHIP_UNKNOWN')
                continue
            self.alert('unresolved:' + row['key'], 'GUARDIAN ACTION UNRESOLVED — RECONCILING; NO DUPLICATE POST')
        return not self.store.pending()

    def _act(self, action, position, atr):
        if position.leverage < 2 or self.store.attempted(action, position.position_id):
            return
        if not self.config.armed(action):
            self.alert('dry:' + action + position.position_id, 'DRY-RUN INTENT ' + action + '\nPOSITION GUARD READ-ONLY')
            return
        if not self.reconcile():
            return
        permit = self.client.preflight(action, position, atr)
        row = {'key': action + ':' + position.position_id + ':1', 'action': action,
               'positionId': position.position_id, 'risk_epoch': 1, 'status': 'INTENT',
               'timestamp': self.clock(), 'body': permit['body']}
        self.store.append('actions', row)  # fsync must finish before the ONLY POST call
        self.alert('intent:' + row['key'], 'GUARDIAN PROTECTION INTENT\nAction: ' + action)
        try:
            response = self.client.execute(permit)
            row = dict(row, status='RESPONSE', timestamp=self.clock(), response=response)
            self.store.append('actions', row)
            self.alert('response:' + row['key'], 'GUARDIAN PROTECTION RESPONSE RECEIVED\nAction: ' + action + '\nExchange reconciliation pending')
        except SafetyError:
            self.store.append('actions', dict(row, status='RESPONSE', timestamp=self.clock(), result='AMBIGUOUS'))
            self.alert('response:' + row['key'], 'GUARDIAN PROTECTION RESPONSE AMBIGUOUS\nAction: ' + action + '\nReconciling; no duplicate action')
        if action == 'SL' and row.get('response', {}).get('orderId'):
            self.store.state.setdefault('owned_sl', {})[position.position_id] = row['response']['orderId']
            self.store.save()
        # Bounded reads only; a surviving position does not justify a duplicate POST.
        for attempt in range(2):
            self.reconcile()
            if not self.store.pending():
                break
            if attempt == 0:
                time.sleep(.2)

    def _position_text(self, position, details, orders, target):
        data = dict(current_entry_quality(self.bias, details['mark']),
                    volatility=volatility_state(details['atr'], details['mark']))
        return render_copilot(data, self.config, position, details, orders.get('status'), target,
                              private_ready=self.client.credentials_present)

    def _tpsl_notice(self, position, details, orders, statuses, target):
        """Notification memory only; never changes order assessment or actions.

        A target move is material at max(0.25 ATR, 0.1% mark) relative to
        the last notification. Price noise does not reset the hourly reminder.
        """
        warning_codes = sorted(set(statuses) & {
            'EXISTING_SL_CLOSER_TO_LIQUIDATION_OR_UNVERIFIED', 'EXISTING_TP_OR_UNKNOWN_UNTOUCHED'})
        previous = self.store.state.get('tpsl_notice') or {}
        ranks = {'NORMAL': 0, 'WARNING': 1, 'DANGER': 2, 'EMERGENCY': 3}
        signature = json.dumps({'statuses': sorted(set(statuses)),
                                'orders': sorted(orders, key=lambda row: json.dumps(row, sort_keys=True))},
                               sort_keys=True, separators=(',', ':'))
        target = _safe_order_number(target)
        prior_target = _safe_order_number(previous.get('sent_target'))
        material = (target is None) != (prior_target is None)
        if target is not None and prior_target is not None:
            material = abs(target - prior_target) >= max(.25 * (details.get('atr') or 0), .001 * details['mark'])
        changed = (previous.get('position_id') != position.position_id or not previous.get('active')
                   or previous.get('signature') != signature
                   or ranks[details['state']] > ranks.get(previous.get('risk'), -1) or material)
        due = self.clock() - previous.get('sent_at', 0) >= 3600
        row = dict(previous, position_id=position.position_id, active=bool(warning_codes),
                   signature=signature, risk=details['state'])
        if warning_codes and (changed or due):
            self.alert('tpsl:' + position.position_id,
                       '⚠️ STOP PROTECTOR NO VERIFICADO\n' + render_risk(details, warning_codes, target)
                       + '\nLa orden manual se respeta; no se cancela ni reemplaza.', cooldown=0)
            row.update(sent_at=self.clock(), sent_target=target)
        self.store.state['tpsl_notice'] = row

    def cycle(self):
        now = self.clock()
        # CAPITAL first. Direction downloads never delay an emergency action.
        position, details, mark, atr, sl_status, target = None, None, None, None, None, None
        private_verified = False  # notification readiness, never authorizes a mutation
        try:
            mark = self.client.mark()
            atr = self.market.venue_atr()
            if self.client.credentials_present:
                clean = self.reconcile()
                position = self.client.position()
                private_verified = True
                previous = self.store.state.get('position_id')
                if position is None:
                    if previous:
                        self.store.append('positions', {'timestamp': now, 'event': 'MANUAL_CLOSE_DETECTED', 'positionId': previous})
                        self.alert('manual:' + previous, 'MANUAL_CLOSE_DETECTED\n' + previous)
                    self.store.state['position_id'] = None
                    self.store.state.pop('tpsl_notice', None)
                else:
                    details = risk(position, mark, atr, self.config)
                    orders = self.client.orders(position.position_id)
                    target = None
                    try:
                        target = catastrophic_stop(position, mark, atr, self.client.precision(), self.config)
                        sl_status = assess_orders(orders, position, target)
                    except SafetyError:
                        sl_status = ['STOP_TARGET_UNAVAILABLE_OR_INVALID']
                    emergency_processed = False
                    order_summary = [{'id': order.get('id') if isinstance(order.get('id'), str)
                                      and order['id'].isdecimal() else None,
                                      'tpPrice': _safe_order_number(order.get('tpPrice')),
                                      'slPrice': _safe_order_number(order.get('slPrice')),
                                      'slStopType': order.get('slStopType') if order.get('slStopType') in ('MARK_PRICE', 'LAST_PRICE') else None,
                                      'slQty': _safe_order_number(order.get('slQty'))} for order in orders]
                    text = self._position_text(position, details,
                                               {'status': sl_status, 'orders': order_summary}, target)
                    if clean and position.leverage >= 2 and details['state'] == 'EMERGENCY':
                        self.alert('risk:' + position.position_id + details['state'],
                                   render_risk(details, sl_status, target) + '\n\n' + text)
                        self._act('CLOSE', position, atr)
                        emergency_processed = True
                    if previous != position.position_id:
                        self.store.append('positions', {'timestamp': now, 'event': 'NEW_POSITION_DETECTED', **asdict(position)})
                        self.alert('new:' + position.position_id, text + '\n\nNEW POSITION DETECTED')
                        if now < self.store.state.get('lockout_until', 0):
                            self.alert('lockout:' + position.position_id, '🚨 GUARDIAN LOCKOUT VIOLATION\nApp trading is not physically blocked\n' + text)
                    self.store.state['position_id'] = position.position_id
                    opposite = ('LONG_ALLOWED' if position.side == 'SHORT' else 'SHORT_ALLOWED')
                    if self.bias['bias'] == opposite:
                        self.alert('conflict:' + position.position_id + opposite,
                                   text)
                    elif previous == position.position_id and self.store.state.get('position_bias') != self.bias['bias']:
                        self.alert('aligned:' + position.position_id + self.bias['bias'], text + '\n\nPOSITION CONTEXT UPDATED')
                    self.store.state['position_bias'] = self.bias['bias']
                    if details['state'] != 'NORMAL':
                        self.alert('risk:' + position.position_id + details['state'],
                                   render_risk(details, sl_status, target) + '\n\n' + text)
                    self._tpsl_notice(position, details, order_summary, sl_status, target)
                    if clean and position.leverage >= 2:
                        if details['state'] == 'EMERGENCY' and not emergency_processed:
                            self._act('CLOSE', position, atr)
                        elif not orders and target is not None:
                            self._act('SL', position, atr)
                self.store.save()
            if self._failures:
                self.alert('blind:recovered', '✅ CONEXIÓN RECUPERADA\n\n'
                           'Datos de Bitunix vuelven a estar verificados.\n'
                           'Guardian continúa en su modo configurado.', cooldown=0)
            self._failures = 0
        except SafetyError as error:
            print('GUARDIAN_BLIND_CODE=' + str(error), flush=True)
            self._failures += 1
            stages = {
                1: ('🟡 DATOS TEMPORALMENTE NO VERIFICABLES\n\n'
                    'No puedo verificar datos frescos de Bitunix en este ciclo.\n'
                    '🔒 No realizaré acciones automáticas hasta recuperar datos.'),
                2: ('🟠 DATOS DEGRADADOS\n\nSigo sin poder verificar datos frescos.\n'
                    '🔒 Guardian permanece bloqueado para mutaciones.'),
                3: ('🚨 GUARDIAN SIN DATOS FIABLES\n\nNo puedo verificar el estado actual de Bitunix.\n'
                    '🚫 NO MUTATION\n⚠️ Revisa Bitunix manualmente si tienes una posición abierta.'),
            }
            stage = min(self._failures, 3)
            self.alert('blind:' + str(stage), stages[stage], cooldown=0 if self._failures <= 3 else 300)
            mark, details = None, None
        if now >= self._bias_due:
            self.bias = self.market.bias()
            self._bias_due = now + 60
        data = dict(current_entry_quality(self.bias, mark),
                    volatility=volatility_state(atr, mark) if mark is not None else 'UNKNOWN')
        copilot = render_copilot(data, self.config, position if details else None, details,
                                 sl_status, target, private_ready=self.client.credentials_present)
        decision_key = self.bias['bias'] + ':' + data.get('entry_quality', 'CAUTION')
        if not self._started:
            self._started = True
            status = 'PRIVATE POSITION GUARD DISABLED — credentials absent' if not self.client.credentials_present else (
                'CAPITAL PROTECTION ARMED' if self.config.armed('SL') and self.config.armed('CLOSE') else 'POSITION GUARD READ-ONLY')
            self.alert(self._startup_key, copilot + '\n\nI-GOD TRADE GUARDIAN ONLINE\n' + status + '\nRisk engine active')
            self.store.state['copilot_decision'] = decision_key
            print(status, flush=True)
        if not self._startup_position_checked and private_verified:
            if position is None or details is not None:
                self._startup_position_checked = True
                if position is not None:
                    self.alert(self._startup_key + ':position', '💼 POSICIÓN ABIERTA DETECTADA\n\n' + copilot)
        if self.store.state.get('copilot_decision') != decision_key:
            self.alert('copilot:' + decision_key, copilot)
            self.store.state['copilot_decision'] = decision_key
        self.store.save()
        if now >= self._snapshot_due:
            self.store.append('bias', {'timestamp': now, **data, 'koncorde': diagnostic(),
                                       'risk': details, 'human_snapshot': copilot})
            self._snapshot_due = now + 300
        heartbeat = {'timestamp': now, 'mark': mark, 'bias': self.bias['bias'], 'position': position is not None,
                     'entry_quality': data.get('entry_quality', 'CAUTION'),
                     'risk': details['state'] if details else 'UNKNOWN',
                     'armed': {'sl': self.config.armed('SL'), 'close': self.config.armed('CLOSE')},
                     'last_successful_private_read': self.client.last_private,
                     'last_successful_public_read': self.client.last_public}
        verified_position = private_verified and (position is None or details is not None)
        if position is not None and self.store.attempted('CLOSE', position.position_id):
            verified_position = False  # never report a pre-action position as current
        position_view = None
        if verified_position and position is not None:
            position_view = dict(side=position.side, entry=position.entry, qty=position.qty,
                                 leverage=position.leverage, pnl=position.pnl, liq=position.liq)
        self.command_snapshot.publish(dict(timestamp=now, data=data, mark=mark,
                                           position_verified=verified_position, position=position_view,
                                           risk=details, sl_status=sl_status, stop_target=target,
                                           human_snapshot=copilot,
                                           mode=self.config.mode,
                                           protection=protection_status(self.config, self.client.credentials_present))
                                      if mark is not None and (details is not None or self.bias['bias'] != 'UNKNOWN') else None)
        print(json.dumps(heartbeat), flush=True)
        return heartbeat


def main():
    store = None
    commands = None
    try:
        config = Config.from_env()
        store = Store(config.state_dir)
        client = Bitunix(config, os.getenv('BITUNIX_API_KEY', ''), os.getenv('BITUNIX_API_SECRET', ''))
        guardian = Guardian(client, store, Market(client), Telegram(os.getenv('TELEGRAM_BOT_TOKEN', ''),
                            os.getenv('TELEGRAM_CHAT_ID', ''), alert_chat_id=os.getenv('TELEGRAM_ALERT_CHAT_ID', '')))
        commands = TelegramCommands(os.getenv('TELEGRAM_BOT_TOKEN', ''), os.getenv('TELEGRAM_CHAT_ID', ''),
                                    guardian.command_snapshot, guardian.telegram.send_owner,
                                    enabled=os.getenv('GUARDIAN_ENABLE_COMMANDS', 'false').lower() == 'true')
        commands.start()
        while True:
            started = time.monotonic()
            guardian.cycle()
            time.sleep(max(0, 10 - (time.monotonic() - started)))
    except KeyboardInterrupt:
        pass
    except Exception:
        print('GUARDIAN STOPPED — SAFE FAILURE; NO NEW MUTATION', flush=True)
        raise SystemExit(1) from None
    finally:
        if commands is not None:
            commands.stop()
        if store is not None:
            store.close()


if __name__ == '__main__':
    main()
