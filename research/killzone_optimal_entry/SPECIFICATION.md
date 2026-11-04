# Killzone Optimal Entry Research V0 — predeclaración

PINE_A exclusivamente: America/New_York con DST, Asia 20–23, Londres 02–05.
Los cuatro niveles se congelan a las 06:00 después de cerrar Londres. El ciclo
con 02:00 inexistente en primavera queda incompleto. Se preserva la matemática
Pine auditada de PR #41, sin usar Probability Radar ni porcentajes como filtros.

El nombre «Optimal» expresa la pregunta, no una optimización ni una promesa.
NO VIRGIN HOLDOUT. Se reutiliza la historia ya examinada de noviembre de 2025
a octubre de 2026. Las tres particiones de cuatro meses son descriptivas; no
reentrenan ni seleccionan parámetros. El siguiente paso independiente sería forward.

## Comparaciones fijadas antes de calcular resultados nuevos

| Método | Señal causal | Entrada propuesta |
|---|---|---|
| BASELINE | Color del cuerpo total Londres al cerrar | Apertura 1m de 06:01 + coste adverso |
| AFTER_LONDON | Cierre Londres fuera de Asia y cuerpo alineado | Igual que BASELINE |
| BREAKOUT | Primer cuerpo H1 completo fuera de HIGH/LOW después de Londres | Apertura 1m un minuto después de confirmarse |
| RETEST | Primera ruptura anterior, después otra H1 toca su nivel y cierra fuera | Apertura 1m un minuto después del retest |
| LIMIT_ZONE | Dirección del cuerpo Londres; midpoint de su rango congelado | Límite en midpoint, publicado 06:01, penetración mínima de un tick |
| NO ENTRAR | Falta señal, datos, orden de precios, R/R o activación | Cero exposición y cero PnL |

Cada método consume su primera oportunidad, incluso si se rechaza. RETEST no
usa el mismo bar de ruptura ni cambia después al lado que ganó. Un límite no
se desplaza al mínimo/máximo realizado. Su zona es midpoint–cierre Londres,
con un solo precio de orden fijado en midpoint; no se busca el mejor retroceso.

TP = target teórico PINE_A. NO se aplica aquí el adelanto OWNER_B de 200 ni
las franjas visuales 500. El SL común es el extremo opuesto de Londres más
0,20 ATR14 congelado a 06:00. Son hipótesis nuestras de riesgo, no del Pine.
Se exige 1,5R neto, riesgo estimado máximo 0,25 %, nominal+fee dentro del equity.
No se eleva el riesgo mediante apalancamiento. Equity se reinvierte cronológicamente.

Las reglas completas de latencia, fills conservadores, SL/TP simultáneo, gaps,
caducidad, costes, incertidumbre y clasificación están en specification.json.
Ese JSON se commitea antes de ejecutar los nuevos outcomes. No se cambia tras verlos.

## Alcance ejecutable y bloqueos

Los datos son BINANCE SPOT BTCUSDT. LONG representa una simulación con costes
supuestos, no fills observados. SHORT es solo exposición direccional hipotética:
faltan préstamo/inventario o una serie y reglas de futuros con funding, mark y
costes verificables. Un SHORT positivo no obtiene la clasificación PROMISING.
No se usa Spot como si fuera Bitunix. No hay implementación de órdenes ni conexiones.

Los fills limitados no prueban prioridad en cola; se exige penetración en vez
de mero toque y no se permite mejora favorable de precio. Se reporta la incertidumbre.
La referencia de mercado un minuto después es simulable, no un fill garantizado.

Solo se añaden archivos research y un workflow offline. Sin cambios en Guardian,
V8, readiness, indicadores, protocolos, journals ni las PR #41/#42/#43.

SHADOW ONLY. TRADE AUTHORITY: NONE.
