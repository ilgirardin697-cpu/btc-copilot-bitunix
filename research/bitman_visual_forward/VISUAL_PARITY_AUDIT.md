# Bitman: auditoría visual y matemática

SHADOW ONLY. TRADE AUTHORITY: NONE. **PARIDAD VISUAL REAL: PENDIENTE.**

## Evidencia y límites
La referencia disponible es la descripción del propietario de una captura de
TradingView, no un CSV ni una lectura de píxeles por este agente. Se identifica
1H, AO y una línea ADX. BTCUSDT · BINANCE no confirma el ticker completo ni
el contrato: BINANCE:BTCUSDT es una posibilidad no verificada. No convertir
esa posibilidad en Spot confirmado ni en USD-M confirmado.

El intervalo visible aproximado es 13–21 octubre 2026; marcas amarillas cerca
del 15 y 17–18 y azul cerca del 19. Se conservan como fechas aproximadas del
gráfico, sin convertirlas a UTC. Faltan zona horaria, timestamps exactos de
los cierres, ticker completo, venue, autor/versión/parámetros y exportaciones.
No se asignan los círculos a velas inventadas.

Es un ejemplo visual seleccionado POST-HOC. Aunque octubre quede fuera del
dataset de PR33 (termina 2026-09-01), su selección posterior no lo convierte
en holdout independiente ni evidencia prospectiva.

## Matemática conocida
AO público: SMA5((H+L)/2) − SMA34((H+L)/2); color por cambio de AO.
GREEN significa pendiente positiva, no necesariamente AO>0; RED no significa
necesariamente AO<0. La referencia pública describe el Saucer como dos barras
correctivas y una recuperación en el mismo lado de cero.
[TradingView AO](https://www.tradingview.com/support/solutions/43000501826-awesome-oscillator-ao/).

ADX mide fuerza; +DI/−DI aportan dirección. El color rojo de su trazo no determina
el lado. La pendiente de ADX es una diferencia de sus valores, no de AO.
[TradingView DMI](https://www.tradingview.com/support/solutions/43000502250-directional-movement-dmi/).

Nuestra definición congelada usa TR con H−L en la primera barra, RMA14 sembrada
con media simple de 14 valores finitos, primer DM desconocido, DI normalizado por
ATR, DX=0 para suma DI finita e igual a0, y otra RMA14 para ADX. Esta inicialización
puede diferir de un built-in o script con otra semilla. No afirmar igualdad con
ta.dmi solo por compartir longitud 14. Exportamos ambas series para medir diferencias.
ADX 14/14 y AO 5/34 son parámetros de nuestra referencia, NO valores confirmados
de la captura. No se modifican para ajustar curvas.

FE conserva una sola fórmula de PR33: gamma13 de rango recorrido/rango extremo.
No es ADX, no da dirección y no está probada su paridad con Bitman.
EXACT BITMAN INDICATOR PARITY: NOT PROVEN.
EXACT BITMAN FE PARITY: NOT PROVEN.

## Qué se evaluó realmente en PR33
| Interpretación visual | Regla evaluada / diferencia |
|---|---|
| AO recupera tras corrección | A exige dos pendientes correctivas y recuperación, con tres AO del mismo signo |
| Línea ADX gira | Solo AO_DMI añadía ADX slope>0 y slope anterior<=0, más DI alineado |
| Candidatos priorizados ahora | AO_CONTEXT y AO_FE NO exigen giro ADX ni DI alineado |
| Contexto de gráfico 1H | El filtro A también exige AO4H/1D alineados y recuperar extremo previo3 barras |
| Entrada dibujada en el círculo | PR33 entra a la apertura posterior, con costes y stop previo6 barras ±0.25 ATR |
| Ejemplos visuales favorables | PR33 conserva perdedores, controles, costes e incertidumbre |
| Posible Spot de la captura | Research usa BINANCE_USDM_PERPETUAL; no se equiparan datasets |

Por tanto PR33 NO prueba que esos círculos se reproduzcan ni valida la combinación
visual del propietario. La selección actual de dos candidatos está informada por
sus resultados y se etiqueta POST-HOC.

## Comparador reproducible
1. Confirmar ticker/venue y parámetros, conservar captura y configuración originales.
2. En TradingView 1H, cargar historia suficiente y añadir pine/visual_export_v0.pine.
   Es un exportador de referencia pública, no el indicador original. Su compilación
   y ejecución reales en TradingView aún NO han sido verificadas por este PR.
3. Exportar los datos del gráfico y plots. Cargar la historia hasta la primera barra
   realmente usada por Pine: SEED_START_MS debe coincidir con la primera fila.
   No recortar errores de warmup hasta que encajen.
4. Conservar el CSV RAW local-only/gitignored, calcular SHA256 y completar una copia
   de export_metadata.template.json. Mapear cabeceras explícitamente, sin adivinarlas.
   exported_at_ms debe ser el instante real; OPEN_MS/CLOSE_MS son Unix ms.
5. Ejecutar:
   python -m research.bitman_visual_forward.compare --csv research/cache/reference.csv --metadata research/cache/reference.json --output research/cache/parity.json

[Exportación oficial](https://www.tradingview.com/support/solutions/43000537255-how-to-export-chart-data/).
Se comparan valores, disponibilidad NaN, errores máximos/medianos y signos;
tolerancias fijas abs1e-8/rel1e-9, sin búsqueda de offset, reescalado ni parámetros.
Se excluyen velas marcadas abiertas; una fila confirmada futura, gaps, duplicados,
semilla ausente o timestamps incoherentes hacen fallar la auditoría.
CLOSE_MS es disponibilidad exclusiva; Binance closeTime es 1ms anterior.

FROZEN_DEFINITION_V0 contrasta el exportador identificado por hash con nuestro
cálculo sobre los mismos OHLC. El perfil TV_BUILTINS_OR_ORIGINAL admite AO/ADX
originales como diagnóstico, sin asumir inputs o inicialización idénticos.
Comparar OHLC contra research USD-M requiere ticker perpetuo confirmado y venue
atestiguada; Spot/UNKNOWN no se normalizan a USD-M.

Los tests sintéticos solo verifican el mecanismo. Nunca cuentan como exportación
independiente. Incluso una igualdad numérica del exportador NO demuestra paridad
con la captura ni con indicadores privados. No se han recuperado valores reales
de TradingView en esta tarea.

## Estado de referencia faltante
- CSV completo con OHLC, AO, ADX y sus cierres/flags confirmados.
- Configuración exacta de los indicadores originales y origen de sus datos.
- Semilla/historia cargada, ticker completo y contrato.
- Zona horaria y cierres UTC exactos de las cuatro marcas.
- Compilación/ejecución manual verificada del exportador y hash de su fuente.

Hasta entonces: PENDING_ACTUAL_TRADINGVIEW_EXPORT_AND_CONFIGURATION.
No hay una coincidencia visual medida que podamos declarar.
