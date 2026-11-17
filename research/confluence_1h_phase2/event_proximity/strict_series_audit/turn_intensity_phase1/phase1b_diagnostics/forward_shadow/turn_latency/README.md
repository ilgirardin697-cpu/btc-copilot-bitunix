# Turn latency — diagnóstico offline

[Informe sencillo](results/TURN_LATENCY_REPORT.md). No es otra estrategia, no calcula rentabilidad y no modifica el NO EDGE de PR #55.

La especificación quedó comprometida antes de contar resultados: `400264d`, `protocol.json`. `source_seal.json` identifica el código numérico reproducido; no modifica ni vuelve a sellar ningún protocolo anterior.

## Reproducir

Python3.12, NumPy2.3.5 y tzdata. Matplotlib solo para gráficos. La dependencia matemática es el archivo original auditado `research/confluence_1h/indicators.py`, intacto.

El NPZ H1 auditado se obtiene del paquete de PR #55, SHA256 `5b2544c9bf353cedb77a07781ffe9e6202b12513c0c10f3d25bca67756a4825a`. El JSON público del ejemplo está versionado en `../swing_capture/results/diagnostic_raw.json`, SHA256 `e5cb4c2bd439b74066846e4a8076cc1c1aeea1e4fc91cb433810b51a77ea29e8`. No se descarga mercado ni se llama a servicios.

Desde la raíz del repositorio, PowerShell:

```powershell
$mod = 'research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.forward_shadow.turn_latency'
python -m unittest "${mod}.test_latency" -v
python -m "${mod}.study" --data validated_market.npz --diagnostic ruta_al_diagnostic_raw.json --out resultado_nuevo
python -m "${mod}.report"
```

`study` exige una salida NUEVA y no sobrescribe resultados. `report` representa únicamente los resultados ya calculados en `results/`; no reajusta parámetros ni recalcula señales. Si se genera otra carpeta para reproducción, comparar sus datos con los archivos versionados antes de usarla como carpeta de gráficos. La CLI de mercado solo lee archivos locales.

En Windows, la profundidad heredada de los guards puede exceder el límite de archivos `.pyc` temporales de `compileall`. Puede compilarse en memoria con `compile(source, path, 'exec')` y ejecutarse con `PYTHONDONTWRITEBYTECODE=1`; no se cambia código protegido para solucionar una ruta de caché. CI Linux ejecuta la suite y las dependencias numéricas existentes.

## Qué evidencia falta de TradingOne

No se ha recibido una exportación numérica real nueva para AO, ADX/DMI, Konkorde o BBWP. Se conserva el punto visual comunicado de pececillos, sin convertirlo en paridad certificada. Las pruebas numéricas internas y sintéticas NO son registros externos.

`export_rows.template.csv` contiene solo cabeceras, nunca valores inventados. `export_metadata.template.json` deja como desconocidos los metadatos no comprobados. Se necesitan nombres de series, vela estándar H1 cerrada, ticker/venue exactos, OHLCV base, ajustes, inicio de inicialización, apertura/cierre UTC y precisión. El comparador devuelve diferencias por campo aunque la paridad completa siga bloqueada por metadatos o valores ausentes. Ver `compare_export.SETTINGS` para el perfil matemático explícito; no rellenarlo sin contrastarlo con la plataforma.

```powershell
python -m "${mod}.compare_export" export_real.csv --metadata metadata_verificada.json --market mismo_mercado.npz --venue BINANCE_SPOT --out comparacion_nueva.json
```

El archivo de mercado debe tener el mismo prefijo e identidad de venue que el exportado. No se aplican shifts, rescalados, tolerancias ajustadas a los resultados ni cambios de fórmula. Las coincidencias redondeadas pueden no bastar para demostrar un cambio de pendiente. Una comparación aritmética no autentica el origen de una exportación.

## Integridad y límites

Los resultados incluyen las prealertas falsas, giros sin prealerta y finales censurados, ambos sentidos y todos los años. Las distancias desde extremos ya conocidos son referencias descriptivas, no entradas perfectas. Los denominadores ex-post están separados del detector. Las pruebas verifican causalidad, simetría, pérdida de datos, expiración y ausencia de dependencias de red/ejecución.

`files_sha256.json` identifica los archivos, `audit_bundle.zip` los conserva junto a las pruebas, y `bundle.json` publica su hash. El gran NPZ histórico ya auditado no se duplica; se documenta su origen y checksum.

No nuevo observador, infraestructura, backtest de rentabilidad, orders, merge ni deploy. No modificaciones de producción ni de las investigaciones anteriores.

SHADOW ONLY. TRADE AUTHORITY: NONE.
