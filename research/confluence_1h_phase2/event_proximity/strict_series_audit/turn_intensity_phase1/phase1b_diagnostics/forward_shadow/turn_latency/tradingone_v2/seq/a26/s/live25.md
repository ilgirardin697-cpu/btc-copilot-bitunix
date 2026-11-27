# Bitman — Directo del 25/11/2026: evidencia para I-GOD

Fuente primaria: https://www.youtube.com/watch?v=3Dqmz82NPbE

## Alcance y procedencia

Notas elaboradas a partir de dos consultas de subtítulos españoles realizadas en ChatGPT mediante vidIQ (10 créditos en total). Se recuperaron extractos con marcas temporales de la transcripción (340 líneas en la respuesta original); este documento es una síntesis trazable, NO una transcripción íntegra. No se inspeccionaron fotogramas, gráficos, órdenes ni fills. Las afirmaciones del autor no son resultados de backtesting ni evidencia de rentabilidad realizada. Los tiempos de abajo son posiciones dentro del vídeo, no horas de mercado. Los errores del reconocimiento de voz pueden afectar nombres o cifras; consultar el original si son determinantes.

## Evidencia directa del 25 de noviembre

| Tiempo | Observación del autor (paráfrasis) | Límite de la evidencia |
|---|---|---|
| [22:49](https://youtu.be/3Dqmz82NPbE?t=1369) | Contempla cuña, banderín invertido o canal descendente; la figura de consolidación todavía no está determinada. | No hay ruptura confirmada. |
| [25:02–27:09](https://youtu.be/3Dqmz82NPbE?t=1502) | En semanal distingue una cuña ascendente histórica que interpreta como rota a la baja y otra descendente interna cuyo soporte relaciona con 55K. Espera una futura ruptura superior de la segunda. | Geometría y probabilidades citadas no verificadas; no implica nuevo máximo histórico. |
| [27:59–29:23](https://youtu.be/3Dqmz82NPbE?t=1679) | Presenta 62–55K como zona para DCA en contexto de acumulación, no como entrada apalancada inmediata. Contempla permanecer días o semanas en esa zona, visitar 54–55K y rebotar hacia 60–63K. Sigue esperando convergencia 2W. | Hipótesis del autor; no fecha de ruptura ni garantía de suelo. |
| [30:10–32:58](https://youtu.be/3Dqmz82NPbE?t=1810) | La expansión de volatilidad semanal acompaña desplazamientos amplios; la caída de volatilidad acompaña movimientos menores. Aclara que volatilidad no proporciona dirección. | No determina umbral, pendiente, ventana ni línea exacta para el evento. |
| [33:52–35:00](https://youtu.be/3Dqmz82NPbE?t=2032) | Vincula el cruce descendente de cero del área semanal de Konkorde con el mínimo local que, según su interpretación, suele producirse en la primera semana de cruce. Usa esto como argumento para 55K. | Sin identidad inequívoca del área, casos completos ni tasa verificada. |
| [38:10–42:46](https://youtu.be/3Dqmz82NPbE?t=2290) | Compara visualmente episodios de expansión semanal en mercados bajistas (movimientos en torno a 30–35%, con ejemplos de 37%) y alcistas (60–70%). | Comparación retrospectiva del autor, no estimación validada; evitar extrapolar como TP. |
| [44:57–45:31](https://youtu.be/3Dqmz82NPbE?t=2697) | La posible zona de suelo no excluye revisitar 55K, 54K o 53K si el soporte descendente se desplaza con el tiempo. | No convertir en trayectoria de precio prevista ni stop. |
| [52:20–53:45](https://youtu.be/3Dqmz82NPbE?t=3140) | En diario, BBWP sigue decreciendo, AO lleva tres barras verdes, ADX sigue creciendo y todavía no confirma el retroceso alcista. Área de volumen Konkorde bajo cero, con media cercana. Espera que ADX termine girando, pero aún no lo observa. | Lectura durante directo; verificar cierres de velas antes de codificar. La secuencia no es una regla obligatoria demostrada. |
| [54:02–54:53](https://youtu.be/3Dqmz82NPbE?t=3242) | Recuerda señal LONG previa del RSI ajustado en 1H, que según él tuvo recorrido favorable de aproximadamente 6%. | Recorrido favorable no equivale a PnL ejecutado. |
| [55:26–56:46](https://youtu.be/3Dqmz82NPbE?t=3326) | Declara que el 25 su estrategia RSI 1H dio señal SHORT, antes del movimiento hacia 57.300. Menciona recorrido favorable de 3,13% y su objetivo habitual de 10% sobre margen con 10x. | Hora exacta, instrumento, precio de señal, entrada, stop, fill, costes, margen y PnL no verificados. No confundir el timestamp del vídeo con hora de la señal. No adoptar apalancamiento ni prometer rentabilidad. |
| [59:46](https://youtu.be/3Dqmz82NPbE?t=3586) | Remite al directo anterior para la configuración de BBWP. | No revela aquí parámetros adicionales. |
| [1:23:54](https://youtu.be/3Dqmz82NPbE?t=5034) | Menciona que miembros del grupo investigan RSI y FE. | No identifica fórmula ni configuración privada. |

## Evidencia complementaria: directo del 24

Fuente: https://www.youtube.com/watch?v=FT__YRYnShc. Notas de subtítulos recuperados anteriormente; sin inspección de fotogramas.

- [27:50–28:41](https://youtu.be/FT__YRYnShc?t=1670): segunda barra verde AO diario, ADX no confirma giro, impulso bajista aún vigente.
- [51:20–53:31](https://youtu.be/FT__YRYnShc?t=3080): última señal 1H LONG; al momento del directo aún no había señal SHORT. Espera la próxima señal sin forzar operación.
- [1:12:51–1:13:26](https://youtu.be/FT__YRYnShc?t=4371): parámetros BBWP verbalizados: fuente Close, basis SMA, length 13, lookback 252, extreme high 98, extreme low 2. No se verificó visualmente la configuración de línea de señal. Los cuatro primeros coinciden con los parámetros principales recuperados de TradingOne-2.0-diseno.json. Verificar thresholds y señal por separado.

## Aplicación al addendum PR58 (hipótesis nuestras, no reglas demostradas de Bitman)

- Registrar las tres señales declaradas: SHORT 05/11 (hora exacta desconocida), LONG 22/11 (17:00 Madrid según directo del 23, anclaje de vela pendiente), SHORT 25/11 (hora exacta desconocida). No escoger parámetros para hacer coincidir únicamente estos eventos; comparar con todas las señales y periodos independientes. La identidad del RSI privado sigue sin verificarse.
- Separar contexto semanal/2W, impulso diario y gatillos 1H. Diferenciar operaciones tendenciales de rebotes contra tendencia; evaluar con velas cerradas y referencias disponibles en tiempo real.
- Comparar secuencia de giro BBWP, recuperación AO, descenso ADX y recuperación Konkorde frente a variantes sin exigir simultaneidad. No interpretar ADX o BBWP como dirección por sí solos. Distinguir giro de pendiente de cruce de nivel.
- Evaluar expansiones BBWP semanal y distribuciones de retorno/ATR, con controles y régimen definido ex ante. No validar con ejemplos retrospectivos elegidos por el autor.
- Contrastar con BITMAN_AUDITORIA_20261126.md: SniperRBW, gatillo 1H sobre 59.758 publicado 25/11 19:04 Madrid, cierre 21:00 a 59.879,23 y objetivo 60.900 alcanzado después. Es un caso de un miembro, no una señal de Bitman. Fills y stop no verificados.
- No atribuirle a Bitman stops, trailing, BE o parciales que no ha explicado en estos fragmentos. Compararlos como hipótesis de gestión con costes, financiación y deslizamiento. Mantener SHADOW ONLY, TRADE AUTHORITY NONE, V8_LIVE_EXECUTION=false.
- No crear otra estrategia ni ajustar parámetros a estos casos; integrar los hallazgos en el estado central del proyecto y distinguir evidencia, hipótesis, resultados negativos y datos pendientes. La muestra de PR58 no demuestra ventaja económica.

## Pendientes

Fotogramas originales del SHORT del 25, hora y mercado exactos; identidad y parámetros del RSI; definición operacional del área semanal Konkorde, BBWP y convergencia 2W; validación independiente de las tasas y magnitudes citadas. La transcripción íntegra no se ha guardado localmente. Este documento permite continuar el addendum sin nuevas consultas de pago; no sustituye la fuente original si se requieren datos que los subtítulos recuperados no permiten precisar.
