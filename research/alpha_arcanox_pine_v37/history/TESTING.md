# Validación final de la evaluación histórica

- Python3.12.12, suite global final:1177 tests,0 fallos.
- Suite histórica aislada:42 tests,0 fallos. Laboratorio completo:144 tests
  (102 previos de Pine/paridad real y42 históricos).
- ML RSI safety audit:OK; Guardian protection AST y V8 hashes intactos.
- Arquitectura del gate manual:7 tests/0 fallos con referencia V8 requerida.
- Arquitectura semanal:9 tests/0 fallos con referencia V8 requerida.
-95 archivos de runtime/datos protegidos, sin cambios.
-25 checksums oficiales,13 H1 y12 de1m:todos verificados.
-9504 H1 y525600 minutos contiguos;8760 agregaciones60min→1H exactas.

Las pruebas cubren timestamp Spot en microsegundos, normalización exacta,
schema, datos parciales, OHLC y contigüidad, igualdad de niveles entre control
y cuerpo completo, causalidad, ausencia de ejecución y credenciales, capital
restante sin resets, costes reconciliados, nominal+comisión dentro del capital,
entrada posterior y SL/TP solo después de confirmar, ambigüedad adversa,
gaps, timeout, todos los ciclos/meses y checksum de artifacts.

El test de arquitectura detectó inicialmente una mención narrativa a la capa
del gate dentro de una cadena de texto del generador de informes. Se retiró
esa palabra del texto Python; no existía import o consumo del gate y no se
cambió la prueba ni su baseline. La repetición final completa está verde.

La primera pasada detectó una cota de DD inferior al DD observado en algunos
meses por omitir la comisión de salida y el orden favorable/adverso intraminuto.
Se corrigió SOLO ese reporting. Se conserva el primer resultado completo
comprimido y el auditor valida igualdad exacta de todos los ledgers/fills,
cash/MTM curves, PnL, IC, clasificaciones y reglas, con lista de campos cambiados.

C requiere inputs de exchange verificables: las pruebas exigen que faltantes
produzcan BLOCKED_NOT_EVALUABLE con métricas null. Nunca0 liquidaciones,
probabilidad0 de ruina ni una simulación de margen usando Spot como mark.
La fórmula de solvencia se prueba solo con inputs sintéticos etiquetados.

La fuente Pine, core.py, profiles.py, replay.py, risk.py, parity.py y el helper
de64 registros permanecen idénticos a78a20d9. No refreeze de protocolos existentes.
No órdenes, flags, Telegram, Railway, merge o deploy.

El workflow histórico es offline, valida artifacts versionados y no descarga
datos ni invoca servicios. Los workflows existentes continúan independientes;
sus resultados remotos se verifican para el HEAD publicado.

SHADOW ONLY. TRADE AUTHORITY: NONE.
