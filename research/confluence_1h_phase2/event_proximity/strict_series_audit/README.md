# Fase4A — regla estricta original: tendencia frente a pececillos

**Respuesta: 7 señales, 3LONG y4SHORT, y7 operaciones en cada escenario2R/3R.**
BASE reproduce las0 señales de PR #46. **INCONCLUSO**, sin relajación de reglas.

El [informe](F4A_RESULTS.md) contiene embudo, resultados anuales y por lado,
incertidumbre, controles y el caso de noviembre separado. `artifacts/` conserva
todas las horas, decisiones, operaciones, equity, controles y escenarios funding.

Esta rama añade solamente `strict_series_audit/` sobre PR #48
`384032d7917e354552c5842a74d3f3f72918ac34`. Las PR #46/#47/#48, sus resultados,
fórmulas y protocolos permanecen intactos. No se llama al detector de proximidad.

## Único cambio y congelamiento

```python
view = dict(features)
view['kon_trend'] = features['minnows']
return original_signals(view)
```

La media roja sigue siendo **EMA15 de tendencia**. Cambia la serie cruzada y su
signo previo, no la roja. ADX14/14 con descenso previo desde>40, AO5/34 con dos
pendientes, BBWP7/100 literal>85 y ATR14 no cambian. Tampoco se altera el simulador.

`protocol.json` quedó registrado antes de medir resultados en
`e626d46d278f115947a5ae69a2e8b6999401a272`; SHA256
`59d72126409f2882bc0dbdda1ef5719ad2530be1132e7d7eb10007b2dbcbe99d`.
La función de sustitución y el evaluador se registraron en `55b904a` antes de
ejecutar. La motivación es retrospectiva, informada por la identificación visual
y por el hallazgo comunicado de otra auditoría. **NO VIRGIN HOLDOUT.** No se ha
recibido un nuevo ZIP identificable de esa segunda auditoría en esta tarea; se
comprueba directamente el hallazgo comunicado, sin atribuirle pruebas no leídas.

## Reproducir offline

Python3.12 y dependencias originales del research; matplotlib solo para gráficos.

```text
python -m research.confluence_1h_phase2.event_proximity.strict_series_audit.evaluate --cache market_cache --out resultados_nuevos
python -m unittest research.confluence_1h_phase2.event_proximity.strict_series_audit.test_strict_series -v
python -m unittest discover -v
```

`market_cache` debe ser el cache original de PR #46 o su copia íntegra incluida
en el ZIP de auditoría. El loader original verifica el NPZ y los153 inputs raw
por SHA256; no descarga ni rellena huecos. El evaluador no ejecuta las antiguas
sensibilidades de umbrales, nuevos filtros, ADXdesde-mínimos ni nuevas ventanas.

Para regenerar gráficos sobre los resultados entregados:

```text
python -m research.confluence_1h_phase2.event_proximity.strict_series_audit.plots --cache market_cache
```

El evaluador conserva exactamente FULL, DEVELOPMENT, TEST y las cuatro WF de
PR #46, con el embargo/purga original. Usa200 controles originales por escenario,
emparejados por mes, lado y régimen4H cerrado, tanto en FULL como TEST.
Los intervalos son97.5% para dos targets co-primarios y bloques calendario de7días.
Los días sin eventos permanecen en el denominador del procedimiento original.

## Interpretar los archivos

* `signals_all.csv.gz`: 70.128 filas, 35.064 horas por variante, incluidos los
  rechazos. Mismos inputs comunes; no son70.128 muestras independientes.
* `trades_all.csv`: libros y ventanas etiquetados. **Solo FULL/COMBINED** cuenta
  las7 oportunidades únicas por target. LONG_ONLY/SHORT_ONLY son cuentas
  contrafactuales, no asignaciones simultáneas. No sumar escenarios ni ventanas.
* `annual.csv`: cohortes por año de entrada y curva anual de la cuenta continua;
  no se reinicia capital cada año. `net_usdt` atribuye todo el trade a su entrada;
  `calendar_net_change_usdt` sigue los cambios de equity en el calendario.
* `metrics.csv`: los netos son del escenario funding indicado. La columna
  `exact_net_usdt` vacía significa que no está verificado ese punto exacto.
* `funding_bounds.csv`: alternativa optimista de marcas ausentes, siempre separada.
* `random_controls.csv.gz`: todos los ensayos, incluyendo los0-eventos de BASE;
  no se produce un p-value de permutación ni se interpreta n=1 como evidencia.
* `november_incident.json`: señal a05:00Madrid en ambas venues, referencia de
  primera apertura y slippage modelado. No contiene PnL del episodio ni lo
  presenta como validación OOS o como un fill real observado.

## Paquete para auditoría independiente

`audit_bundle/IGOD_F4A_CLAUDE.zip` incluye los ocho archivos solicitados de PR #48
**byte a byte del commit384032d**, más sus dependencias relevantes, este laboratorio,
informe, resultados, pruebas y cache público original. El manifiesto interno da
origen y hashes; `audit_bundle_sha256.json` permite verificar el ZIP exterior.
No contiene credenciales, datos privados de cuentas ni un servicio operativo.

Para las comprobaciones numéricas sin una copia Git completa, el paquete permite:

```text
python verify_bundle.py
python -m unittest research.confluence_1h_phase2.event_proximity.strict_series_audit.test_strict_series.NumericalTests research.confluence_1h_phase2.event_proximity.strict_series_audit.test_strict_series.ObservedRunTests -v
```

Los guards de procedencia que consultan commits y las regresiones productivas
requieren clonar el repositorio con su historial. Sus resultados reales se
conservan en `validation.json`; no se afirma que Claude ya haya ejecutado el ZIP.

No Railway, Bitunix, Telegram, ejecución, apalancamiento operativo, merge ni deploy.
SHADOW ONLY. TRADE AUTHORITY: NONE.
