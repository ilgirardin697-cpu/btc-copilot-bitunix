# PRICE congelado — seguimiento independiente

**B. PROMETEDOR PERO PENDIENTE DE DATOS PROSPECTIVOS.**

Selección de PRICE solicitada DESPUÉS de examinar PR #42: POST-HOC. No es nueva validación.
No se cambian coeficientes, escalado, clipping o variables. No se reentrena ni recalibra.
PR #41, PR #42, OWNER_B/C y las fórmulas originales permanecen intactos.

## Qué significa precio solo

Seis variables: minuto/60, posición en rango combinado parcial, desplazamiento Londres/Asia,
ancho parcial Londres/Asia, cambio Asia/Asia y ancho combinado/ATR14 H1 confirmado.
**ATR14 ya estaba en PRICE** como escala OHLC: no es un filtro direccional nuevo.
Eliminarlo haría otro modelo; no se hace. No hay AO, ADX, DMI, BBWP o tendencia4H.
No se añaden nuevas variables. Distancias y cambios de rango están representados solo
por las seis transformaciones originales; no se amplía la lista después del test.

## Congelamiento

Protocolo y assets congelados en3c3f90a antes de ajustar/evaluar la nueva referencia estructural.
SHA modelo: `db59d952e6c79da87adb7a31cba41a6ee3a5879a8e0c57638336e58f7be6a6d9`.
SHA protocolo: `892ec9aa89c4b1984eab46d6c20d97704379e022671ddc34c68227131e164289`.
Referencia estructural: tres terciles FIJOS de posición en el rango parcial; frecuencias de
clase aprendidas solo de2022–2023, ponderación1/60 por minuto y prior20 ciclos por tercil.
No busca bins, suavizado, combinación o umbral ganador. PRIOR es el publicado, sin refit.

## Comparación histórica ya vista — NO HOLDOUT VIRGEN

| Modelo | n ciclos test visto | Brier | Log-loss | MacroECE |
|---|---:|---:|---:|---:|
|PRIOR|667|0.640150|1.060809|0.012074|
|STRUCTURE|667|0.628010|1.037920|0.013685|
|PRICE|667|0.598303|0.990154|0.028397|

Mejora PRICE frente a PRIOR: 6.537% RELATIVA del Brier; no puntos de rentabilidad.
IC95 de ganancia absoluta: [0.02571744186389837, 0.05858326815962178].
Frente a STRUCTURE: ganancia 0.029707, IC95 [0.01485131624965976, 0.04588848887454387].

### SUPERIOR / INFERIOR / NINGUNO por separado

| Clase | n ciclos de esa clase | Brier binario | Prob media | Frecuencia | ECE |
|---|---:|---:|---:|---:|---:|
|SUPERIOR_FIRST|180|0.185663|0.281281|0.269865|0.021865|
|INFERIOR_FIRST|175|0.183267|0.252974|0.262369|0.027356|
|NEITHER|312|0.229373|0.465745|0.467766|0.035971|

### Cinco instantes predeclarados — precio congelado

| Hora NY | n ciclos | Brier | Log-loss | ECE | Ganancia vs estructura |
|---|---:|---:|---:|---:|---:|
|05:00|667|0.601599|0.996104|0.030270|0.026191|
|05:15|667|0.598478|0.990750|0.041383|0.031401|
|05:30|667|0.599300|0.990128|0.030643|0.028216|
|05:45|667|0.599705|0.992671|0.032548|0.030819|
|05:59|667|0.595725|0.987657|0.030941|0.032926|

Los60 minutos no son60 muestras independientes: IC por bloques circulares de7 ciclos,2000 réplicas.
monthly.csv contiene todos los meses/modelos; historical_comparison.json conserva calibración
por clase, bins, IC y comparaciones. No se escoge el minuto, mes o clase mejor.
Meses test con mejora Brier vs PRIOR:18/22; vs STRUCTURE:17/22; ambos:17/22.
Cotas superiores IC95 de ECE por clase, bootstrap por ciclos: [0.05063209894133784, 0.05563243381161887, 0.07067501841503514].

## Protocolo prospectivo aún sin activar

Cohorte fija:2026-11-05 a2027-05-04,181 ciclos de calendario. Nada anterior entra como forward.
Predicciones05:00/15/30/45/59 capturadas antes06:00; se conservan los demás minutos disponibles.
La recepción debe ser real, antes de empezar el outcome y a<=120s del as-of. Logs importados
tarde sirven como diagnóstico, NUNCA como evidencia prospectiva. No existe override de reloj CLI.
El capturador es local/offline, de un escritor, no se ha conectado ni activado un servicio.
Tras20:00, un registro separado añade el label calculado con datos públicos verificables.
La igualdad de features con mercado se verifica entonces; no se reescriben las predicciones.
El texto Pine Logs no autentica criptográficamente su origen; se requiere revisión externa.

Mínimos:150 ciclos completos,30/clase y>=95% cobertura del calendario. Son mínimos operativos,
NO una prueba automática. El análisis solo puede aprobarse tras terminar la cohorte fija.
Brier: IC97.5% por bloques debe mejorar AMBOS baselines (Bonferroni dos comparaciones).
Log-loss no peor; por clase Brier no peor y límite IC>=−.01; macroECE<=.05, cadaECE<=.08
y límite superior IC95<=.10. Mejora en los cinco instantes y>=2/3 de meses elegibles.
Se exigen>=5 meses con>=10 ciclos. No se recalibra para superar un gate fallido.
Paridad real: compilación/realtime/recarga,>=3 ciclos distintos con cinco instantes por ciclo,
features rtol/atol1e-8 y probabilidades atol1e-10. Comparaciones locales no cuentan como Pine real.
Incluso un resultado suficiente requiere revisión y release nuevo; no hay interruptor de porcentajes.

## Evidencia que existe ahora

**Ciclos prospectivos:0. Logs reales PRICE comparados:0. Compilación TradingView: PENDIENTE.**
No se ha descargado noviembre como si fuera evidencia prospectiva. No hay tareas automáticas
de captura, órdenes, Telegram o Railway. Se entrega Pine completo para la prueba técnica manual.
Las probabilidades internas experimentales de los logs están etiquetadas NO VALIDADAS;
el panel no muestra porcentajes. El journal distingue captura tardía/replay de evidencia elegible.

La mejora predictiva histórica no demuestra rentabilidad, ejecución ni oportunidad operativa.
No hay resultados de trading, TP/SL nuevos o apalancamiento. No se modifica TP±200.

SHADOW ONLY. TRADE AUTHORITY: NONE.
