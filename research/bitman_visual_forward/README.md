# Validación visual y diseño forward Bitman

Estado: **NO-GO para construir/activar observer conectado**.
Paridad visual exacta PENDING; no hay señal rentable demostrada.

- VISUAL_PARITY_AUDIT.md: fuente, fórmulas, diferencias y referencia que falta.
- FORWARD_PROTOCOL.md: selección POST-HOC, tres candidatos, causalidad y journal futuro.
- artifacts/pr33_reference_summary.json: frecuencias extraídas de PR33, sin nuevo backtest.
- capture_reference.json: descripción del propietario, sin completar datos desconocidos.
- compare.py + pine/visual_export_v0.pine: mecanismo offline para CSV independiente.
- design.py/snapshot.py/ledger_contract.py: contratos puros probados con fixtures sintéticas.
- protocol_manifest.json: fuentes y configuración del diseño; activation_at UNSET.

No observer, scheduler, host, worker, conexión de mercado o persistencia live.
No modificación de producción, PR33 ni BITMAN_WEEKLY_FORWARD_V1.

SHADOW ONLY. TRADE AUTHORITY: NONE.
