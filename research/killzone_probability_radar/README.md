# I-GOD Killzone Probability Radar

Indicador independiente Pine v6 y laboratorio offline. **NO VALIDADO: sin porcentajes visibles.**
No es Killzone V3.7 Lite modificado, ni cambia OWNER_B o OWNER_C.
No hay órdenes, alertas, webhooks, Telegram, servicio continuo ni integración productiva.

- [Archivo completo para TradingView](I_GOD_Killzone_Probability_Radar.pine).
- [Instrucciones de instalación y prueba real pendiente](TRADINGVIEW.md).
- [Informe de entrenamiento y validación](artifacts/MODEL_TRAINING_VALIDATION.md).
- [Resultados completos, calibración y modelos](artifacts/model_validation.json).
- [Mensual](artifacts/monthly.csv), [por minuto](artifacts/per_minute_test.csv),
  [todos los ciclos/exclusiones](artifacts/cycles.csv).
- [Comparación Python/Pine: alcance y bloqueo](artifacts/pine_comparison.json).
- [Ejemplo SUPERIOR](artifacts/example_SUPERIOR_FIRST.svg),
  [INFERIOR](artifacts/example_INFERIOR_FIRST.svg), [NINGUNO](artifacts/example_NEITHER.svg).
- [Protocolo congelado antes del análisis](specification.json).

La prueba posterior tiene 667 ciclos y la selección usa únicamente 2024.
PRICE_4H mejora el Brier frente al prior, pero no demuestra mejora incremental
respecto a PRICE con IC95 positivo. No se reemplaza el candidato usando el test.
El precio solo aporta información histórica; esto no demuestra una ventaja de trading.
ADX mide fuerza, no dirección. AO/ADX/DMI y BBWP son fórmulas públicas,
no indicadores propietarios de Bitman verificados.

La paridad de este radar en TradingView sigue pendiente. El espejo escalar local
es una comprobación de aritmética, no un test Pine real ni evidencia independiente.
Los 64 logs del indicador anterior no validan este radar.

## Reproducir sin servicios

Python 3.12, numpy, requests y base IANA tzdata (en Windows instalar `tzdata`).
Los pasos descargan solo archivos públicos oficiales; no necesitan claves.
El entrenamiento no se ejecuta en CI; CI comprueba los artifacts versionados.

```sh
python -m research.killzone_probability_radar.data
python -m research.killzone_probability_radar.dataset
python -m research.killzone_probability_radar.model
python -m research.killzone_probability_radar.build
python -m unittest research.killzone_probability_radar.test_radar -v
```

Los ZIP/npy y ejecuciones están en `cache/killzone_radar_v1/`, ignorado por Git.
El manifiesto conserva URL, checksum oficial, tamaño y unidad temporal de cada archivo.
`features_and_labels.npz` contiene únicamente datos públicos derivados de replay histórico;
NO es un journal forward. Permite reproducir scoring sin descargar 2,5 millones de minutos.

## Captura prospectiva opcional, todavía no activada

Pine Logs solo emite el último timestamp realmente disponible en tiempo real.
No exporta 60 supuestas observaciones pasadas al conectar el indicador.
Recargar pierde su watermark `varip`: hace falta capturar los logs externamente.
El importador offline admite el formato y conserva los originales en hash-chain:

```sh
python -m research.killzone_probability_radar.journal logs_reales.txt --journal research/cache/killzone_radar_v1/predictions_forward.jsonl
python -m research.killzone_probability_radar.parity logs_reales.txt --out research/cache/killzone_radar_v1/parity_actual.json
```

Solo se permite escritura del journal en `research/cache`, nunca `/data`.
IDs repetidos idénticos no escriben; valores distintos con el mismo ID se rechazan;
corrupción/truncamiento no se repara. El importador es de un solo escritor.
No autentica criptográficamente que el texto provenga de TradingView: conserva
`captured_at`, `emitted_at` y su procedencia declarada. No se fabricó ningún log real.
No se inicia observación continua con este trabajo. Los outcomes comparativos se
guardarán separadamente, sin sobrescribir las predicciones originales.

SHADOW ONLY. TRADE AUTHORITY: NONE.
