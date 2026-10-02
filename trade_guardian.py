"""Independent disarmed-by-default manual copilot and liquidation emergency guard."""
from dataclasses import asdict
import json
import os
import time
from guardian_bitunix import Bitunix
from guardian_market import Market
from guardian_risk import Config, SafetyError, risk, catastrophic_stop, assess_orders
from guardian_store import Store
from guardian_telegram import Telegram
from koncorde_shadow import diagnostic
from guardian_signals import volatility_state


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
        self._failures = 0

    def alert(self, key, text, cooldown=300):
        last = self.store.state.setdefault('alerts', {}).get(key, 0)
        if last and self.clock() - last < cooldown:
            return
        self.store.append('alerts', {'timestamp': self.clock(), 'key': key, 'text': text})
        self.store.state['alerts'][key] = self.clock()
        self.store.save()
        try:
            self.telegram.send('I-GOD TRADE GUARDIAN\n' + text)
        except Exception:
            pass

    def _confirmed(self, row, result):
        confirmed = dict(row, status='CONFIRMED', timestamp=self.clock(), result=result)
        self.store.append('actions', confirmed)
        if row['action'] == 'CLOSE':
            until = self.clock() + self.config.lockout_minutes * 60
            self.store.state['lockout_until'] = until
            self.store.save()
            self.alert('closed:' + row['positionId'], 'EMERGENCY CLOSE CONFIRMED\nPosition: ' + row['positionId'])

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
        try:
            response = self.client.execute(permit)
            row = dict(row, status='RESPONSE', timestamp=self.clock(), response=response)
            self.store.append('actions', row)
        except SafetyError:
            self.store.append('actions', dict(row, status='RESPONSE', timestamp=self.clock(), result='AMBIGUOUS'))
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
        flow = self.bias.get('flow', 'UNKNOWN')
        ratio = self.bias.get('taker_buy')
        flow_line = f'{flow} ({ratio:.1%} taker buy)' if isinstance(ratio, (float, int)) else flow
        return (f'{position.side} BTCUSDT\nEntry: {position.entry:g}\nSize: {position.qty:g}\n'
                f'Leverage: {position.leverage:g}x\nPnL: {position.pnl:g}\nMark: {details["mark"]:g}\n'
                f'Liquidation: {position.liq:g}\nMarket bias: {self.bias["bias"]}\n'
                f'TREND: 4H {self.bias.get("trend4", "UNKNOWN")}; 1H {self.bias.get("trend1", "UNKNOWN")}\n'
                f'MOMENTUM: ML_RSI27_REAL LOW/RSI27/EMA4 {self.bias.get("momentum", "UNKNOWN")} '
                f'(GREEN EVENT={self.bias.get("green_event", False)}; RED EVENT={self.bias.get("red_event", False)})\n'
                f'FLOW: {flow_line}\nSTRUCTURE: 15m {self.bias.get("structure", "UNKNOWN")}\n'
                f'WHY: {self.bias.get("why", "Insufficient evidence")}\n'
                f'Risk: {details["state"]}\nLiq distance: {details["distance_pct"]:.2%}\n'
                f'ATR1H: {details["atr"]}\nATR%: {details["atr_pct"]}\n'
                f'Volatility: {volatility_state(details["atr"], details["mark"])}\n'
                f'Liq distance ATR: {details["distance_atr"]}\n'
                f'Existing SL: {orders}\nCatastrophic SL target: {target}')

    def cycle(self):
        now = self.clock()
        # CAPITAL first. Direction downloads never delay an emergency action.
        position, details = None, None
        try:
            mark = self.client.mark()
            atr = self.market.venue_atr()
            if self.client.credentials_present:
                clean = self.reconcile()
                position = self.client.position()
                previous = self.store.state.get('position_id')
                if position is None:
                    if previous:
                        self.store.append('positions', {'timestamp': now, 'event': 'MANUAL_CLOSE_DETECTED', 'positionId': previous})
                        self.alert('manual:' + previous, 'MANUAL_CLOSE_DETECTED\n' + previous)
                    self.store.state['position_id'] = None
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
                                   'GUARDIAN EMERGENCY\n' + text)
                        self._act('CLOSE', position, atr)
                        emergency_processed = True
                    if previous != position.position_id:
                        self.store.append('positions', {'timestamp': now, 'event': 'NEW_POSITION_DETECTED', **asdict(position)})
                        self.alert('new:' + position.position_id, 'NEW POSITION DETECTED\n' + text)
                        if now < self.store.state.get('lockout_until', 0):
                            self.alert('lockout:' + position.position_id, '🚨 GUARDIAN LOCKOUT VIOLATION\nApp trading is not physically blocked\n' + text)
                    self.store.state['position_id'] = position.position_id
                    opposite = ('LONG_ALLOWED' if position.side == 'SHORT' else 'SHORT_ALLOWED')
                    if self.bias['bias'] == opposite:
                        self.alert('conflict:' + position.position_id + opposite,
                                   '⚠️ TRADE AGAINST BIAS\nCONSIDER EXIT / REDUCE\nDO NOT ADD\nGuardian automatic close for direction: NO\n' + text)
                    elif previous == position.position_id and self.store.state.get('position_bias') != self.bias['bias']:
                        self.alert('aligned:' + position.position_id + self.bias['bias'], 'POSITION CONTEXT UPDATED\n' + text)
                    self.store.state['position_bias'] = self.bias['bias']
                    if details['state'] != 'NORMAL':
                        self.alert('risk:' + position.position_id + details['state'],
                                   ('🚨 GUARDIAN EMERGENCY' if details['state'] == 'EMERGENCY' else '🚨 LIQUIDATION DANGER' if details['state'] == 'DANGER' else 'LIQUIDATION WARNING') + '\n' + text)
                    if 'EXISTING_SL_CLOSER_TO_LIQUIDATION_OR_UNVERIFIED' in sl_status:
                        self.alert('weaker:' + position.position_id, '⚠️ EXISTING SL IS CLOSER TO LIQUIDATION THAN GUARDIAN SAFE LIMIT OR PROTECTION UNVERIFIED\nManual order untouched')
                    if 'EXISTING_TP_OR_UNKNOWN_UNTOUCHED' in sl_status:
                        self.alert('tp-only:' + position.position_id, 'EXISTING TP/SL HAS NO VERIFIED CATASTROPHIC STOP\nGuardian will not replace or cancel the existing order')
                    if clean and position.leverage >= 2:
                        if details['state'] == 'EMERGENCY' and not emergency_processed:
                            self._act('CLOSE', position, atr)
                        elif not orders and target is not None:
                            self._act('SL', position, atr)
                self.store.save()
            self._failures = 0
        except SafetyError as error:
            self._failures += 1
            self.alert('blind', '🚨 GUARDIAN BLIND\nFresh venue state cannot be verified; NO MUTATION\n' + str(error))
            mark, details = None, None
        if now >= self._bias_due:
            self.bias = self.market.bias()
            self._bias_due = now + 60
        if not self._started:
            self._started = True
            status = 'PRIVATE POSITION GUARD DISABLED — credentials absent' if not self.client.credentials_present else (
                'CAPITAL PROTECTION ARMED' if self.config.armed('SL') and self.config.armed('CLOSE') else 'POSITION GUARD READ-ONLY')
            self.alert('startup:' + str(int(now)), f'I-GOD TRADE GUARDIAN ONLINE\n{status}\nMode: {self.config.mode}\n'
                       f'Place SL armed: {self.config.armed("SL")}\nFlash close armed: {self.config.armed("CLOSE")}\n'
                       f'Symbol: BTCUSDT\nMarket bias: {self.bias["bias"]}\n'
                       f'TREND 4H/1H: {self.bias.get("trend4", "UNKNOWN")}/{self.bias.get("trend1", "UNKNOWN")}\n'
                       f'MOMENTUM ML_RSI27_REAL LOW/RSI27/EMA4: {self.bias.get("momentum", "UNKNOWN")}\n'
                       f'FLOW: {self.bias.get("flow", "UNKNOWN")}\n'
                       f'STRUCTURE 15m: {self.bias.get("structure", "UNKNOWN")}\n'
                       f'WHY: {self.bias.get("why", "Insufficient evidence")}\n'
                       f'Last closed 1H: {self.bias.get("last_closed_1h")}\nRisk engine active')
            print(status, flush=True)
        if now >= self._snapshot_due:
            self.store.append('bias', {'timestamp': now, **self.bias, 'koncorde': diagnostic(), 'risk': details})
            self._snapshot_due = now + 300
        heartbeat = {'timestamp': now, 'mark': mark, 'bias': self.bias['bias'], 'position': position is not None,
                     'risk': details['state'] if details else 'UNKNOWN',
                     'armed': {'sl': self.config.armed('SL'), 'close': self.config.armed('CLOSE')},
                     'last_successful_private_read': self.client.last_private,
                     'last_successful_public_read': self.client.last_public}
        print(json.dumps(heartbeat), flush=True)
        return heartbeat


def main():
    store = None
    try:
        config = Config.from_env()
        store = Store(config.state_dir)
        client = Bitunix(config, os.getenv('BITUNIX_API_KEY', ''), os.getenv('BITUNIX_API_SECRET', ''))
        guardian = Guardian(client, store, Market(client), Telegram(os.getenv('TELEGRAM_BOT_TOKEN', ''), os.getenv('TELEGRAM_CHAT_ID', '')))
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
        if store is not None:
            store.close()


if __name__ == '__main__':
    main()
