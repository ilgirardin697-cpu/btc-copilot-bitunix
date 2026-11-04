# Pegar el radar en TradingView — sin contratar un plan

1. Abre **BINANCE:BTCUSDT Spot**, velas estándar y temporalidad **1H**.
   Otro exchange, el perpetuo, Heikin Ashi u otro timeframe quedan bloqueados.
2. Conserva intacto tu indicador Killzone H1 V3.7 Lite. Abre un script **nuevo**
   en Pine Editor y pega entero `I_GOD_Killzone_Probability_Radar.pine`.
3. Guarda como **I-GOD Killzone Probability Radar** y añade al gráfico.
   La compilación en tu cuenta es una verificación pendiente: este entorno no dispone
   de compilador ni sesión TradingView. No afirmamos que ya haya compilado allí.
4. El panel usa por defecto arriba derecha; puedes cambiar esquina. La zona horaria
   del gráfico no altera las sesiones internas: siempre `America/New_York` con DST.
5. Por defecto se oculta fuera de 05:00–06:00 Nueva York. Para comprobar el panel
   a otra hora, desmarca «Ocultar fuera…». Mostrará fuera de hora/último timestamp;
   no una predicción inventada actual. Si no tiene datos suficientes, indicará incompletos.

## Qué debe aparecer

```text
I-GOD KILLZONE RADAR                 H1 · SPOT
SUPERIOR PRIMERO                     —
INFERIOR PRIMERO                     —
NINGUNO                             —
Estado                              NO VALIDADO
Datos                               COMPLETOS A TIMESTAMP / INCOMPLETOS
Ultima informacion UTC              timestamp real disponible
Londres restante                    minutos a ese timestamp
Modelo                              KZR_V1_b3e7f819bb07
SIN PROBABILIDADES VALIDADAS
SHADOW ONLY · NO ORDERS
TRADE AUTHORITY: NONE
```

No hay input para desbloquear probabilidades. La puerta de publicación es una
constante falsa: se necesita un nuevo análisis revisado, no mover un interruptor.
Las funciones exportadas contienen los coeficientes entrenados para comparación;
su presencia no implica aprobación del modelo ni muestra porcentajes.

## Hora y causalidad

Se solicitan arrays 1m mediante `request.security_lower_tf`, con un máximo explícito
de 100.000 intrabarras. En H1 son aproximadamente 1.666 horas/69 días si hay 60
minutos por hora. No intenta recuperar cinco años desde Pine. La disponibilidad real
depende del plan, historial cargado y feed; no hace falta exportar CSV ni pagar otro plan.

- 05:00 NY: usa Asia y las H1 02, 03 y 04 ya cerradas.
- 05:17 NY: solo incorpora los 17 minutos de Londres cerrados hasta ese instante.
- 05:59 NY: incorpora 59 minutos. El minuto 05:59–06:00 todavía está abierto.
- 06:00 NY: termina la estimación; los targets definitivos sirven para outcome,
  nunca como si hubieran sido conocidos durante la hora anterior.

No basta `barstate.isconfirmed` dentro de una petición: se filtran `time`, `time_close`,
orden y contigüidad de los arrays. Los indicadores H1 se leen con `[1]`, y la4H
con `close[1]-close[2]` y lookahead_on compensado por el offset. No se usa la4H abierta.
El estado de sesiones se confirma DESPUÉS del bloque predictivo; así la H1 histórica
05 no filtra su high/low definitivo a las reconstrucciones del minuto05:15.

## Límites reales y recarga

Pine ejecuta por actualizaciones del mercado, no por un temporizador de pared.
Aunque BTC tenga muchos ticks, no se garantiza una ejecución exacta cada minuto:
si no llega update o el feed demora, se conserva el timestamp de información disponible.
Un gap no se completa con la vela H1 definitiva. No se promete ausencia absoluta
de repainting: el proveedor puede revisar datos y una recarga cambia profundidad/feed.

`varip` solo evita duplicados durante la ejecución actual y guarda el panel intrabar.
Tras recargar no conserva un fichero ni una prueba de qué se emitió antes. Pine Logs
también tiene retención limitada: el propietario debe guardar los logs fuera de Pine.
No se ha desplegado ningún capturador externo. El importador offline añade y verifica
una cadena hash, sin convertir un replay en observaciones reales.

## Verificación real todavía pendiente

Durante una futura 05:00–06:00 NY, sin órdenes ni alertas:

1. Comprueba compilación, símbolo H1, panel, timestamps y datos completos.
2. Abre Pine Logs y guarda las líneas `IGOD_KILLZONE_RADAR_V1=...`.
3. Comprueba que solo registran la última información cerrada, no minutos futuros
   ni 60 registros retroactivos al conectar. Puede saltarse minutos si faltan ticks.
4. Captura las líneas antes de recargar. Tras recargar compara ambos exports,
   conservándolos por separado: cualquier cambio debe investigarse, no sobrescribirse.
5. Ejecuta el comparador con los mismos datos públicos/ticker. Si el ciclo es posterior
   a la ventana histórica, indicará `NO_OFFLINE_REFERENCE_CYCLE` hasta obtener referencia.
6. Guarda errores/avisos del compilador o diferencias; no los marques como aprobados.

Actualmente: **0 registros TradingView de este radar comparados**. El resultado local
de aritmética a 2,22e-16 no sustituye esta prueba ni la de actualizaciones en directo.

Fuentes oficiales: [arrays y feeds](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/),
[límites](https://www.tradingview.com/pine-script-docs/writing/limitations/),
[repainting](https://www.tradingview.com/pine-script-docs/concepts/repainting/).

SHADOW ONLY. TRADE AUTHORITY: NONE.
