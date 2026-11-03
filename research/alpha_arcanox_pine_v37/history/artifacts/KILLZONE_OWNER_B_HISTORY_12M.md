# Killzone OWNER_B — evaluación histórica offline de 12 meses

**Conclusión principal: INCONCLUSIVE. No hay ventaja neta demostrada.**
Control cierre simple: **NO EDGE**. OWNER_C 40x: **INCONCLUSIVE / BLOCKED_NOT_EVALUABLE**.

## Fechas, protocolo y datos

Periodo: 2025-11-01 00:00 UTC → 2026-11-01 00:00 UTC exclusivo (365 ciclos de Londres).
Octubre de 2025 completo inicializa ATR14; sus outcomes no entran en la evaluación.
Fechas, fuente, costes y reglas congelados en046491f ANTES de descargar y analizar.
Precisión de caducidad en b725a2d, después de descargar pero ANTES de calcular outcomes:
el siguiente inicio de Asia se refiere al ciclo vigente. Una confirmación justo en su caducidad
se registra pero no tiene ventana para entrar. El helper antiguo de64 registros no se modifica;
su igualdad de hora avanzaba al día posterior, sin afectar a aquellos dos casos previos.
Los manifests de descarga conservan el hash del primer protocolo; el hash de análisis incluye la precisión.
Hash final del protocolo: `23a236d03415438957f0ac4a820f668f87b2947916a9fd5a4fbe078b41e55cb3`.
Binance Spot BTCUSDT oficial, 13 ZIP H1 y12 ZIP1m con25 checksums SHA256 oficiales.
9504 horas incluyendo warmup;525600 minutos;8760 horas evaluadas coinciden EXACTAMENTE
con sus60 minutos. Sin huecos, duplicados, imputación o velas abiertas.
Los timestamps Spot de estos archivos están en microsegundos, normalizados explícitamente a ms.
[Fuente y formatos oficiales](https://github.com/binance/binance-public-data/blob/master/README.md).
Raw ZIP local en research/cache; manifests/URLs/checksums en summary.json; OHLC H1 público comprimido incluido.
NO VIRGIN HOLDOUT. La ventana ya comparte historia de mercado vista en otros estudios; los64 logs
posteriores se usaron para matemática, no para validar rentabilidad. No se tocaron fórmulas ni indicadores.

## Reglas y escenarios que se mantienen

OWNER_B: UTC−4 fijo, Asia20–00 (5), Londres01–04 (4), cuerpo COMPLETO, primera confirmación.
Proyecciones fuente con inset3%; TP LONG=SUPERIOR−200 / SHORT=INFERIOR+200.
SL HIGH−0.20 ATR14 / LOW+0.20 ATR14; mínimo1.5R neto; máximo0.25% de riesgo estimado
y nominal<=equity, sin apalancamiento. El presupuesto y el nominal se recalculan con el capital restante.
10000 USDT es solo escala inicial. No se reinicia entre meses o pérdidas ni hay fondos externos.
Comisión0.1% por lado y slippage2bps por lado: escenarios conservados del estudio previo,
NO tarifas históricas verificadas de la cuenta ni fills observados. Funding no aplica a esta serie Spot.
SHORT es una exposición direccional hipotética: no hay préstamo/inventario ni sus costes verificados.
No representa Bitunix Futures, ni una venta Spot ejecutable sin inventario o préstamo.

## A. Hipótesis del precio — todas las primeras confirmaciones

- Ciclos totales:365; sin confirmación:84; con confirmación:281.
- Casos con target aún por delante y tiempo posterior:218.
- Alcanzan el target teórico:106/218 = 48.62%.
- No llegan antes de caducar:112; mediana entre los que llegan:98.5 minutos.
- Target antes de SL o sin tocar SL:70; SL antes del target o sin target posterior:122.
- De ellos,36 llegan al target DESPUÉS de haber tocado SL.
- Ninguno de ambos hasta caducar:26.
- Target ya detrás al confirmar:58; sin tiempo posterior:7.
Las dos últimas categorías se solapan:2 señales están en ambas. Se conservan todas en el ledger;
no se cuentan como predicciones exitosas targets ya alcanzados durante la vela confirmadora.
Hitos registrados al minuto, con tiempo a target como límite superior de1m. Horizonte finito:
siguiente inicio de Asia. No se busca indefinidamente hasta encontrar un target futuro.
Estos conteos incluyen señales rechazadas por riesgo; no son un win rate de operaciones.

## B. Estrategia — solo entradas que pasan el filtro

- Superan el cálculo al cierre:38; entradas vigentes aceptadas:36.
Dos que pasan el cálculo no tienen ventana posterior antes de caducar. No se fabrican fills.
- Resultado bruto antes de costes:68.6761 USDT; comisiones:306.2689; slippage:61.2538.
- Neto:-298.8466 USDT (-2.9885%); equity final:9701.1534.
- Expectativa:-0.334734 R/trade; IC95 por bloques7d:[-0.7546551448063848, 0.1139124704124839].
- Win rate neto:19.44%; profit factor monetario neto:0.567082.
- Drawdown realizado:3.0759%; MTM a cierre1m:3.3268%.
- Cota adversa intraminuto:3.3507% (supone orden extremo favorable→adverso).
- Salidas:{'SL': 28, 'TIME_EXIT': 2, 'TP': 6}; ambigüedades dentro del mismo minuto:0.
- Exposición temporal superior:0.6674%; pérdidas sobre presupuesto por gaps:0.
- Ex-best1:-0.444609 R; meses positivos:1/12; segundo semestre:-48.1085 USDT.
La clasificación estaba fijada antes de outcomes: con36 entradas y un IC que cruza cero corresponde
INCONCLUSIVE, aunque el punto estimado sea negativo. No es PROMISING y no recomienda activación.
Las entradas son escenarios de primera apertura posterior+slippage, no fills reales acreditados.
Se revalida el R/R allí sin mover SL/TP. Una barra1m que toque ambos aplica SL primero y se marca.
Los gaps al stop usan la apertura peor; un gap hacia TP no obtiene un precio mejor gratuitamente.
La propia vela que confirma queda totalmente fuera del outcome. Comisión de salida se carga una sola vez.

## Mensual — OWNER_B (capital nunca reiniciado)

| Mes | Ciclos | Sin señal | Confirmaciones | Targets/eligibles | Entradas | Neto USDT | Equity final | DD MTM1m % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025-11 | 30 | 8 | 22 | 6/17 | 6 | -86.3326 | 9913.6674 | 1.0640 |
| 2025-12 | 31 | 10 | 21 | 7/15 | 3 | -74.1653 | 9839.5020 | 0.7481 |
| 2026-01 | 31 | 9 | 22 | 10/17 | 0 | 0.0000 | 9839.5020 | 0.0000 |
| 2026-02 | 28 | 4 | 24 | 9/18 | 5 | -68.3138 | 9771.1882 | 0.8386 |
| 2026-03 | 31 | 3 | 28 | 8/21 | 8 | -21.9263 | 9749.2619 | 0.7965 |
| 2026-04 | 30 | 6 | 24 | 8/19 | 0 | 0.0000 | 9749.2619 | 0.0000 |
| 2026-05 | 31 | 5 | 26 | 9/21 | 1 | -24.3730 | 9724.8889 | 0.2500 |
| 2026-06 | 30 | 7 | 23 | 12/18 | 5 | -32.4746 | 9692.4144 | 1.3954 |
| 2026-07 | 31 | 6 | 25 | 9/20 | 3 | 109.2499 | 9801.6643 | 0.5479 |
| 2026-08 | 31 | 5 | 26 | 11/22 | 2 | -48.9462 | 9752.7181 | 0.4994 |
| 2026-09 | 30 | 16 | 14 | 7/9 | 0 | 0.0000 | 9752.7181 | 0.0000 |
| 2026-10 | 31 | 5 | 26 | 10/21 | 3 | -51.5647 | 9701.1534 | 0.5287 |

## LONG / SHORT — simulación separada por lado

| Lado | n | Neto USDT | Media R | Win rate | PF neto |
|---|---:|---:|---:|---:|---:|
| LONG | 16 | -36.4760 | -0.088171 | 25.00% | 0.866121 |
| SHORT | 20 | -262.3706 | -0.531985 | 15.00% | 0.372097 |

## Sensibilidad: cierre simple con las MISMAS sesiones y niveles OWNER_B

No es PINE_A. Se verifica igualdad exacta de fechas y niveles de los365 ciclos; solo cambia cuerpo→cierre.
| Modelo | Confirmaciones | Targets/eligibles | Entradas | Neto USDT | Media R | IC95 R | PF | Clasificación |
|---|---:|---:|---:|---:|---:|---|---:|---|
| OWNER_B | 281 | 106/218 | 36 | -298.8466 | -0.334734 | [-0.7546551448063848, 0.1139124704124839] | 0.567082 | INCONCLUSIVE |
| OWNER_B_CLOSE_ONLY_SENSITIVITY | 323 | 153/299 | 63 | -817.6942 | -0.539729 | [-0.7806589498723887, -0.26568252283260824] | 0.363429 | NO EDGE |

Visita al target: cuerpo 48.62% vs cierre 51.17%.
Diferencia emparejada:-2.5467 puntos; IC95 bloques:[-7.245946427510836, 2.071737786023503].
Esperar cuerpo completo cambia también la hora y precio de la primera entrada, y a veces su lado.
No interpretar36 vs63 como simplemente eliminar27 operaciones idénticas. No se escoge ganador
ni se cambia la estrategia porque el control salga peor. Mensual de ambos:monthly.csv.

## Control de calidad y limitaciones

Primer resultado conservado con hash en reporting_fix_audit.json. Se corrigió exclusivamente la
cota de drawdown para incluir comisión de salida y extremos intraminuto con orden desconocido.
El auditor comprueba que ledgers, fills, PnL, curvas MTM observadas, CI y clasificaciones son idénticos.
El IC95 es incertidumbre histórica condicionada a este año y costes, no garantía de distribución futura.
Los fees son escenario, el slippage no está observado, faltan spread/latencia y costes de borrow SHORT.
El drawdown bajo depende en parte de poca exposición y tamaño limitado, no demuestra edge.
No hay live paper, orders, Telegram o Railway. Guardian, V8, ML RSI y protocolos intactos.

## Datos y gráficos para revisar

[Equity](equity.svg) · [Monthly CSV](monthly.csv) · [Resumen y manifests](summary.json)
[Todos los ciclos B](cycles_OWNER_B.csv) · [Todos los trades B](trades_OWNER_B.csv)
[Stress40x y bloqueo](STRESS_40X_NO_SL.md) · [Resultados completos comprimidos](study_results.json.gz)

- [Ejemplo objetivo: first_LONG_winner.svg](first_LONG_winner.svg)
- [Ejemplo objetivo: first_LONG_loser.svg](first_LONG_loser.svg)
- [Ejemplo objetivo: first_SHORT_winner.svg](first_SHORT_winner.svg)
- [Ejemplo objetivo: first_SHORT_loser.svg](first_SHORT_loser.svg)

SHADOW ONLY. TRADE AUTHORITY: NONE.
