# I-GOD Killzone Radar — PRICE congelado

**B. PROMETEDOR PERO PENDIENTE DE DATOS PROSPECTIVOS.**
Panel: **SIN PROBABILIDADES VALIDADAS**. Cero observaciones forward reales.

Este seguimiento es una elección POST-HOC solicitada después de PR #42.
Conserva literalmente el modelo PRICE, sus coeficientes, escalado y clipping.
No cambia PR #41/#42 ni sus resultados. No busca nuevas variables o parámetros.

- [Pine completo independiente](I_GOD_Killzone_Probability_Radar.pine).
- [Instalación y prueba técnica](TRADINGVIEW.md).
- [Informe con clases, minutos, calibración e IC](artifacts/PRICE_RADAR_REPORT.md).
- [Mensual completo](artifacts/monthly.csv) y [cinco instantes](artifacts/anchor_minutes.csv).
- [Resultados estructurados](artifacts/historical_comparison.json).
- [Protocolo precongelado](protocol.json), [modelo exacto](frozen_PRICE.json),
  [referencia de frecuencias](frozen_PRIOR.json) y [referencia estructural](artifacts/frozen_STRUCTURE.json).
- [Estado de paridad real pendiente](artifacts/pine_parity_status.json).

## Precio solo, con una precisión necesaria

Las seis variables originales son minuto, posición dentro del rango combinado,
cambio Londres normalizado por rango Asia, rango Londres/rango Asia, cambio Asia/rango Asia,
y rango combinado/ATR14 H1 confirmado. ATR es una escala derivada de OHLC que YA estaba
en PRICE. No se elimina porque cambiaría el modelo. No hay AO, ADX/DMI, BBWP o tendencia4H.
La variación del rango se refleja al actualizar el rango parcial; no se añade un delta nuevo.

PINE_A se conserva: Nueva York con DST, Asia20–23, Londres02–05, forecast05:00–05:59.
Los objetivos finales no están disponibles durante esa hora. Solo etiquetan el primer toque
entre06:00 y20:00. No hay franjas500, TP±200, entradas, stops o resultado económico en este radar.
OWNER_B/C y TP adelantado200 permanecen intactos en su investigación original.

## Reproducción offline

Python3.12, numpy, requests y tzdata (Windows). No descarga datos nuevos:
reutiliza el dataset público auditado/versionado de PR #42.

```sh
python -m research.killzone_price_radar.report
python -m research.killzone_price_radar.build
python -m unittest research.killzone_price_radar.test_price -v
```

PRICE no se reentrena. Solo la referencia tabular se calcula con el train original:
tres terciles fijos de posición, suavizado20 ciclos con el prior ya congelado.
El protocolo y los coeficientes se guardaron en3c3f90a antes de ver esa comparación.
Se conserva la muestra común original de PR #42 y sus exclusiones de warmup/datos;
no se readmiten retrospectivamente ciclos excluidos para mejorar la comparación.

## Observación prospectiva preparada, NO activada

Cohorte2026-11-05→2027-05-04. No se transforma noviembre ya observado, replay o un CSV
histórico en señales forward. No se ha creado un receptor, webhook o tarea automática.

Captura manual local de una exportación de Pine Logs **mientras sigue siendo prospectiva**:

```sh
python -m research.killzone_price_radar.forward capture --logs logs_reales.txt --journal research/cache/price_forward_v1.jsonl
python -m research.killzone_price_radar.forward status --journal research/cache/price_forward_v1.jsonl
```

La recepción usa el reloj real del capturador, no un argumento `--asof`.
Debe llegar antes06:00 NY y a<=120s del minuto conocido. Una exportación posterior
se conserva como diagnóstico, pero queda ineligible para la cohorte prospectiva.
No se puede sustituir la primera predicción por otra mejor tras recargar o revisar el feed.
IDs idénticos no duplican; revisiones conflictivas se rechazan sin sobrescribir.
Se verifica toda la cadena hash; truncamiento/corrupción no se repara.
Captura de un solo escritor. La cadena es evidencia local de integridad, no un sello de
tiempo ni una autenticación criptográfica de TradingView. Requiere revisión externa.

Después de madurar el ciclo, outcome independiente:

```sh
python -m research.killzone_price_radar.forward settle --date 2026-11-05 --manifest ruta/download_manifest.json --journal research/cache/price_forward_v1.jsonl
```

El manifest debe corresponder a archivos públicos Binance Spot oficiales BTCUSDT H1/1m,
con URLs, checksums y ZIP originales en la misma carpeta. Se debe auditar su adquisición
oficial; un archivo que alguien llame manifest no autentica su procedencia por sí solo.
Se exige contigüidad, OHLC, coincidencia1m/H1 y contexto ATR idéntico. El fichero mensual
puede publicarse después del ciclo: se espera, no se inventa el label ni se descarga vía cuenta.
La etiqueta se añade como registro separado, nunca modifica la predicción.

Se necesitan cinco instantes por ciclo y datos públicos verificados. Los60 minutos
son medidas repetidas del mismo ciclo. Los criterios de muestra, cobertura, Brier,
log-loss, calibración, clases, meses y paridad están fijados en protocol.json.
No hay aprobación temprana ni ajuste al ver resultados. Un N mínimo no valida nada.
La conclusión A requiere revisión independiente y una nueva release aprobada;
ningún archivo de entrada ni interruptor puede habilitar porcentajes en este Pine.

La mejora predictiva histórica no acredita rentabilidad ni ejecución de trades.
No órdenes, apalancamiento, Telegram, Guardian, V8, Railway, merge o deploy.

SHADOW ONLY. TRADE AUTHORITY: NONE.
