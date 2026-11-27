# I-GOD Sequential Market Shadow V0

Motor experimental de secuencias y simulación automática local. **No despliegue,
no captura continua, no ejecución real.** [Informe](out/REPORT.md).

La declaración previa al replay está en [SPEC](../sequential_market/SPEC.md)
y spec.json, commit daa8673. [Addendum](sources.json), commit19a2f57, registra el
segundo documento recibido antes de los resultados. No cambia gates de emisión.
Esto no modifica BITMAN_WEEKLY_FORWARD_V1 ni los protocolos TURN22/TURN11.

## Ejecutar

Desde la raíz de este worktree, Python3.12 + NumPy:

```powershell
$mod = 'research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.forward_shadow.turn_latency.tradingone_v2.seq'
python -B -m unittest "${mod}.test_seq" -v
python -B -m "${mod}.run" --out resultado_nuevo
```

Los inputs públicos y recibos están en d/. No descarga red. El destino debe ser
nuevo; no se sobreescribe un replay anterior. Un input incorrecto/gap/hash diferente
detiene el cálculo. Se conservan todos los WATCH, invalidados, expirados, rechazados,
fills simulados y cierres. El ledger encadena hashes; no es un journal forward.
El último estado abierto queda censurado, nunca se inventa un fill de fin de datos.

## Arquitectura y reglas

- maths reutiliza fórmulas auditadas: AO5/34, ADX14/14, Koncorde completo,
  BBWP13/252/SMA5 y TSA119/2.8. No usa el ML RSI operativo.
- Frame confirma fractales2+2 al cierre de la segunda vela derecha. Los niveles
  se usan desde su disponibilidad, nunca desde el extremo retrospectivo.
  Retest requiere una vela posterior; falsas rupturas registran extensión/ATR.
- Engine conserva memoria independiente LONG/SHORT, prealerta de desaceleración,
  giro, confirmación estructural, invalidación, caducidad y agotamiento.
  BBWP/ADX y marcos superiores son descriptivos, no una dirección automática.
  El arco Fred no tiene definición suficiente: NO se fabrica un detector.
- Paper solo produce registros locales: entrada siguiente15m, costes, stop,
  parcial, BE neto, trailing y salida temporal. Sin promediar ni apalancar;
  exposure() analiza lotes hipotéticos y pérdidas previas sin cambiar nada.
- run une2W/1W/1D/4H/1H/15m por disponibilidad y ejecuta replay. Las series
  futuras pueden estar precalculadas con fórmulas causales, pero at() nunca las
  entrega antes del cierre; tests de prefijo comprueban esta propiedad.
- El bloque de RSI reconstruye el original LOW27/ALMA4 solo para diagnóstico
  de5/22Nov, con origen de historial declarado. No participa en el detector.
  No certifica el RSI privado, los precios o el contrato de Bitman.

El TSA es el perfil del JSON del propietario, NO los ajustes117/2.8/150/100 de
Hermi ni la línea privada de Bitman. La convención2W de este prototipo tampoco
está certificada; BBWP2W completo no está disponible con240 velas y queda nulo.

## Seguridad y costes

Comisión .1% por fill, slippage adverso .05% por fill: hipótesis conservadoras
reutilizadas, no tarifa de una cuenta. Riesgo modelado .5%, cap1x, límite simulado
de drawdown5% marcado a cierres/aperturas; se enclava hasta terminar el replay.
No es garantía de pérdida máxima: gaps y deslizamiento pueden superar el stop.
No se ofrecen estimaciones de liquidación con datos Spot.

Funding Spot: NOT_APPLICABLE. Los SHORTs son aritmética direccional sintética
colateralizada; faltan préstamo y contrato/funding/mark de futuros. El motor
rechaza modo futuros antes de simular para no fingir costes cero.

Ejecución real no existe en el módulo. No lee variables, claves, posiciones,
Railway o Telegram. V8_LIVE_EXECUTION=false es una aserción del entorno SHADOW
local, no una lectura independiente de producción. Ningún servicio se inicia.

Los55 tests incluyen causalidad, reinicio por replay/deepcopy, invariancia de
prefijo, ledger, stops, gaps, parcial, BE, SHORT, costes, drawdown acumulado y
aislamiento. Las suites existentes verifican900 estados y los hashes protegidos.
Las guardas estáticas no sustituyen un sandbox frente a código adversarial.

## Evidencia y validación pendiente

evidence.json separa fuente derivada, enseñanzas verbales e hipótesis propias.
Los originales locales se identifican por SHA256 sin publicar sus secciones de
cuenta. No hay capturas/fills primarios ni certificación TradingOne completa.
La captura pública es retrospectiva, con corte09UTC24Nov y recibos reales;
available_at es disponibilidad modelada de mercado, no hora de emisión real.

No se optimiza con este resultado ni se inicia otro backtest masivo. PR55 sigue
NO EDGE, PR50 NO TESTABLE y PR57 mantiene limitaciones de paridad externa.
Revisión independiente del código y un sucesor congelado son prerrequisitos
para una evaluación independiente posterior. La automatización técnica de una
simulación no demuestra esperanza positiva ni autoriza entradas.

SHADOW ONLY. TRADE AUTHORITY: NONE.
