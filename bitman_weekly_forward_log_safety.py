"""CI only: restore the exact external logging imports before old V1 guards."""
from bitman_weekly_forward.safety import ADDITIONS as ORIGINAL_ADDITIONS,normalize_source as original_normalize
from daily_plan_safety import FRAGMENTS,normalize_router
from capital_v2_safety import FRAGMENTS as CAPITAL_FRAGMENTS,normalize_capital

ADDITIONS = dict(ORIGINAL_ADDITIONS)
ADDITIONS['guardian_commands.py'] = tuple(FRAGMENTS)
ADDITIONS['trade_guardian.py'] = tuple(ADDITIONS['trade_guardian.py'])+CAPITAL_FRAGMENTS


def normalize_source(path,source):
    if path=='guardian_commands.py':
        return normalize_router(source)
    if path=='trade_guardian.py':
        source=normalize_capital(source)
        new='                from bitman_weekly_forward_logging import after_cycle\n'
        old='                from bitman_weekly_forward.host import after_cycle\n'
        if source.count(new)!=1:raise AssertionError('Diagnostic hook differs from audited import')
        source=source.replace(new,old,1)
    elif path=='mlrsi_safety_audit.py':
        new='from bitman_weekly_forward_log_safety import normalize_source'
        old='from bitman_weekly_forward.safety import normalize_source'
        if source.count(new)!=2:raise AssertionError('Diagnostic audit adapter differs')
        source=source.replace(new,old)
    return original_normalize(path,source)
