# Hipótesis principal: impulsos confirmados, entrada 1H y continuidad 4H

Actualización documental de PR #58. No cambia el motor anterior ni ejecuta otro backtest. La hipótesis prioritaria es la aportación del miembro conservada en `member.json`, no una estrategia oficialmente verificada de Bitman. Los resultados negativos y archivos anteriores quedan intactos.

## Qué podemos definir con las fuentes disponibles

| Elemento | Definición comprobable | Qué falta para llamarlo confirmación del método |
|---|---|---|
| AO | `SMA5(HL2) − SMA34(HL2)`. Pendiente `diff = AO[t] − AO[t−1]`. El Pine público suministrado dibuja verde si diff >0 y rojo si diff ≤0 | No sabemos si el miembro exige un cambio de color, persistencia, posición respecto a cero, cruce de cero u otra secuencia |
| Alerta pública AO | `changeToGreen = crossover(diff,0)`; rojo `crossunder(diff,0)`. Es un cruce de la pendiente, no de AO con cero | Esa alerta de color no certifica una entrada Bitman. En particular, un previo diff=0 se trata de forma distinta que el giro estricto entre pendientes no nulas de algunas investigaciones antiguas |
| ADX | Fuente pública 14/14, DM+/DM−, TR y suavizados Wilder. El Pine dibuja `sig` como línea roja; no determina dirección | No contiene una definición de «90°» ni una regla de impulso confirmado. Ningún umbral de pendiente se deduce del zoom |
| ADX reproducible | ΔADX en puntos por hora y Δ²ADX en puntos por hora²; nivel, +DI y −DI por separado | Pendiente o persistencia mínima pendiente de evidencia original. No sustituirla por ADX>40, Q75 o 2+2 de protocolos anteriores |
| Konkorde | `tendencia`, `tiburones`, `pececillos=tendencia+osc_pos`; roja `EMA15(tendencia)` según los inputs activos. Áreas y líneas se superponen | Qué serie confirma, frente a qué referencia, cuántos cierres y qué invalida la condición. Slope, cruce con roja y cruce de cero son hechos distintos |
| BBWP | Perfil offline activo CLOSE/SMA13/252, señal SMA5. Registrar nivel y pendiente; condición textual del miembro >50 | Paridad completa con el indicador retocado de Bitman y si se usa valor principal, señal o alguna condición adicional. La configuración verbal del directo24 respalda fuente/basis/13/252, no demuestra toda la semántica |
| Entrada 1H | Cualquier interpretación debe esperar el cierre y registrar disponibilidad; primera ejecución posible después de confirmar | Definición completa del conjunto de confirmaciones. Ni el color AO ni BBWP>50 aisladamente son entrada |
| Continuidad 4H | Solo el último 4H completamente cerrado puede formar contexto disponible | No está definido si exige estructura, AO, DMI, Konkorde o una combinación. No elegir automáticamente un filtro ganador |
| Refinamiento 15m/5m | Se estudia como temporización posterior, sin convertir mínimos futuros en entradas | 15m está disponible en el replay; 5m no se ha capturado aquí. Faltan gatillo, expiración y criterio de ejecución; bajar de timeframe no garantiza mejorar el resultado |

Referencias verificadas en el repositorio: `../../sources/ao.pine` líneas3–9, `adx.pine` líneas12–27 y `koncorde.pine` líneas295–313, junto con `../../profile.json` y `../../source_manifest.json`. Estos son los scripts públicos recuperados del JSON de TradingOne, no el código privado del método.

El contraste visual de pececillos del15Nov aporta un valor redondeado coincidente, no paridad certificada de la serie completa. El color amarillento no identifica por sí solo un área cuando hay superposición.

## Impulso, retroceso y contexto mayor no son equivalentes

Las notas anteriores sobre el oscilador **semanal** distinguen impulso a favor del signo y corrección de color contrario con contracción. Esa enseñanza no debe trasladarse automáticamente a1H como si se hubiese verificado la misma regla allí.

El miembro propone operar únicamente impulsos confirmados en1H y usar4H para continuidad. Falta saber si «retroceso» significa una fase correctiva local antes de reanudación, o si también excluye cualquier rebote contra la tendencia4H. Son criterios diferentes. El episodio SniperRBW documenta una condición alcista1H con4H todavía bajista; procede de otro miembro y no resuelve esa ambigüedad.

El directo25, a52:20–53:45 según la síntesis aportada, describe un diario con AO recuperando y ADX todavía creciente: es recuperación pendiente, no una confluencia alcista completa ya confirmada. Las observaciones de magnitud semanal a30:10–32:58 no atribuyen dirección a la volatilidad. La frase del miembro no permite borrar estas distinciones ni afirmar que Bitman confirmó la combinación exacta.

## Qué no volveremos a optimizar

PR #46/#49 emplearon cruces de área/roja, condiciones de signo, ADX>40 y BBWP7/100>85. PR #50/#51 estudiaron agotamiento, inicio y rebote fallido con2+2/1+1, intensidad y controles por régimen. PR #55 probó gestión completa y terminó negativa. PR #58 es un prototipo secuencial con ADX/BBWP descriptivos, no un ensayo de la combinación textual de este miembro.

Estas pruebas relacionadas conservan su conclusión y no se repiten con umbrales alterados para capturar noviembre. Tampoco se presentan como refutación o validación exacta de la hipótesis aún incompleta. No añadimos a este motor un filtro BBWP>50, una nueva confirmación, un stop o un refinamiento5m para intentar mejorar su histórico.

## Decisión de investigación

**Definición original de confirmación: INCOMPLETA. Evaluación económica de esta combinación: NO EJECUTADA.** No existe todavía una señal numérica completa a la que asignar rentabilidad o una muestra fuera de observación previa. El código `member.py` sigue devolviendo confirmaciones no especificadas, sin emitir operaciones.

Para completar la regla hace falta evidencia original que identifique la confirmación AO, la serie/condición Konkorde, la fuerza ADX y la continuidad4H; o aprobar expresamente convenciones nuevas etiquetadas como hipótesis nuestras, nunca atribuidas al autor. Después deben fijarse ejecución, invalidación, costes, funding aplicable y evaluación independiente antes de mirar sus resultados. No se inicia captura continua, no se mueve ningún periodo ni se relajan criterios.

Este documento es una nueva adición textual; no sustituye el plan, manifiesto, dataset, ZIP ni resultados previamente sellados del addendum. No se han usado nuevos créditos de vidIQ.

SHADOW ONLY. TRADE AUTHORITY: NONE. Sin órdenes, merge, deploy ni modificaciones productivas.
