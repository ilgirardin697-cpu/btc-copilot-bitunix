# Auditoría independiente I-GOD Confluencia 1H — scripts de verificación

Reproducir (Python 3.10+, numpy, pandas, scipy):

    python audit1_parity.py   # referencia en bucle (semántica Pine) vs ZIP: RSI/MFI/Koncorde/ADX/AO/BBWP
    python audit2_struct.py   # causalidad de señales finales, cota matemática de `tendencia`, asimetría LONG/SHORT
    python audit3_funnel.py   # embudo de filtros sobre precios SIN ventaja (compáralo con el de Codex)
    python audit4_null.py     # motor del ZIP con entradas aleatorias: coste/R, win rate de equilibrio, potencia
    python audit5_indep.py    # dependencia estructural entre los 4 filtros

LÍMITES (importante):
- Todos los datos son SINTÉTICOS (GARCH con colas gruesas, sin ventaja por construcción). Sirven para probar
  propiedades de la REGLA y del MOTOR, no para estimar rentabilidad de BTC.
- No se pudo descargar BTCUSDT real ni acceder al repositorio de Codex: sus cifras NO están verificadas aquí.
- Paridad con TradingView/TradingOne NO comprobada: solo coherencia interna con una referencia escrita desde la doc de Pine.
- `igod_confluencia_backtest.py` es la copia sin modificar del ZIP original.
