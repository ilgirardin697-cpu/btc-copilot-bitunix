# Confluencia H1, fase 2: identidad de series y semántica temporal

**INCONCLUSO. SHADOW ONLY. TRADE AUTHORITY: NONE.**

Este laboratorio añade una auditoría estática y un comparador externo. No escoge
una estrategia, no calcula rentabilidad y no cambia PR #46. Su base exacta es
`522201530c1b81453ea653fc8a1860b1b10eabaf` de esa PR DRAFT. Todo el contenido
anterior permanece intacto; el trabajo nuevo ocupa un directorio separado.

El informe principal es [CONFLUENCE_PHASE2.md](CONFLUENCE_PHASE2.md). No hay una
serie «amarilla» inequívoca: las áreas del original se superponen y sus colores
pueden configurarse. Se comparan las tres áreas con la media roja original.

## Reproducir la auditoría offline

Python 3.12, NumPy y tzdata; matplotlib solo para regenerar gráficos.

```text
python -m unittest test_confluence_1h_phase2 test_confluence_1h_research -v
python -m research.confluence_1h_phase2.describe
```

El segundo comando usa únicamente dos fixtures públicos locales, comprueba sus
SHA256 y genera CSV descriptivos y gráficos. No descarga datos ni evalúa trades.
Los fixtures terminan antes de cualquier evolución posterior al intervalo de
diagnóstico. Los generadores de precios sintéticos de los tests no son evidencia
externa ni backtests nuevos.

## Comparar una exportación real

No se ha recibido ninguna exportación de TradingOne. El ZIP independiente contiene
scripts y resultados **sintéticos**, no registros de dicha plataforma. El comparador
ya acepta CSV de columnas nombradas, JSONL y CSV de Pine Logs; no inventa registros.

1. Conservar intacto el archivo exportado original. Copiar
   `export_metadata.template.json` a un archivo local y completar solo datos
   comprobados: plataforma real, ticker completo, venue, configuración, tipo de
   vela, unidades de volumen, precisión y significado/formato del timestamp.
   `settings=null` y origen de inicialización desconocido bloquean la equivalencia,
   pero permiten examinar diferencias numéricas.
2. Mapear los títulos exactos de las columnas a `pececillos`, `tendencia`,
   `tiburones` y `ma_trend`. No inferir nombres por color ni considerar
   `ma_trend` una media de `pececillos` o de `tiburones`.
3. Disponer del OHLCV de la misma venue y de todo el prefijo de inicialización.
   El formato de mercado es el de `export_rows.template.csv` para precios, usando
   la columna `open_time_ms` en lugar de `time`; las columnas mínimas son
   `open_time_ms,open,high,low,close,volume`. Su manifiesto requiere `sha256`,
   `venue`, `symbol`, `timeframe_seconds`, `rows`, `first_open_ms`, `last_open_ms`.
   Puede ser CSV o CSV.gz. Los manifiestos públicos de `fixtures/` son ejemplos
   reales de formato, **no una atribución del gráfico del propietario a Binance**.
4. Ejecutar, eligiendo una salida nueva que no sobrescriba evidencia anterior:

```text
python -m research.confluence_1h_phase2.compare export.csv --metadata metadata.json --market mercado.csv.gz --market-manifest mercado.json --out comparacion_nueva.json
```

Se rechazan filas incompletas de tiempo, velas abiertas, duplicados, huecos,
orden temporal incorrecto y discrepancias de mercado. Se informan errores OHLCV
y por cada serie, cruces frente a la roja, giros de pendiente y pasos por cero.
No hay ajuste del eje temporal, búsqueda de correlaciones, rescalado de valores
ni selección del subconjunto que mejor coincida. Los empates por redondeo quedan
indeterminados. La primera fila no puede certificar un cruce sin su anterior;
un giro de pendiente requiere tres valores consecutivos.

La tolerancia es `1e-7` con exportación de precisión completa, o medio quantum
de los decimales declarados más `1e-7`. Es una cota para el contraste, no prueba
de que dos feeds redondeados sean idénticos. No se aceptan precisiones de menos
de dos decimales. Se conserva el SHA256 del archivo original y de los metadatos.

**Una coincidencia numérica no certifica por sí sola la identidad de la línea
seleccionada visualmente ni desbloquea un backtest.** El comparador conserva la
revisión de origen/identidad como pendiente. Tampoco puede autenticar criptográficamente
que un CSV procede del servidor de una plataforma.

## Diagnóstico Pine opcional

`I_GOD_Koncorde_Three_Series.pine` es un indicador nuevo, pasivo y sin alertas.
Reproduce las fórmulas públicas por defecto ya auditadas y muestra las tres áreas
y la media roja. Incluye AO, ADX/DMI, ATR e internos PVI en la ventana de datos.
No sustituye al original ni modifica el Pine de PR #46.

No se ha compilado ni ejecutado este nuevo archivo en TradingOne/TradingView.
Su compatibilidad requiere una plataforma que soporte Pine v6; no se presupone
que «TradingOne» sea TradingView.

En una plataforma compatible se puede activar `Closed-bar diagnostic logs`,
desactivado por defecto. El prefijo es `IGOD_KONCORDE_SERIES_V1=`. Para CSV de
Pine Logs, declarar `export_format=PINE_LOGS_CSV`, `message_column` con el título
real del mensaje y `timestamp_format=unix_ms`. Para JSONL usar `JSONL`.

Los mensajes incluyen ticker, OHLCV, las cuatro series, inicio del histórico,
apertura `time`, cierre `available_at`, `emitted_at=timenow` y si son recálculos
históricos. `timenow` en un replay es el reloj de ejecución actual; **no demuestra
una emisión forward en noviembre**. No se ajusta la apertura usando el timestamp
exterior de Pine Logs.

No hace falta contratar ninguna suscripción para revisar el código o ejecutar
el comparador offline. Obtener suficientes valores reales y sus ajustes sigue
siendo una tarea pendiente de evidencia externa.
