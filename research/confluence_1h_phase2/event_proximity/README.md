# Confluencia H1: evidencia visual parcial y proximidad causal

**INCONCLUSO. SHADOW ONLY. TRADE AUTHORITY: NONE.**

Rama independiente basada en PR #47 `4dcc5d94217b9b387fc69f93ad325e28aaf2a856`.
Solo se añaden archivos en este subdirectorio. PR #46, PR #47 y todos sus archivos
previos se conservan intactos. No hay nuevas fórmulas de indicadores ni backtest.

La coincidencia `−40,40` se registra como **contraste visual externo comunicado
por el propietario**. No se ha recibido/inspeccionado aquí la captura ni una
exportación numérica nueva. No se certifica paridad completa Python/plataforma.

El [informe](EVENT_REVIEW.md) contiene las tablas horarias, ambos casos y los
ejemplos cronológicos favorables y desfavorables. `artifacts/` guarda todos los
cruces del periodo, no solo los ejemplos ilustrados, además de CSV y gráficos.

La propuesta `CONFLUENCE_EVENT_PROXIMITY_DRAFT_V0` y el calendario de revisión
quedaron registrados en `dbaf7fbe8488dd148121b2f7407f9ce91c3c89fa` **antes** de
medir los ejemplos adicionales. Su SHA256 es
`f6ff11a8d0db416719828009a1c13c62b2805c7953dca2e4dcef239102c7fc38`.
Es una hipótesis post-hoc motivada por ejemplos conocidos, no una estrategia
validada ni un holdout virgen. La ventana no se ha variado tras ver resultados.

## Reproducir offline

Python 3.12, NumPy y tzdata; matplotlib opcional para los gráficos.

```text
python -m unittest research.confluence_1h_phase2.event_proximity.test_event_proximity -v
python -m research.confluence_1h_phase2.event_proximity.audit
python -m unittest discover -v
```

El primer comando comprueba la propuesta, timestamps, contexto cerrado y evidencia.
El segundo usa únicamente los fixtures públicos locales y regenera los CSV/JSON
y gráficos. No descarga, no accede a cuentas ni calcula PnL. `detector.py` emite
registros de replay diagnóstico, nunca predicciones forward, órdenes o entradas.

Los tests están dentro de paquetes ya reconocidos por `unittest discover`, de modo
que las regresiones globales existentes de CI los ejecutan con dependencias. En
el job ligero sin NumPy se omiten, como los tests anteriores; el workflow dedicado
de confluencia exige NumPy. No se modifica ningún workflow anterior.

## Propuesta: una ventana y contextos separados

Máxima separación entre eventos: **dos cierres H1**, ventana `[t−2,t]` de tres
instantes de cierre. Se fija para admitir un desfase corto y la vela adicional
necesaria para confirmar dos pendientes del AO; no por beneficio posterior.
No se prueban otras ventanas ni se elige posteriormente la más favorable.

Para cada área se describen, por separado:

* Hipótesis UP: cruce de área sobre roja + **inicio** de dos pendientes AO positivas
  mientras AO<0 + giro ADX. Exige que área siga sobre roja y AO siga recuperándose.
* Hipótesis DOWN: cruce bajo roja + inicio de dos pendientes AO negativas mientras
  AO>0 + giro ADX. Exige alineación inversa actual.
* `PEAK_DECELERATION`: giro ADX desde máximo, con pendiente actual no positiva.
* `TROUGH_BUILDING`: giro ADX desde mínimo, con pendiente actual no negativa.

Los dos contextos ADX no se mezclan ni se selecciona uno mirando los outcomes.
La serie primaria provisional es `pececillos`; marrón y azul son canales de
comparación diagnóstica, no tres operaciones independientes.

La confirmación se fecha en el cierre en que llega el último requisito. Nunca
se atribuye al vértice anterior. El bundle expira entero cuando su evento más
antiguo supera dos cierres. Se invalida por pérdida de alineación tras el cruce,
AO que cambia de signo/deja de recuperar, reversión del contexto ADX, datos no
finitos o un hueco horario. Tras discontinuidad se requieren tres observaciones
limpias para volver a evaluar giros.

Los eventos se consumen al confirmar, expirar o cancelar. Un estado AO persistente
no genera nuevas confirmaciones ni resucita un evento antiguo. Cada canal tiene
su deduplicación; los canales comparten información y no son observaciones de
rentabilidad independientes.

**Entrada, stop, salida, costes y funding permanecen sin definir.** Esta propuesta
no autoriza un backtest de rentabilidad ni una integración. Harían falta una
especificación de riesgo/ejecución nueva, paridad suficiente y revisión adicional.

## Procedencia

* H1 principal: mismo prefijo Spot desde septiembre de PR #47, ampliado con dos
  GET públicos `/api/v3/time` y `/api/v3/klines` sin credenciales. Se preserva el
  punto numérico anterior. Corte cerrado: 15/11/2026 15:00 UTC / 16:00 Madrid.
* Contexto superior: 13 ZIP mensuales públicos de Spot, octubre 2025–octubre 2026,
  más las horas de noviembre. 9.855 H1, sin huecos; 1.464 horas de solapamiento
  archivo/REST contrastadas sin diferencias superiores a 1e-8. Los archivos
  originales permanecen en caché; solo OHLCV público normalizado está versionado.
* Se verifican otra vez los SHA256 contra el manifiesto auditado previo. Ese
  manifiesto declara checksums oficiales verificados originalmente; sus respuestas
  `.CHECKSUM` no están conservadas aquí y **no se afirma haberlas vuelto a obtener**.
  Los archivos Spot usan microsegundos; la división explícita por 1.000 produce
  milisegundos antes de validar apertura/cierre y secuencia exacta.
* El receipt HTTP original de los ficheros REST reutilizados no estaba atestiguado;
  los dos GET nuevos sí conservan su hora real. Ninguno es una emisión histórica
  de TradingOne. Los hashes prueban integridad local, no autentican la captura.
* Contexto 4H/diario UTC; semanas lunes00UTC. Solo grupos completos de 4/24/168
  horas. Se corta el input en cada `available_at` antes de agregar. Se muestran
  AO, su pendiente y DMI; su concordancia de signo da un sesgo **descriptivo**.
  La extensión semanal no es una nueva regla del Direction Engine. Sus 57 semanas
  permiten AO34, pero no SMA200 ni el ranking BBWP semanal completo: son UNKNOWN.

No se toca Railway, Bitunix, Guardian, V8, ML RSI, Telegram, operabilidad, ejecución,
protecciones ni protocolos. Ningún runtime importa este módulo.
