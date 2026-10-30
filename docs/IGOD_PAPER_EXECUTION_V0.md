# I-GOD Shadow Paper Execution V0 — piloto forward autónomo

SHADOW ONLY. TRADE AUTHORITY: NONE. **No ejecuta órdenes en ningún exchange.**

Este servicio separado convierte observaciones cerradas en planes y operaciones
**simuladas**. Los precios son públicos reales; los fills, comisiones y
deslizamientos son modelos. Ni el simulador ni la confluencia tienen rentabilidad
validada. Los resultados de PR #33/#34 no se transforman en evidencia forward.

## Código auditado y reutilización

Base: `fc211d8e36c6db55185efa8309eb8f980beab2ea`, PR #32 mergeado.

| Fuente revisada | Uso en este piloto |
|---|---|
| `trade_guardian.py`, `guardian_bitunix.py`, `guardian_risk.py` | Auditados; nunca importados, iniciados ni modificados |
| `guardian_signals.py` / Manual Copilot V1 | Única dependencia de producción: funciones matemáticas puras sin red ni cuentas |
| `main.py` / planner | Auditado; no se importa porque contiene configuración y mensajería |
| `trend_v8.py` y `origin/v8-real-executor:v8_executor.py` | Auditados; ninguna importación, cambio, activación o acceso al executor |
| ZIP del propietario | Motor y README conservados byte a byte en `igod_paper/vendor/` |

La copia del motor original sigue siendo un módulo offline sin conectividad.
El adaptador incremental reutiliza su `Config`, validación y redondeo de tamaño,
y reproduce sus convenciones de costes, stops, sizing y prioridad adversa.
Los diez tests originales están incluidos con únicamente el import adaptado.
`attachment_manifest.json` contiene hashes del ZIP y del motor.

**Distinción de procedencia:** el Manual Copilot de Guardian toma dirección de
Binance Spot. Este piloto aplica sus mismas funciones a **Binance USD-M** para
que confluencia, ATR y precio simulado pertenezcan a una sola venue. Se identifica
como `MANUAL_COPILOT_V1_RULES_ON_USDM_PAPER_V0`; no se presenta como una exportación
de señales observadas por producción ni como paridad Spot/USD-M.

El momentum reutilizado es el **LOW27 EMA4 del Copilot existente**, no el host
ML RSI confirmed LOW29 de producción. No se lee ni reconstruye su journal.
No se afirma paridad con indicadores propietarios Bitman.

## Especificación fijada antes del piloto continuo

1. Símbolo fijo BTCUSDT, venue `BINANCE_USDM_PERPETUAL`; fuente HTTPS pública
   `fapi.binance.com`, endpoints exclusivos GET `/fapi/v1/klines` y
   `/fapi/v1/fundingRate`. Sin claves, proxies ambientales, redirects ni fallback
   a otra venue. Timeout de conexión 3 s y lectura 10 s.
2. Solo velas cerradas, contiguas, ordenadas, con 12 columnas y closeTime exacto.
   Páginas de hasta 1500, presupuesto de recuperación máximo 10.000 velas.
   Un gap, duplicado, NaN, error HTTP o funding no verificable bloquea el avance
   afectado; no se inventan precios ni operaciones.
3. Confluencia cada cierre 15m, respetando el margen de propagación de 3 s:
   funciones originales `guardian_signals.snapshot`, tendencias SMA200 1H/4H,
   momentum causal LOW27 EMA4, flujo taker, estructura con pivotes confirmados
   2-left/2-right y calidad de reclaim. Warmup: 3200×1H, 220×4H, 220×15m.
   No se añaden patrones o filtros ni se cambian thresholds para generar trades.
4. Solo `LONG_ALLOWED` / `SHORT_ALLOWED` **y** `entry_quality=GOOD` programan
   un plan hipotético. WAIT/UNKNOWN/CAUTION/POOR también quedan registrados.
   Una posición o plan a la vez; una decisión por cierre 15m.
5. **Entrada causal:** primera apertura 5m estrictamente posterior al instante
   real de observación, no la apertura ya pasada en el cierre de la señal.
   El plan se confirma con append+flush+fsync antes de esa apertura. El fill
   se contabiliza cuando está disponible su vela 5m cerrada. Nunca se programa
   retrospectivamente una señal perdida durante una caída del proceso.
6. La señal caduca si la apertura prevista supera 15m desde su cierre.
   Si al abrir ya se perdió el nivel de reclaim o se alcanzó el nivel opuesto,
   se cancela el plan de papel. No se persigue el precio.
7. Parámetros V0, sin calibración: capital **SIMULADO 140 USDT**, riesgo objetivo
   0,5%, máximo notional 2×, máximo 2 trades/día UTC, bloqueo tras pérdida
   realizada diaria de 2%, cooldown de dos velas, step 0,0001 BTC y notional
   mínimo simulado 5 USDT. No representan saldo, permisos ni filtros Bitunix.
8. Stop V0 = 1,5×ATR14 **5m** conocido al observar; target = 1,5R sobre distancia
   de stop. Tamaño incluye costes conservadores y límite notional. Stop y target
   se congelan al fill. Estos defaults son ilustrativos, no óptimos ni validados.
9. Extensiones operativas declaradas respecto del ZIP: cierre 15m adverso al
   nivel congelado de reclaim invalida la tesis; salida temporal a las 288 velas
   5m (24h). Prioridad: STOP, TARGET, invalidación, tiempo. No se optimizaron.
10. Si stop y target se tocan en una vela: STOP primero. Un gap adverso usa el
    peor open. Target no recibe mejora por gap favorable. Costes asumidos:
    comisión 6 bps por lado y slippage adverso 3 bps por lado. Las comisiones
    de entrada se descuentan inmediatamente, incluso si la posición sigue abierta.
11. Funding: tasas y markPrice públicos reales, para posiciones existentes antes
    del settlement. A igualdad exacta entrada/settlement no se presupone tenencia
    previa. Un cargo intrabar se aplica conservadoramente aunque el stop pudiera
    haber ocurrido antes; un crédito intrabar ambiguo se omite. No se utiliza
    funding futuro para seleccionar entradas ni se aplica cero ante un error de red.
12. No hay liquidación, order book, fills Bitunix ni garantía de pérdida máxima.
    MAE de velas puede sobreestimar excursión anterior a una salida; MFE excluye
    extremos favorables del candle de salida cuando su orden intrabar es desconocido.

## Persistencia y reinicios

Directorio exclusivo `/paper-data` de un volumen NUEVO en `igod-research-lab`.
No se monta ni utiliza el `/data` de Guardian.

- `paper_v0.jsonl`: fuente autoritativa append-only; IDs deterministas,
  secuencia, observed_at real, payload, state_after, previous_hash y record_hash.
- Primer registro `FORWARD_START`: activación real, configuración, fuentes/hashes
  del código y cero señales históricas importadas. Warmup no genera operaciones.
- Registros `SIGNAL_OBSERVED` y `CLOSED_BAR_PROCESSED`: contexto y hashes de
  inputs, OHLC público procesado, funding, acciones simuladas y resultado.
- `paper_state.json`: checkpoint derivado; se puede reconstruir del journal.
- `report.json` y `report.md`: informes derivados de lectura.
- Lock exclusivo de proceso; flush+fsync antes de confirmar un registro.
- Un tail truncado, hash inválido, duplicado, secuencia inválida o cambio de
  configuración/código detiene el simulador. Nunca trunca ni repara el journal.
- Reiniciar reproduce el estado ya comprometido. Recupera velas cronológicamente
  para posiciones/planes previamente registrados; no crea señales históricas.
- Un error de fsync implica almacenamiento incierto: no reintenta el append;
  exige reiniciar y validar el journal. No toca otros servicios.

Cambiar reglas o fuentes exige un protocolo/directorio de experimento separado.
No se altera `BITMAN_WEEKLY_FORWARD_V1` ni se reutiliza su journal.

## Aislamiento del despliegue de pruebas

Proyecto **igod-research-lab**; servicio nuevo `igod-paper-simulator`, Amsterdam
`europe-west4-drams3a`, 1 réplica, volumen propio `/paper-data`.
La etiqueta del environment existente de ese proyecto es `production`, pero NO
es el proyecto ni el environment de Guardian. No se reutiliza el servicio
temporal `bitman-market-data-test` ni el market-data productivo.

Imagen construida con `igod_paper/Dockerfile`: contiene exclusivamente el
paquete paper y `guardian_signals.py`, sin ningún cliente de cuenta/órdenes,
Guardian, planner, V8 executor o sender. No necesita secretos ni Telegram.
Se rechaza el arranque si se detectan variables de credenciales o ejecución.

Comando explícito:

```text
python -m igod_paper --directory /paper-data --serve
```

El `railway.json` productivo NO debe aplicarse a este servicio: configurar
`configFile=""`, Dockerfile dedicado mediante
`RAILWAY_DOCKERFILE_PATH=igod_paper/Dockerfile`, comando explícito, `PORT=8080`,
healthcheck `/health`, región Amsterdam y ningún dominio público por defecto.
Servidor dual IPv4/IPv6. `/health` acredita vida del proceso, no rentabilidad ni
calidad del feed; el estado HEALTHY/DEGRADED está en logs e informe.

## Consulta y operación

- Logs Railway: `IGOD_PAPER_STATUS=` muestra estado, capital simulado, trades,
  costes y drawdown; nunca claves ni datos de cuenta.
- HTTP privado GET: `/`, `/report.json`, `/report.md`, `/health`. Ningún endpoint
  acepta operaciones ni modifica estado. No hay API de configuración ni control.
- Informe local: `python -m igod_paper --directory <directorio_nuevo>` hace un
  ciclo de datos públicos y genera Markdown/JSON; requiere acceso autorizado
  a Binance USD-M. Para continuidad usar `--serve`. Nunca usar `/data`.
- Cero trades al arrancar es válido. No forzar señales para demostrar actividad.
  Revisar el informe tras eventos naturales y acumular evidencia, incluyendo
  pérdidas. No mezclar tests sintéticos o pilotos locales con el journal continuo.
- No modificar código o configuración sobre un journal existente para mejorar
  resultados. Revisar incidentes y límites de volumen antes de cambiar nada.

## Validación

```text
python -m unittest test_igod_paper test_igod_paper_vendor test_igod_paper_safety -v
python mlrsi_safety_audit.py
python test_bitman_weekly_boundary.py --require-v8 -v
python test_bitman_readiness_boundary.py --require-v8 -v
python -m unittest discover -v
```

Los tests incluyen ganancias/pérdidas LONG y SHORT sintéticas, colisiones,
gaps, costes/funding, timing de observación, 100 reinicios, integridad, riesgo,
HTTP read-only y las 87 fuentes protegidas existentes. La suite original
conserva la matriz 900 (780/59/59/1/1) y los hashes de V8/protocolo semanal.

Referencias de datos oficiales:
[USD-M market data](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data).

**No se ha identificado un edge nuevo. Este piloto mide lo que ocurra a partir
de su activación; resultados insuficientes o negativos deben conservarse.**
