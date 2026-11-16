# I-GOD Fase 1B — diagnóstico, no nueva estrategia

Rama independiente desde PR #50 exacta `a48af422f485554dd28ee8da45a3cf1aa0a01929`. Todos sus archivos, reglas, resultados y conclusión NO TESTABLE permanecen intactos. Este subdirectorio es una adición bajo el prefijo permitido por las guardas previas; no se modifica ninguna guarda antigua.

## Contenido

- `REPORT.md`: resultados completos y límites.
- `diagnostic_plan.json`: alcance fijado antes de medir; no cambia el protocolo original.
- `trace.py`: observación de la función original mediante tracing de Python y hash de fuente reconocido. No reimplementa sus decisiones ni parchea sus valores.
- `replay.py`: disponibilidad por cierre, primeros giros, confirmaciones y retrasos. Todas las primeras pendientes se registran, incluidas las que fallan; las referencias retrospectivas no son entradas operativas.
- `inference_costs.py`: reconstrucción de sigma solo con parejas de desarrollo, sensibilidad MDE0.10/0.30/0.50pp y tarifas con cohortes/controles idénticos.
- `evaluate.py`: evaluador offline; revalida los153 archivos públicos originales y la identidad con los resultados de PR50.
- `fixtures/`: Spot y USD-M separados, respuestas nuevas originales y recibos reales UTC/SHA256. Cuatro GET públicos sin credenciales; ninguna consulta privada.
- `artifacts/`: CSV completos, cuatro gráficos y configuraciones/resultados. `trace.csv.gz` expone tokens y motivos, `early_turns.csv` no oculta intentos fallidos, `delay.csv` separa referencias no causales y censura, `cost_rows.csv.gz` conserva todos los escenarios sin seleccionar ganador.

La cohorte histórica conserva desarrollo/evaluación originales y la ausencia de holdout virgen. Los casos12–15nov2026 fueron observados antes: solo diagnóstico contaminado, sin capturas forward ni rentabilidad independiente. No se añade historia desde2019.

## Reproducción

Python3.12, NumPy2.3.5, requests2.32.5 (importado solo por el loader histórico), tzdata para Europe/Madrid en sistemas que no lo incluyen. El evaluador no descarga datos. Matplotlib es opcional para regenerar gráficos.

```powershell
python -m research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.evaluate --cache <market_cache> --out <directorio_nuevo>
python -m research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.report
python -m unittest research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.test_phase1b -v
```

El informe lee los artifacts versionados; `--out` permite una comparación independiente sin sobrescribirlos. El ZIP incluye las dependencias matemáticas originales, los datos públicos brutos, los artifacts padres necesarios y las instrucciones. Guardas que necesitan `git show` requieren clonar el repositorio con historia completa; no se presentan como verificadas solo desde ZIP. En Windows, extraer en una ruta corta para evitar límites de longitud.

El siguiente open con slippage es una hipótesis de ejecución, no un fill observado. Un mínimo/máximo dentro de la vela del vértice AO es referencia de hindsight, no acceso al extremo exacto. Las muestras condicionadas a confirmar2+2 no validan entrar antes; por eso se conservan también los primeros cambios que no prosperan. La sensibilidad de comisión Bitunix VIP0 sobre precios/funding Binance no es un backtest de ejecución Bitunix.

No gestor de TP1, break-even o trailing. No trading, Telegram, Railway, observer nuevo, merge ni deploy. Producción y PR #46–#50 intactas.

**SHADOW ONLY. TRADE AUTHORITY: NONE.**
