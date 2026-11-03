"""Audit the supplied source bytes; generate a SEPARATE passive Pine Logs copy."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from .parity import NUMERIC, BOOLEAN
from .profiles import SOURCE_SHA256

HERE = Path(__file__).resolve().parent
SOURCE_HASH = SOURCE_SHA256
SOURCE = HERE/'source/Killzone_H1_v3_7_Lite.txt'


def audit():
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_HASH:
        raise ValueError('SUPPLIED_SOURCE_MODIFIED')
    text = raw.decode('utf-8-sig')
    lines = text.splitlines()
    inputs = []
    formulas = []
    important = ('aHigh','aLow','lHigh','lLow','amplitude','topInAsia','bottomInAsia',
                 'topBoxHeight','bottomBoxHeight','topAnchor','bottomAnchor',
                 'newTopTarget','newBottomTarget','highGuideValue','lowGuideValue',
                 'highConfirmed','lowConfirmed','measureNow','upperZoneNow','lowerZoneNow')
    for index, line in enumerate(lines,1):
        if 'input.' in line:
            inputs.append(dict(line=index,text=line))
        if any(re.match(r'(?:(?:float|bool) )?'+name+r'\s*(?::=|=)',line) for name in important):
            formulas.append(dict(line=index,text=line))
    return dict(supplied_source_sha256=SOURCE_HASH, bytes=len(raw),lines=len(lines),
                declaration='Pine v6 / V3.7 Lite / educational adaptation',
                author_identity='NOT_INDEPENDENTLY_VERIFIED',alpha_parity='NOT_PROVEN',
                inputs=inputs,formula_lines=formulas,
                executable_comparison='REPORTED_SEPARATELY_IN_REAL_TRADINGVIEW_PARITY_ARTIFACT',
                source_is_not_profitability_evidence=True)


def diagnostic_bytes():
    """Original bytes are an exact prefix. Appended logs do not alter expressions.

    This generated copy has NOT been compiled in TradingView in this environment.
    No alertcondition or sender is added. Logging is opt-in and bounded to a day.
    """
    audit()
    fields = []
    def s(name,value):
        fields.append((name, "'\"' + "+value+" + '\"'"))
    def n(name,value):
        fields.append((name,'kzDiagNumber('+value+')'))
    def b(name,value):
        fields.append((name,'str.tostring('+value+')'))
    s('tickerid','syminfo.tickerid');s('timeframe','timeframe.period')
    s('source_sha256',repr(SOURCE_HASH))
    n('mintick','syminfo.mintick')
    b('standard_chart','chart.is_standard')
    s('asiaTZ','asiaTZ');s('londonTZ','londonTZ')
    for name in ('asiaStartHour','asiaCandles','londonStartHour','londonCandles',
                 'topInsetPct','bottomInsetPct','topUSD','bottomUSD'):
        n(name,name)
    for name in ('time','time_close','open','high','low','close'):
        n(name,name)
    b('confirmed','barstate.isconfirmed')
    for name in NUMERIC:
        n(name,name)
    for name in BOOLEAN:
        b(name,name)
    expression = "'KZ_PARITY_V37={' + " + " + ',' + ".join(
        repr('"'+key+'":')+' + '+value for key,value in fields) + " + '}'"
    suffix = '''
// DIAGNOSTIC COPY ONLY. Original source above remains unchanged.
// Opt-in, closed H1, bounded UTC range. NO automated activation.
bool kzDiagEnabled = input.bool(false, "Enable diagnostic Pine Logs", group="Offline parity")
int kzDiagStart = input.time(timestamp("2026-10-31T00:00:00+00:00"), "Log from UTC", group="Offline parity")
int kzDiagEnd = input.time(timestamp("2026-11-02T00:00:00+00:00"), "Log until UTC (exclusive)", group="Offline parity")
kzDiagNumber(float value) => na(value) ? "null" : str.tostring(value, "0.################")
if kzDiagEnabled and isH1 and barstate.isconfirmed and time >= kzDiagStart and time < kzDiagEnd
    log.info(''' + expression + ''')
'''
    return SOURCE.read_bytes() + suffix.encode('utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--diagnostic-copy',type=Path)
    args = p.parse_args()
    print(json.dumps(audit(),ensure_ascii=False,indent=2))
    if args.diagnostic_copy:
        with args.diagnostic_copy.open('xb') as f:
            f.write(diagnostic_bytes())


if __name__ == '__main__':
    main()
