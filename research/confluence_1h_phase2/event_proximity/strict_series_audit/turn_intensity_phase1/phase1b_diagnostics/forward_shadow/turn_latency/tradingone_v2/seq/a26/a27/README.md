# Auditoría Bitman · 27/11/2026 · PR58

**SHADOW ONLY · TRADE AUTHORITY NONE.** Revisión estática y matemática offline. APK, DEX y JavaScript no instalados ni ejecutados. No nuevas señales, servicios, backtests de rentabilidad, optimización o cambios productivos. Divergence Intelligence excluido.

## Resultado principal

La observación del APK sobre los percentiles es consistente con el control de flujo del Pine aportado **y ya estaba contemplada en I-GOD**. No corresponde sustituir los umbrales por medias K-means convergidas. Sí existen diferencias de parámetros, arranque, fuente y ranking de volatilidad que impiden intercambiar las pantallas sin más.

La comparación controlada reutiliza 1.846 velas Spot H1 cerradas, abiertas desde 10/09/2026 09:00 UTC, disponibles hasta 26/11/2026 07:00 UTC, y 611 velas 4H del mismo archivo auditado. No se descargan datos nuevos. No es la fuente por defecto del APK: el código de éste carga futuros Bitget/Bitunix, hasta cinco páginas de 200 velas, y permite cambios persistidos en localStorage. Desconocemos los ajustes efectivos de una instalación concreta. No equiparamos Spot, USD-M y Bitunix.

| Perfil comparado, mismo LOW/histórico/ancla | RSI del último cierre | p25 | p75 | Medias Lloyd baja/alta (alternativa diagnóstica) |
|---|---:|---:|---:|---:|
| TXT/APK por defecto: LOW27 SMA4 | 57,182528 | 42,408999 | 53,070583 | 38,057008 / 63,812793 |
| TradingOne activo: LOW27 ALMA4, sigma1, offset0 | 57,296858 | 42,396164 | 53,108396 | 38,007321 / 63,600857 |
| Parámetros operativos: LOW29 EMA4 | 55,873342 | 42,805527 | 52,745427 | 38,836397 / 63,967738 |

Estos valores son cálculos locales sobre la misma muestra, **no lecturas independientes de TradingView, TradingOne o del APK**. Frente al replay literal existente, error máximo <=2,85e-14 en valor/umbrales ALMA; <=1,43e-14 EMA. Test adicional contra `mlrsi_math.CausalSeries` operativo en 200 velas con iguales parámetros/ancla: tolerancia 1e-10. No se importa esta investigación desde producción.

## 1. ML RSI: lo que se ha comprobado

En el original auditado de BackQuant y en el TXT, `array.new_float(3)` crea tres posiciones NA; no equivale a un array vacío con capacidad tres. Las distancias se añaden después. Sus índices ya no son 0/1/2 para las distancias finitas. Los nuevos centroides también empiezan con tres NA; la comparación ignora desigualdades con NA en condiciones y el `break` precede a la asignación. La ejecución durante el arranque establece el estado persistente de seis posiciones. Al sobrescribir las primeras tres con p25/p50/p75, los umbrales visibles retienen esos percentiles **recalculados sobre el conjunto acumulado**, no tres constantes fijadas para siempre al inicio. El nombre K-means por sí solo no describe la salida observable.

La semántica NA de [Pine v6](https://www.tradingview.com/pine-script-docs/language/type-system/) y el valor inicial de [arrays](https://www.tradingview.com/pine-script-docs/language/arrays/) respaldan esta lectura estática. El texto dentro del APK afirma una comprobación con etiquetas de TradingView: se registra como afirmación del adaptador; no hemos recibido sus registros originales ni la certificamos de forma independiente. [Página original BackQuant](https://www.tradingview.com/script/DKa7Dmc5-Machine-Learning-RSI-BackQuant/): referencia pública; no prueba de paridad de una configuración privada posterior.

Diferencias concretas:

- El APK por defecto usa percentiles, y deja `thresholdMethod='kmeans'` como alternativa explícita. No ejecutar ni seleccionar esa alternativa para mejorar resultados.
- El APK sólo acumula valores finitos y espera cuatro. El Pine literal también conserva NA iniciales y su prueba de tamaño ya puede cumplirse al aparecer el primer RSI válido. En la muestra hay **tres velas de diferencia de disponibilidad inicial**, aunque los umbrales comunes posteriores coinciden matemáticamente en este diagnóstico. Una señal temprana podría diferir.
- `maxData=3000` aplica al ancla de carga y admite hasta 3.001 índices; el array del Pine no expulsa muestras cuando llegan nuevas velas en directo. El APK recalcula el inicio a partir de la longitud recibida. Recarga, paginación o prefijo distinto pueden cambiar resultados. Mismo símbolo y timeframe no bastan.
- APK RSI: pérdida media cero devuelve100, incluso ventana completamente plana; nuestro literal deja indeterminado gain+loss=0. Es una diferencia de borde documentada, no una razón para modificar el motor operativo.
- Color TXT: `>=` superior y `<=` inferior; BackQuant/TradingOne y función ML del APK: `>`/`<`. Una igualdad puede colorearse sin producir cruce. Suite APK además redondea comparaciones a nueve decimales.
- El cruce usa RSI y umbral de la vela previa y actual. Puede aparecer al moverse el umbral aunque RSI esté plano. No confundir CROSS con RESUME del observador operativo.
- Rango de umbrales y performance memory están declarados pero no alteran la salida de este recorrido original. No les atribuimos aprendizaje que el código no realiza.

## 2. Fractal Energy de Loren

La definición verificable es **CHOP27 suavizado HMA5**, no una FE privada certificada:

`TR=max(H-L,abs(H-Cprev),abs(L-Cprev))`, primera vela `H-L`.

`CHOP=100*log10(sum(TR,27)/(highest(H,27)-lowest(L,27)))/log10(27)`.

El TXT sustituye rango cero por1. `FE=HMA5(CHOP)=WMA2(2*WMA2(CHOP)-WMA5(CHOP))`, según la convención entera auditada; pendiente estrictamente negativa; FE>38,2; máximo incluyendo actual y seis anteriores >=50; cruce ML; cooldown compartido `bar_index-last_signal_bar>10`. Un candidato rechazado no consume cooldown. Una aceptación impide la dirección contraria durante diez velas: la siguiente elegible es +11. HMA puede sobrepasar los extremos de CHOP; no se recorta a0–100. Rango/TR cero puede dar log indefinido: no inventar valor.

El filtro TS por defecto es **Ninguno**. Las opciones son media actual, superior o ambas. No añadir filtros obligatorios. El CHOP genérico del APK tiene otros defaults, arranca una vela después y no implementa HMA en su selector de suavizado: **no es equivalente a FE27/HMA5 del TXT**.

| Mismo conjunto H1; conteos descriptivos, no operaciones | Cruces UP / DOWN | ML aislado, cooldown compartido | ML + FE, cooldown compartido |
|---|---:|---:|---:|
| LOW27 SMA4 | 26 / 43 | 53 | 33 |
| LOW27 ALMA4 | 26 / 42 | 55 | 32 |
| LOW29 EMA4 | 26 / 43 | 54 | 32 |

Los cooldowns se aplican independientemente a cada alternativa; el subconjunto final no se interpreta como muestras emparejadas idénticas. `fe_gate_counts.csv` conserva **todos** los cruces, incluso descartes y motivos booleanos. FE reduce candidatos; **no sabemos todavía si añade valor predictivo neto**. No hemos calculado PnL ni seleccionado parámetros por sus resultados. La futura prueba incremental deberá mantener mismas fuentes, arranque, entrada posterior, costes y línea base inclusiva; fijarse antes de examinar outcomes y reconocer todo este histórico como exploratorio. No se activa un colector nuevo.

## 3. Trend Speed y rechazos

Se contrastaron `calc_trend_speed` del TXT, `advanceTrendMean` del APK y el original Zeiierman conservado en `tradingone_v2/sources/tsa.pine` (su hash anterior permanece intacto):

`M=highest(abs(C),200)`; `N=5+((C+M)/(2M))*(max_length-5)`.

`delta=abs(C-nz(Cprev))`; `A=delta/highest(delta,200)`, divisor cero→1.

`alpha=min(1,2/(N+1)*(1+A*accel))`; `mean=alpha*C+(1-alpha)*mean_prev`, semilla primer close.

Los tres implementan la misma recurrencia de **media de precio** con iguales parámetros/prefijo. No equivale a haber certificado también el histograma de velocidad, tabla de ondas o filtros MTF completos. TXT118/2,8; TradingOne activo119/2,8; Suite APK default117/2,7, aunque admite parámetros. Dos implementaciones Python de la recurrencia dan igualdad exacta en1.846 H1 y611 4H. Cambiar118→119 desplaza la media hasta28,895715 unidades de precio H1 y51,304855 en4H en esta muestra; no es un fallo de redondeo.

Se registran contactos/rechazos **con una definición propia explícita**, sin atribuirla a Bitman: mecha toca la media actual pero apertura y cierre permanecen estrictamente del mismo lado. H1:59 hacia arriba/62 hacia abajo;4H:13/12. CSV conserva hora de disponibilidad y media. No hay resultados posteriores ni afirmación de eficacia, ni uso de una 4H incompleta para confirmar1H. Esta definición descriptiva no decide entrada, stop ni señal confirmada.

## 4. Konkorde y BBWP

| Componente | Correspondencia estática | Diferencias / límite |
|---|---|---|
| APK `verde` | `pececillos=tendencia+oscPVI` | Un área amarillenta no identifica por sí sola una serie. |
| APK `marron` | `tendencia=(RSI(OHLC4)+MFI(HLC3)+BollOsc(OHLC4)+Stoch/3)/2` | Mismos defaults14/25/21/3 yEMA15; verificar prefijo y división por cero. |
| APK `azul` | `tiburones=oscNVI` | PVI/NVI semilla100 vs1: factor cancela en ratio homogéneo si resto idéntico. |
| APK `media` | EMA15 de **tendencia**, no EMA15 de pececillos | Diferencias de semilla EMA/NA cambian arranque. |
| MFI APK | Retorno50 cuando flujo negativo cero | Pine público no impone ese50; no asumir equivalencia en ese borde. PVI/NVI/Boll/Stoch APK fuerzan0 en denominador cero; Pine puede quedarNA. |
| APK `bbwp`/`bbwpLine` genéricos | CLOSE SMA13/252, señalSMA5 | Ranking incluye actual, factor ancho4 vs2, primer valor una vela antes; no es el ranking literal de TradingOne. |
| APK `suiteBbwp` | Ancho2, ranking contra historia anterior, rightmost/ties antes de insertar | Diseño estático coincide con Pine auditado, distinto del BBWP genérico del propio APK. No certificar por compartir nombre. |

BBWP genérico vs literal TradingOne:1.832 pares,929 difieren>1e-9; diferencia media0,297791 puntos y máxima33,333333 incluyendo arranque. Dos diferencias de disponibilidad. El factor constante de ancho no cambia por sí solo el ranking; lo cambian pertenencia de ventana, momento de inserción y empates. Ninguna de estas cifras proviene de ejecutar el APK. La volatilidad no aporta dirección por sí misma. Tampoco convierte BBWP proxy>50 en confirmación oficial Bitman.

En la Suite del APK, **el color ADX procede de cruces RSI14 con su SMA20**, con ésta dentro de30–70; no representa directamente un giro de pendiente ADX ni dirección DMI. El valor ADX y el color se calculan en rutas distintas. AO bruto sigue5/34, pero `aoPlot` se reescala con el máximo absoluto de las últimas300 observaciones del conjunto cargado. Al añadir datos puede cambiar la altura dibujada de barras pasadas: es reescalado visual, no una nueva confirmación causal. Nunca usar esa altura retrospectivamente normalizada como variable de señal. No inferimos un ángulo matemático a partir del panel. La Suite vuelve a construir ML con sus propios parámetros y no garantiza heredar los ajustes del panel ML independiente.

## 5. Causalidad, repaint y paridad pendiente

El TXT carece de guard `barstate.isconfirmed` alrededor de sus alertas. `request.security` usa `lookahead_off`, pero sin desplazar la expresión a una vela HTF ya cerrada: en directo puede leer4H en formación. `gaps_on` limpia el dibujo, no certifica datos finales. La documentación de [repainting](https://www.tradingview.com/pine-script-docs/concepts/repainting/) distingue estos casos.

El APK etiqueta velas como `closed`, pero su worker pasa todas al cálculo ML/BBWP/Konkorde y esas funciones no filtran ese campo. Presentar una última fila no equivale a una señal cerrada. Su descarga incluye normalmente la vela en formación; el resumen sí busca una cerrada en otra ruta. No se puede extrapolar esa precaución a todas las series/paneles. Sin ejecución no afirmamos qué alertas reales muestra una instalación.

**Pendiente para certificación externa:** exportación numérica emparejada de LOW/RSI/umbrales/FE/TS/series Konkorde/BBWP, ticker y venue exactos, OHLCV, prefijo íntegro y primer índice, ancla de carga, ajustes efectivos, estados provisional/cerrado y timestamps. No se proporcionaron con estos archivos. La coincidencia visual anterior pececillos−40,40 sigue siendo evidencia puntual, no certificación completa. No se inventa paridad privada Bitman.

El enlace LUPA4.4 aportado no pudo recuperarse mediante la herramienta web. No se atribuye su fórmula, configuración ni licencia al TXT o al APK. No se consumieron créditos vidIQ.

## 6. Fuentes, licencias y consolidación

`source_inventory.json` conserva SHA256, tamaños, funciones y líneas de los archivos auditados; originales extraídos sólo en caché local ignorada. Se inspeccionó ZIP, no se instaló ni ejecutó APK/DEX/JS. Firma de archivo `META-INF` no autentica por sí sola la autoría. APK SHA256:`25bf86bed8b30d1f15c6af1c7f719d7f17afac4fdd29bff46319603801d3bce3`; TXT:`4b3f867a85b3ab402b6f42b18afb7b94be9358e2f08220a7b400e91c2b97bff9`.

Las cabeceras del APK atribuyen ML RSI/BBWP aMPL2.0 y Trend Speed aCC BY-NC-SA4.0. El original Zeiierman local también conservaCC BY-NC-SA4.0. El TXT no aporta una licencia explícita general; no se ha demostrado permiso sobre todo el APK/Konkorde ni que LUPA comparta licencia. No se redistribuyen esos archivos completos ni se copia su código a producción. Se reutilizan los ports públicos auditados con sus avisos, referencias y pruebas matemáticas propias. Cualquier futura reutilización de código debe revisar alcance y obligaciones de licencia antes de integrarlo.

La fuente derivada del directo26/11 documenta canales paralelos/pisos y confluencia1H dentro de contexto4H/diario. No tenemos anclajes exactos, escala del gráfico ni coordenadas temporales previas al movimiento; no se crea una regla geométrica fingiendo precisión. La aportación del miembro sobre impulso1H, continuidad4H, AO/Konkorde confirmados y volatilidad>50 sigue **incompleta**: no tenemos definiciones originales numéricas verificadas de ambas confirmaciones ni del ángulo ADX. Un ángulo depende del zoom; sólo pendiente en puntos/hora y aceleración son reproducibles sin escala. Su cálculo ya existe en a26 y se conserva.

PR61 quedó cerrada sin merge tras validación manual de `/position` y `/risk`, sin ampliar alcance. Informe de piloto en la conversación de esa PR; PnL/CROSS pendientes se conservan. No debe confundirse un aviso con un stop real: el propietario confirmó ausencia deSL. Esto no bloquea la auditoría de indicadores y no autoriza acciones sobre posiciones.

Se conservan las pérdidas y conclusiones negativas de PR58/a26, todos sus hashes y protocolos anteriores. No se ha afinado el motor para volverlo rentable. **Siguiente paso justificado:** obtener paridad externa de las nuevas series y completar la definición original de impulso antes de una evaluación incremental. No hay nueva estrategia validada ni recomendación de integración productiva.

## Reproducción y archivos

Con Python3.12/NumPy2.3.5 y dependencias del workflow existente:

    python -B -m research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.forward_shadow.turn_latency.tradingone_v2.seq.a26.a27.run --out /tmp/igod-source-review-new
    python -B -m unittest research.confluence_1h_phase2.event_proximity.strict_series_audit.turn_intensity_phase1.phase1b_diagnostics.forward_shadow.turn_latency.tradingone_v2.seq.a26.a27.test_sources -v

La salida debe ser nueva; se rechaza sobrescribir resultados. `out/` contiene resumen, CSV comprimido con todas las series comparadas, todos los cruces y motivos FE, y contactos TS1H/4H. No se cambia la fecha final para incorporar un caso favorable. Las pruebas sintéticas demuestran propiedades del código; no son evidencia externa de la plataforma ni rentabilidad.

Los workflows existentes se conservan sin editar: su `unittest discover` ya encuentra `a27/test_sources.py`. En Windows se requiere una base `tzdata` accesible a `zoneinfo` para la regresión global; puede indicarse mediante `PYTHONTZPATH`. El primer intento local detectó esa ausencia y una modificación del workflow rechazada por los guardas históricos. Se retiró el cambio de workflow, se situaron todos los archivos nuevos bajo la ruta permitida `seq/a26/a27` y se repitieron las pruebas; no se relajó ningún guard. `validation.json` conserva también ese diagnóstico inicial.
