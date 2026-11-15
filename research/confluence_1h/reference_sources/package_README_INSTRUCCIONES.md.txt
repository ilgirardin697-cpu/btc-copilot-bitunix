# I-GOD Confluencia 1H — paquete de INVESTIGACIÓN (sin operaciones reales)

Este paquete implementa el prompt para **BTCUSDT 1H de Binance** y usa las dos fuentes que enviaste:

- `Texto pegado (2).txt`: **Koncorde 3.0 — BITMAN PROXY** (fuente en Pine 6), de donde se extrae la fórmula de `tendencia` y su `ma_trend` (EMA15). No afirmamos que sea el Konkorde original de Bitman ni que la línea principal sea la misma que has señalado visualmente hasta verificarlo en el panel de datos.
- `Texto pegado(20261115-104742).txt`: **BBWP** (Pine 6) con **SMA7**, **lookback100**, ranking respecto de los anchos de banda **anteriores**, no incluyendo la barra actual. En las capturas hay otras versiones/ajustes; deberás cotejar los valores de ambos sistemas antes de usar resultados.

## Archivos

- `I_GOD_Confluencia_v5.pine` — estrategia **Pine Script v5**, velas cerradas, LONG/SHORT, marcadores y líneas verticales en la barra de señal. Por defecto la orden de mercado se llena en la **apertura siguiente**; la posición se protege con stop a 1,5 ATR y TP a 2R (puedes seleccionar 3R). Salida temporal al cierre de la barra 24. Solo investigación.
- `igod_confluencia_backtest.py` — Python reproducible: motor OHLC explícito; 70/30 IS/OOS, walk-forward 4 ventanas **dentro del IS**, análisis de sensibilidad, métricas, comparativa de 200 muestras aleatorias, CSV de señales y operaciones; opcional cotejo de referencia con `backtesting.py` (no equivalente numéricamente).
- `test_confluencia.py` — pruebas de siguiente apertura, stop antes de TP cuando ambos se tocan, salida tras 24 velas y causalidad de señales e indicadores.

## Reglas exactas ensayadas

1. **LONG**: `tendencia` del proxy cruza sobre su EMA15, con `tendencia` previa <0. **SHORT**: cruce inverso y `tendencia` previa >0.
2. `ADX(14, suavizado 14)[1] < ADX[2]` y `ADX[2] >40` (35, 40, 45 en sensibilidad). Es intencional que **no se exija** `ADX[0] < ADX[1]` porque el prompt de Claude no lo exige. Esto es un giro detectado en vela anterior, no una garantía de cambio de dirección.
3. AO = SMA5(hl2)-SMA34(hl2), negativo y creciente en dos cierres para LONG, positivo y decreciente en dos cierres para SHORT.
4. BBWP >85, con SMA7 y lookback100 (80, 85, 90 en sensibilidad).
5. Entrada a apertura posterior; un máximo de una posición; salida SL a 1,5 ATR14 en precio real de entrada, TP a 2R/3R y timeout tras 24 barras.
6. Riesgo presupuestado 1 % del capital; **nocional limitado a 1x** por defecto (no se usa alto apalancamiento). Comisión de entrada y salida 0,1 % cada una, deslizamiento desfavorable 0,05 % cada una en el motor Python. Una brecha de precio puede generar una pérdida mayor al 1 %.

### Detalles que importa comprobar en el gráfico

- El indicador **Konkorde del archivo trae tres capas**: `pececillos`, `tendencia` y `tiburones`, con `ma_trend` roja. **Este paquete cruza `tendencia` contra `ma_trend`**, porque es la serie a la que está aplicada la EMA roja. Si por «amarilla» señalabas otra capa, **no es todavía la misma estrategia**. Revisa nombres/valores en la ventana de datos de TradingOne.
- La fuente BBWP funciona en 0–100 con comparación contra muestras anteriores. No intercambiar 7/100 con 13/252 sin revalidar: producen eventos distintos.
- Una línea vertical **NO** es una entrada en esa misma barra. La señal se reconoce al cierre y, como pronto, se ejecuta la barra posterior.

## Reproducir el backtest histórico

Python 3.10+.

```bash
python -m pip install numpy pandas requests matplotlib "backtesting>=0.6.3"
python -m unittest -v test_confluencia.py
python igod_confluencia_backtest.py --download --start 2023-01 --end 2026-10 --random-trials 200 --out resultados
```

Los datos se descargan desde **archivos públicos mensuales de Binance Spot** (`data.binance.vision`); en este entorno de ChatGPT no he podido descargar y ejecutar esos históricos, por lo que **no se proporciona rentabilidad ni tasa de acierto observada**. Si Binance rechaza descargas, usa un CSV de velas `open_time,open,high,low,close,volume`, timestamp UTC de **apertura**:

```bash
python igod_confluencia_backtest.py --csv btcusdt_1h.csv --out resultados
```

Para cotejar con un simulador independiente (requiere `backtesting.py`):

```bash
python igod_confluencia_backtest.py --csv btcusdt_1h.csv --check-backtesting
```

**Aviso**: ese cotejo opcional **no es una réplica exacta** del motor principal: ancla su SL/TP inicialmente al cierre de señal, utiliza un spread aproximado para representar deslizamiento y cierra por tiempo en la apertura siguiente. Se deben comparar tendencias generales, **no igualar operaciones ni porcentajes**. El motor principal implementa literalmente los supuestos solicitados; para ejecución real se requiere prueba con datos de tick/minuto.

## Resultados guardados

- `sensitivity_in_sample.csv`: las 18 combinaciones predefinidas de ADX, BBWP y R; nunca se selecciona con el 30 % final OOS.
- `walkforward_four_folds.csv`: 4 pruebas expansivas dentro del 70 % de desarrollo; entrenamiento anterior a validación cronológica.
- `oos_trades.csv`: cada trade, hora UTC de señal/entrada/salida, precio, motivo, resultado neto y R.
- `oos_equity.csv`: evolución por hora de cuenta simulada, empezando con 200 USDT.
- `random_baselines.csv`: controles con las mismas salidas, stops y costes, emparejando números candidatos y proporciones LONG/SHORT. **Puede diferir el número de operaciones ejecutadas por la prohibición de solapamiento**; por eso se muestra y no debe leerse el p-value como prueba formal de significación.
- `signals_all.csv`: todas las banderas y valores que puedes contrastar con tus líneas azules.
- `metadata.json`: ajustes usados, versión e hipótesis.

Si todas las reglas producen **menos de 20 operaciones in-sample**, el algoritmo **no optimiza** y conserva 40/85/2R. Esto es importante: filtros tan estrictos pueden dar muy pocos trades, aunque visualmente parezca que hay muchos giros buenos.

## ¿Existe lookahead bias o repintado?

En la **detección de señales**, se han evitado de forma deliberada:

- Se opera en el **cierre confirmado** de la vela 1H (`barstate.isconfirmed` en Pine) y en Python solo se usan datos de la barra ya cerrada.
- No hay `request.security()` con lookahead, ni offsets negativos, ni pivotes retroactivos.
- El BBWP excluye la propia vela del conjunto con el que hace la comparación.
- Se **entra en la barra siguiente** a la señal. El indicador de ADX utiliza `adx[1]` y `adx[2]` en lugar de valores futuros.
- Se someten los cálculos a una prueba de prefijo temporal: añadir velas nuevas no cambia indicadores anteriores.
- Si en la misma vela se tocaron SL y TP, **Python contabiliza el SL primero**, sin asumir que ocurrió lo favorable.

**Limitaciones que persisten**: el motor OHLC desconoce el orden intrabar; una entrada/SL de mercado puede sufrir gaps, spread real superior o fills parciales; los datos spot no incluyen funding, mark price ni liquidación del contrato de futuros. TradingView usa `slippage` en **ticks fijos**, no 0,05 % variable: `3000 ticks` = 30 USDT si el tick es 0,01 (0,05 % cuando BTC ronda 60.000); no hay paridad exacta con Python a precios distintos. La salida `immediately=true` en Pine al cierre tampoco está garantizada a ese precio real.

La comparación de histórico y gráficos debe revisarse **antes** de usar el modelo. Un alto win rate no demuestra ventaja si los costes y pérdidas superan las ganancias. No conectar Bitunix ni habilitar V8 LIVE a partir de este estudio.
