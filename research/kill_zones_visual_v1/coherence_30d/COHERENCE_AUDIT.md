# Auditoría de coherencia — V1 congelada, 30 días

**Decisión: NO-GO para iniciar PAPER prospectivo como reproducción del vídeo.**
No se ha calculado PnL ni buscado parámetros. La implementación es causal y
rechaza planes inválidos, pero no demuestra fidelidad de la línea de ruptura y
no produce un solo plan admisible en este bloque. Esto NO demuestra NO EDGE
del método original: la formalización elegida sigue siendo una hipótesis.

## 1. Línea del compañero frente a línea utilizada

[Comparación esquemática](line_parity.svg) · [galería de los 30 días](index.html).

En las fotos 06:23 / 10:54 aparecen segmentos seleccionados casi verticales;
05:24 / 13:07 sustentan la medición y el traslado, con inferencias ya señaladas.
El fotograma disponible próximo a 09:55 es 10:11. Ninguno certifica por sí solo
una prolongación infinita del segmento de medida como umbral de confirmación.
No se atribuyen identidad ni fórmula a otras líneas visibles del gráfico.

V1 toma **A en el mínimo de la caja inferior a la hora real de esa vela**, B en
el máximo de la superior a su hora real, y confirma contra **la prolongación
infinita de A–B**, evaluada en la apertura de la vela cuyo cierre la confirma.
Los horarios de esos anclajes y la identidad «medición = línea de ruptura» son
suposiciones añadidas. La clonación conserva el vector, pero eso no valida la
identidad del disparador. La colocación C también es una decisión experimental.

Las coordenadas fotografiadas están en píxeles, sin precios/UTC calibrados ni
escala lineal/log verificada. El diagrama no alinea mercados/fechas diferentes
como si fuesen el mismo ejemplo. **PARIDAD DE LÍNEA / MÉTODO: NO PROBADA.**
Los JPG originales no se alteran ni se publican en este commit; sus hashes y
limitaciones están en el `source_audit.json` anterior.

## 2. Por qué los días 1 y 2 son ambiguos

| Fecha Londres | Asia [mínimo, máximo] | Londres [mínimo, máximo] | Relación |
|---|---:|---:|---|
| 2026-09-01 | 78,150.00 — 78,868.70 | 77,777.00 — 79,149.80 | Londres contiene Asia |
| 2026-09-02 | 76,682.30 — 77,767.80 | 76,706.00 — 77,731.70 | Asia contiene Londres |

V1 exige que una caja tenga AMBOS extremos estrictamente por encima de la otra.
Si una contiene a la otra, ninguna satisface ese orden. Es un rechazo por una
convención incompleta de V1, **no por datos ausentes**. Solapamiento parcial
con extremos ordenados sí puede ser válido: no se rechaza todo solapamiento.
No se eligieron centros, diagonales alternativas ni anclajes para salvar esos días.

## 3. Explicación exacta del 3 de septiembre

- A = 01:00 UTC / 76,927.30; B = 07:00 UTC / 78,144.70.
- Altura = 1,217.40; pendiente de la prolongación = 202.90 USDT/h.
- Copia UP: A′ = 09:00 UTC / 77,887.90; B′ = 15:00 UTC / **79,105.30**.
  La hora del extremo copiado NO predice llegada a target.
- Vela 14:00–15:00 UTC: O **78,802.20**, C **80,508.40**.
- Línea evaluada en x = 14:00: **79,565.00**. Se cumple
  `78,802.20 <= 79,565.00 < 80,508.40`: V1 confirma el cruce UP a las 15:00.
- Pero `target 79,105.30 < línea 79,565.00 < cierre 80,508.40`.
  La apertura siguiente es **80,508.40**, sin gap. SL = **76,927.30**.
- Resultado: `CONFIRMED_HYPOTHESIS` para el cruce y
  `REJECTED_STOP_TARGET_ORDER / TARGET_NOT_AHEAD_OF_ENTRY` para el plan.

Por tanto, «CONFIRMED» no significa «entrada LONG válida». La línea continúa
desplazándose con el tiempo mientras el target de la copia queda fijo. No hay
en V1 un requisito previo que mantenga target y disparador en orden utilizable.
El rechazo posterior funciona; no se convierte ese cruce en una operación.

## 4. Viabilidad mecánica de todo septiembre

Muestra fija: 30 fechas Londres 01–30/09/2026, America/New_York (UTC−4 aquí).
BTCUSDT **BINANCE_USDM_PERPETUAL**, archivo público Binance Vision USD-M.
8,640 velas 5m → 720 velas 1H completas. 0 huecos, duplicados o velas rellenadas.
SHA256 de CSV horario:
`1cdbf33d11d772ae3e469af66fc5c7f79a6bba809989800c7c38b07cce4d592f`.
Procedencia y checksum oficial guardado: [manifiesto](data_manifest.json).
Histórico reutilizado, **NO VIRGIN HOLDOUT**. No es observación forward.

| Recuento | n |
|---|---:|
| Días totales | 30 |
| Geometría válida | 23 |
| BOX_ORDER_AMBIGUOUS | 7 |
| Válidos sin confirmación | 18 |
| Confirmaciones UP / DOWN | 3 / 2 |
| Planes de referencia admisibles | **0** |
| Planes rechazados | **5** |
| Entradas pendientes | 0 |

Los 7 ambiguos: 01, 02, 12, 17, 19, 20 y 24. En 5 Asia contiene Londres;
en 2 Londres contiene Asia. No se pierden días de la muestra por filtrarlos.

| Fecha | Cierre confirmación UTC | Lado hipotético | Línea | Cierre señal | Entrada referencia | Target | Motivo |
|---|---|---|---:|---:|---:|---:|---|
| 03/09 | 15:00 | UP | 79,565.00 | 80,508.40 | 80,508.40 | 79,105.30 | target detrás de entrada |
| 04/09 | 13:00 | DOWN | 79,990.10 | 79,423.80 | 79,423.90 | 79,678.20 | target detrás de entrada |
| 10/09 | 13:00 | DOWN | 77,022.00 | 76,859.90 | 76,859.90 | 77,235.80 | target detrás de entrada |
| 11/09 | 13:00 | UP | 77,941.45 | 77,992.70 | 77,992.70 | 77,932.30 | target detrás de entrada |
| 18/09 | 14:00 | UP | 79,496.0875 | 80,046.50 | 80,046.50 | 79,566.30 | target detrás de entrada |

En 3 confirmaciones (03, 10, 11) el target ya queda detrás de la propia línea.
En 2 (04, 18) todavía queda por delante de la línea, pero el cuerpo confirmador
lo supera. En las 5 queda detrás del cierre **antes** de considerar la entrada:
no es un efecto de slippage o de un gap posterior. No hay rechazos por SL mal
ordenado ni por ausencia de entrada. No se probaron entradas más rápidas,
targets móviles, otros relojes o nuevos anclajes para producir señales.

## 5. Gráficos completos, integridad y decisión

La [galería](index.html) contiene TODOS los 30 días, no solo ejemplos favorables.
Ver [01 ambiguo](charts/2026-09-01.svg), [02 ambiguo](charts/2026-09-02.svg),
[03 rechazo UP](charts/2026-09-03.svg), [04 rechazo DOWN](charts/2026-09-04.svg),
[05 sin confirmación](charts/2026-09-05.svg) y [18 rechazo UP](charts/2026-09-18.svg).
Las velas posteriores se muestran como contexto visual; no se miden resultados
de operación ni se usan para redibujar anclajes o escoger variantes.
[CSV completo](daily_audit.csv) · [JSON completo](daily_audit.json) · [resumen](summary.json).

Cada confirmación y su plan se reproducen idénticamente al cortar los datos en
su instante de disponibilidad y al cierre del día. El código V1 permanece en
el SHA256 `20a646c5cd5300b6cb478d578a1904d446fd28a72ebb94ff527679345df926e2`;
las reglas no se han modificado ni refrozen. La ambigüedad no se oculta, y los
planes inválidos no se transforman en operaciones.
Pruebas: **46 específicas / 0 fallos** y suite global **1,079 / 0 fallos** con
Python 3.12.12. Se comprueban el blob V1 revisado, particiones del recuento,
prefijos causales, checksum, mes completo y regeneración idéntica de los 30
gráficos/JSON. No se debilitaron canarios ni se tocaron los hashes congelados.

**Detener este V1 antes de una evaluación prospectiva PAPER del método del vídeo.**
Conservarlo como herramienta de auditoría visual. La carencia de planes y la
falta de paridad del disparador impiden recomendarlo como implementación fiel.
Los 30 días no demuestran rentabilidad ni ausencia de edge del método original.
No procede corregir retrospectivamente el modelo para conseguir entradas.
Es un único mes de una venue y solo cinco cruces: no estima con robustez la
frecuencia futura ni demuestra que un plan admisible sea imposible en otros
periodos. El bloqueo de fidelidad es independiente de esos límites de muestra.

PR #40, Guardian V2, V8, ML RSI, readiness, weekly V1, Telegram y Railway intactos.
Sin órdenes, alertas operativas, merge ni deploy.

SHADOW ONLY. TRADE AUTHORITY: NONE.
