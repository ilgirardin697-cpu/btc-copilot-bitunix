# I-GOD V8 Trend Core SHADOW

V7.3.8.6 (`live_auto.py`, `main.py`) y `railway.json` se conservan intactos.
Este PR no activa V8 en Railway. Inicio independiente, cuando se autorice:

```sh
python trend_v8.py
```

BTCUSDT fijo. Solo velas 4H cerradas, con margen temporal de 1,5 segundos,
histórico continuo y última vela vigente. SMA200 incluye el último cierre:
cierre > SMA200 = LONG; cierre <= SMA200 = FLAT. Nunca SHORT; sin TP1/TP2
ni condiciones RSI/ADX/MACD. SMA125/150/175/225/250/300 son telemetría.
Se requieren 200 velas; comparativas sin suficiente histórico quedan en null.

La simulación entra con nocional de 1x su equity y mantiene la cantidad hasta
FLAT. No configura leverage en Bitunix ni lee los parámetros de leverage V7.
`V8_SHADOW_INITIAL_EQUITY` fija el equity virtual inicial (1000 USDT por defecto).
`V8_SHADOW_TURNOVER_COST=0.001` descuenta 10 bps del nocional efectivo
en cada entrada y salida; HOLD no paga costes. Para financiar posición y coste
sin deuda: nocional de entrada = equity / (1 + coste), cantidad = nocional / precio.
Así la exposición vale exactamente 1x del equity NETO tras pagar la entrada.
Salida: efectivo recibido = cantidad * precio * (1 - coste).
Equity NETO y PnL NETO son las métricas principales. State/journal conservan
realized_net (trades cerrados, incluidos ambos costes), costes acumulados,
PnL bruto y realized_gross para diagnóstico. PnL bruto describe la misma
cantidad negociada, sumando los costes al PnL neto; no es otra cartera sin costes.
No añade otro modelo separado de comisiones, slippage o funding.

Tras downtime se procesan todas las velas cerradas posteriores a last_candle,
en orden y con SMA calculada solo hasta cada cierre. Todo el replay se valida
antes de modificar estado. El worker conserva todo el histórico descargado
(hasta aproximadamente 400 velas); se necesitan 199 cierres anteriores a la
primera vela pendiente. Huecos, datos obsoletos o historial insuficiente bloquean
el ciclo sin saltar velas. Primer arranque: solo el cierre vigente; si es LONG,
la operación se etiqueta BOOTSTRAP_LONG, sin afirmar un crossover histórico.
Las observaciones privadas durante replay son actuales, llevan observed_at_ms
y no participan en las decisiones ni representan el estado histórico de cuenta.
Estados/journals antiguos de PnL bruto se rechazan: utilizar otro directorio,
conservando esos artefactos. Tampoco se puede cambiar el coste de una simulación
ya persistida. No se inventan retroactivamente costes de operaciones antiguas.

`V8_MODE` solo admite SHADOW. `LIVE_EXECUTION` y `LIVE_AUTO_START` no tienen
efecto. No importa el ejecutor V7. El transporte Bitunix únicamente permite GET
a cinco rutas exactas de velas, cuenta, posiciones e histórico/fills. No existe
interfaz de colocación, modificación, cancelación, cierre ni cambio de leverage.
Telegram usa los destinatarios existentes, únicamente envía avisos; no consume
comandos y así no interfiere con el polling de V7.

Archivos independientes bajo `V8_DATA_DIR/v8`, o
`RAILWAY_VOLUME_MOUNT_PATH/v8`, o `./v8`:

- `igod_v8_shadow_state.json`: estado virtual, reemplazo atómico.
- `igod_v8_shadow_journal.jsonl`: decisiones, comparación SMA, equity virtual,
  posiciones reales observadas y reconciliación de fills.

El journal se sincroniza antes del estado y permite recuperar un fallo entre
ambas escrituras; un registro truncado provoca parada al recuperar. Ejecutar
una sola instancia por directorio. Un cierre se procesa una vez por timestamp.
Sin credenciales funciona con datos públicos. Fallos privados quedan marcados
READ_ERROR sin afectar la decisión SMA200. Ninguna posición real se adopta.
Las observaciones de equity reales no alteran la cartera virtual.
Reconciliación observada: suma realizedPNL de fills - abs(fees) + funding.
Histórico limitado a 100 posiciones y 100 fills por posición; faltantes o límite
de fills alcanzado quedan INCOMPLETE. No se atribuye ese PnL a V8.

Validación sin red ni credenciales:

```sh
python -m py_compile trend_v8.py test_trend_v8.py
python -m unittest discover -v
```

GitHub Actions ejecuta esas comprobaciones en push y pull_request, sin secretos,
órdenes ni despliegues.
