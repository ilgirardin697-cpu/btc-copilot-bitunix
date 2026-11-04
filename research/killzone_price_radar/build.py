"""Export exact PRICE coefficients into an independent Pine; publication remains closed."""
import hashlib
import json
from .core import HERE,verify_freeze,read_json
from .report import OUT,write_json


def pine_function(m):
    lines=['f_predict(array<float> x) =>']
    for k in range(3):lines.append(f'    float z{k} = {m["weights"][0][k]:.17g}')
    for j in range(6):
        lines.append(f'    float v{j} = math.max(-8.0, math.min(8.0, (array.get(x, {j}) - ({m["mean"][j]:.17g})) / {m["scale"][j]:.17g}))')
        for k in range(3):lines.append(f'    z{k} += v{j} * ({m["weights"][j+1][k]:.17g})')
    lines+=['    float largest = math.max(z0, math.max(z1, z2))','    float e0 = math.exp(z0 - largest)',
            '    float e1 = math.exp(z1 - largest)','    float e2 = math.exp(z2 - largest)',
            '    float total = e0 + e1 + e2','    [e0 / total, e1 / total, e2 / total]']
    return '\n'.join(lines)


def scalar_export_check(m,x):
    import math
    z=list(m['weights'][0])
    for j in range(6):
        v=max(-8,min(8,(float(x[j])-m['mean'][j])/m['scale'][j]))
        for k in range(3):z[k]+=v*m['weights'][j+1][k]
    e=[math.exp(t-max(z)) for t in z]
    return [t/sum(e) for t in e]


def main():
    import numpy as np
    from .core import predict
    manifest=verify_freeze();m=read_json('frozen_PRICE.json')
    source=(HERE.parent/'killzone_probability_radar/radar.template.pine').read_text(encoding='utf-8')
    source=source.replace('shorttitle="I-GOD KZ Radar"','shorttitle="I-GOD PRICE Radar"')
    source=source.replace('// Independent research indicator. Original Killzone V3.7 Lite is not changed.',
        '// Frozen PRICE only, post-hoc choice. Original Killzone V3.7 Lite is not changed.')
    source=source.replace('const string MODEL_STATUS = "@@MODEL_STATUS@@"',
        'const string MODEL_STATUS = "NO VALIDADO"\nconst string PROTOCOL_HASH = "'+manifest['protocol_sha256']+'"')
    begin=source.index('float upMove =');end=source.index('[mt, mcTime, mh, ml, mclose]')
    source=source[:begin]+source[end:]
    source=source.replace(' and available4h <= time','')
    start=source.index('    array<float> x = array.from(');end=source.index('\n',start)
    source=source[:start]+'''    array<float> x = array.from(count / 60.0, (price - combinedLow) / (combinedHigh - combinedLow), (price - lOpen) / ahWidth, (partialHigh - partialLow) / ahWidth, (aClose - aOpen) / ahWidth, (combinedHigh - combinedLow) / atr14[1])'''+source[end:]
    old='''            string probabilities = MODEL_VALIDATED ? ",\\\"probabilities\\\":[" + str.tostring(pUpper, "#.############") + "," + str.tostring(pLower, "#.############") + "," + str.tostring(pNeither, "#.############") + "]" : ",\\\"probabilities\\\":null"'''
    replacement='''            // Internal research forecasts only. Never rendered as validated percentages.
            string probabilities = ",\\\"research_probabilities\\\":[" + str.tostring(pUpper, "#.############") + "," + str.tostring(pLower, "#.############") + "," + str.tostring(pNeither, "#.############") + "]"'''
    if source.count(old)!=1:raise ValueError('AUDITED_TEMPLATE_LOG_SURFACE_CHANGED')
    source=source.replace(old,replacement)
    start=source.index('            string payload =');end=source.index('\n',start)
    payload='''            string payload = "IGOD_PRICE_RADAR_V1={\\\"protocol\\\":\\\"IGOD_KILLZONE_PRICE_FORWARD_V1\\\",\\\"protocol_hash\\\":\\\"" + PROTOCOL_HASH + "\\\",\\\"version\\\":\\\"" + MODEL_VERSION + "\\\",\\\"available_at\\\":" + str.tostring(knownAt) + ",\\\"emitted_at\\\":" + str.tostring(timenow) + ",\\\"minute\\\":" + str.tostring(count) + ",\\\"status\\\":\\\"EXPERIMENTAL_NOT_VALIDATED\\\",\\\"origin\\\":\\\"PINE_REALTIME_UNATTESTED\\\",\\\"features\\\":[" + vector + "]" + probabilities + "}"'''
    source=source[:start]+payload+source[end:]
    template=source.replace('@@MODEL_VERSION@@',manifest['model_version'])
    (HERE/'radar.price.template.pine').write_text(template,encoding='utf-8',newline='\n')
    pine=template.replace('@@MODEL_FUNCTION@@',pine_function(m))
    (HERE/'I_GOD_Killzone_Probability_Radar.pine').write_text(pine,encoding='utf-8',newline='\n')
    data=np.load(HERE.parent/'killzone_probability_radar/artifacts/features_and_labels.npz')
    x=data['X'][::17,::7,:6].reshape(-1,6)
    error=float(abs(predict(x)-np.array([scalar_export_check(m,v) for v in x])).max())
    write_json(OUT/'pine_parity_status.json',dict(model_version=manifest['model_version'],model_sha256=manifest['model_sha256'],
        offline_scalar_vectors=len(x),offline_scalar_max_error=error,
        offline_scope='ARITHMETIC_ONLY_NOT_ACTUAL_PINE_EXECUTION_NOT_INDEPENDENT_PARITY',
        actual_tradingview_records=0,actual_complete_cycles=0,compile='PENDING',realtime='PENDING',reload='PENDING',
        prospective_cycles=0,publication_enabled=False))
    artifacts={}
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name!='artifact_manifest.json':
            raw=p.read_bytes();artifacts[p.name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    write_json(OUT/'artifact_manifest.json',artifacts)
    print(json.dumps(dict(version=manifest['model_version'],PRICE_changed=False,publication=False,actual_TV_records=0)))


if __name__=='__main__':main()
