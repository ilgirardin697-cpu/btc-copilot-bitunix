# I-GOD V8 REAL

Executor independiente: `python v8_executor.py`. No cambia `railway.json` y este
PR no despliega ni activa ejecución. No garantiza rentabilidad: hay riesgo de
pérdida, slippage, liquidación y fallos de conectividad. La estrategia no tiene
TP1/TP2, runner, trailing ni stop de estrategia; salida normal por señal FLAT.

## Decisión y exposición

`trend_v8.py` es la única fuente de decisiones: BTCUSDT, cierre 4H completamente
cerrado (margen temporal 1,5 segundos), SMA200. Close > SMA200 = LONG; igualdad
o inferior = FLAT. Nunca SHORT. SMA125/150/175/225/250/300 solo telemetría.
No importa el planner ni la estrategia V7. Una decisión por timestamp de vela.
Se registra primero SHADOW y después REAL comprueba el mismo objeto canónico,
fingerprint SHA256, dirección y registro durable de SHADOW.

`V8_LIVE_EXPOSURE=0.25` es **exposición nominal**, no margen multiplicado por
leverage. El target inicial es equity real estimada * exposición, descontando
`V8_LIVE_RESERVE=0.002` (20 bps para fees/slippage) y redondeando qty hacia abajo.
Ejemplo: equity 200 USDT, target 50; antes del redondeo se envían 49,90 USDT.
La cuota no aumenta durante HOLD, no promedia pérdidas ni se aumenta después
de una pérdida. Configuración admitida: 0 < exposición <= 1.

Leverage obligatorio y máximo **1x**. Solo existe una mutación de leverage con
valor literal 1. Si hace falta, se configura 1 y se vuelve a leer desde Bitunix;
si no se puede verificar, no se envía entrada. Un cierre también requiere 1x.
Los topes de nominal son comprobaciones previas al envío con precio actual;
una orden MARKET puede sufrir slippage y la exposición cambia con el precio.
La reserva no garantiza un máximo de ejecución durante saltos del mercado.

Equity estimada = available + frozen + margin + crossUnrealizedPNL +
isolationUnrealizedPNL, igual que la estimación de infraestructura existente.
No se asumen valores para campos ausentes. Cuenta positiva, ONE_WAY, API
disponible, reglas BTCUSDT válidas, qty/min/max y efectivo suficiente son
obligatorios antes de operar. No se modifica el modo de cuenta automáticamente.

## Armar y desarmar

Por defecto `V8_LIVE_EXECUTION=false`: cero mutaciones, incluso de leverage.
`LIVE_EXECUTION` y `LIVE_AUTO_START` de V7 no habilitan V8.
Con `V8_LIVE_EXECUTION=true`, iniciar el worker registra `V8 REAL ARMED` y el
instante ARM en estado/journal. **No está armado por este PR.**

Cada reinicio crea una barrera ARM nueva. Solo una vela cuyo cierre sea posterior
al ARM puede producir una orden; también debe tener menos de cinco minutos.
El bootstrap histórico LONG nunca abre REAL. Se necesita una transición nueva
FLAT -> LONG; HOLD LONG después del bootstrap tampoco permite entrar tarde.
La señal FLAT posterior al ARM cierra únicamente una posición verificada V8.
Históricos perdidos se reconstruyen en SHADOW; REAL consume sus registros,
sin recalcular decisiones ni operar retrospectivamente. Un cierre perdido
antes de ARM tampoco ejecuta al reiniciar: requiere revisión y una nueva FLAT.

Para desarmar el worker activo, sin polling Telegram:

```sh
python v8_executor.py --disarm
python v8_executor.py --status
```

El primer comando crea `V8_DISARM`, comprobado antes de cada mutación. No cancela
ni cierra posiciones por sí mismo. La salida normal también se deshabilita.
Para rearmar: detener worker, revisar posición/state/journal, retirar únicamente
el marcador `V8_DISARM`, configurar true y reiniciar. Nunca borrar state o
journal para desbloquear una orden incierta. Para solo observar, reiniciar con
false. No se añade `/v8status`: no hay segundo consumidor de `getUpdates`.
Notificaciones: ARMED, DISARMED, SIGNAL LONG/FLAT, LONG OPENED, POSITION CLOSED
y BLOCKED con motivo fijo, sin secretos ni URLs de credenciales.

## Ownership, persistencia y reconciliación

State: `V8_DATA_DIR/v8/igod_v8_live_state.json`; journal:
`V8_DATA_DIR/v8/igod_v8_live_journal.jsonl`. Si no se define V8_DATA_DIR,
usa RAILWAY_VOLUME_MOUNT_PATH o el directorio de trabajo; con volumen /data
resultan `/data/v8/...`. SHADOW conserva archivos distintos y su coste de
10 bps por turnover. Solo una instancia y ningún segundo worker SHADOW que
escriba al mismo directorio.

Los clientId son `igodv8-<candle_time>-o/c`. La intención se sincroniza al disco
ANTES del POST; luego se comprueban orden FILLED, clientId exacto, side,
reduceOnly, qty, leverage 1, modo ONE_WAY, fills y posición mediante Bitunix.
Posición inicial ajena = bloqueo, aunque parezca una antigua posición V8.
Nunca adopta manuales/V7. Para cerrar deben coincidir positionId, qty y todos
los fills con la orden de apertura persistida. Cambios de qty o fills ajenos
bloquean el cierre. SELL se permite únicamente MARKET reduceOnly=true;
no hay SELL de apertura, reverse, flash-close ni cierre global.

No crea órdenes protectoras. Cualquier pendiente normal o protectora es
ambigua y bloquea; no cancela órdenes que este executor no ha creado y probado.
No existen endpoints de TP ni cancel-all. Históricos/fills truncados o ausentes,
fills parciales y estados de órdenes no concluyentes también bloquean.

Timeout, error o crash después de intención: exclusivamente reconciliación de
lectura, incluso desarmado. **Nunca reenvía la orden**, aunque no se encuentre.
Una intención sin resultado concluyente detiene nuevas órdenes hasta revisión
operativa del exchange. Las escrituras del estado son atómicas; el journal
durable permite recuperar una caída entre journal y estado. Un registro
truncado o incoherente falla cerrado. Se sacrifica disponibilidad para impedir
duplicados; no hay reintento automático de órdenes rechazadas/parciales.

REAL registra precio y qty de fills, nocional, fees reales, funding de posición,
slippage relativo al cierre 4H (fracción y bps), realized gross y realized net
(gross - fees de entrada/salida + funding). Guarda fingerprint y métricas
SHADOW esperadas al lado del resultado real. SHADOW simula 1x de equity virtual;
REAL comienza con 0,25x de equity real, por lo que sus cantidades/PnL absolutos
no son directamente equivalentes sin normalizar exposición y capital.

## Exclusión V7 y rollback

`execution_guard.py` mantiene un bloqueo del sistema operativo durante la vida
del worker V8. Una guardia mínima en el transporte privado V7 impide TODAS sus
mutaciones (incluidos leverage y entradas), manteniendo sus lecturas. No cambia
su estrategia. V7 bloquea también con V8_LIVE_EXECUTION=true en su entorno.
El bloqueo se libera al terminar o caer el proceso.

Todos los procesos deben usar **este código actualizado** y el mismo directorio
de bloqueo: `V8_EXECUTION_LOCK_DIR`, o RAILWAY_VOLUME_MOUNT_PATH, o cwd. El lock
local no controla instancias en otras máquinas/volúmenes ni software externo:
no ejecutar V7 antiguo u otros bots en esa cuenta. El preflight detecta sus
posiciones/órdenes, pero no puede impedir acciones remotas entre consultas.

Rollback: desarmar y detener V8, verificar y resolver por separado cualquier
posición real e intención pendiente; conservar sus artefactos. No arrancar V7
si quedan posición/órdenes V8. Solo después de cuenta limpia y revisión, volver
al arranque V7 existente con V8_LIVE_EXECUTION=false. No hay cambios de Railway
ni rollback automático que cierre dinero real.

## Variables y validación

- V8_LIVE_EXECUTION=false: único interruptor de mutaciones.
- V8_LIVE_EXPOSURE=0.25: target nominal inicial.
- V8_LIVE_RESERVE=0.002: reserva nominal (mínimo 0.001).
- BITUNIX_API_KEY / BITUNIX_SECRET_KEY: entorno, nunca código/logs.
- V8_DATA_DIR / RAILWAY_VOLUME_MOUNT_PATH: persistencia.
- V8_EXECUTION_LOCK_DIR: bloqueo compartido V7/V8.
- V8_SHADOW_INITIAL_EQUITY=1000 y V8_SHADOW_TURNOVER_COST=0.001: SHADOW.
- TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ALERT_CHAT_ID: avisos opcionales.

```sh
python -m py_compile trend_v8.py v8_executor.py v8_bitunix.py execution_guard.py test_trend_v8.py test_v8_executor.py live_auto.py
python -m unittest discover -v
git diff --check
```

CI ejecuta sintaxis y todos los tests SHADOW/REAL, sin credenciales ni red Bitunix.
Los tests usan un exchange simulado; no certifican fills reales ni disponibilidad
de los endpoints. Contrato contrastado con documentación oficial:
[órdenes y reduceOnly](https://www.bitunix.com/api-docs/futures/trade/place_order.html),
[leverage](https://www.bitunix.com/api-docs/futures/account/change_leverage.html),
[verificación leverage](https://www.bitunix.com/api-docs/futures/account/get_leverage_and_margin_mode.html),
[fills](https://www.bitunix.com/api-docs/futures/trade/get_history_trades.html).
