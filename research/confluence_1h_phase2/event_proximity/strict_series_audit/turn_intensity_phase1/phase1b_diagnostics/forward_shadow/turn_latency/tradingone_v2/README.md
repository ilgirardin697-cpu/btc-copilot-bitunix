# TRADINGONE_V2 — perfil offline independiente

[Informe y gráficos](results/TRADINGONE_V2_REPORT.md). **No certificación numérica externa, no estrategia, no backtest de rentabilidad.**

Los seis originales y sus licencias están en `sources/`; `profile.json` conserva los inputs ACTIVOS del JSON2.3.21, no sus defaults. Se declara referencia en commit `a678a75`. No OPT. No cambios en resultados/indicadores/protocolos anteriores ni módulos productivos.

Los espacios finales de los Pine recibidos se conservan como evidencia de fuente, con una excepción de whitespace limitada a esos seis assets. Los archivos Python y metadatos nuevos mantienen la comprobación normal. Solo se normalizan finales de línea de metadatos locales; los bytes de las respuestas HTTP no se alteran.

## Ejecutar sin red

Python3.12 y NumPy2.3.5; matplotlib solo para gráficos y tzdata para Madrid. Desde raíz del repo, PowerShell:

```powershell
$mod = 'research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.forward_shadow.turn_latency.tradingone_v2'
$lab = $mod.Replace('.', '/')
python -B -m unittest "${mod}.test_profile" -v
python -B -m "${mod}.study" --data "$lab/data" --out resultado_nuevo
python -B -m "${mod}.report"
```

`study` no sobrescribe su destino. El renderer lee los resultados versionados `results/`; para auditar otra reproducción, comparar sus tablas antes de representarla. No hay descarga automática al importar, scheduler, observador ni servicio. Todos los datos de entrada de este replay están incluidos. `data/manifest.json` y recibos describen los GET públicos puntuales ya realizados; no hay endpoint privado ni credenciales.

`profile.calculate` es un kernel matemático; el harness valida continuidad, rango y corte cerrado de sus datos. La captura de la última vela aún abierta se procesa separadamente como PROVISIONAL, con timestamp de recepción real y rollback. No es un cierre ni una predicción registrada por TradingOne.

## Semántica de carga y directo

- Primario: hipótesis controlada de3200 barras totales,3199 cerradas más una abierta. El JSON no exporta su prefijo real.
- Mismo prefijo/anclaje: determinista y sin cambios históricos al añadir una observación posterior. No se confirma una preview en el estado original.
- Sesión iniciada antes del16Nov: se conserva su anclaje y se añaden cierres; el array original ML RSI crece.
- Reload: vuelve a seleccionar muestras mediante `last_bar_index`, por lo que sus thresholds históricos pueden revisarse. Los valores del histórico recalculado NO son emisiones prospectivas certificadas.
- Una barra adicional de inicialización se conserva como control de sensibilidad, sin buscar el origen que mejor coincida con una captura.

`OriginalMLRSI` reproduce el control de flujo de BackQuantV5, incluida la creación de arrays con3NA seguida de push, y el break anterior a la reasignación. No llama al ML RSI operativo para LOW27. La referencia I-GOD29 de `study` reutiliza únicamente su clase matemática pura en un objeto local para comparación; no altera sus constantes, journals o procesos. La curva EMA27 es solo comparación de suavizado, no una reproducción del Lloyd completo de Manual Copilot.

## Pendiente de paridad real

No hay registros numéricos de TradingOne en este input. Son fuentes/configuración, no resultados ejecutados. Harían falta sus series de velas cerradas con OHLCV, precisión, ticker/venue, principio de historial, índice final, hora de captura y algunos snapshots de recarga/directo. Se enumeran las hipótesis de built-ins en `results/summary.json`: NA/arrays/percentiles, HMA5, lectura de speed en TSA, gradiente/redondeo/renderer. No se presenta una comparación Python/Python como prueba independiente de plataforma.

Campos recomendados para ese contraste: apertura/cierre UTC, confirmed, OHLCV base, AO, ADX/DI, pececillos/tendencia/tiburones/roja, BBWP/SMA5, RSI raw/ALMA/thresholds/colores y TSA Dynamic Trend/Trend Speed. Precisión de dos decimales puede no certificar cruces próximos al umbral.

## Archivos de auditoría

`results/nov16_17.csv` contiene todas las44 horas por apertura Madrid, con17Nov parcial. `hourly.csv.gz` guarda todo el calentamiento/replay; `comparison.csv` separa los indicadores/referencias; `reload.csv` registra ambas sesiones; `provisional.json` conserva el snapshot real público no cerrado; `tsa_table.json` contiene las métricas de ondas originales. `checks.json`, `files_sha256.json` y `audit_bundle.zip` facilitan revisión independiente.

Las guardas de arquitectura, los900 estados de operabilidad, V8 y ML RSI siguen verificándose con las suites existentes. Los tests técnicos no son evidencia de rentabilidad o paridad externa. El límite Windows de rutas `.pyc` se evita con `-B` o compilación en memoria, sin tocar módulos protegidos.

SHADOW ONLY. TRADE AUTHORITY: NONE.
