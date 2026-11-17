# Diagnóstico causal del retraso de giros

No se evalúa otra estrategia ni la rentabilidad. PR #55 conserva sus doce resultados negativos.

Se congela `protocol.json` antes de contar eventos históricos. La secuencia de noviembre ya es conocida: no es una validación ni se usa para escoger parámetros.

Para cada indicador: pendiente `d=x[t]-x[t-1]`, aceleración `a=d[t]-d[t-1]`. Si sigue subiendo pero cada vez menos, hay desaceleración, no todavía giro bajista. La situación inversa anticipa descriptivamente un posible giro al alza. Una sola desaceleración inicia una prealerta por episodio. La confirmación exige cambio estricto de signo de pendiente; nunca se fecha en el vértice anterior.

Se observan dos horas para resolver la prealerta, heredadas de la proximidad temporal de PR #55 y sin optimización: giro, recuperación del impulso previo, pendiente plana o caducidad. Los casos de final de archivo se censuran. Una prealerta falsa significa que no se confirmó ese giro bajo esta definición, no que perdiera una operación.

AO y pececillos se presentan simétricamente como hipótesis UP/DOWN. ADX y BBWP no indican dirección del precio: sus giros se etiquetan como fuerza/volatilidad y se miden ambas excursiones de precio por separado.

El recorrido consumido se mide desde un extremo que YA se conocía en la prealerta, congelado desde el comienzo del tramo de pendiente. No representa un mínimo/máximo perfecto. Se conserva también la deriva entre los cierres de prealerta y confirmación. La fracción de movimiento compara contra una ventana común de cuatro horas posteriores a la prealerta: su denominador es explícitamente ex-post y no alimenta la detección.

BBWP 7/100 y 13/252 se calculan por separado con la misma fórmula pública auditada. El archivo original adjunto tiene valores por defecto 7/100. No se atribuye 13/252 a TradingOne sin verificar configuración y serie. No se sustituye nada en el motor ni en PR #55.

La equivalencia externa de los cuatro indicadores continúa pendiente si faltan exportaciones de TradingOne, identidad de indicadores, ajustes, mercado y prefijo de inicialización. Una coincidencia visual redondeada de pececillos no certifica todas las series. Las pruebas sintéticas prueban código; no son evidencia independiente de plataforma.

SHADOW ONLY. TRADE AUTHORITY: NONE.
