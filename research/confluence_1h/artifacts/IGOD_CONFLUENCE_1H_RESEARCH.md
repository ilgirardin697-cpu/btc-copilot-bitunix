# I-GOD — Confluencia 1H: auditoría y evaluación offline

**INCONCLUSO — NO-GO para integración o trading.**

Con las reglas base se detectan **0 LONG y 0 SHORT** en 35,064 horas evaluadas. No existe una muestra de operaciones con la que estimar rentabilidad. No se relajan los filtros para obtenerla.

SHADOW ONLY. TRADE AUTHORITY: NONE.

## 1. Fuentes y alcance

- ZIP y dos fuentes adjuntas conservados byte a byte en `reference_sources/`; hashes en `source_manifest.json`.
- Rama independiente desde `9d40020d539033cefb8f01734db8c6a6fdbba2e3`. Los 151 archivos base protegidos conservan sus hashes. No se cambia producción.
- Fórmulas del proxy público, no indicadores propietarios de Bitman. **EXACT BITMAN PARITY: NOT PROVEN**.
- La serie usada para el cruce es `tendencia` contra `ma_trend` (EMA15), no `pececillos` ni `tiburones`.

## 2. Congelamiento antes de resultados

- Protocolo original: commit `4896dee9b9ae4bc28c05e479562a1511f48cd972`, SHA256 `8562b94976abaad64bb49e7d46cb2fe94ee546e3d81cfb5b8b5511c8739519e5`.
- Addenda de datos previos a toda evaluación: `fe29923` (dos huecos de mark), `a077a0b` (mark de settlement exacto), `85ec9ba` (incertidumbre explícita por marks ausentes). No cambian señales ni umbrales.
- Implementación del estudio fijada en `e5fb1d6` antes del primer resultado. Las adaptaciones posteriores son reporting, diagnóstico, formatos REST y tests; ninguna selección de parámetros.
- Dos TP coprimarios 2R/3R; sensibilidad de un factor ADX35/45 o BBWP80/90. No búsqueda ni selección del mejor resultado.
- **NO VIRGIN HOLDOUT**: una separación cronológica no convierte mercado previamente examinado en datos vírgenes. Cero evidencia prospectiva de esta estrategia.

## 3. Dataset verificable

| Campo | Resultado |
|---|---|
| Mercado principal | BINANCE_USDM_PERPETUAL, BTCUSDT |
| Evaluación | 01/11/2022 00:00 UTC → 01/11/2026 exclusivo, cuatro años |
| Velas H1 | 36,528 totales; 1,464 warmup; 35,064 evaluadas |
| Archives ZIP/checksums oficiales | 148 verificados, incluidos dos diarios de recuperación |
| Funding | 4,383 rates, contrastados contra REST público |
| Mark exacto ausente | 1,093 settlements; nunca se sustituyen silenciosamente |
| Huecos finales de trade-price / imputación | 0 / 0 |

Los 48 huecos de mark price de los mensuales (24/02/2023 y 29/06/2026) se recuperaron de archivos diarios oficiales de la misma venue, con checksums. No se interpolaron.
Los rates son reales; un mark de settlement vacío continúa siendo desconocido. El escenario acotado usa high/low del mark H1, se identifica en cada trade y no se presenta como un precio exacto.
Al no haber trades base, esta limitación no crea pérdidas/beneficios ficticios: los métricos de rendimiento siguen N/D.

[Provenance y checksums Binance](https://github.com/binance/binance-public-data) · [REST funding](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data).

## 4. Auditoría matemática y ejecución

La auditoría completa está en [AUDIT.md](../AUDIT.md).

- Koncorde: RSI14 sobre OHLC4, MFI14 sobre HLC3, oscilador BB25×2, estocástico21/SMA3, EMA15. PVI/NVI y capas se calculan, pero no son filtros añadidos.
- AO = SMA5(HL2) − SMA34(HL2). Color/pendiente no equivale a signo respecto a cero.
- ADX/DMI14/14: se separa la semilla de true range de DMI de ATR14. La normalización inicial de DI cambia respecto al ZIP; no se modifica la lógica de dirección.
- BBWP SMA7 / previas100: `binary_search_rightmost` devuelve un índice, no siempre count(<=). Se conserva el comportamiento literal en empates. El ZIP no es idéntico a esa fuente.
- Diferencias de señales ZIP versus port auditado en todo el input: LONG=0, SHORT=0. No se ha ejecutado su selector de 18 configuraciones.
- Referencia escalar local independiente: pasa los campos verificables con tolerancia 1e-8/1e-9. **No es una ejecución de Pine**.
- Pine diagnóstico completo y comparador entregados. Registros reales de este nuevo Pine: **0**. Compilación y paridad TradingView: **NO VERIFICADAS**.
- El Pine v5 original usa 3000 ticks fijos de slippage, tamaño al cierre previo y salida `immediately` al cierre. Python usa porcentaje por fill y una salida temporal simulable a la siguiente apertura. No se declara equivalencia entre brokers.

## 5. Qué condición descarta las coincidencias

| Condiciones acumuladas | LONG | SHORT |
|---|---:|---:|
| KON_CROSS_AND_PREVIOUS_SIGN | 61 | 2363 |
| PLUS_LAGGED_ADX_DECLINE | 0 | 73 |
| PLUS_AO_TWO_SLOPES | 0 | 21 |
| PLUS_BBWP_ABOVE85 | 0 | 0 |

El filtro ADX es literalmente `ADX[t−1] < ADX[t−2]` y `ADX[t−2] >40`. No exige un suelo actual, un giro al alza, ni siquiera que el valor de t−2 sea un máximo local frente a t−3. Tampoco exige dominancia +DI/−DI.
Esta implementación ensaya la coincidencia concreta del ZIP, no cualquier parecido visual entre líneas. No se declara que sea la única formalización posible del concepto de confluencia.

## 6. Simulación y costes fijados

- Entrada en apertura posterior al cierre confirmado, con 0,05% adverso. SL=1,5ATR14 conocido al emitir; TP=2R/3R bruto. Salida tras 24 barras completas a apertura posterior.
- Una posición simultánea por cuenta. COMBINED es principal; LONG_ONLY/SHORT_ONLY son cuentas contrafactuales separadas, nunca asignaciones simultáneas de una cuenta real.
- Comisión 0,1% por lado, slip0,05% por lado, funding separado. Son escenarios de costes pedidos por el usuario; no tarifas/fills autenticados.
- Equity inicial200 USDT; presupuesto al stop incluyendo fees/slip1%; nominal+fee<=equity. Sin multiplicador de apalancamiento. Gaps/funding futuro pueden superar el presupuesto; se registran breaches.
- Stop primero si ambos niveles se tocan dentro de una H1 sin orden intrabar conocido. Una apertura ya fuera de un nivel se procesa antes que las mechas posteriores.
- MFE/MAE de wicks son cotas H1; no se inventa el orden del precio después de la salida. DD a cierre y cota adversa separados.

## 7. IS/OOS y walk-forward

Corte70/30 bruto: **2025-08-19T16:00:00Z**. IS termina24h antes y TEST empieza24h después. Purga adicional de señales sin horizonte completo de hasta24h y apertura de salida dentro de la ventana.
Cuatro ventanas expansivas30→40,40→50,50→60,60→70% dentro del desarrollo. Parámetros fijos: no entrenamiento/selección de un ganador en cada fold.

| TP | Libro | IS operaciones | TEST operaciones | Win rate / PF / expectancy / Sharpe |
|---|---|---:|---:|---|
| 2R | COMBINED | 0 | 0 | N/D: sin muestra |
| 2R | LONG_ONLY | 0 | 0 | N/D: sin muestra |
| 2R | SHORT_ONLY | 0 | 0 | N/D: sin muestra |
| 3R | COMBINED | 0 | 0 | N/D: sin muestra |
| 3R | LONG_ONLY | 0 | 0 | N/D: sin muestra |
| 3R | SHORT_ONLY | 0 | 0 | N/D: sin muestra |

Los cuatro folds, los años y los regímenes tienen cero trades base. `year_side_regime.csv` y `metrics.csv` los conservan. La curva200→200, retorno0% y DD0% son consecuencia mecánica de no operar: **no miden seguridad ni capacidad predictiva**.
Controles: el runner de 200 semillas por libro/TP empareja mes, lado y régimen causal4H SMA200. Con cero candidatos son controles vacíos; no existe una comparación estadística ni p-value útil.
Bootstrap predeclarado por bloques calendario7d (2000 réplicas), incluyendo días sin eventos. Con cero operaciones el IC es `null`, no [0,0]. No se fabrica una distribución de resultados ni ex-best1/3.

## 8. Sensibilidad sin seleccionar ganador

| Vecino predeclarado | TP | Libro combinado TEST n | Neto escenario | Expectancy |
|---|---|---:|---:|---:|
| BASE | 2R | 0 | 0.00 USDT | N/D |
| ADX35 | 2R | 0 | 0.00 USDT | N/D |
| ADX45 | 2R | 0 | 0.00 USDT | N/D |
| BBWP80 | 2R | 1 | -2.00 USDT | -1.000R |
| BBWP90 | 2R | 0 | 0.00 USDT | N/D |
| BASE | 3R | 0 | 0.00 USDT | N/D |
| ADX35 | 3R | 0 | 0.00 USDT | N/D |
| ADX45 | 3R | 0 | 0.00 USDT | N/D |
| BBWP80 | 3R | 1 | -2.00 USDT | -1.000R |
| BBWP90 | 3R | 0 | 0.00 USDT | N/D |

El único evento de los vecinos BBWP80 es SHORT perdedor: −1R en ambos TP. No cambia la regla principal85 ni demuestra nada con n=1. No se adopta ningún vecino. Stress de costes15bps fee/10bps slip: igualmente sin operaciones base.

## 9. Giro 15/11/2026: separado y causal

**POST-HOC OBSERVATION — NOT PART OF VALIDATION.** 02:00 Europe/Madrid =01:00 UTC. Se distinguen apertura de vela y disponibilidad al cierre; los gráficos del incidente usan x=available_at.

| Venue | Disponible Madrid | AO | ΔAO | ADX | ΔADX | BBWP | Cruce Kon LONG | Señal completa |
|---|---|---:|---:|---:|---:|---:|---|---|
| BINANCE_USDM_PERPETUAL | 2026-11-15T02:00:00+01:00 | -2684.850 | -170.186 | 57.036 | 0.121 | 96 | False | NO |
| BINANCE_USDM_PERPETUAL | 2026-11-15T04:00:00+01:00 | -2990.101 | 14.192 | 55.796 | -2.102 | 91 | True | NO |
| BINANCE_SPOT | 2026-11-15T02:00:00+01:00 | -2681.548 | -169.317 | 57.017 | 0.077 | 96 | False | NO |
| BINANCE_SPOT | 2026-11-15T04:00:00+01:00 | -2990.875 | 9.647 | 55.720 | -2.127 | 91 | True | NO |

A las02:00 Madrid no existe la confluencia completa. El cruce Kon posterior, disponible04:00 Madrid, no cumple la caída ADX pasada ni dos pendientes AO ascendentes. El rebote posterior no se acredita como trade ni se cambian reglas para capturarlo.
Solo velas realmente cerradas recibidas de las APIs públicas Spot y USD-M, conservadas por separado con SHA256. No se completa un outcome24h aún inmaduro. Algunos RAW se reutilizaron después de corregir un parser de timestamps REST int: no se inventa received_at histórico; esa limitación se marca en su manifest.

## 10. Archivos, gráficos y reproducción

- `signals_all.csv.gz`: todas las35064 horas, valores y gates (descomprimir para CSV). `signals_all.jsonl.gz`: mismo contenido estructurado.
- `trades_all.csv`: esquema con cero operaciones base; `sensitivity_trades.csv`: también conserva las pérdidas de sensibilidad.
- `equity_all.csv.gz`, `metrics.csv`, `random_controls.csv`, `sensitivity.csv`, `year_side_regime.csv`, `signal_funnel.csv`.
- `all_signals_equity.png`, `development_test.png`: todo el periodo. Sin marcadores/SL/TP base porque no existen entradas aceptadas.
- `rejected_1.png`…: primeros cruces/rechazos cronológicos por reglas objetivas, **no trades perdedores o ganadores inventados**. `example_selection.json` confirma que no hay ejemplos de trades base.
- `incident_BINANCE_SPOT.png` y `incident_BINANCE_USDM_PERPETUAL.png`: episodio real, separado.
- `data_manifest.json`, `indicator_audit.json`, `artifact_checksums.json`, hashes de fuentes y protocolo. Los RAW públicos permanecen en cache ignorada; descarga reproducible con checksums.

Desde la raíz del worktree, con Python3.12 y dependencias research:

```powershell
python -m research.confluence_1h.data
python -m research.confluence_1h.evaluate
python -m research.confluence_1h.incident
python -m research.confluence_1h.report
python -m unittest test_confluence_1h_research -v
```

Las evaluaciones con datos ya descargados no requieren red. No hay entrenamiento ni selección automática. No ejecutar el driver original del ZIP como sustituto: cambia datos/selección/semántica de simulación.

## 11. Limitaciones y decisión

**INCONCLUSO. NO-GO para detector operativo o integración en I-GOD.**

No hay evidencia de edge ni evidencia suficiente para estimar un rendimiento negativo de las reglas base: no generan operaciones en esta muestra. La definición auditada no sirve todavía como candidato con frecuencia observable.
Falta paridad real del Pine y una muestra prospectiva adecuada. No se afirma que un parecido visual de indicadores garantice una entrada rentable. Las reglas no se recalibran con este histórico.
Guardian V2, V8, ML RSI, la capa de operabilidad, market-data, Telegram, Railway y BITMAN_WEEKLY_FORWARD_V1 permanecen intactos. Ningún módulo productivo importa este laboratorio. Sin merge ni deploy.

**SHADOW ONLY. TRADE AUTHORITY: NONE.**
