# PRE_BITMAN_RESEARCH_AUDIT

Fecha de corte de esta auditoría: **2026-10-15**. Rama: `pre-bitman-research-audit`.
Base: última `main` recuperada, `9d0024a45d8e40193162a3864a876ca5ab61d1da`.

**Decisión previa a BITMAN:** reutilizar la infraestructura causal y los controles;
no promover automáticamente ningún motor de señales auditado. Confluence es
frágil, GREEN_RESUME 1H merece seguimiento pero es inconcluso, 15m management y
Early Breakout no superan sus criterios, y los SHORT A–G fueron rechazados.
No existe aquí evidencia forward suficiente para afirmar que una regla funciona
en producción. **No se ha implementado, optimizado ni seleccionado BITMAN.**

`FORWARD_VOLUME_DATA: PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR`

## Alcance, fuentes y separación de evidencia

- **HISTORICAL EVIDENCE:** artefactos persistidos en las ramas, no una ejecución
  nueva ni una actualización de sus datasets hasta el 15 de octubre.
- **EXISTING OOS EVIDENCE:** TEST cronológicos ya congelados en cada estudio.
  OOS respecto a su selección original; no son un TEST virgen para diseñar BITMAN
  después de haber leído estos resultados.
- **LIVE/FORWARD EVIDENCE AVAILABLE:** topología y deployment Railway, volumen
  montado y acceso a logs. Sirve para auditar disponibilidad, no rentabilidad.
- **LIVE/FORWARD EVIDENCE PENDING:** journals reales de señales/outcomes de `/data`.
  No se sustituyen por eventos reconstruidos ni por los logs parciales.

Fuentes reproducibles: [refs congeladas](research/pre_bitman_artifacts/refs.json),
[evidencia numérica y SHA256](research/pre_bitman_artifacts/historical_evidence.json),
[tablas comparables](research/pre_bitman_artifacts/TABLES.md),
[consulta Railway sanitizada](research/pre_bitman_artifacts/railway_readonly_evidence.json).
Cada archivo research inspeccionado conserva rama, commit, ruta, bytes y SHA256.
Las selecciones `best`/`selected` se leen tal como fueron archivadas: no se
vuelven a ordenar candidatos por TEST. No se reescribieron estudios originales.

## 1. Inventario de ramas: main no contiene toda la investigación

| Rama remota inspeccionada | Commit congelado | Contenido relevante | Archivos research ausentes en main |
|---|---|---|---:|
| confluence-engine-research | `6f83f9ab2451` | primer Confluence, benchmark, funding, neighbors/ablation | 14 |
| mlrsi-1h-research | `47eee36f7208` | LOW27 1H, 8 cohortes, gestión/control/regímenes | 15 |
| mlrsi-pattern-research | `c049302691e7` | LOW27 15m, hipótesis TP1/BE/trail, NO EDGE | 14 |
| early-breakout-shadow | `28a4ad821c8a` | observador y estudio cerrado NO EDGE | 0 |
| v8-bear-research | `5354d5ba7b60` | siete SHORT, financiado, contribución marginal | 11 |
| mlrsi-mtf-observer | `55c1c988df1d` | observer LOW29/PINE_PARITY_V4, recovery, journals | 0 (*) |
| main | `9d0024a45d8e` | Guardian, Copilot, forward audit, niveles, Early Breakout | 0 |
| v8-real-executor | `724f14fdd723` | ejecutor V8 independiente | 0 (*) |
| confluence-exact-mlrsi (**adicional**) | `01d567523981` | segunda pasada clustering RSI14/27 CLOSE | 23 |

(*) La columna cuenta solamente rutas bajo `research/`, no todo el árbol.
**main no contiene el observer ni el ejecutor V8** de esas dos ramas. Su código
operativo vive fuera de `research/`. Los ceros no implican equivalencia de ramas.
Los SHA completos y las rutas faltantes están en el inventario JSON.

La revisión adicional `confluence-exact-mlrsi` evita perder una investigación
directamente pertinente. Su antiguo nombre «exact» no acredita paridad con el
TradingView actual; tampoco se heredan como hechos actuales las reservas de una
copia de terceros descritas en aquel informe histórico.

## 2. Configuraciones distintas: no mezclar señales de ML RSI

| Sistema/estudio | Matemática efectiva | Mercado |
|---|---|---|
| Confluence original | aproximación RSI14 / EMA5 / thresholds fijos 45–55 | Binance USD-M perpetual |
| Confluence segunda pasada | RSI14/27 **CLOSE**, EMA4, k-means rolling 3000 | mismo perpetual |
| Pattern 15m / ML RSI 1H | **LOW27**, EMA4, k-means causal rolling 3000 | Binance spot |
| Manual Copilot actual | **LOW27** 1H, EMA4, rolling causal existente | dirección con Binance; riesgo con Bitunix |
| Observer MTF actual | **LOW29**, EMA4, **PINE_PARITY_V4**, array persistente/gate Pine | Binance spot |

PINE_PARITY_V4 conserva literalmente las peculiaridades de arrays/NA/igualdad
del source entregado por el usuario; en su camino normal los thresholds retienen
percentiles. **No es el k-means convencional rolling de los estudios LOW27.**
Hay fixtures de la tabla TradingView para una comparación concreta; no prueban
paridad universal. `Exact BackQuant TradingView parity is NOT proven.`
APPROACHING y PROVISIONAL no son eventos confirmed ni evidencia de entrada.

Consecuencia: una expectativa LOW27 histórica no valida LOW29 V4 live. Los
journals deberán separarse por `config_version`, TF y modo confirmed/provisional.
No se modifica ninguno de esos algoritmos en esta auditoría.

## 3. CONFLUENCE ENGINE — HISTORICAL / EXISTING OOS

Fuente: [informe original en su commit](https://github.com/ilgirardin697-cpu/btc-copilot-bitunix/blob/6f83f9ab2451dd3ef33e9ca7ab90b2d15dd95258/research/CONFLUENCE_RESULTS.md).
710.208 velas 5m perpetual; 2020-01-01 → 2026-10-02 00:00 UTC; 7.398
funding events. TRAIN 2020–2021, VALIDATION 2022–2023, TEST 2024–corte.
352 candidatos iniciales: selección sobre TRAIN/VALIDATION, sin corrección
completa por múltiples pruebas. No llamar a esta búsqueda pequeña/independiente.

### Candidato D_60m_R60_1_opposite

Trigger **1H**, régimen SMA200 **1H** (`R60`), LONG + taker buy ≥60% + estado
momentum verde aproximado; salida opposite/invalidación del régimen. No incluye
sweep, estructura 15m, divergencia ni ML RSI LOW29 V4. El benchmark V8 usa **4H**.

| Split | Return | CAGR | Sharpe | Sortino | MaxDD | PF | Expectancy/trade | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TRAIN | +90,77% | 38,09% | 1,697 | 2,470 | −12,43% | 3,570 | +2,3751% | 30 |
| VALIDATION | +41,39% | 18,92% | 1,395 | 2,273 | −10,36% | 2,927 | +1,6821% | 23 |
| TEST | +68,76% | 20,95% | 1,121 | 1,692 | −15,58% | 1,845 | +0,5906% | 96 |
| ALL | +355,17% | 25,17% | 1,362 | 2,048 | −15,58% | 2,450 | +1,1184% | 149 |

| Control, mismo TEST | Return | CAGR | Sharpe | Sortino | MaxDD | PF | n trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| V8 SMA200 4H LONG/FLAT | +69,83% | 21,22% | 0,767 | 1,134 | −33,43% | 1,865 | 82 |
| Buy & hold, proxy de precio sin funding | +100,18% | 28,69% | 0,775 | 1,107 | −53,47% | NA | 1 |
| Funded hold | +64,30% | 19,77% | 0,606 | 0,865 | −60,71% | NA | 1 |

Los TRAIN/VALIDATION/ALL de los tres controles están completos en TABLES.md.
El D mejora Sharpe/DD, no CAGR/return frente a V8. Bootstrap pareado contra V8:
diferencia de crecimiento log anual −4,85%, IC95 [−33,43%, +23,57%], frecuencia
positiva 35,8%. No demuestra superioridad estadística; no corrige multiplicidad.

### Fragilidad 55/60/65 y ablation

| Taker | VALIDATION Sharpe | TEST return | TEST expectancy |
|---|---:|---:|---:|
| 55% | −0,247 | −20,23% | −0,0566% |
| 60% (congelado) | 1,395 | +68,76% | +0,5906% |
| 65% | 1,929 | −1,82% | −0,0998% |

Una pequeña variación destruye el resultado. No seleccionar 55/65 ni otro umbral
ahora. Los vecinos sweep 12/24/48 coinciden en D porque D no usa sweep: son
duplicados funcionales, **no nueve confirmaciones independientes**.

| Ablation de entradas, salida común | TEST return | TEST expectancy |
|---|---:|---:|
| R | −95,97% | −0,1659% |
| L | −4,45% | +0,0026% |
| M | −95,71% | −0,1689% |
| RL | +21,25% | +0,1371% |
| RM | −14,28% | −0,0102% |
| LM | +77,84% | +0,4771% |
| RLM | +68,76% | +0,5906% |

La salida sigue dependiendo de régimen/momentum incluso al quitar esos bloques
de entrada; reentradas pueden inflar turnover. Son diagnósticos de filtros,
no siete estrategias plenamente independientes. El control con salida ATR común
da LM +2,32% y RLM +20,17%, pero tampoco prueba significancia. El bootstrap de
tercera confirmación en TEST frente a LM da −1,91% de crecimiento log anual,
IC95 [−11,11%, +3,41%], frecuencia positiva 32,4%. **Confluencia no demostrada**.
No convertir un gate booleano de ablation en prueba estadística.

### Costes, funding, concentración y walk-forward

1x nominal inicial, cantidad fija, ejecución apertura siguiente, sin liquidación
exchange. Coste base 10 bps/lado (mitad fee/mitad slippage); funding histórico
firmado. MaxDD de cierres, no peor drawdown intrabar. El notional/equity puede
derivar: «1x al entrar» no equivale a leverage constante ni simulación de margen.

| Coste/lado | TEST return |
|---|---:|
| 5 bps | +85,73% |
| 10 bps | +68,76% |
| 20 bps | +39,28% |

Costes ALL: fees/slippage/funding y turnover de cada split en el JSON completo.
El funded hold ALL alcanza insolvencia (−100%): no confundirlo con spot hold.
Retorno ALL sin mejor trade +268,71%; sin mejores tres +154,52%. Intervalo
bootstrap de expectancy ALL [0,4787%, 1,8196%]; no es un IC de TEST independiente.
El walk-forward archivado es **evaluación anual de parámetros fijos**, no
reentrenamiento rolling: 2024 +65,11%, 2025 +10,29%, 2026 parcial −7,33%.
Resultados anuales, costes y muestras se detallan en la sección 7 y TABLES.md.

**Conclusión original preservada: PROMISING — MORE RESEARCH; no promoción.**

### Segunda pasada con clustering realista de la época

[Informe de la rama adicional](https://github.com/ilgirardin697-cpu/btc-copilot-bitunix/blob/01d5675239816f5953f1213f6729c20e21975aff/research/CONFLUENCE_EXACT_MLRSI_RESULTS.md).
Seleccionado antes de TEST: `RSI27_STATE_M_0.60_opposite_1`, **momentum solo**,
CLOSE27 rolling, no confluencia ni filtro taker efectivo.
TEST: +24,01%, CAGR 8,13%, Sharpe 0,411, DD −44,38%, PF 1,289,
expectancy +0,6734%, n=64. 20 bps/lado conserva +9,07% TEST.
Sin mejor operación TEST: **−15,25%**; sin mejores tres: **−46,44%**.
2025 anual independiente −18,62%; 2026 −5,27%.

STATE/EVENT empatan en PnL para M/opposite porque el estado repetido llega con
posición abierta; sus probabilidades por señal usan denominadores distintos.
La aparente estabilidad taker del seleccionado es vacua: no utiliza taker.
RLM CLOSE27 a55/60/65 da TEST −2,30%/+34,26%/−3,85%; 65% tiene muestra ínfima.
No se rescata un vecino después de mirar TEST. Clasificación archivada
PROMISING — MORE RESEARCH, restringida aquí por concentración TEST y drawdown.

## 4. ML RSI 1H — hipótesis y variantes

[Informe congelado](https://github.com/ilgirardin697-cpu/btc-copilot-bitunix/blob/47eee36f7208382d7939a047161c49f61136378e/research/mlrsi_1h/RESULTS.md).
Spot público: 754.202 velas 5m desde 2019-08-01, 62.843 horas completas,
18 gaps no interpolados; corte 2026-10-03 21:00 UTC. LOW27/EMA4 rolling.
Gestión seleccionada solo con TRAIN/VALIDATION. Entrada next 1H open, costes
5 bps fee +2 bps slip, stop slip5; stress 6/5/10. Funding/basis excluidos.

| Evento | Barras confirmación | Gestión congelada | TEST n | Media neta | PF |
|---|---:|---|---:|---:|---:|
| GREEN_CROSS | 1 | color sin SL | 207 | +0,0443% | 1,031 |
| GREEN_RESUME | 1 | color sin SL | 228 | +0,7273% | 1,534 |
| RED_CROSS | 1 | color runner, SL1 ATR económico | 281 | −0,1952% | 0,565 |
| RED_RESUME | 1 | runner SL1 / trail1 ATR económico | 266 | −0,1783% | 0,647 |
| GREEN_CROSS | 2 | runner SL1 / trail1,5 ATR | 177 | −0,2213% | 0,516 |
| GREEN_RESUME | 2 | runner SL1 / trail1,5 ATR | 141 | −0,1065% | 0,727 |
| RED_CROSS | 2 | fixed1R / SL1 ATR | 226 | −0,1351% | 0,710 |
| RED_RESUME | 2 | fixed2R / SL1 ATR | 182 | −0,2978% | 0,597 |

**GREEN_RESUME 1 barra es interesante, no edge confirmado.** Mantiene +0,647%
stress y +0,473% sin mejores tres. IC95 semanal de su propia media neta
[−0,404%, +1,805%] incluye cero. Contra control emparejado: n=216, ventaja
+1,094 puntos porcentuales, IC95 [+0,117%, +2,029%]. Las dos afirmaciones son
compatibles: el contraste relativo es positivo, la rentabilidad absoluta incierta.

Los 228 eventos se solapan. Equity secuencial: solo71 trades, +7,183% acumulado
y DD31,604% al cierre de trades; DD intratrade no incluido. No anualizar la media
por evento como CAGR ni sumar 228 rendimientos como una cartera operable.

Con el **mismo** color sin SL, dos barras produce +0,915%/n141/PF1,669, pero
IC95 [−0,372%, +2,145%] y ventaja de control incierta. No sustituye al modelo
preseleccionado de dos barras mostrado en la tabla. Los vecinos SL0,75/1/1,25/1,5
del GREEN_RESUME de una barra dan medias netas −0,004%/+0,055%/−0,010%/+0,087%.
Runner ATR1/trail1,5: −0,146%. El resultado depende mucho de dejar correr sin SL;
no justifica quitar protección real ni diseñar un stop con pérdidas ilimitadas.

HTF descriptivo, mismo GREEN_RESUME color sin SL:
sin filtro n228/+0,727%/PF1,534; 4H alineado n183/+0,992%/PF1,794;
1D n144/+0,921%/PF1,759; ambos n126/+1,005%/PF1,862.
La alineación merece hipótesis nueva pre-registrada, **no filtro elegido por TEST**.
A24h, +1/−1 es50,4% y +2/−1 es25,0% en n228: un buen trade de color hasta72h
no implica una gran probabilidad de paso favorable a24h.

GREEN_CROSS es marginal y negativo bajo stress; su media sin mejores tres
es −0,174%. Los dos RED y sus variantes seleccionadas no tienen edge neto
positivo. No reciclarlos automáticamente como motor SHORT.
**Clasificación preservada: INTERESTING BUT INCONCLUSIVE.**

## 5. ML RSI 15m y EARLY BREAKOUT — lo que ya fracasó

[15m congelado](https://github.com/ilgirardin697-cpu/btc-copilot-bitunix/blob/c049302691e7857691adaf652cd283874c0734a2/research/mlrsi_pattern/RESULTS.md):
LOW27 rolling. Modelos congelados de una barra con TP1/BE/trail500, SL0,30%:

| Evento | TEST n | Media neta | PF |
|---|---:|---:|---:|
| GREEN_CROSS | 745 | −0,1874% | 0,240 |
| GREEN_RESUME | 850 | −0,1788% | 0,295 |
| RED_CROSS | 1084 | −0,2002% | 0,218 |
| RED_RESUME | 980 | −0,1991% | 0,223 |

Dos barras y vecinos 0,25/0,30/0,40/0,50% o trails ATR no rescatan el modelo.
Las salidas opposite tenían algunos resultados positivos, pero no superaron
robustez/concentración/control y la selección original. **15M = NO EDGE for
tested hypothesis**, no una demostración de que todo indicador 15m sea inútil.
El 2026 parcial de las cuatro gestiones seleccionadas sigue negativo.

[EARLY BREAKOUT](research/early_breakout_artifacts/EARLY_BREAKOUT_RESULTS.md):
selección congelada `p0.2_n2_v1.5_h1_a1`, squeeze/volumen/MACD/hold.

| Split | Squeezes | Developing | +1/−1 a24h | +2/−1 | False breakout |
|---|---:|---:|---:|---:|---:|
| TRAIN | 3155 | 838 | 47,4% | 30,1% | 48,1% |
| VALIDATION | 3095 | 795 | 42,6% | 22,8% | 55,1% |
| TEST | 4429 | 891 | 44,1% | 24,0% | 53,0% |

Control TEST +1/−1 46,6%; IC95 diferencia [−7,17,+2,47] puntos porcentuales.
Vecinos ATR15/20/25:45,1/44,1/45,4%, sin mejora estable. Sin top3 eventos, media
direccional24h −0,0100%. Lead mediano930min se calcula solo sobre153 matches:
no es anticipación garantizada ni evidencia de rentabilidad. En2026 n212,
+1/−1 45,3%, false breakout47,2%. **NO EDGE; no gate ni pieza automática de BITMAN**.
El incidente82,6k→84k quedó sin fecha inequívoca; no se inventó un matching.

## 6. V8 BEAR — rechazo de motores SHORT

[Fuente](https://github.com/ilgirardin697-cpu/btc-copilot-bitunix/blob/5354d5ba7b609201f12e5359e46fd2f696e2fc07/research/V8_BEAR_RESULTS.md).
4H perpetual, hasta2026-10-01 12:00 UTC. TRAIN2020–2022, TEST2023–corte:
**splits distintos de Confluence/MLRSI**. Coste10bps por unidad de cambio de
exposición y funding histórico; cartera por pesos objetivo, distinta de cantidades
fijas de Confluence. No comparar directamente sus CAGR como un ranking común.

| SHORT | Motor | Return ALL aislado | Return TEST aislado |
|---|---|---:|---:|
| A | espejo close < SMA200 4H | −57,14% | −44,51% |
| B | A + SMA200 slope negativa | −32,72% | −28,30% |
| C | régimen/slope + Donchian20/10 | +4,02% | −0,25% |
| D | régimen + Donchian55/20 | −40,55% | −27,96% |
| E | EMA50 < EMA200 y close < EMA50 | −65,81% | −49,56% |
| F | momentum504 barras | −76,63% | −43,58% |
| G | cierre diario < SMA50 diaria | −29,40% | −23,00% |

TRAIN preseleccionó F y C, no un ganador TEST. V8 LONG/FLAT: CAGR ALL36,10%,
Sharpe0,96, DD−52,50%, funding incluido. C+V8 SHORT0,25x: CAGR37,34%, Sharpe0,98,
DD−54,30%. Mejora pequeña con DD global peor. Bootstrap pareado TEST de C:
incremento anual0,59%, IC95[−3,96%,+5,73%]. C vecinos:0/6 SHORT aislados positivos
TEST. Sin mejor SHORT2022, CAGR combinado35,74% < baseline36,10%.
**REJECT SHORT ENGINE**: no reutilizar un espejo LONG ni un buen2022 como edge SHORT.

## 7. Diagnóstico2026: evidencia, límites y atribución

2026 en los estudios es **enero–principios de octubre**, no año completo ni
actualización histórica hasta15/10. El número pequeño de trades y el cambio de
mercado entre estudios impiden una atribución causal concluyente por bloque.

| Año D, flat anual | Return | PF | n | Win rate | Avg winner | Avg loser | Exposición temporal |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024 | +65,11% | 5,346 | 24 | 54,17% | +4,974% | −1,100% | 20,70% |
| 2025 | +10,29% | 1,404 | 35 | 37,14% | +2,932% | −1,234% | 16,58% |
| 2026 | −7,33% | 0,755 | 37 | 29,73% | +1,911% | −1,072% | 21,62% |

**Diagnóstico nuevo derivado de los artefactos existentes:** la contribución cash
bruta de precio, `net return + fees + slippage + funding`, pasa +75,76% → +18,57%
→ **+0,22%**. En2026 fees3,598% + slippage3,598% + funding0,356% del equity inicial
convierten ese residual en −7,327%. No es un rerun sin costes, pues los tamaños
reales del backtest ya dependían de los costes. Funding es mucho menor que
turnover/ejecución. Pierde frecuencia de aciertos y magnitud de ganadores, no se
observa una ampliación equivalente de la pérdida media. No «arreglarlo» bajando costes.

| Bloque | Evidencia2026 | Diagnóstico permitido |
|---|---|---|
| Trend | D/R60 se deteriora; GREEN_RESUME alineado funciona mejor en TEST | no demuestra que toda tendencia haya dejado de funcionar; D no es V8 4H |
| Flow/taker | D60 falla2026 y55/65 fallan TEST | umbral frágil y edge conjunto debilitado; falta ablation anual comparable para causalidad |
| Momentum aproximado | D usa RSI14/EMA5 fijo | no atribuir su caída al LOW29 V4 que D nunca utilizó |
| ML RSI LOW27 1H | GREEN_RESUME1 n80/+0,718%/PF1,454; GREEN_CROSS1 n62/+0,155%/PF1,108 | no colapso universal; evidencia dependiente de gestión/color sin stop |
| ML RSI SHORT 1H | RED_CROSS1 n68/−0,181%; RED_RESUME1 n63/−0,244% | no edge neto demostrado, problema previo a2026 también |
| Structure/sweep | D no los usa | no se puede culpar a estos bloques de la caída de D |
| Volatility | GREEN_RESUME1 TEST Q1/Q2 positivos; Q3 n17/−2,407%, Q4 n3/−0,948% | pista de régimen, muestra pequeña; no nuevo corte de volatilidad elegido por TEST |
| Short filters | V8 A–G TEST débiles, C marginal | ningún motor bajista robusto a reutilizar automáticamente |

Para separar efecto precio/regímenes de deterioro del predictor se necesita un
contraste condicional **predefinido**: misma dirección/mes/volatilidad/HTF, control
emparejado, costes iguales y bloques calendario. Las tablas disponibles no
identifican causalmente cuál de trend/flow/momentum falló; afirmar más sería inventar.

## 8. LIVE/FORWARD EVIDENCE AVAILABLE

Lectura Railway del15/10, sin valores de variables ni secretos:

- proyecto `victorious-energy`; Guardian `SUCCESS`, inicio `python trade_guardian.py`,
  source **mlrsi-mtf-observer**/`55c1c988df1d`, última instalación07/10 13:59:36UTC.
- volumen `igod-guardian-data`, `/data`,500MB. Montaje comprobado; contenido no leído.
- V8 `SUCCESS`, `python v8_executor.py`, branch `v8-real-executor`, SHA `724f14fdd723`.
- consulta limitada101 logs Guardian,15/10 18:42:52–18:59:32UTC. No contiene un
  export íntegro de journals; **no se usa para probabilidades, muestras o rendimiento**.
- proyecto `igod-research-lab` existe sin servicios; no se creó ni arrancó ninguno.

No se deduce SHADOW/PROTECT ni el arming real por nombres de variables. No se
leyeron sus valores; esta auditoría **no cambió ninguna configuración ni permiso**.
Tampoco el montaje demuestra supervivencia del canary o integridad de todos los
archivos. Eso requiere leer la copia autorizada de los journals y sus manifests.

## 9. LIVE/FORWARD EVIDENCE PENDING

`FORWARD_VOLUME_DATA: PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR`

| Directorio | Archivos buscados | Acceso / n / resultados |
|---|---|---|
| `/data/copilot_audit/` | signals/outcomes/snapshots JSONL, state y canary | PENDING / NA / NA |
| `/data/mlrsi/` | igod_mlrsi_events.jsonl, state y caches | PENDING / NA / NA |
| `/data/early_breakout/` | events/outcomes/snapshots JSONL, state | PENDING / NA / NA |

El conector ofrece configuración/deployments/logs, no filesystem/exec/export.
No hay CLI Railway instalada/autenticada ni export local. El usuario confirmó
que no puede aportar acceso adicional ahora. **NA no es cero eventos**.
No se solicitaron credenciales Bitunix, Telegram ni Railway. No se consultaron
posiciones/PnL privados; ninguna rentabilidad del usuario es evidencia de señales.

Por tanto quedan sin medir con datos reales: GREEN_CROSS/GREEN_RESUME/RED_CROSS/
RED_RESUME por15m/1H/4H, entradas3/3 GREEN/RED, LONG_ALLOWED/SHORT_ALLOWED y
GOOD/CAUTION/POOR. No hay aquí resultados forward nuevos que puedan publicarse
honestamente. La ausencia de acceso **no bloquea esta auditoría histórica**.

### Utilidad reproducible de importación read-only

[research/import_forward_journals.py](research/import_forward_journals.py) acepta
una copia de `/data` con los tres subdirectorios, o un subdirectorio individual.
**No importa AuditStore ni otro store operativo**, pues esos constructores pueden
crear locks/reparar tails. No abre los originales en modo escritura, no trunca
líneas incompletas, no pide red ni credenciales, no descarga ni arranca módulos.
Outputs obligatoriamente fuera del árbol fuente; hashes antes/después detectan
cambios. No se genera ningún archivo en `/data`.

```powershell
python -m research.import_forward_journals `
  --input-dir C:/exports/igod-data-copy `
  --output-dir C:/reports/igod-forward-audit `
  --as-of 2026-10-15T19:00:00Z `
  --market-csv C:/exports/binance-spot-5m.csv
```

CSV opcional: `time,open,high,low,close`, aperturaUTC en milisegundos, orden
estricto y sin duplicados. Si falta, aprovecha outcomes completos FORWARD_LIVE
de Copilot ya registrados; las barreras/horizontes ausentes quedan NA, no fallos.
Si se aporta, recalcula **solo outcomes** de eventos existentes a1/4/12/24/48/72h,
MFE/MAE y +0,5/−0,5, +1/−1, +2/−1, +3/−1,5. LONG/SHORT simétricos.

El horizonte comienza en la observación registrada, nunca se backdata al candle
antiguo; se excluye la5m parcial que contiene la observación. La referencia es
el cierre ya conocido del evento, **no un fill ejecutado**. Los gaps censuran el
horizonte, los inmaduros siguen pendientes; doble toque5m es AMBIGUOUS excluido
y contado, NEITHER permanece sin éxito. Las frecuencias históricas de otros
estudios con adverse-first no son comparables sin armonizar esta convención.

Solo confirmed se evalúa. Se excluyen fuentes históricas, snapshots como señales,
provisional/approaching, duplicados conflictivos y catch-up ML RSI retrasado una
TF o más. Un journal sin etiqueta de recovery no distingue perfectamente todos
los catch-ups recientes: se conservan lag/config y se debe inspeccionar cobertura;
no se afirma que cada fila equivalga a una alerta live entregada. Versiones no
se mezclan. Los3/3 preservan su evento/TF original (el observer los journaliza
como evento global, habitualmente con TF15m), no se fabrican tres señales.

`forward_report.json` y `FORWARD_REPORT.md` contienen inventario SHA256, incidencias,
cohortes, n, rangos de observación, madurez por horizonte, medias/medianas y pasos
favorables. Se separa ALL/GOOD/CAUTION/POOR/LONG/SHORT de Copilot. Conteos de Early
Breakout son inventario, sin cambiar NO EDGE ni inventar dirección a un squeeze.
Los grupos pequeños llevan advertencia. No significancia ni PnL de una estrategia.

### Qué aportarán esos journals y cómo podría cambiar BITMAN

1. Fechas reales de inicio/fin, n únicos, cobertura, pérdidas de observación,
   reboots, configs mezcladas y eventos retrasados. Permitirán saber si la muestra
   es suficiente antes de interpretar porcentajes.
2. Distribuciones posteriores reales por evento/TF y3/3, incluidos los seis
   horizontes y controles emparejados definidos antes de comparar. El importador
   aporta descriptivos; los controles/bootstrap se pre-registrarán al contar
   con una muestra utilizable, sin inventar un IC hoy.
3. Separación dirección y timing: ¿GOOD al inicio del episodio mejora a
   CAUTION/POOR? El audit actual no registra otra entrada si el mismo episodio
   pasa después aGOOD; no confundir las cohortes.
4. Comparación LOW29 V4 forward con LOW27 histórico y estabilidad por fecha/
   volatilidad/HTF. Si no replica, no trasladar el edge de LOW27 aLOW29.
5. Comprobación de que3/3 añade información frente a1H, de que los SHORT no
   siguen perdiendo y de que el efecto sobrevive fuera del estudio2026 existente.

**Sí, puede cambiar la selección BITMAN.** Evidencia forward favorable y suficiente
podría conservar una pieza actual y reducir el alcance de FUSION; deterioro,
concentración, costes o falta de ventaja frente al control podrían descartarla.
Una muestra pequeña no reemplaza un TEST ni rescata una hipótesis fallida.
Se compararán hipótesis predefinidas, no se escogerá el mejor TF/barrier después.

## 10. Reutilizar, descartar, mantener inconcluso

| Componente | Recomendación basada en evidencia |
|---|---|
| Closed candles, delayed pivots, next-bar fills, manifests y split locks | REUTILIZAR como infraestructura causal |
| V8 LONG/FLAT | CONSERVAR como benchmark independiente; ninguna modificación del executor |
| Fees/slippage/funding y estrés | REUTILIZAR y armonizar mercado/sizing entre competidores |
| Journal prospectivo, dedupe, madurez/censura | CONSERVAR; importar copias antes de declarar validación forward |
| D60 Confluence | COMPARADOR congelado; no adoptar por su CAGR/Sharpe bonito |
| GREEN_RESUME 1H + contexto HTF | HIPÓTESIS prioritaria, inconclusa; no desplegar ni confundir presets |
| Manual Copilot direction/entry-quality | NO CAMBIAR; evaluar sus episodios reales antes de sustituir piezas |
| Guardian protección | NO TOCAR; su función de capital es independiente del alpha |
| Umbral taker60 como verdad universal / más confirmaciones siempre mejor | DESCARTAR esa conclusión; neighbors/ablation no la sostienen |
| TP1→BE ingenuo→trail500 con SL0,30% en15m | NO REPETIR el mismo grid para buscar rescate |
| Early Breakout como permiso de entrada | DESCARTAR; NO EDGE |
| SHORT espejo, A–G sin nueva hipótesis independiente | NO PROMOVER / no repetir tuning retrospectivo |

**Ningún componente de señales puede afirmarse robusto simultáneamente OOS y
forward con los datos hoy accesibles.** Esto no exige reescribirlo: exige medir.

## 11. Hipótesis concretas para un BITMAN posterior

La auditoría se escribe antes de diseñar reglas. `BITMAN_CLASSIC` necesita una
definición/fuente objetiva: ese nombre por sí solo no especifica fórmulas,
timeframes, entradas, salidas o costes. No se inventa una supuesta estrategia
clásica ni se la optimiza en esta entrega.

Protocolo candidato, todavía **no implementación**:

- H1 CLASSIC añade información a un control EMA trend simple y al drift deBTC,
  con misma exposición/mercado/costes y controles emparejados; no basta ganar en bull.
- H2 FUSION mejora **una sola pieza** de CLASSIC al introducir contexto1H/4H
  predefinido o GREEN_RESUME1H, manteniendo el resto idéntico. Ablation con salidas
  también independientes de los bloques retirados.
- H3 GOOD timing mejora a dirección sola. Solo eventos realmente registrados;
  no convertir sus soportes/resistencias en permiso nuevo en producción.
- H4 el deterioro2026 es explicable por menor continuación tras el impulso y
  turnover, contrastado con regímenes/control; no arreglarlo con nuevos umbrales.
- H5 SHORT aporta una contribución independiente y estable. Rechazarlo si no
  mejora aislado/marginalmente; nunca asumir simetría de LONG.

Competidores obligatorios: V8 SMA2004H, D congelado, MLRSI1H con sus filtros
predefinidos como diagnóstico, EMA trend simple y buy&hold. Antes de comparar:
misma serie spot/perp, rango/splits, sizing, fricciones/funding, warmup,
equity mark-to-market y tratamiento de gaps/dobles toques. Una tabla de resultados
procedentes de estudios distintos **no resuelve esa competición**.

Congelar reglas y pocos vecinos en TRAIN/VALIDATION antes de un nuevo TEST.
El TEST2024–oct2026 ya se ha leído repetidamente: reportarlo como OOS reutilizado,
con sensibilidad de selección, no validación independiente de BITMAN. Reservar
un corte temporal posterior al protocolo y el forward futuro para confirmación.
Bootstrap calendario, concentración top1/top3, años/regímenes, muestras, costes
stress y ablation son necesarios; no sumar indicadores correlacionados.

No volver a probar: un screenshot como etiqueta, buscar el mejor55/60/65 enTEST,
rescatar SHORT solo por2022, interpretar un lead condicional como edge, usar3/3
como entrada por definición, o sustituir protecciones por una salida color sinSL.

## 12. Reproducción, validación y límites de esta entrega

```powershell
# Ya hay refs.json congelado; no volver a --freeze para cambiar la muestra.
python -m research.pre_bitman_audit
python -m py_compile research/pre_bitman_audit.py research/import_forward_journals.py test_pre_bitman_audit.py
python -m unittest test_pre_bitman_audit -v
python -m unittest discover -v
git diff --check
```

El extractor requiere los objetos Git de las refs congeladas. No ejecuta selección,
no baja nuevos precios ni altera artefactos originales. Los tests forward usan
fixtures sintéticos, **no evidencia live**. La utilidad no se ha ejecutado sobre
journals Railway porque no son accesibles. Las pruebas cubren hashes inmutables,
tail corrupto sin reparación, dedupe, versiones, fuente prospective, no backfill,
closed5m, madurez, gaps, retornos LONG/SHORT, MFE/MAE, las cuatro barreras,
outcomes ya guardados, determinismo y ausencia de red/stores/capacidades operativas.

Validación final local: **29/29 tests dedicados, 408/408 de unittest discover,
0 fallos y 0 skips** con el Python habitual del proyecto. Compilación y
`git diff --check` pasan. Un primer intento con un intérprete embebido antiguo
de cache no era válido: importaba un namespace `requests` incompleto, sin
`sessions`. Se repitió la suite con el intérprete habitual y dependencias reales;
no se alteró producción ni se ocultaron tests para resolver ese entorno.
Los archivos operativos del worktree son idénticos a la main congelada; también
se guardaron hashes de V8 y ML RSI en sus ramas reales. No se abrió ni ejecutó
ningún store sobre el volumen Railway.

V8 UNCHANGED. GUARDIAN PROTECTION UNCHANGED. ML RSI MATH UNCHANGED.
EARLY BREAKOUT UNCHANGED. NO MERGE. NO REAL ORDER. NO RAILWAY DEPLOY.
