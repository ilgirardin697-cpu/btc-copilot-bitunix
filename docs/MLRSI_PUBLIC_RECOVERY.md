# Recuperación del provider ML RSI

Preset intacto: LOW / Wilder RSI29 / EMA4 / PINE_PARITY_V4.
`mlrsi_math.py`, referencia Pine, renderer, protección Guardian, poller y V8
son idénticos a `f6612014be20aca52fd35b872bc504e8f0727eb1`.
SHADOW ONLY, trade_authority=false. No se cambia Railway ni se despliega.

## Incidente observado y límite del diagnóstico

El usuario reportó tres últimos cierres congelados en 07/10/2026 00:00 UTC,
lecturas de mercado fallidas cada 30 segundos y Guardian saludable. Los logs
antiguos solo imprimen `MLRSI_PUBLIC_READ_FAILED`; no permiten conocer la
excepción concreta de ese incidente. DNS/TCP funcionando no demuestra que la
respuesta HTTP/schema/disco fuera válida. No se afirma una causa de producción
sin recuperar esa evidencia.

Se demuestra un defecto específico del commit desplegado ejecutando su código
original, extraído con git show, con un transporte público fake:

1. Se guarda una vela abierta.
2. El primer fetch después del cierre devuelve una primera versión cerrada,
   todavía sin la nueva vela abierta.
3. `verified_at` ya supera el cierre, y el cursor incremental apunta a esa vela.
4. Binance devuelve otra versión del mismo timestamp.
5. El código original lanza `ValueError('MLRSI_CLOSED_CANDLE_REVISED')` antes de
   actualizar la cache. Los siguientes intentos vuelven a comparar la misma
   versión antigua: 12 intentos fallan, con cache idéntica.
6. Reiniciar lee la misma cache envenenada: la excepción persiste.

Esto prueba el mecanismo y su excepción, no que fuera necesariamente el que
ocurrió en Railway. Otra fuente de bloqueo comprobada en el código es una
cache inválida validada fuera de su recuperación, o un gap que supera la
paginación incremental. Los tests cubren ambos caminos. No hay regla midnight.

## Diagnósticos sanitizados

Cada fallo ahora muestra TF y código, por ejemplo:

```
MLRSI_PUBLIC_READ_FAILED 15m MLRSI_CLOSED_CANDLE_REVISED
MLRSI_PUBLIC_READ_FAILED 1h HTTP_429
MLRSI_PUBLIC_READ_FAILED 4h MLRSI_TIMEOUT
```

Solo se permiten códigos estáticos conocidos o HTTP_100..599. Nunca se muestra
el texto de una excepción arbitraria, body, URL, headers, tokens o IDs.
Se distinguen JSON, schema/valor/duplicado, histórico stale/insuficiente/gap,
revisión, lectura/escritura de cache, timeout y error de red. Una excepción no
reconocida se registra como MLRSI_PUBLIC_ERROR. Los avisos de recuperación son
MLRSI_PUBLIC_REBOOTSTRAP, MLRSI_RECENT_CANDLE_FINALIZED y
MLRSI_TIMEFRAME_REBOOTSTRAP, con TF/código estáticos.

## Recuperación sin intervención

- Gracia **120 segundos desde el cierre**, inclusiva. Una revisión de una vela
  que ya se leyó como cerrada dentro de esa gracia sustituye la cache pública.
  También se refresca la vela previa aunque exista una nueva vela abierta.
  Es consolidación de datos; no cambia el instante de cierre ni la matemática.
- Fuera de la gracia, la revisión se rechaza y se registra. Se persiste una
  cache vacía por TF con nueva generación/epoch. El próximo ciclo reconstruye
  desde datos públicos, en lugar de volver a comparar indefinidamente la fila.
- Una cache corrupta se valida/descarta de manera controlada. Una lectura con
  error de permisos se identifica; no se sustituye por una supuesta lectura
  fresca. La escritura debe completar atomic replace/fsync antes de actualizar
  la cache en RAM o declarar éxito.
- Gaps de más de 7000 barras abandonan explícitamente el cursor incremental.
  Otros huecos/staleness también invalidan la cache. Se permite un bootstrap
  público acotado, no interpolación. Bootstrap normalmente 4 páginas; límite
  máximo 8 peticiones por fetch. Cache incremental permanece acotada.
- HTTP429/5xx aplica una pausa por TF de 30 segundos; ningún loop infinito de
  reintentos dentro del fetch. Timeout/red no cambian la cache válida. El worker
  continúa intentando cada ciclo. No se marca FRESH hasta recibir/persistir
  datos completos y actuales. Un backend o disco que siga fallando no puede
  producir una recuperación ficticia.

Cada cache contiene `generation` y un `epoch` UUID sin datos personales. El
epoch detecta recreación/corrupción incluso si se pierde el contador y vuelve
a coincidir. La cache heredada adopta un epoch en su primera escritura; esto
puede exigir una reconstrucción observacional silenciosa una sola vez. Ambos
campos se comparan con metadata independiente del estado ML RSI, por TF.
No se usan Guardian Store, posiciones, permisos ni estado de V8.

## Catch-up silencioso

Un fetch fallido marca la TF en recuperación; esta condición se persiste. El
siguiente fetch válido actualiza el histórico continuo o reconstruye solo su
carry público si generation/epoch cambió. La TF vuelve a FRESH, y su antigüedad
pública se reinicia. Los otros TF no se reconstruyen por ese fallo.

En el ciclo de recuperación NO se envían señales de cierre ni avisos de la
vela abierta recuperada como nuevos, incluido el último cierre del catch-up.
La confluencia recuperada actualiza su episodio sin mandar una nueva entrada
3/3. Catch-up continuo puede journalizar sus timestamps reales; un rebootstrap
no fabrica eventos históricos ni modifica filas anteriores. No se recalculan
resultados futuros. Solo cambios observados después de recuperar pueden volver
a alertar. Startup puede mostrar CURRENT STATUS, nunca NEW SIGNAL.

La función PINE_PARITY V4 permanece byte-equivalent al baseline: no se cambian
seed, RSI/EMA, percentiles, clustering, color, thresholds, CROSS o RESUME.
Reconstruir desde datos corregidos aplica esa MISMA función a los nuevos datos;
una nueva ancla de carga puede variar el histórico efectivo como ya documentaba
PINE_PARITY. No se afirma paridad universal ni se concede autoridad de trading.

## APPROACHING sin duplicados

La distancia/rearm observacional sigue siendo <=1.0 / >1.5. Telegram permite
**máximo un APPROACHING_GREEN y un APPROACHING_RED por TF y timestamp abierto**.
Salir a1.7 y volver a0.9 en esa misma vela rearma internamente pero no repite
el aviso. Un timestamp posterior puede volver a avisar después del rearm.
El último timestamp avisado por color se persiste; el journal sirve de respaldo
para la migración/restart. PROVISIONAL tiene sus propios latches independientes.

## Evidencia automatizada

`test_mlrsi_recovery.py` reproduce el commit desplegado y verifica grace edges,
cierre simultáneo15m/1H/4H, finalización, revisión antigua, autorrecuperación,
restart con cache revisada/corrupta/ausente, gaps, HTTP429/5xx, JSON/schema,
timeouts, errores de disco, aislamiento, epochs, catch-up silencioso, siguiente
evento nuevo, confluencia y deduplicación APPROACHING.

```
python -m py_compile mlrsi_public.py mlrsi_observer.py test_mlrsi_recovery.py
python -m unittest test_mlrsi_observer test_mlrsi_integration test_mlrsi_pine_parity test_mlrsi_source_parity test_mlrsi_recovery -v
python mlrsi_safety_audit.py
python -m unittest discover -v
git diff --check
```

La auditoría exige hashes V4 intactos, AST completo de protección Guardian,
archivos operativos V8 intactos y ausencia de métodos/autoridad de órdenes.
