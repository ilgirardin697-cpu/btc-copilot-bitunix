# Validación de la entrega

Python 3.12.12. Suite global: **1.228 tests, 0 fallos**.
Suite específica del radar: **51 tests, 0 fallos**.
No hay compilador ni ejecución real de TradingView en este entorno.

Las pruebas cubren:

- America/New_York, UTC variable, DST primavera sin 02:00 y otoño con cuatro H1.
- Timestamp Spot ms/us por fecha, closeTime parcial excluido sin reparar, schema,
  duplicados, gaps y ventana de outcome con extremo derecho excluido.
- Prefijos de 1m, m=0, exclusión de minuto60, cambios futuros que no alteran el pasado,
  etiquetas sin acceso a features y features sin acceso a targets finales.
- Primer toque SUPERIOR/INFERIOR/NINGUNO; AMBIGUO no se convierte en NINGUNO.
- Optimización convergida en los cuatro modelos, escalado solo train, selección solo
  validación, bootstrap por ciclos, scoring y publicación cerrada al fallar el gate.
- Aritmética escalar exportada frente a numpy: tolerancia1e-12; esta es una prueba
  interna, NO paridad TradingView independiente.
- Captura opcional append-only, dedupe, conflictos, hash-chain, tampering y truncamiento
  rechazados sin reparar; no se acepta publicar porcentajes con el gate cerrado.
- Hash del protocolo, checksum de artifacts, fórmula Pine original y95 archivos
  protegidos; ausencia de imports de ejecución y llamadas mutantes.
- Orden causal del Pine, sin H1/4H abiertas, sin estrategias/alertas, logs solo realtime.

El log esperado de fixtures `MLRSI_PUBLIC_REBOOTSTRAP 15m MLRSI_CLOSED_CANDLE_REVISED`
aparece en la suite verde y no constituye una regresión. No se cambió código ML RSI.

CI dedicado: `Killzone Probability Radar offline audit`, sin red/datos de cuenta durante
tests ni entrenamiento. Instala dependencias públicas, compila Python y valida artifacts.
Los demás workflows se conservan y se verifican contra el HEAD publicado.

NO comprobado aún: compilación Pine en TradingView, datos intrabar realtime reales,
igualdad real del vector/features/probabilidades, retención efectiva de Pine Logs y recarga.
`actual_tradingview_records_compared=0`, publicación deshabilitada. No se sustituyen
estas pruebas por fixtures sintéticos ni por la paridad del indicador anterior.

SHADOW ONLY. TRADE AUTHORITY: NONE.
