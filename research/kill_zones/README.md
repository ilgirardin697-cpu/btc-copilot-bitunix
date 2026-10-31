# I-GOD — Kill Zones Asia/Londres V0

**Resultado: NO EDGE en las variantes formalizadas. No integrar ni activar alertas.**

Este resultado no demuestra ni refuta la regla exacta del vídeo: no se pudo
acceder al proyecto privado de Descript ni al mensaje de Telegram, por lo que
no se han visto los anclajes ni la traslación. El resumen por minutos procede
del propietario. **EXACT VIDEO DIAGONAL / PROJECTION PARITY: NOT PROVEN.**

## Evidencia principal
- Fuente: BTCUSDT **BINANCE_USDM_PERPETUAL**, archivos oficiales Binance Vision.
- Septiembre 2023–septiembre 2026: 324.288 velas de 5m, 27.024 velas de 1H,
  3.378 registros de funding; 74 ZIPs verificados, sin huecos ni duplicados.
- Warmup 2023; desarrollo 2024; validación 2025; evaluación enero–septiembre 2026.
- **NO VIRGIN HOLDOUT:** histórico reutilizado en otros estudios; no es forward real.
- Dos variantes de anclajes, ruptura horizontal de referencia, Nueva York con
  DST frente a UTC−4 fijo, TP completo y TP95: doce celdas, todas NO EDGE.
- Señal exclusivamente tras cierre 1H; entrada en la apertura siguiente.
  Ejecución simulada con 5m, stop primero en ambigüedad, stops y targets congelados.
- Costes por lado: 0,06 % comisión + 0,05 % slippage; stress 0,10 % slippage.
  Funding con tasas reales y precio trade como **proxy** del mark de settlement.
  No se ha verificado el fee tier de una cuenta ni el funding cashflow exacto.

Variante principal predeclarada: New York / EXTREME_TIMES / TP95.

| Métrica de evaluación | Resultado |
|---|---:|
| Operaciones | 203 (115 LONG, 88 SHORT) |
| Aciertos netos | 45,81 % |
| TP ejecutado antes del stop | 44,33 % |
| Esperanza neta | −0,293 R |
| IC95, bootstrap en bloques | [−0,456; −0,132] R |
| Profit factor normalizado en R | 0,516 |
| Profit factor monetario del paper | 0,643 |
| Retorno paper | −24,95 % |
| Drawdown MTM a cierres 5m | 26,61 % |
| MAE media, límite inferior | 0,728 R |
| MFE media, límite inferior | 0,636 R |
| Esperanza neta stress | −0,372 R |
| Excluyendo las 3 mejores operaciones | −0,340 R |

Paper: 10.000 USDT iniciales, hasta 1 % de riesgo reservado y máximo 1x de
notional, sin apalancamiento simulado. PF en R y curva en USDT usan ponderaciones
distintas; no se presenta el PF normalizado como PF monetario de una cuenta real.

La referencia horizontal TP95 también pierde: −0,112 R, PF_R 0,671.
Las diagonales no aportan una mejora defendible. La diferencia diaria pareada
es −0,146 R; su intervalo familiar corregido incluye cero. No se elige un ganador.

## Indicadores, sin recalibrar
| Filtro de la variante principal | n | Aciertos | Esperanza neta |
|---|---:|---:|---:|
| Sin filtros | 203 | 45,81 % | −0,293 R |
| AO slope alineado | 142 | 51,41 % | −0,203 R |
| ADX rising + DMI alineado | 69 | 59,42 % | −0,092 R |
| Konkorde proxy | 114 | 55,26 % | −0,140 R |
| AO + ADX/DMI + Konkorde proxy | 50 | 60,00 % | −0,099 R |

ADX mide fuerza; DMI aporta la dirección. Mejorar el porcentaje de acierto no
basta para obtener una esperanza neta positiva. Las fórmulas congeladas no cambiaron.
ML RSI confirmado real: **sin overlap en este corte**; el journal disponible
es de octubre de 2026. No se reconstruyeron eventos ni se sustituyeron por RSI.
EXACT BITMAN KONKORDE PARITY: NOT PROVEN.

## Addendum TP conservador solicitado después
Los cuatro offsets se fijaron antes de sus cálculos, pero después de conocer el
estudio original: **POST-HOC, sin holdout independiente**. Mismas particiones,
stops, costes, entrada y simulador; no cambian los doce resultados originales.

| Offset desde TP geométrico | n evaluación | Esperanza neta | Resultado |
|---|---:|---:|---|
| 0,10 ATR14 confirmado | 203 | −0,287 R | NO EDGE |
| 0,25 ATR14 confirmado | 202 | −0,274 R | NO EDGE |
| 5 bps del cierre de confirmación | 203 | −0,279 R | NO EDGE |
| 10 bps del cierre de confirmación | 202 | −0,272 R | NO EDGE |

LONG resta el offset; SHORT lo suma. Si el target ya no queda al lado correcto
de la entrada real simulada, se descarta. No se fuerza señal diaria.
No se ha creado emisor, payload operativo, bot ni scheduler Telegram.
El posible formato informativo futuro queda descrito, condicionado a evidencia
robusta y a otro protocolo/revisión; **actualmente no se cumple esa condición**.

## Archivos consultables
- [Informe completo y tablas de las doce celdas](artifacts/KILL_ZONES_RESEARCH_V0.md)
- [Addendum de offsets y resultados fuera de la fase de desarrollo](artifacts/TP_OFFSET_ADDENDUM.md)
- [Manifiesto público y checksums](artifacts/data_manifest.json)
- [Todas las operaciones, incluidas pérdidas](artifacts/trades.csv)
- [Protocolo fijado antes de outcomes](specification.md)
- [Protocolo separado de offsets](tp_offset_addendum_specification.md)
- [Pruebas, aislamiento y trazabilidad](VERIFICATION.md)

Los gráficos muestran el primer ganador y perdedor de evaluación LONG y SHORT
por orden cronológico. No se usaron para calibrar:
[LONG ganador](artifacts/figures/long_winner.png),
[LONG perdedor](artifacts/figures/long_loser.png),
[SHORT ganador](artifacts/figures/short_winner.png),
[SHORT perdedor](artifacts/figures/short_loser.png).

## Reproducir
Usar Python 3.13 para el entorno numérico/gráficos registrado; las regresiones
productivas usan Python 3.12 como sus baselines AST y workflows existentes.

```text
python -m pip install -r research/kill_zones/requirements.txt
python -m research.kill_zones.data --download --cache research/cache/kill_zones_public
python -m research.kill_zones.study run --cache research/cache/kill_zones_public
python -m research.kill_zones.tp_offsets run --cache research/cache/kill_zones_public
python -m unittest discover -s research/kill_zones -t . -v
```

Los locks publicados deben verificarse; no refreezarlos para encajar otro resultado.
El cache de datos queda gitignored. Producción no importa este laboratorio.
No cambios en Guardian V2, V8, ML RSI, operativa actual, mercado privado, protocolos
semanales, Railway ni Telegram. Ninguna orden ni acceso a credenciales.

**PAPER / SHADOW ONLY. TRADE AUTHORITY: NONE.**
