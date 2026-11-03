# Verificación local — 2026-11-03

Python3.12.12; base de zonas IANA disponible mediante PYTHONTZPATH local. Linux
CI usa su base IANA del sistema. Sin credenciales, producción ni exchange API.

| Comprobación | Resultado |
|---|---|
| Nueva suite `research.alpha_arcanox_pine_v37.test_pine` | 75 tests, 0 fallos |
| `python -m unittest discover -v` final | 1108 tests, 0 fallos |
| `python mlrsi_safety_audit.py` | MLRSI_SAFETY_AUDIT_OK; Guardian AST / V8 hashes intactos |
| `python test_bitman_readiness_boundary.py --require-v8 -v` | 7 tests, 0 fallos |
| `python test_bitman_weekly_boundary.py --require-v8 -v` | 9 tests, 0 fallos |
| Archivos de runtime/datos protegidos por nuevo manifest | 95 sin cambios (CRLF→LF únicamente para hash multiplataforma) |
| Source Pine y fixture público | SHA256 originales conservados |
| Reconstrucción vectorial/copia diagnóstica | determinismo comprobado |

La suite global incluye las 900 combinaciones de readiness y compara el hash
de resultados aprobado: WAIT780, WATCH_LONG59, WATCH_SHORT59, READY_LONG1,
READY_SHORT1. No se han modificado los canarios existentes.

El mensaje `MLRSI_PUBLIC_REBOOTSTRAP 15m MLRSI_CLOSED_CANDLE_REVISED` procede
de una fixture de la suite existente; el resultado final es OK, no una regresión
de ML RSI. No se han cambiado sus módulos.

Los tests propios de comparador son fixtures SINTÉTICAS de plumbing, no salidas
TradingView recuperadas. Registros TradingView reales:0. Compilación Pine en
plataforma: PENDIENTE. Paridad Alpha privado: NOT PROVEN. Rentabilidad no evaluada.

Se añade un workflow offline aislado. Su resultado remoto se reporta aparte
del test local, sin inferir SUCCESS por haber preparado el YAML.

El archivo Pine conserva incluso sus líneas finales en blanco; `.gitattributes`
excluye SOLO su comprobación `blank-at-eof` y evita conversión de bytes. El
resto del patch conserva `git diff --check`, sin relajar controles productivos.

SHADOW ONLY. TRADE AUTHORITY: NONE.
