# Paridad REAL TradingView / Python — 2026-11-03

Fuente: exportación del propietario, BINANCE:BTCUSDT Spot H1. No es una fixture sintética.
Se valida la reproducción contra el Pine exportado, no autenticidad de autoría del indicador privado.

**MATCH_FOR_SUPPLIED_LOGS: 64 filas de entrada; 33 comparadas; 31 iniciales excluidas; 2 pares de sesiones completos; 0 discrepancias.**
Máximo error absoluto medido: 0.0; tolerancia: 1e-07.
Intervalo comparado por apertura de barra: 2026-11-02 11:00Z → 2026-11-03 19:00Z.
No se inyectaron aHigh/aLow/asiaReady ni valores agregados para validar el primer ciclo.

SHA256 logs: `3fc02a8fc12664591766df834c869b10d66cf54606ce12b5e9f87ce54b9d3097`.
SHA256 revisión externa: `a515fedc25841f59632bb20a86d11733bf9aca8cfd9f5a30d5716e54752b9db1`.
El CSV anterior a esta conversión no se adjuntó: su hash solo está DECLARADO por la revisión externa.

## Diferencias por campo

| Campo | Comparaciones | Pares numéricos | Pares nulos | Error máximo | Discrepancias |
|---|---:|---:|---:|---:|---:|
| aHigh | 33 | 33 | 0 | 0.0 | 0 |
| aLow | 33 | 33 | 0 | 0.0 | 0 |
| lHigh | 33 | 27 | 6 | 0.0 | 0 |
| lLow | 33 | 27 | 6 | 0.0 | 0 |
| amplitude | 33 | 2 | 31 | 0.0 | 0 |
| topBoxHeight | 33 | 27 | 6 | 0.0 | 0 |
| bottomBoxHeight | 33 | 27 | 6 | 0.0 | 0 |
| topAnchor | 33 | 27 | 6 | 0.0 | 0 |
| bottomAnchor | 33 | 27 | 6 | 0.0 | 0 |
| newTopTarget | 33 | 27 | 6 | 0.0 | 0 |
| newBottomTarget | 33 | 27 | 6 | 0.0 | 0 |
| highGuideValue | 33 | 27 | 6 | 0.0 | 0 |
| lowGuideValue | 33 | 27 | 6 | 0.0 | 0 |
| globalHigh | 33 | 23 | 10 | 0.0 | 0 |
| globalLow | 33 | 23 | 10 | 0.0 | 0 |
| targetTop | 33 | 23 | 10 | 0.0 | 0 |
| targetBottom | 33 | 23 | 10 | 0.0 | 0 |
| aCount | 33 | 33 | 0 | 0.0 | 0 |
| lCount | 33 | 33 | 0 | 0.0 | 0 |
| direction | 33 | 33 | 0 | 0.0 | 0 |
| inAsia | 33 | 0 | 0 | 0.0 | 0 |
| inLondon | 33 | 0 | 0 | 0.0 | 0 |
| startAsia | 33 | 0 | 0 | 0.0 | 0 |
| endAsia | 33 | 0 | 0 | 0.0 | 0 |
| startLondon | 33 | 0 | 0 | 0.0 | 0 |
| endLondon | 33 | 0 | 0 | 0.0 | 0 |
| asiaReady | 33 | 0 | 0 | 0.0 | 0 |
| measureNow | 33 | 0 | 0 | 0.0 | 0 |
| pairReady | 33 | 0 | 0 | 0.0 | 0 |
| topInAsia | 33 | 0 | 0 | 0.0 | 0 |
| bottomInAsia | 33 | 0 | 0 | 0.0 | 0 |
| highConfirmed | 33 | 0 | 0 | 0.0 | 0 |
| lowConfirmed | 33 | 0 | 0 | 0.0 | 0 |
| longBreak | 33 | 0 | 0 | 0.0 | 0 |
| shortBreak | 33 | 0 | 0 | 0.0 | 0 |
| upperTouch | 33 | 0 | 0 | 0.0 | 0 |
| lowerTouch | 33 | 0 | 0 | 0.0 | 0 |
| fired | 33 | 0 | 0 | 0.0 | 0 |
| highAlerted | 33 | 0 | 0 | 0.0 | 0 |
| lowAlerted | 33 | 0 | 0 | 0.0 | 0 |

Los booleanos se comparan exactamente; los pares nulos no se cuentan como mediciones numéricas.

## Señales PINE_A

| Lado | Apertura UTC | Confirmación al cierre UTC | Replay comprobado | Cuerpo completo en niveles A |
|---|---|---|---|---|
| LONG | 2026-11-01T23:00:00Z | 2026-11-02T00:00:00Z | False | False |
| SHORT | 2026-11-02T11:00:00Z | 2026-11-02T12:00:00Z | True | False |
| LONG | 2026-11-03T12:00:00Z | 2026-11-03T13:00:00Z | True | False |

Dos señales están comprobadas por replay; la del primer ciclo SOLO consta en el export.
Las tres primeras señales close-only dejan parte del cuerpo dentro. Esto NO implica que OWNER_B no confirme después.

## El ejemplo de los cuatro niveles

| Fecha del par PINE_A | HIGH | LOW | SUPERIOR | INFERIOR | Replay OHLC completo |
|---|---:|---:|---:|---:|---|
| 2026-11-01T11:00:00Z | 78285 | 77517.2 | 78653.4351 | 77095.25 | False |
| 2026-11-02T11:00:00Z | 78878.01 | 77926.7 | 79342.6012 | 77179.79030000001 | True |
| 2026-11-03T11:00:00Z | 77314.01 | 76502.63 | 77939.27199999998 | 75753.39230000002 | True |

El 1-Nov coincide NUMÉRICAMENTE con las cuatro etiquetas antiguas: SUPERIOR78653.4351 se muestra78653.44.
Su álgebra desde los extremos guardados coincide, pero no se han reconstruido sus velas de Asia ausentes.
Esto vincula los números a un ciclo de BINANCE:BTCUSDT/PINE_A; no autentica por sí solo el gráfico privado original.

## DST del 1 de noviembre

05:00Z = 01:00 EDT (UTC−4); 06:00Z = 01:00 EST (UTC−5). Ambas barras existen, separadas1H real.
PINE_A: Londres02–05 EST son aperturas07–10Z; measureNow en11Z, primer cierre confirmable12Z.
OWNER_B mantiene UTC−4: Londres01–04 son05–08Z; niveles en09Z y primera barra externa cierra10Z.
La parte del fold y el primer ciclo solo se auditan desde el export; los dos pares posteriores son los replays completos.

## GO / NO-GO

**GO para evaluación PAPER exclusivamente offline con OWNER_B y sus propios niveles.**
NO-GO para activación continua, integración productiva o trading real. Dos pares no prueban rentabilidad.
SHADOW ONLY. TRADE AUTHORITY: NONE.
