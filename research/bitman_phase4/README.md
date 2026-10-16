# BITMAN REAL Phase4 — directional confluence research

**INCONCLUSIVE / SHADOW ONLY / trade_authority=false.**

Base exacta PR23: `ee4e59016220ec733b19a37d14429f8fdde6d348`.
No se modifica PR23, sus68 tests ni su resultado INCONCLUSIVE. BITMAN Phase2
permanece REJECT. Ninguno de estos experimentos representa toda la metodología
privada Bitman. El resultado no concede permiso de entrada.

- [Resultados y reglas completas](PHASE4_RESULTS.md)
- [Provenance nueva: cuatro transcripciones primarias](SOURCES.md)
- [Propuesta legacy/ruido, no ejecutada](LEGACY_SIGNAL_AUDIT.md)

## Arquitectura aislada

`spec.py` preregistra seis familias LONG/cuatro SHORT. `core.py` utiliza únicamente
módulos puros congelados de PR23 y genera secuencias causales AO→ADX/DI; 1H/4H,
1D contextual. `ledger.py` es un simulador académico financiado, no un cliente de
órdenes. `study.py` separa físicamente DEV de TEST y conserva locks y resultados.
`report.py` solo presenta artifacts congelados. `telegram.py` es un renderer puro,
sin sender/token/poller. No hay un nuevo proceso forward integrado o desplegado.

No imports de producción ni clientes de cuenta; no HTTP, órdenes, secretos,
poller adicional ni lectura/escritura de estados de producción. Los scripts solo
leen el cache público verificado y escriben en este namespace o salida research
explícita. El renderer puede mostrar LONG/SHORT como **hipótesis observacional**,
nunca como autorización. No se ejecuta ninguna limpieza legacy.

RSI privado: PRIVATE / PARITY NOT PROVEN. Trend Speed: NOT IMPLEMENTED / FORMULA
NOT VERIFIED. Producción ML RSI no se importa ni modifica. Koncorde/volatilidad
son proxies públicos, no clones privados. No se usa RSI verde/rojo como regla.

## Datos y metodología

Python3.12.12, numpy2.3.5; requests2.32.5 solo para tests del repo. Historial Git
completo necesario para fingerprints. Dataset ignorado heredado verificado:
`research/cache/bitman/hourly.npz`, SHA256
`e355d2dfe58f479a4c789e1ff6cdffceabcf4cb55ff5c5d0c7c465d9d59fee25`.
61,723 velas1H completas (warmup octubre2019), 7,440 registros de funding;
cutoff2026-10-15T19:00Z. No actualización silenciosa del dataset.
Fuentes/rangos/checksums en `artifacts/data_manifest.json`; adquisición pública
original documentada en README de Phase2, commit44029b4. Reutilizar **datos**, no
reglas rechazadas. No hace falta acceder a Railway ni cuentas.

TRAIN2020–21, VALIDATION2022–23, TEST2024–cutoff. TEST reutilizado OOS, no virgin.
`freeze` se ejecutó antes de medir; el hash cubre spec/core/ledger/study con LF.
`develop` corta físicamente precios/funding antes de2024, selecciona eventos,
escribe event_lock y después chequea elegibilidad neta sin reranking. Ninguna
familia fue elegible; los cuatro fallbacks son diagnósticos no promocionables.
`evaluate` exige protocolo/lock intactos y no sobrescribe resultados existentes.
Walk-forward anual2022–26 utiliza solo años anteriores a cada fold.

Los eventos miden retornos brutos/excursiones/first-passage en futuros1H cerrados;
no son estrategias. Las estrategias seleccionadas tienen costes/funding y entradas
siguiente apertura. Fees5bps, slip2bps, stopslip5bps; stress6/5/10. 1x nominal de
entrada, cantidad fija; LONG/SHORT independientes. El libro no modela margen ni
liquidación exacta Bitunix. Stops revisados en1H pueden tener incertidumbre
intrabar. Funding usa precio1H de settlement proxy. PF es ratio de retornos por
trade, no beneficios monetarios con equity variable. No combinar las curvas1x.

## Reproducir

No ejecutar `freeze`/`develop` sobre los locks publicados para retocarlos.
Con el cache exacto disponible y una salida nueva:

```text
python -m research.bitman_phase4.study evaluate --output-dir research/cache/bitman_phase4_replay_new
python -m research.bitman_phase4.report
python -m compileall -q research/bitman_phase4 test_bitman_phase4.py
python -m unittest test_bitman_phase4 -v
python -m research.bitman_phase4.safety
python -m unittest discover -v
git diff --check
```

Comparar results.json byte por byte y eventos/trades tras descomprimir gzip:
las cabeceras gzip contienen hora de escritura y no prueban una divergencia.
El replay realizado queda documentado en `artifacts/validation.json`. CI no
descarga datos grandes ni transcripciones: prueba fixtures offline, integridad
de locks, causalidad, aislamiento y regresión completa.

Para crear una investigación nueva se debe usar otro namespace/versión y otro
protocolo, nunca sobrescribir este experimento después de mirar TEST.

## Evidencia pendiente

**FORWARD_VOLUME_DATA: PENDING / NOT ACCESSIBLE FROM CURRENT CONNECTOR.**
No señal reconstruida se etiqueta como observación live. GradoA requiere forward
independiente no disponible; B exige superar todos los gates históricos; C actual.
No probabilidades inventadas ni sizing por grade. Las transcripciones verifican
explicaciones cualitativas, no rentabilidad ni indicadores privados exactos.

## Seguridad

Fingerprints de producción y todos los archivosPR23; AST/capability audit sin
transporte/cuenta/orden. Versiones fijadas de V8/ML RSI fingerprinted en el audit
heredado, sin integrar sus ramas. El PR depende del HEADPR23 aún no fusionado;
al compararlo con main incluye ese contenido heredado sin cambiarlo.

V8 UNCHANGED. GUARDIAN PROTECTION UNCHANGED. ML RSI UNCHANGED.
MANUAL COPILOT UNCHANGED. EARLY BREAKOUT UNCHANGED.

**NO MERGE. NO RAILWAY DEPLOY. NO REAL ORDERS. NO production Telegram changes.**
