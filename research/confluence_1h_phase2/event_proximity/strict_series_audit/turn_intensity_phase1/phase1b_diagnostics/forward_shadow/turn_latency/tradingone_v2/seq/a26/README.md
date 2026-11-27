# Addendum de PR #58 — cómo reproducirlo

SHADOW ONLY. TRADE AUTHORITY: NONE. Sin captura continua ni conexiones de trading.

Desde la raíz del repositorio, con Python3.12, NumPy2.3.5, requests y tzdata:

    python -B -m research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.forward_shadow.turn_latency.tradingone_v2.seq.a26.run --out /tmp/igod-a26-replay
    python -B -m unittest research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.forward_shadow.turn_latency.tradingone_v2.seq.a26.test_a26 -v

No requiere red: usa d/ y verifica bytes originales, prefijos y hash-chain. Rechaza sobrescribir resultados.
El directorio de salida nuevo debe no existir. En Windows elige una ruta local corta dentro del workspace.
El exportador observe.py se utilizó una sola vez para200 observaciones, sin señales ni outcomes de la hipótesis del miembro.
El gráfico se generó con plot.py (Matplotlib), sin reconstrucción visual de indicadores privados.

Este ZIP incluye el paquete de auditoría padre audit.zip íntegro. Extraer primero ese paquete según su README,
y después superponer los archivos repo/ de este ZIP conservando las rutas relativas a la raíz del repositorio.
Se incluye el módulo mlrsi_math.py sin cambios para la comparación del perfil operativo.
También se puede usar directamente el checkout exacto de la PR; el padre y sus resultados siguen versionados.

manifest.json verifica los archivos del addendum. La hash-chain anterior y el prefijo de los nuevos datos deben coincidir.
No se importa research desde producción. No se cambia una regla porque el resultado sea negativo.
La nueva cita de un miembro es una hipótesis incompleta: no existe backtest ni comparación fuera de muestra de esa combinación.
Fuente exacta/confirmaciones AO y Konkorde siguen pendientes;5m no capturado;manual Murphy no disponible localmente.
