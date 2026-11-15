# I-GOD: giros ADX + AO, intensidad y entrada a12 horas

Nueva investigación aislada sobre PR49 exacta `9793acff82388c5a60b59796af4c6fa765331129`. **No modifica PR46–49**. Las adiciones están anidadas aquí para respetar sus guardas de fuente; no se debilitan las guardas para permitir otra ubicación. Ningún consumidor productivo importa este paquete.

## Formalización fijada antes de resultados

El propietario confirmó el15/11/2026 tres patrones conceptuales. Las convenciones numéricas siguientes son hipótesis nuevas explícitas, no una certificación de indicadores privados ni una reproducción ya demostrada de capturas.

| Patrón | Configuración principal | Control espejo |
|---|---|---|
| P1 Agotamiento de caída | LONG: pico ADX que cae, AO negativo recupera, pececillos recupera | SHORT: AO positivo pierde impulso, mismo contexto ADX |
| P2 Inicio de impulso bajista | SHORT: suelo ADX que sube, AO deteriora con cualquier signo, pececillos cae, −DI>+DI | LONG: AO/pececillos recuperan y +DI>−DI |
| P3 Rebote fallido | SHORT: AO sigue negativo tras dos pendientes positivas y dos negativas; pececillos gira abajo, sin exigir cruce de media | LONG: AO sigue positivo tras corrección y vuelve a subir |

Cada giro exige **dos pendientes previas estrictamente opuestas y dos posteriores estrictamente alineadas**, cinco valores conocidos. No se retrofecha al vértice. Para P1 el ADX forma pico; P2 forma suelo; P3 no añade un filtro ADX que el propietario no definió. El cruce con EMA roja queda como distinción conceptual de investigaciones anteriores: aquí se evalúan giros de pececillos, no se impone un cruce.

AO5/34, ADX/DMI14/14, ATR14 y pececillos se importan del cálculo auditado de PR46 sin editarlo. AO color/pendiente y signo se tratan por separado. BBWP se registra como contexto, sin convertirse en filtro nuevo. La EMA roja original sigue siendo EMA15(tendencia), nunca EMA(pececillos).

### Intensidad y episodios

La ventana de ranking es720 horas anteriores exactas; no entra la vela actual ni ninguna posterior. Midrank empírico con empates. AO: cambio de dos barras normalizado por precio; también se guardan nivel y pendiente normalizados. Pececillos: magnitud del cambio de dos barras. ADX: nivel en el vértice y diferencia entre medias de las dos pendientes posteriores/anteriores.

**Primario Q75** exige todos los componentes aplicables en su cola intensa; Q90 y ALL son secundarios. P1 utiliza nivel ADX alto; P2 nivel bajo y giro grande, no un umbral alto copiado del pico. Para P3 los componentes de intensidad son AO y pececillos, y ADX es descriptivo. Son cortes marginales conjuntos, **no una obligación de seleccionar exactamente25% o10% de episodios**; pueden producir muy pocos o ninguno.

Los tokens pueden coincidir como máximo con2 horas de separación. Caducan/cancelan como conjunto, se consumen y no reaparecen. Una dirección contraria, pérdida de signo requerido, inversión ADX/DMI cuando aplica, gap o dato inválido impiden confirmar. Separación mínima de25 horas por patrón/lado, aplicada a todos los episodios válidos antes de filtrar intensidad. Se conserva el ledger de expiraciones y descartes.

### Prueba principal

Una única familia de6 contrastes (tres patrones y sus espejos). Entrada modelada en primera apertura H1 posterior; salida en apertura12 horas después de **esa entrada**, no desde el vértice ni desde la señal.4/24h secundarios. Sin stop en Fase1; retornos netos porcentuales y equivalentes normalizados por ATR, **no R**.

Cada episodio busca3 controles de idéntico lado, mes, régimen4H confirmado y tercil de ATR/precio causal; sin reemplazo dentro de cada celda y sin posiciones temporales superpuestas entre controles. No se relaja un estrato insuficiente. Se publican todos los episodios y la cobertura del subconjunto emparejado.

Comisiones0.1% por lado y slippage adverso0.05% por lado: supuestos conservadores heredados, no tarifas personales verificadas. Funding real de Binance USD-M, con bandas cuando falta mark exacto o el settlement coincide con apertura/salida. Nunca se presenta esa banda como neto exacto ni como ejecución Bitunix observada.

IC95 y p aproximada mediante bootstrap centrado en bloques móviles de7 días,2000 réplicas, semilla20261115. Referencia metodológica: [Künsch1989, bloques para observaciones dependientes](https://doi.org/10.1214/aos/1176347265). No es prueba exacta de aleatorización; depende de supuestos de estabilidad. Corrección escalonada de Holm para las6 pruebas; celdas no testables conservan p=1 en la familia, no desaparecen.

Potencia80% para diferencia mínima neta0.10 puntos porcentuales a12h; planificación conservadora α=.05/6. Sigma se estima solo en desarrollo, con fallback conservador predefinido. Tamaño efectivo = varianza por observación / varianza bootstrap de la media, limitado a n; se exigen también20 bloques ocupados. Es una estimación de dependencia, no una certeza de potencia con distribuciones desconocidas. Las celdas insuficientes son **NO TESTABLE**, aunque una media o p descriptiva parezca favorable.

## Separación temporal

- Datos públicos BTCUSDT USD-M cerrados, warmup desde septiembre2022; mismo NPZ y153 fuentes verificadas de PR46.
- Desarrollo noviembre2022–diciembre2024; evaluación enero2025–septiembre2026,24h de embargo a cada lado de la frontera y purga de salidas.
- Octubre–noviembre2026 queda como diagnóstico ya observado y no se puntúan sus resultados aquí. **NO VIRGIN HOLDOUT** en los datos previamente examinados, incluyendo el bloque denominado evaluación.
- Protocolo forward planificado17/11/2026–17/11/2027 UTC, no activado. Fecha fija,12 meses completos, análisis final solo tras maduración24h, sin parada por rendimiento. La meta de muestra efectiva de cada celda queda congelada en el artifact de potencia de desarrollo. Si no alcanza muestra o95% de cobertura verificable, termina NO TESTABLE; no se extiende ni desplaza silenciosamente. Retrasos de activación se conservan como ausencias; históricos no cuentan como forward. Requiere futura revisión independiente y autorización de captura.

## Ejecución offline

```powershell
python -m unittest research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.test_turns -v
python -m research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.evaluate --cache <market_cache> --out <nuevo_directorio>
```

No se descargan datos desde el evaluador. El loader revalida el NPZ y todos los archivos públicos auditados. `artifacts/` contiene los episodios completos, controles, resultados favorables/desfavorables, tablas mensuales, ALL/Q75/Q90 y4/12/24h. `BITUNIX_OFFICIAL_AUDIT.md` separa documentación vigente y estrés condicional de una liquidación histórica no demostrada.

Los12 workflows existentes se mantienen sin cambios y descubren las pruebas nuevas. Compilación/ejecución matemática no sustituye paridad externa: sigue existiendo solo un punto visual comunicado por el propietario y ninguna exportación numérica completa de la plataforma original.

**No hay trading, Telegram, servicio, flag o captura forward activos. SHADOW ONLY. TRADE AUTHORITY: NONE.**
