# BITMAN — VALIDACIÓN VISUAL Y FORWARD RESEARCH

**Decisión: NO-GO para pasar ahora a construcción de un observer.**
**GO limitado a recopilar exportaciones y validar offline.**
SHADOW ONLY. TRADE AUTHORITY: NONE. Sin runtime, merge ni deploy.

## 1. Estado autoritativo preservado
Base de este PR: fc211d8e36c6db55185efa8309eb8f980beab2ea, PR32 mergeado.
Guardian no recibe cambios y no se intenta sortear la incidencia Railway.
PR33 permanece DRAFT en f71947224d4afc8f97ed72b34d8fe15be2770167.
Sus 35 comparaciones siguen 28 NO EDGE, 7 INCONCLUSIVE, 0 PROMISING.
No se reevalúan retornos ni parámetros; solo se extraen estadísticas publicadas
mediante git show del commit fijo. PR30/31 y el protocolo semanal V1 no cambian.

## 2. Qué sabemos del ejemplo visual
El propietario identifica TradingView 1H, AO y una línea ADX. Símbolo visible
BTCUSDT · BINANCE; contrato y ticker completo no confirmados. Las fechas
13–21 octubre 2026 y las marcas 15/17–18/19 son aproximadas del gráfico, no UTC.
Los dos círculos de 17–18 no se asignan artificialmente uno a cada día.

Faltan CSV, configuración/autor/versión/inputs, timezone y cierres exactos.
No se dispone de una lectura independiente de la captura ni ejecución Pine real.
**PENDING_ACTUAL_TRADINGVIEW_EXPORT_AND_CONFIGURATION.**
El ejemplo sigue siendo POST-HOC y no es prueba de rentabilidad.

## 3. Resultado de la auditoría matemática
AO público 5/34 sobre HL2 y el Saucer coinciden conceptualmente con la familia A;
eso no demuestra que la captura use esos inputs.
ADX es fuerza, no dirección. DMI+/− es una serie distinta. Rojo no significa SHORT.
La matemática congelada tiene semillas explícitas; la equivalencia numérica con
un ADX built-in 14/14 depende también de historia e inicialización.
No hay ajuste de parámetros, offset temporal, reescalado o tolerancias tras ver
resultados. EXACT BITMAN INDICATOR PARITY: NOT PROVEN.

El comparador incluye definición congelada y built-in Pine como diagnósticos
separados. Pruebas sintéticas verifican Python, no prueban que Pine compiló ni que
los valores originales TradingView coinciden. Véase VISUAL_PARITY_AUDIT.md.

## 4. Diferencia crítica con la hipótesis visual
La familia A busca recuperación AO en el mismo lado de cero tras dos barras
correctivas. AO_CONTEXT añade 4H/1D y recuperación de estructura 3 barras.
AO_FE añade FE descendente. **Ninguno de estos dos candidatos exige giro ADX.**
El filtro ADX/DMI de PR33 era otra variante (AO_DMI), no la seleccionada aquí.
Forward registraría giro ADX y DMI como cuatro estratos descriptivos fijos,
sin convertirlos en un nuevo filtro ni seleccionar después el más favorable.

## 5. Candidatos y frecuencia — SELECCIÓN POST-HOC
Todos usan A y STRUCTURE_2R, LONG/SHORT simétricos.
Datos copiados del intervalo reutilizado 2024-01-01→2026-09-01:32 meses calendario.

| Candidato | n | LONG/SHORT | Media neta R | IC95 | Eventos/año calendario | Meses para 100 al mismo ritmo |
|---|---:|---|---:|---|---:|---:|
| AO_ONLY referencia | 351 | 177/174 | -0.0876 | [-0.2439,0.0635] | 131.6 | 9.1 |
| AO_CONTEXT | 52 | 27/25 | 0.1895 | [-0.2065,0.5258] | 19.5 | 61.5 |
| AO_FE | 35 | 20/15 | 0.3262 | [-0.2195,0.7745] | 13.1 | 91.4 |

| Candidato | 2024 completo | 2025 completo | 2026 ene–ago |
|---|---:|---:|---:|
| AO_ONLY | 135 | 127 | 89 |
| AO_CONTEXT | 22 | 13 | 17 |
| AO_FE | 18 | 7 | 10 |

No anualizar la fila 2026 como si fuera un año completo. La tasa promedio usa 32
meses calendario, no la exposición entre primer/último trade de PR33.
No es una promesa de frecuencia futura: cambia régimen, actividad, completitud
y el modelo de disponibilidad/entrada. CONTEXT pierde 299 de 351 oportunidades,
y FE 17 adicionales de 52; mayor media puntual no prueba valor incremental.

En 12 meses cabría esperar aproximadamente 20 y 13 eventos si el ritmo se repitiera.
Por lado sería aún menos. Esperar 100 eventos podría llevar 5.1 y 7.6 años; 100 por
lado bastante más. No hay un N mágico que valide edge. Como ilustración IID de
precisión de una proporción, n=100 aún supone hasta ±9.8 puntos porcentuales al 95%;
dependencia temporal, selección POST-HOC y R asimétrico empeoran esa simplificación.
Se publicarán denominadores y cobertura, sin inflar n con cada barra o variantes.

## 6. Diseño prospectivo
FORWARD_PROTOCOL.md fija los tres candidatos, fuente USD-M, warmup sin señales
históricas forward, clocks, etiquetas de datos ausentes, planes de entrada
precomprometidos, riesgo estructural 0.5–4ATR / target 2R / 48h y costes 12/21/30 bp
nominales de ida/vuelta. Los parámetros técnicos originales no se retocan.

La entrada prospectiva paper sería la primera apertura 5m después de observed_at,
con plan persistido antes. Es una adaptación causal explícita: no simula conocer
la apertura 1H que ya pasó al detectar el cierre. El fill ideal de PR33 se separa
como contrafactual. Latencia y recovery se registran, no se ocultan.

Se registran todos los anchors AO, filtros fallidos, stops invalidados y resultados
desfavorables, más referencias calendario lunes/jueves fijadas antes de los datos.
No se usan futuros timestamps del mismo mes como señales de control ficticias.
Los outcomes se maduran a 48h; funding desconocido deja neto UNKNOWN.
Censura y posteriores correcciones son nuevos registros, nunca edición histórica.

## 7. Integridad y aislamiento
Contratos puros y fixtures cubren prefijos/futuro, cierres 1H y contexto 4H/1D,
paridad con funciones exactas de PR33, dedupe, conflictos, orden y hash-chain.
Un checkpoint independiente detecta truncación del sufijo; una hash-chain sola
no autentica a un escritor que pueda rehacerla completa.
No se implementa writer físico, fsync, locks, procesos, red ni scheduler.
Las pruebas en memoria no prueban durabilidad en Railway.

Guardas verifican que producción no importe este research y que archivos
productivos, fórmulas congeladas y protocolo semanal sigan intactos.
Los 900 casos de operabilidad y audits existentes se ejecutan sin modificar sus
baselines. No hay integración con ejecución, Telegram o permisos de trading.

## 8. Recomendación y bloqueos
**NO-GO para construir ahora el observer propuesto.**
Faltan:
1. Referencia exportada/configuración verificable y ejecución Pine real.
2. Contrato autorizado USD-M 5m/funding: el gateway existente solo entrega1H.
3. Revisión independiente de la adaptación de disponibilidad/entrada paper.
4. Diseño y pruebas de durabilidad/recovery del writer futuro.

Ningún bloqueo se resuelve en este PR mediante producción, infraestructura,
proxy, Spot, nuevos endpoints o cambio de reglas. Se entrega el comparador y
el protocolo para revisión. Recoger mejor evidencia es razonable; prometer
entradas rentables o activar algo no lo es.

## Fuentes y archivos
- [AO oficial](https://www.tradingview.com/support/solutions/43000501826-awesome-oscillator-ao/)
- [ADX/DMI oficial](https://www.tradingview.com/support/solutions/43000502250-directional-movement-dmi/)
- [Exportación oficial](https://www.tradingview.com/support/solutions/43000537255-how-to-export-chart-data/)
- [Pine execution](https://www.tradingview.com/pine-script-docs/language/execution-model/)
- artifacts/pr33_reference_summary.json conserva los SHA256 originales.
- capture_reference.json conserva lo conocido y lo desconocido de la captura.

NO MERGE. NO DEPLOY. NO RAILWAY. NO TELEGRAM.
SHADOW ONLY. TRADE AUTHORITY: NONE.
