# Cómo leer y usar I-GOD

I-GOD tiene sistemas separados. Una señal de uno no activa ni sustituye a los demás. Este mapa describe la versión preparada en Git: estos PRs **no despliegan Railway**, no cambian variables y no arman protección o ejecución. Los nuevos textos y el registro forward aparecerán cuando se ejecute su versión correspondiente.

## 1. Manual Copilot: evidencia para decidir manualmente

Ayuda a Igor a distinguir LONG, SHORT o esperar. Usa tendencia 4H/1H, ML RSI27 LOW EMA4 causal, flujo taker, estructura 15m confirmada y calidad de entrada. Solo velas cerradas; no usa pivotes futuros como conocidos. No ejecuta operaciones.

El lenguaje de dirección es:

| Estado visible | Significado |
| --- | --- |
| 🟢 LONG CONFIRMADO | Las reglas actuales apoyan LONG; falta comprobar el momento de entrada. |
| 🔴 SHORT CONFIRMADO | Las reglas actuales apoyan SHORT; falta comprobar el momento de entrada. |
| 🟡 SIN DIRECCIÓN CONFIRMADA | Las tendencias o confirmaciones necesarias no están alineadas. Esperar. |
| ⚫ DATOS INSUFICIENTES | No se puede verificar evidencia suficiente. No operar basándose en esa lectura. |

Dirección y entrada son dos cosas distintas. GOOD permite mostrar «PUEDES BUSCAR ENTRADA» según las reglas actuales. CAUTION/POOR pide esperar mejor entrada o no perseguir precio, aunque la dirección siga confirmada. No significa certeza ni probabilidad medida. Las reglas de dirección y entrada no se han optimizado en esta fase.

Los niveles también tienen dos escalas: **R1/S1 locales 15m** para contexto cercano y **R2/S2 estructurales 1H**. Se calculan de forma independiente con pivotes confirmados. Un nivel local a ≤0.15 ATR1H del mark recibe la etiqueta «Muy cercano — nivel local/timing»; esta etiqueta no cambia dirección o entrada. Si el mark cruza un nivel, se avisa de que falta cierre 15m/1H y no se reclasifica por ello. Cruzar R1/S1/R2/S2 no concede permiso por sí solo. Si no hay pivotes suficientes, no se inventan niveles.

## 2. Trade Guardian: posición real y capital

Lee la posición BTCUSDT real de Bitunix, mark, liquidación, leverage y protección existente. Vigila distancias en porcentaje y ATR. Sus estados NORMAL/WARNING/DANGER/EMERGENCY describen proximidad a liquidación, independientemente de la dirección del Copilot.

**Actualmente SHADOW/desarmado: la protección automática no está activa.** Un objetivo catastrófico teórico mostrado en Telegram no demuestra que ese stop exista en Bitunix. Guardian no lo colocará automáticamente en SHADOW. Revisa tus órdenes reales y su trigger en la aplicación.

Una posición contraria a la dirección confirmada genera aviso, nunca cierre automático por dirección. Guardian nunca abre, aumenta, promedia o invierte una posición. La única posibilidad de cierre automático de su V1, si se armara en un proceso de auditoría futuro, sigue siendo una emergencia de capital/liquidación con sus verificaciones y triple-arm. Los comandos no pueden armarlo.

El primer fallo de verificación fresca ya bloquea mutaciones. Los mensajes progresan de amarillo transitorio a naranja degradado y rojo sin datos fiables; la conexión recuperada se anuncia una vez. No interpretar un aviso amarillo como una operación de emergencia. Tampoco confiar en datos viejos.

`NORMAL risk does NOT mean guaranteed safe.`

NORMAL no es garantía de seguridad: gaps, fallos de exchange, interrupciones y slippage extremo pueden causar liquidación. Guardian tampoco garantiza prevenirla.

## 3. Copilot Forward Audit: qué pasó después de las señales

Es investigación descriptiva sin trading. Registra una transición observada WAIT/opuesta → LONG_ALLOWED o SHORT_ALLOWED, una vez por episodio continuo. WAIT rearma; UNKNOWN no. Una dirección ya activa al primer arranque no recibe un inicio inventado. El reinicio conserva el episodio.

Congela calidad y evidencia al inicio. Evalúa velas públicas 5m posteriores, a 1/4/12/24/48h: retorno direccional, MFE/MAE y orden de barreras. No usa el PnL de Igor para demostrar rendimiento de la señal. GOOD es el subconjunto de episodios que **empezaron** con GOOD; una mejora posterior no reescribe la entrada original.

`/stats` separa ALL/GOOD/CAUTION/POOR/LONG/SHORT, siempre con n, maduros, pendientes e incompletos. Los pendientes no son fracasos. Huecos de datos se censuran; un toque simultáneo de ambas barreras en una vela no permite conocer el orden. Muestras pequeñas se advierten y no se presentan como edge probado. Estos resultados no incluyen un sistema de entradas/salidas, fees o slippage.

El registro empieza al ejecutar la nueva versión, sin backfill histórico presentado como live. Se guarda en `/data/copilot_audit`: state atómico y journals fsynced de señales, resultados e instantáneas diarias. **Necesita un volumen persistente de Railway que cubra `/data`**; este trabajo no lo configura. El canary empieza en amarillo; `/stats` solo muestra recuperación tras reinicio en verde cuando otro proceso reabre y guarda su UUID. Un canary corrupto o perdido no da esa garantía. Esta prueba no certifica recuperación ante desastres ni la infraestructura. Fallos de auditoría no detienen el bucle de protección.

`Forward statistics are signal statistics, not Igor's account returns.`

Con el tiempo, este registro permitirá examinar si las señales muestran un resultado posterior útil. No lo demuestra antes de acumular evidencia suficiente.

## 4. V8: estrategia mecánica independiente

V8 tiene sus propias reglas mecánicas, estado, señales y gates. **No interpretes una señal V8 como decisión del Manual Copilot.** El texto «V8 STRATEGY SIGNAL» lo distingue; LONG detectado no demuestra una apertura. FLAT es un objetivo sin exposición, no una entrada SHORT.

La ejecución real continúa desarmada por configuración. El ajuste de mensajes está aislado en la rama `v8-real-executor`; no se llevó su implementación de ejecución a main ni se desplegó. Si en el futuro se habilitara, los mensajes deben distinguir habilitación de configuración, gates, actuación pendiente y ejecución reconciliada; no negar una operación realmente confirmada. Los textos no cambian la estrategia, exposición o permisos.

## 5. Early Breakout: investigación con NO EDGE

La conclusión histórica actual es **NO EDGE**. No se usa para conceder entrada, cambiar dirección del Copilot o cerrar posiciones. Es una capa de investigación/observación separada. No se modificó su investigación ni se inició el servicio en esta fase.

## Consultas Telegram

Solo el propietario configurado puede preguntar; los destinatarios de alertas no adquieren ese permiso. El lector de comandos continúa opt-in y desactivado por defecto. Ningún comando abre/cierra operaciones, modifica leverage/margen, pone stops o arma módulos.

| Comando | Qué muestra |
| --- | --- |
| `/status` | Resumen actual, dirección, calidad, niveles locales/estructurales, posición y modo. |
| `/why` | Por qué esperar o favorecer LONG/SHORT y qué evidencia falta. |
| `/position` | Tu posición real verificada de Bitunix y su relación con la dirección. |
| `/risk` | Riesgo/liquidación, SL verificado o no, objetivo teórico y protección realmente armada/desarmada. |
| `/levels` | R1/S1 15m, R2/S2 1H y cierres a vigilar; nunca una orden de entrada. |
| `/stats` | Toda la historia forward registrada; también `/stats 30d`, `/stats 90d`, `/stats all`. |
| `/help` | Ayuda de las consultas disponibles. |

Las consultas de mercado muestran antigüedad; más de 30 segundos lleva aviso de datos desactualizados. `/stats` tiene su propia fecha de actualización y solo usa registros FORWARD_LIVE. No sustituye un snapshot fresco ni concede entrada. Si no hay datos/resultados maduros, lo dice claramente.

`A profitable open position does NOT prove the original entry was good.`

Una operación abierta con beneficio no valida retrospectivamente la señal, el timing o el riesgo asumido.

`No module guarantees profitability.`

Referencias: [Guardian](../TRADE_GUARDIAN.md), [auditoría forward](../COPILOT_FORWARD_AUDIT.md), [Early Breakout](../EARLY_BREAKOUT_SHADOW.md).
