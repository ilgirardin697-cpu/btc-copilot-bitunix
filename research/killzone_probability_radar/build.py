"""Build auditable artifacts and a publication-gated independent Pine indicator."""
import csv
import hashlib
import html
import json
from pathlib import Path
import shutil
import numpy as np
from .data import HERE, CACHE, protocol_hash, HOUR
from .dataset import FEATURES, schedule, window
from .model import predict
from .parity import pine_arithmetic

OUT = HERE/'artifacts'


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False, ensure_ascii=False)+'\n', encoding='utf-8', newline='\n')


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fields, lineterminator='\n'); w.writeheader(); w.writerows(rows)


def pine_function(m):
    lines = ['f_predict(array<float> x) =>']
    for k in range(3): lines.append(f'    float z{k} = {m["weights"][0][k]:.17g}')
    for j, ix in enumerate(m['indices']):
        lines.append(f'    float v{j} = math.max(-8.0, math.min(8.0, (array.get(x, {ix}) - ({m["mean"][j]:.17g})) / {m["scale"][j]:.17g}))')
        for k in range(3): lines.append(f'    z{k} += v{j} * ({m["weights"][j+1][k]:.17g})')
    lines += ['    float largest = math.max(z0, math.max(z1, z2))',
              '    float e0 = math.exp(z0 - largest)', '    float e1 = math.exp(z1 - largest)',
              '    float e2 = math.exp(z2 - largest)', '    float total = e0 + e1 + e2',
              '    [e0 / total, e1 / total, e2 / total]']
    return '\n'.join(lines)


def svg_example(day, row, report, h):
    from datetime import date, datetime, timezone
    s = schedule(date.fromisoformat(day)); bars = window(h, s['asia'], s['end'])
    lo = min(min(bars[:, 3]), row['final_bottom']); hi = max(max(bars[:, 2]), row['final_top']); span = hi-lo
    lo -= span*.05; hi += span*.05
    def x(t): return 60+(t-s['asia'])/(s['end']-s['asia'])*820
    def y(p): return 470-(p-lo)/(hi-lo)*350
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1250" height="600" viewBox="0 0 1250 600">',
             '<rect width="1250" height="600" fill="#101c29"/>',
             f'<text x="30" y="30" fill="white" font-family="sans-serif">{day} · BINANCE SPOT H1 · HISTORICAL REPLAY, NOT FORWARD / NOT TRADINGVIEW</text>']
    for left, right, color, name in [(s['asia'], s['asia_end'], '#134f6b', 'ASIA'), (s['london'], s['close'], '#4c4163', 'LONDON')]:
        b = window(h, left, right)
        parts.append(f'<rect x="{x(left):.2f}" y="{y(max(b[:,2])):.2f}" width="{x(right)-x(left):.2f}" height="{y(min(b[:,3]))-y(max(b[:,2])):.2f}" fill="{color}" stroke="#7791a8"/>')
        parts.append(f'<text x="{x(left):.2f}" y="90" fill="#b7c9d8">{name}</text>')
    for b in bars:
        xx=x(b[0]+HOUR/2); color='#40d3a0' if b[4]>=b[1] else '#ee7687'
        parts.append(f'<path d="M{xx:.2f},{y(b[2]):.2f}V{y(b[3]):.2f}" stroke="{color}"/><rect x="{xx-5:.2f}" y="{min(y(b[1]),y(b[4])):.2f}" width="10" height="{max(1,abs(y(b[1])-y(b[4]))):.2f}" fill="{color}"/>')
    for price, name, color in [(row['final_top'], 'SUPERIOR FINAL', '#e77e82'), (row['final_bottom'], 'INFERIOR FINAL', '#55d1aa')]:
        parts.append(f'<path d="M{x(s["close"]):.2f},{y(price):.2f}H890" stroke="{color}" stroke-dasharray="5 4"/><text x="600" y="{y(price)-8:.2f}" fill="{color}">{name} {price:.2f}</text>')
    parts.append(f'<rect x="{x(s["radar"]):.2f}" y="100" width="{x(s["close"])-x(s["radar"]):.2f}" height="390" fill="#d2aa46" opacity=".18"/>')
    for t, label in [(s['radar'], '05:00 NY'), (s['close'], '06:00 NY / LABEL START'), (s['end'], '20:00 NY')]:
        yy = 540 if t == s['close'] else 520
        parts.append(f'<text x="{x(t)-30:.2f}" y="{yy}" fill="#cad8e5" font-size="12">{label}</text>')
    parts += [f'<text x="930" y="70" fill="#7fe3f4">I-GOD KILLZONE RADAR</text>',
              '<text x="930" y="100" fill="#e8c47d">NO VALIDADO</text>',
              '<text x="930" y="130" fill="#cad8e5">SUPERIOR: —</text>',
              '<text x="930" y="155" fill="#cad8e5">INFERIOR: —</text>',
              '<text x="930" y="180" fill="#cad8e5">NINGUNO: —</text>',
              '<text x="930" y="210" fill="#e8c47d" font-size="12">SIN PROBABILIDADES VALIDADAS</text>',
              f'<text x="30" y="560" fill="#b7c9d8">Outcome observado: {row["label"]}. Targets finales dibujados SOLO desde las 06:00. No eran conocidos durante 05:00-06:00.</text>',
              '<text x="30" y="585" fill="#b7c9d8">Ejemplo elegido: primer ciclo de test de cada clase. No demuestra acierto, rentabilidad ni ejecución Pine.</text>', '</svg>']
    (OUT/('example_'+row['label']+'.svg')).write_text('\n'.join(parts)+'\n', encoding='utf-8', newline='\n')


def main():
    OUT.mkdir(exist_ok=True)
    report = json.loads((CACHE/'training_results.json').read_text()); a = np.load(CACHE/'dataset.npz')
    cycles = json.loads((CACHE/'cycles.json').read_text())['cycles']
    model = report['models'][report['selected_on_validation']]
    model_hash = hashlib.sha256(json.dumps(model, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    version = 'KZR_V1_'+model_hash[:12]
    report.update(model_version=version, model_hash=model_hash)
    write_json(OUT/'model_validation.json', report)
    write_json(OUT/'data_manifest.json', json.loads((CACHE/'download_manifest.json').read_text()))
    write_json(OUT/'excluded_partial_archive_candles.json', json.loads((CACHE/'quality.json').read_text()))
    write_csv(OUT/'cycles.csv', cycles); write_csv(OUT/'monthly.csv', report['monthly']); write_csv(OUT/'per_minute_test.csv', report['per_minute'])
    shutil.copyfile(CACHE/'dataset.npz', OUT/'features_and_labels.npz')
    source = (HERE/'radar.template.pine').read_text(encoding='utf-8')
    source = source.replace('@@MODEL_FUNCTION@@', pine_function(model)).replace('@@MODEL_VERSION@@', version).replace('@@MODEL_STATUS@@', report['model_status'])
    (HERE/'I_GOD_Killzone_Probability_Radar.pine').write_text(source, encoding='utf-8', newline='\n')
    vectors = a['X'][::19, ::7].reshape(-1, 14)
    expected = predict(model, vectors[:, None, :])[:, 0]
    mirror = np.array([pine_arithmetic(model, v) for v in vectors])
    max_error = float(abs(expected-mirror).max())
    write_json(OUT/'pine_comparison.json', dict(local_scalar_checks=len(vectors), local_max_absolute_probability_error=max_error,
        local_status='PASS' if max_error < 1e-12 else 'FAIL',
        local_scope='OFFLINE_ARITHMETIC_MIRROR_NOT_EXECUTED_PINE_NOT_INDEPENDENT_PARITY',
        actual_tradingview_records_compared=0, actual_pine_compilation='NOT_AVAILABLE_IN_THIS_ENVIRONMENT',
        actual_realtime_or_reload_test='PENDING_OWNER_TRADINGVIEW_TEST', publication_gate=False))
    h = np.load(CACHE/'1h.npy', mmap_mode='r'); examples = []
    for label in ('SUPERIOR_FIRST', 'INFERIOR_FIRST', 'NEITHER'):
        row = next(r for r in cycles if r['cycle'] >= '2025-01-01' and r['label'] == label)
        svg_example(row['cycle'], row, report, h)
        index = np.flatnonzero(a['days'] == row['cycle'])[0]
        for minute in (0, 15, 30, 59):
            examples.append(dict(mode='OFFLINE_HISTORICAL_REPLAY_NOT_FORWARD_NOT_TRADINGVIEW',
                cycle=row['cycle'], minute=minute, available_at=row['radar']+minute*60000,
                features=dict(zip(FEATURES, a['X'][index, minute].tolist())), panel_probability_fields=None,
                model_status=report['model_status'], outcome_known_only_after_london=row['label']))
    write_json(OUT/'closed_minute_examples.json', examples)
    prior_test = report['partitions']['test']['PRIOR']; selected = report['selected_on_validation']
    text = f'''# I-GOD Killzone Probability Radar — entrenamiento y validación

**Resultado: {report['model_status']}. SIN PROBABILIDADES VALIDADAS.**
El indicador se entrega con panel y publicación cerrada. No se cambia Killzone V3.7 Lite.
Modelo seleccionado únicamente en validación: **{selected}**. Versión `{version}`.
Fallos del gate predeclarado: `{report['gate_failures']}`. No se cambia de candidato después del test.

## Protocolo, mercado y tiempo

Congelado en affca18 antes de descargar/calcular outcomes. SHA256 `{protocol_hash()}`.
Binance Spot BTCUSDT, no Futures/Bitunix. Train 2022–2023; validación 2024;
test posterior enero2025–octubre2026. Diciembre2021 inicializa indicadores.
Último día de train/validación excluido como embargo. NO VIRGIN HOLDOUT.
La historia de mercado ya apareció en otras investigaciones; esto no es validación prospectiva.

PINE_A: America/New_York con DST, Asia20–23 (4 H1), Londres02–05 (4 H1).
Cada ciclo tiene 60 estimaciones as-of05:00,05:01,…05:59. A05:00 se conocen solo
las H1 anteriores; a05:mm solo se añaden mm minutos cerrados de la última H1.
No hay nueva predicción a06:00: entonces se fijan los targets y comienza el outcome.
El primer toque se busca entre06:00 inclusive y20:00 exclusivo, con1m; ambos en la misma
primera barra1m sería AMBIGUO, no NINGUNO. Las franjas500 y TP±200 no forman parte del label.
No se usan targets definitivos ni el high/low/close final de05H1 como variables predictoras.

## Datos y exclusiones

117 ZIP oficiales con SHA256 comparado con CHECKSUM oficial. Raw local/ignorado.
43101 H1 válidas,2541519 minutos válidos. Tres registros con closeTime anticipado
quedan documentados y excluidos sin modificar el original; dejan gaps explícitos.
También hay huecos de mercado. Se reinicia el warmup tras discontinuidad H1 y se exige
igualdad exacta OHLC entre1m y H1 en todas las horas usadas para predicción/outcome.
{len(cycles)} ciclos de calendario;{len(a['Y'])} utilizables;{sum(r['status']=='INCOMPLETE' for r in cycles)} incompletos;
{sum(r['status']=='AMBIGUOUS' for r in cycles)} ambiguos. Las cinco fechas DST de primavera no tienen02 local
y NO se convierten artificialmente en cuatro velas. Todos los rechazos están en cycles.csv.
105300 filas de estimación NO son105300 observaciones independientes: la unidad es el ciclo.

## Modelos sin búsqueda de parámetros

PRIOR: frecuencias de clase de train con Laplace1. PRICE: seis variables de precio/rangos parciales.
PRICE_MOMENTUM añade AO5/34, slope, ADX14/14, slope y balanceDI. PRICE_BBWP añade
BBWP7/ranking101 y slope. PRICE_4H añade variación de los dos últimos cierres4H confirmados.
H1 AO/ADX/DMI/ATR/BBWP se congelan al cierre05:00 durante la hora predictiva; precio parcial sí cambia.
No se calcula con una4H abierta. El engine congelado se importa solo para fórmulas públicas offline,
sin cambiarlo; no se afirma paridad propietaria de Bitman.
Softmax lineal L2=.01, z-score solo train, clip±8; Adam determinista lr=.03, máximo3000 pasos,
tolgrad1e-7. Sin calibrador posterior, búsqueda de umbrales ni combinaciones exhaustivas.

## Resultados por partición

Multiclass Brier=sum de tres errores cuadrados (menor es mejor); log-loss natural.
IC95: diferencias emparejadas con2000 bootstraps circulares por bloques de7 ciclos.
Calibración: macroECE,10 bins por clase; todos los bins con sus n en model_validation.json.
Las filas/minutos del mismo ciclo mantienen el mismo peso. No se estima n efectivo como60×días.

| Partición | Modelo | Ciclos | Brier | Log-loss | MacroECE | Ganancia Brier vs PRIOR [IC95] |
|---|---|---:|---:|---:|---:|---|
'''
    for part in ('train', 'validation', 'test'):
        for name, r in report['partitions'][part].items():
            text += f"|{part}|{name}|{r['cycles']}|{r['brier']:.6f}|{r['logloss']:.6f}|{r['calibration']['macro_ece']:.6f}|{r['brier_gain_vs_prior']:.6f} {r['brier_gain_ci95']}|\n"
    text += '\n## Incremento sobre precio, estabilidad y limitaciones\n\n'
    for part in ('validation', 'test'):
        r=report['partitions'][part][selected]
        text += f"- {part}: {selected}−PRICE, ganancia Brier {r['gain_vs_price']:.6f}; IC95 {r['gain_vs_price_ci95']}.\n"
    text += f"\nMeses de test con mejora vs PRIOR:{report['positive_test_months']}/{report['test_months']}.\n"
    for era,r in report['eras'].items(): text += f"- {era}: n={r['cycles']}; ganancia Brier vs PRIOR={r['brier_gain_vs_prior']:.6f}.\n"
    text += '''
monthly.csv contiene los cinco modelos en cada mes y per_minute_test.csv los60 minutos;
no se selecciona retrospectivamente el minuto mejor. La comparación por eras usa el MISMO
fit congelado: es una evaluación walk-forward sin actualización, no múltiples retrainings.
La selección entre cuatro candidatos usa2024; la incertidumbre de esa selección y la reutilización
de la historia limitan la evidencia. Un resultado histórico favorable tampoco verifica el feed Pine.

## Python frente a Pine — alcance exacto

El exportador escribe los mismos coeficientes de64bits en Pine. Un espejo escalar comprueba
la aritmética softmax con vectores históricos; NO es ejecución de Pine ni evidencia independiente.
Registros numéricos REALES de este radar en TradingView comparados: **0**.
Compilación en TradingView y pruebas reales de actualización/reload: **PENDIENTES**.
El comparador parity.py admite Pine Logs reales para detectar diferencias por feature y timestamp.
Los64 registros anteriores validan Killzone, NO este nuevo radar. No se reutilizan como paridad del radar.

## Entrega, no repainting y fiabilidad

Pine procesa request.security_lower_tf("1") con tiempos y prefijos contiguos; no incorpora
minutos abiertos. Histórico se reconstruye desde arrays sin leer el final de Londres como predictor.
En tiempo real solo se registra la última información realmente disponible, no se emiten60 registros
retroactivos al conectar. El reloj no dispara Pine: hace falta un update/tick; puede haber retraso.
Si hay huecos se muestra incompleto/última información; no se inventan minutos.
No hay ausencia absoluta de repainting: feeds revisados, arrays limitados, distinta profundidad y
reload pueden cambiar reconstrucciones. varip/Pine Logs no son un journal durable. Se facilita
captura offline append-only/hash-chain de logs entregados por el propietario; nunca se mezcla replay
histórico con observación forward. No existe receptor/webhook, alertas ni despliegue de esa captura.

## Ejemplos

example_SUPERIOR_FIRST.svg, example_INFERIOR_FIRST.svg y example_NEITHER.svg son los primeros
ciclos de test de cada clase, elegidos para auditoría, NO una muestra aleatoria de rendimiento.
closed_minute_examples.json contiene features reales a05:00/15/30/59 y el panel sin porcentajes.
Son reconstrucciones offline, no capturas de TradingView ni predicciones forward observadas.

**Decisión: NO PUBLICAR PROBABILIDADES.** Mantener NO VALIDADO. No hay permiso de trading.
No se retocan reglas ni se sustituye el candidato elegido para obtener un resultado positivo.
Fórmulas, sesiones y niveles originales, OWNER_B/C y producción permanecen intactos.

Documentación oficial consultada:
- [Arrays LTF y datos confirmados](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/).
- [Límites por plan](https://www.tradingview.com/pine-script-docs/writing/limitations/).
- [Repainting y revisiones](https://www.tradingview.com/pine-script-docs/concepts/repainting/).
- [Formato público Binance](https://github.com/binance/binance-public-data/blob/master/README.md).

SHADOW ONLY. TRADE AUTHORITY: NONE.
'''
    (OUT/'MODEL_TRAINING_VALIDATION.md').write_text(text, encoding='utf-8', newline='\n')
    manifest = {}
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != 'artifact_manifest.json':
            manifest[path.name] = dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    write_json(OUT/'artifact_manifest.json', manifest)
    print(json.dumps(dict(model=version, status=report['model_status'], numerical_mirror_max_error=max_error,
                          actual_tradingview_records=0, publication_gate=False)))


if __name__ == '__main__':
    main()
