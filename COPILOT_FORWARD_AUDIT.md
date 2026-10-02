# Auditoría forward del Manual Copilot

Mide qué ocurre **después de las señales**, no la rentabilidad de Igor ni una estrategia con entradas, salidas, costes o slippage. No optimiza parámetros ni cambia reglas. No tiene cliente de cuenta, permisos de trading, comandos de actuación o conexión con V8/Early Breakout.

## Un episodio, un evento

Solo una transición observada WAIT → LONG_ALLOWED/SHORT_ALLOWED, o el cambio directo entre esas dos direcciones, crea un evento. Una dirección continua crea un solo evento, aunque cambie la calidad de entrada o haya nuevas velas. WAIT rearma; UNKNOWN o una observación incompleta no rearma. El primer estado observado al comenzar un registro nuevo se usa como contexto: si ya hay LONG/SHORT, no se inventa un inicio anterior. Debe observarse WAIT o una dirección opuesta antes de registrar el siguiente evento. Al reiniciar se conserva el episodio persistido.

Se congela GOOD/CAUTION/POOR al observar el evento. No se crea otra señal porque una misma dirección pase a GOOD posteriormente. La cohorte GOOD significa **episodios que comenzaron con GOOD**, no todas las oportunidades de reclaim posteriores. El permiso de buscar entrada sigue usando las reglas existentes, independientemente de este registro.

## Registro y almacenamiento

`COPILOT_AUDIT_STATE_DIR=/data/copilot_audit` es el directorio predeterminado:

- `state.json`: schema, último estado observado, timestamp, secuencia y cursor de evaluación.
- `signals.jsonl`: event_id inmutable, source=FORWARD_LIVE, lado, instante real de observación, último cierre 15m, referencia, mark público opcional, tendencias, ML RSI, taker-buy, estructura, volatilidad, calidad/razón, R1/S1/R2/S2, ATR1H público, explicación de campos verificados, versión y SHA si disponible. `state_after` permite reconciliar un append completado antes de guardar state.
- `outcomes.jsonl`: event_id, horizonte, estado, cobertura, retorno direccional, MFE/MAE y cinco first-passages cuando completos. Una corrección de disponibilidad puede añadir un resultado completo después de uno incompleto. Los resultados completos se congelan.
- `snapshots.jsonl`: una instantánea compacta por día UTC con conteos de horizontes y estadísticas. No manda informe diario a Telegram.
- `durability_canary.json`: UUID aleatorio, fecha de creación, contador de arranques y marcador aleatorio de proceso; añade fecha de reapertura en un arranque posterior. No contiene cuentas, chats ni secretos. `state.json` conserva el UUID esperado para detectar desaparición o sustitución del canary.

Hay lock de proceso, reemplazo atómico de state y fsync de journals/state; en POSIX también se sincroniza el directorio. El reinicio reproduce los journals antes de continuar, sin duplicar señales ni resultados completos. Un fragmento final JSONL sin newline se trunca; corrupción de registros completos desactiva la auditoría, sin detener la protección. No se registran credenciales, tokens, IDs de chats o PnL del usuario.

**Producción necesita un volumen persistente de Railway que cubra `/data`.** Este PR no cambia Railway ni comprueba el volumen desplegado. Un directorio escribible no prueba supervivencia a un reinicio. El canary se escribe con reemplazo atómico y fsync de archivo/directorio donde se admite. Su primer arranque es `INITIALIZED_NOT_RESTART_VERIFIED` (amarillo en `/stats`). En otro proceso, solo si se puede validar, reabrir y guardar el mismo UUID, aumenta `boot_count` y pasa a `REOPENED_FROM_PERSISTENT_STORAGE` (verde). Recrear el worker/store en el mismo proceso no aumenta el contador. Un canary corrupto, desaparecido después de inicializarse, sustituido o no escribible deja la persistencia **NO verificada** (rojo), sin afectar la protección ni sobrescribir evidencia corrupta. La primera adopción de esta versión sobre journals previos inicializa el canary en amarillo, sin atribuirles una prueba anterior.

El verde demuestra únicamente que estos archivos se recuperaron tras al menos un reinicio de proceso; no certifica el proveedor, la supervivencia a toda sustitución de contenedor o la recuperación ante un desastre. No se almacenan datos privados en esta comprobación. La auditoría empieza cuando se ejecute la nueva versión: no hay backfill histórico ni cifras live previas a su despliegue.

## Evaluación pública y causal

Un worker separado recibe copias con campos de mercado permitidos. El bucle de riesgo solo encola; sus fallos son no fatales, con diagnósticos estáticos. Se evalúan hasta 20 eventos por pasada con round-robin para que un hueco antiguo no bloquee otros. La cola es limitada; `COPILOT_AUDIT_QUEUE_FULL` señala pérdida de observaciones, nunca un reintento de actuación Bitunix. `/stats` advierte cobertura incompleta y el siguiente estado tras el hueco se observa como contexto, sin inferir una transición perdida. No se garantiza cobertura durante fallos de proceso/almacenamiento. Los datos salen únicamente de GET `https://data-api.binance.vision/api/v3/klines`, BTCUSDT spot, 5m, sin credenciales ni endpoints de cuenta.

La referencia es el último cierre 15m conocido cuando se observó la señal. El horizonte se cuenta desde el instante **de observación**, no desde un cierre anterior. Solo se usan velas 5m cuya apertura está en o después de ese instante y cuyo cierre ya ocurrió. Se excluye la vela parcial que contenía la observación, incluso si luego cierra: sus extremos anteriores al evento no eran posteriores a la señal. La cobertura empieza en el siguiente límite 5m y termina en el último cierre 5m dentro del horizonte. Por ello un evento fuera del límite exacto tiene una cobertura unos minutos menor; se registra explícitamente. No se supone una entrada ejecutada a esa referencia.

Horizontes: 1h, 4h, 12h, 24h y 48h. LONG: close/reference−1; SHORT: 1−close/reference. MFE/MAE usan high/low de esas velas cerradas, con cero como límite de excursión favorable/adversa. Debe existir toda la secuencia esperada; un hueco, duplicado o vela inválida censura el horizonte. No se interpola. Un horizonte no vencido queda pendiente y nunca cuenta como pérdida. Un fallo público deja la evaluación pendiente para reintentar por lectura.

First-passages: +0.5/−0.5%, +1/−0.5%, +1/−1%, +2/−1% y +3/−1%, simétricos para SHORT. Si una misma vela toca ambas barreras primero, el orden intrabar es desconocido: AMBIGUOUS, excluido del denominador y registrado. NEITHER (ninguna barrera dentro del horizonte) permanece en el denominador y no cuenta como éxito. WIN/LOSS indican el orden posterior de barreras, no beneficio/pérdida de una operación real.

## Consulta `/stats`

Solo el propietario existente puede usar `/stats`, `/stats 30d`, `/stats 90d` o `/stats all`. Otros argumentos devuelven ayuda. Son consultas a una copia de estadísticas ya calculadas; nunca llaman a Bitunix ni modifican state/control. Funcionan aunque no haya un snapshot de mercado actual. La autorización y el opt-in de comandos no cambian.

Se filtra siempre source=FORWARD_LIVE y se separan ALL, GOOD, CAUTION, POOR, LONG y SHORT. Cada grupo muestra n registrado, 24h maduros, pendientes e incompletos; porcentajes con su denominador evaluable. Solo los maduros entran en medianas. Menos de 10 maduros: muy pocos casos; menos de 20: muestra pequeña. Los toques ambiguos pueden reducir aún más el denominador. No se combinan grupos pequeños para aparentar evidencia. Las estadísticas son descriptivas, sin afirmar rentabilidad o edge demostrado. Un snapshot de estadísticas de más de 10 minutos se marca desactualizado.

Guardian continúa SHADOW/desarmado, con protección independiente y cierre automático exclusivamente por emergencia de liquidación. Esta auditoría no puede abrir, aumentar, cerrar, invertir, cambiar leverage/margen ni armar ningún módulo. No se modificaron variables o despliegues Railway, V8 o Early Breakout.
