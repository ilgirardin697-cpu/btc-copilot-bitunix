# I-GOD — Plan Diario V1 de dos entradas y dos TP

**Estado: prototipo ejecutable LOCAL, solo lectura / investigación, NO desplegado ni integrado en Railway.**

**SHADOW ONLY. TRADE AUTHORITY: NONE.** Sin lectura de cuenta, sin API privada, sin órdenes y sin envío de Telegram. Los cálculos ilustran una hipótesis de confluencia, no una estrategia rentable o una recomendación de trading.

## Qué hace

- Lee BTCUSDT del endpoint público oficial de **Binance USD-M perpetual** para cinco marcos: 1W, 1D, 4H, 1H y 15m; no mezcla Spot con Futuros ni rellena errores por otra fuente.
- Procesa **solo velas cerradas**, valida tiempos, continuidad, OHLCV y frescura. La vela diaria o semanal que todavía esté abierta NO se convierte en señal definitiva.
- Calcula AO (SMA5 - SMA34 sobre HL2), ADX/DMI (Wilder 14), un **BBWP aproximado de investigación** con source CLOSE, BB length=13, σ=2, lookback=252 y señal SMA5. ADX mide fuerza, +DI/−DI ayuda a interpretar dirección, BBWP mide rango relativo de bandas; ninguno predice el sentido de manera independiente.
- Detecta deterioro/recuperación en 1D, advierte si 1W acompaña o diverge, y exige SMA200 + estructura de pivotes confirmados de 1H/4H para etiquetar un escenario.
- Propone **como máximo** dos entradas condicionales: para LONG, primer soporte y otro inferior; para SHORT, primera resistencia y otra superior. Los TP se obtienen de resistencias/soportes confirmados, no son porcentajes inventados.
- Establece una invalidación común más allá de la entrada B, descarta escenarios con niveles insuficientes, lejanos o RR bruto <1, y calcula el tamaño **simulado** incluyendo un supuesto de costes de 18 bps ida+vuelta.
- Limita por defecto el riesgo estimado de ambas entradas al 0,5 % del capital de ejemplo (140 USDT) y el nocional conjunto a 1×. No supone que ese riesgo se cumpla bajo gaps, liquidaciones, problemas de ejecución, financiación ni volatilidad extrema.
- Genera texto tipo Telegram y JSON para una futura integración. **No envía mensajes**.

## Ejecutar en Windows (una vez, sin tocar Bitunix)

1. Descomprime este ZIP.
2. Abre una terminal dentro de la carpeta `IGOD_Daily_Plan_V1`.
3. Instala una dependencia local: `py -m pip install requests`.
4. Ejecuta: `py -m igod_daily_plan --live-public --paper-equity 140 --out plan.json`.
5. Revisa el texto en pantalla y el JSON generado. **No introduzcas tus claves de Bitunix.**

En Linux/macOS sustituye `py` por `python3`.

**Importante:** el acceso directo al endpoint público Binance USD-M puede dar HTTP 451 o fallar por restricciones geográficas/redes. Si eso ocurre el módulo **se detiene y no inventa señales**, sin cambiar de región, usar proxies ni sustituir la venue silenciosamente. En el entorno donde se preparó el paquete no fue posible obtener velas reales vía red: por tanto, no se ofrece ningún plan de mercado actualizado ni una validación forward en esta entrega.

## Pruebas

```bash
python -m unittest -v test_igod_daily_plan.py
```

21 pruebas unitarias **con datos sintéticos**, sin operaciones reales. Comprueban el AO, ADX, BBWP, pivotes causalmente confirmados, rechazo de huecos, exclusión de velas abiertas, sizing de riesgo conjunto y escenarios simulados LONG/SHORT. No prueban beneficio ni paridad numérica PineTS con TradingOne.

## Cómo se conecta con el proyecto actual

- Referencia GitHub: `ilgirardin697-cpu/btc-copilot-bitunix`, **PR #35 `igod-shadow-paper-execution-v0`**.
- El piloto PAPER de PR #35 está separado de producción, actualmente usa reglas del Manual Copilot con velas 1H/4H/15m; **no se debe reemplazar automáticamente** su motor ni su journal con esta lógica nueva.
- `igod_paper.engine.source_identity()` incluye hashes de ficheros y configuración. Editar el proceso PAPER existente puede invalidar la identidad del journal; la solución prudente es un **nuevo worker experimental de plan diario**, con su propio almacenamiento, fuente/preset y protocolo, sin alterar el journal actual.
- Para la siguiente fase falta **validar la exactitud AO/ADX/BBWP frente a TradingOne**, conectar las velas públicas autorizadas con el plan diario, publicar el informe a una hora fija, añadir alertas ante cambios confirmados y **comprobar los resultados en PAPER**.
- Telegram (si se desea más adelante) solo se conectaría con un emisor saliente autorizado, sin APIs de ejecución ni modificación de las cuentas.

## Limitaciones de la V1

1. No incorpora el Konkorde/ML RSI propietario para evitar afirmar equivalencia sin prueba matemática; se puede añadir como *evidencia opcional*, no como confirmación inventada.
2. No ejecuta la confirmación posterior de 15m; solo describe el disparador que tendrá que implementarse como un estado causal en la siguiente fase.
3. No evalúa el historial completo de resultados ni calcula PnL. Los umbrales son **hipótesis sin edge validado**.
4. Un escenario marcado `SCENARIO_LONG`/`SCENARIO_SHORT` **no es permiso para operar**. Exige otra confirmación 15m, gestión de riesgo y revisión del plan en el momento real de activación.
5. No se ha desplegado en Railway, no se ha cambiado la PR #35 ni el bot de Telegram, ni se ha activado trading real.

## Formato esperado del mensaje diario

```text
I-GOD · PLAN DIARIO BTCUSDT
SESGO: WAIT / WATCH_SHORT / WATCH_LONG / SCENARIO_SHORT / SCENARIO_LONG
1D: AO, ADX, +DI/-DI, BBWP (todos velas cerradas)
1W: contexto y alerta de posible debilitamiento
4H + 1H: dirección SMA200 y estructura de pivotes confirmados
A: zona 1, TP1, condicionada a 15m
B: zona 2, TP2, condicionada a 15m y estructura válida
INVALIDACIÓN: stop teórico compartido, NO colocado
RIESGO: máximo conjunto ilustrativo, datos de simulación
O, cuando faltan pruebas: NO OPERAR + motivo
```
