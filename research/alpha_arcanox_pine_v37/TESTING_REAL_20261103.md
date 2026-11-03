# Verificación con export real — 2026-11-03

- Comparador original de31bcbe3 ejecutado ANTES de cambios: MATCH;64 registros,
  33 comparados,31 iniciales excluidos,2 pares completos. Se conserva su salida
  original en `artifacts/parity_cli_first_run_20261103.json`.
- Error absoluto máximo real0;0 discrepancias por campo. Tabla de pares nulos,
  valores numéricos y booleanos en `artifacts/REAL_TRADINGVIEW_PARITY_20261103.md`.
- Fuente64 real preservada byte a byte, SHA256
  `3fc02a8fc12664591766df834c869b10d66cf54606ce12b5e9f87ce54b9d3097`.
  Schema cerrado de campos públicos de mercado; sin credenciales, cuentas o chats.
- Suite del laboratorio:102 tests/0 fallos (75 anteriores +27 nuevos).
- Suite global Python3.12.12:1135 tests/0 fallos.
- `mlrsi_safety_audit.py`: OK; Guardian protection AST y V8 hashes intactos.
- Readiness boundary `--require-v8`:7 tests/0 fallos.
- Weekly boundary `--require-v8`:9 tests/0 fallos.
- Guardas existentes incluyen900 estados/hash de readiness, protocolos congelados
  y95 archivos de fuente/datos de runtime sin cambios.

No se modifican `parity.py`, `core.py`, `profiles.py`, `replay.py`, `risk.py` ni
los bytes del Pine fuente original respecto de31bcbe3. No se cambia ni un
umbral/horario/inset para obtener el MATCH o para aceptar las operaciones.

Las nuevas pruebas cubren evidencia real separada de fixtures sintéticas,
replay parcial sin inyección, DST fold, tipos y errores por campo, tiempos de
apertura/cierre, OWNER_B independiente de los niveles A, rechazo por1.5R,
TP±200, ATR disponible y cuerpo completo, datos posteriores al cierre,
SL/TP simultáneos adversos, gaps, censura y ausencia de PnL de operaciones
rechazadas. Los dos gráficos contienen las velas reales de la exportación,
con niveles calculados de OWNER_B y señalización explícita de rechazo.

El diagnóstico MLRSI_PUBLIC_REBOOTSTRAP de una fixture sigue siendo esperado;
no es un fallo ni se han alterado módulos ML RSI. El resultado global es OK.

CI remoto se informa aparte del resultado local. El workflow nuevo ejecuta
ambas suites, reproduce artifacts de forma determinista y hace diff-check.
No hay llamada al exchange, Telegram, Railway ni ejecución desde el laboratorio.

SHADOW ONLY. TRADE AUTHORITY: NONE.
