# I-GOD Confluencia 1H — offline research

**INCONCLUSO. NO-GO para integración. SHADOW ONLY. TRADE AUTHORITY: NONE.**

[Informe numérico](artifacts/IGOD_CONFLUENCE_1H_RESEARCH.md) ·
[Auditoría](AUDIT.md) · [Reglas congeladas](specification.md) ·
[Protocolo](protocol.json)

No hay servicio, poller, credenciales, órdenes, flags ni integración productiva.
No se ejecuta el selector original del ZIP. No se cambian fórmulas/thresholds
después de ver resultados. Fuentes adjuntas conservadas byte a byte con MPL.

El resultado base es cero señales completas sobre cuatro años de Binance USD-M
H1. Las métricas de acierto/expectancy son desconocidas, no0% ni rentabilidad0.
Los CSV conservan todos los candidatos y descartes. No se inventan ejemplos
ganadores/perdedores cuando no existen trades base.

## Ejecución local

Python3.12 para las guardas AST congeladas del repositorio. El análisis numérico
también se ejecutó con3.13, pero esa versión cambia dos hashes AST preexistentes.

```powershell
python -m pip install -r research/confluence_1h/requirements-research.txt
python -m research.confluence_1h.data
python -m research.confluence_1h.evaluate
python -m research.confluence_1h.incident
python -m research.confluence_1h.report
python -m unittest test_confluence_1h_research -v
```

`data` es el único paso normal que descarga archivos oficiales, además del
diagnóstico post-hoc separado `incident`. Los RAW públicos quedan en
`research/cache/`, fuera de Git; `data_manifest.json` permite verificar todos.
Sin conexión/red no se fabrican entradas. Tras descargar, `evaluate` es offline.
CSV completos grandes se versionan comprimidos `.csv.gz`.

## Pine y paridad pendiente

`I_GOD_Confluence_Audit.pine` es un indicador diagnóstico v6 completo. Conserva
las condiciones del paquete y la semántica literal de las fuentes por defecto.
No contiene estrategia, órdenes ni alertas. No se ha compilado en TradingView
desde este entorno, que no dispone de editor/browser autenticado.

Para una prueba técnica futura: gráfico estándar `BINANCE:BTCUSDT.P`,1H,
defaults40/85, suficiente warmup y mismo historial. Activar Pine Logs solo para
el intervalo que se exportará. No mezclar ese ticker con `BINANCE:BTCUSDT` Spot.
`open_time` abre la vela; `available_at` es su cierre confirmado en UTC.

```powershell
python -m research.confluence_1h.compare_pine LOGS_REALES.csv --cache research/cache/confluence_1h_market_data --out resultado_paridad_nuevo.json
```

No se requiere contratar TradingView. Sin logs reales el comparador permanece
sin evidencia; fixtures locales no certifican paridad de plataforma/feed.

## Revisión

Las pruebas cubren causalidad por prefijos, fórmulas escalares independientes,
apertura siguiente, stop primero, gaps, riesgo/costes, funding ausente y ambiguo,
una posición, purga, control calendario, parámetros/venue y aislamiento.
El workflow nuevo es offline; no descarga mercado ni ejecuta Railway.
`validation.json` documenta los resultados efectivamente obtenidos.

Nada de este estudio autoriza órdenes, margen, apalancamiento, Telegram, merge,
deploy o cambios Guardian/V8/ML RSI/readiness/mercado/protocolo semanal.
