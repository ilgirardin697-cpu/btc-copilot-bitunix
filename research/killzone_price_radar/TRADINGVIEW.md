# Probar el PRICE Radar en TradingView

1. Abre **BINANCE:BTCUSDT Spot**, velas estándar, **1H**.
2. Conserva Killzone H1 V3.7 Lite intacto. Crea otro script en Pine Editor y pega
   `I_GOD_Killzone_Probability_Radar.pine` de ESTA carpeta, no el de PR #42.
3. Guarda y añade al gráfico. Puedes retirar del gráfico el radar anterior para evitar
   dos paneles en la misma esquina; no hace falta editar ni borrar aquel código.
4. Por defecto solo se muestra entre05:00 y06:00 Nueva York. Desmarca «Ocultar fuera…»
   para inspeccionar el panel a otra hora. No confundir un timestamp antiguo con datos actuales.
5. El estado esperado es **NO VALIDADO / SIN PROBABILIDADES VALIDADAS**.
   No existe una opción para desbloquear porcentajes. No se ha verificado compilación
   en TradingView desde este entorno, que no tiene acceso a su editor/compilador.

## Cómo se actualiza

El horario interno siempre es America/New_York con DST, independientemente del reloj
visible del gráfico. Asia20/21/22/23, Londres02/03/04/05. En primavera puede faltar02:
ese ciclo no completa PINE_A y no se arregla inventando una cuarta vela.

A05:00 solo están confirmadas las H1 anteriores. A05:15 se incorporan15 minutos
cerrados de la última hora. A05:59 se conocen59 minutos. No se pronostica a06:00.
Los extremos finales de Londres nunca alimentan los features de un minuto anterior.
El ATR14 es la misma escala OHLC del PRICE original, leído de la última H1 cerrada.

`request.security_lower_tf` pide hasta100k intrabarras1m, con prefijos contiguos,
timestamps y closeTime. No se consulta4H ni se calculan AO/ADX/DMI/BBWP.
No se garantiza una actualización puntual cada minuto: Pine necesita ticks y feed.
Si faltan datos, debe conservar el timestamp real y marcar incompleto.
Feed revisado, profundidad y recarga pueden alterar reconstrucciones: no se promete
ausencia absoluta de repainting. No se usan reconstrucciones como observaciones forward.

## Pine Logs y dos pruebas distintas

Con «Pine Logs» habilitado se emite solo la última información realmente disponible
en tiempo real. No crea60 registros pasados al conectarse. El prefix es:

```text
IGOD_PRICE_RADAR_V1=...
```

Incluye seis features y `research_probabilities`: son estimaciones estadísticas del
modelo congelado **EXPERIMENTAL_NOT_VALIDATED**, no porcentajes aprobados, órdenes
o una puntuación arbitraria de indicadores. El panel no las muestra como probabilidades validadas.

**Prueba técnica:** guarda logs, errores de compilación y capturas antes/después de recargar.
Puedes enviarlos después; permiten comparar Pine y Python, pero su importación tardía
NO pasa a ser evidencia prospectiva. El comparador es:

```sh
python -m research.killzone_price_radar.parity logs_reales.txt --manifest ruta/download_manifest.json --out research/cache/price_parity_real.json
```

Sin manifest compara solo la aritmética condicional a los features emitidos, no su paridad
con el mercado. La comparación completa exige el mismo mercado/UTC/velas/ATR y referencias
públicas independientes. Ningún espejo Python se presenta como ejecución de Pine.

**Prueba prospectiva:** las cinco predicciones05:00/15/30/45/59 tienen que capturarse
antes06:00 y dentro120s de su timestamp. Un fichero exportado al final del día no cumple
esa recepción contemporánea, aunque sea útil técnicamente. Recargar puede repetir un ID:
el capturador no lo reescribe. Pine Logs/varip no son almacenamiento permanente.
No se ha activado ningún capturador o servicio continuo con este trabajo.

Se necesitan compilación real, pruebas de ticks/reload y tres ciclos con los cinco instantes
para la revisión de paridad. Eso por sí solo NO valida el modelo: también falta la cohorte
prospectiva, sus criterios estadísticos y revisión independiente.

Estado actual: **0 ciclos prospectivos y0 registros Pine PRICE reales comparados**.

Fuentes oficiales: [datos e intrabarras](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/),
[límites](https://www.tradingview.com/pine-script-docs/writing/limitations/),
[repainting](https://www.tradingview.com/pine-script-docs/concepts/repainting/).

SHADOW ONLY. TRADE AUTHORITY: NONE.
