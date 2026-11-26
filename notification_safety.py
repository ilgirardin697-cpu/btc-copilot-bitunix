"""Exact presentation seam removal, never a reset of risk/execution baselines."""
IMPORT='from igod_notifications.runtime import install as install_notifications, emit as emit_notification, observer_sender, after_cycle as notifications_after_cycle, shutdown as shutdown_notifications\n'
INSTALL='        install_notifications(guardian)\n'
AFTER='            try:\n                notifications_after_cycle(guardian)\n            except Exception:\n                pass\n'
SHUTDOWN='        shutdown_notifications()\n'
OLD_SEND="self.telegram.send(text if text.startswith(DECISION_PREFIXES) else 'I-GOD TRADE GUARDIAN\\n' + text)"
NEW_SEND="emit_notification(self.telegram, key, text if text.startswith(DECISION_PREFIXES) else 'I-GOD TRADE GUARDIAN\\n' + text, notice=notice)"
OLD_DEF='    def alert(self, key, text, cooldown=300):'
NEW_DEF='    def alert(self, key, text, cooldown=300, notice=None):'
OLD_NOTICE="                       + '\\nLa orden manual se respeta; no se cancela ni reemplaza.', cooldown=0)"
NEW_NOTICE="                       + '\\nLa orden manual se respeta; no se cancela ni reemplaza.', cooldown=0,\n                       notice={'orders': signature, 'target': target, 'risk': details['state']})"
OLD_BLIND="            self.alert('blind:' + str(stage), stages[stage], cooldown=0 if self._failures <= 3 else 300)"
NEW_BLIND="            self.alert('blind:' + str(stage), stages[stage], cooldown=0 if self._failures <= 3 else 300,\n                       notice={'cause': str(error)})"
OLD_ML='MLRSIHost(send=guardian.telegram.send, logger=Telegram._diagnostic)'
NEW_ML='MLRSIHost(send=observer_sender(guardian.telegram), logger=Telegram._diagnostic)'


def normalize_notifications(path,source):
    from guardian_hedge_safety import normalize_readonly
    source=normalize_readonly(path,source)
    if path!='trade_guardian.py' or IMPORT not in source:
        return source
    for fragment in (IMPORT,INSTALL,AFTER,SHUTDOWN):
        if source.count(fragment)!=1:raise AssertionError('Notification seam differs from reviewed fragment')
        source=source.replace(fragment,'',1)
    for new,old in ((NEW_SEND,OLD_SEND),(NEW_ML,OLD_ML),(NEW_DEF,OLD_DEF),(NEW_NOTICE,OLD_NOTICE),(NEW_BLIND,OLD_BLIND)):
        if source.count(new)!=1:raise AssertionError('Notification adapter changed outside presentation')
        source=source.replace(new,old,1)
    return source
