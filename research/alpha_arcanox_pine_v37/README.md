# Killzone Pine H1 V3.7 Lite — laboratorio independiente

Dos perfiles sin mezcla: `PINE_A` (defaults originales) y `OWNER_B`
(UTC−4, cuerpo completo, reglas PAPER del propietario, TP adelantado200).
SHADOW ONLY. TRADE AUTHORITY: NONE.

**Nueva fase histórica:** [12 meses OWNER_B y control](history/README.md),
con protocolo previo, todos los ciclos y stress40x separado y bloqueado si
faltan reglas verificadas. Los resultados previos de64 registros se conservan.

**Actualización: ya se dispone de64 registros REALES de TradingView. Paridad
comprobada en33 registros/2 pares completos,0 discrepancias;31 iniciales excluidos.**
GO para revisión PAPER offline; sin activación operativa ni validación de edge.
[Informe real](artifacts/REAL_TRADINGVIEW_PARITY_20261103.md) ·
[OWNER_B separado](artifacts/OWNER_B_64_REVIEW.md) · [Gráficos](artifacts/real_evidence.html).

- [Informe y fórmulas](REPORT.md)
- [Protocolo candidato, NO activado](PAPER_PROTOCOL.md)
- [Galería de geometría de pruebas](artifacts/index.html)
- [Fuente original preservada](source/Killzone_H1_v3_7_Lite.txt)
- [Copia diagnóstica Pine Logs, no compilada aquí](artifacts/Killzone_H1_v3_7_Lite_DIAGNOSTIC.pine)
- [Estado explícito de paridad](artifacts/parity_status.json)

Desde la raíz del checkout, Python3.12+ con base IANA (`tzdata` si Windows no
dispone de ella), sin credenciales, servicios ni acceso de red:

```sh
python -m unittest research.alpha_arcanox_pine_v37.test_pine research.alpha_arcanox_pine_v37.test_real_evidence -v
python -m research.alpha_arcanox_pine_v37.build
```

Ejemplo de uso matemático (no estrategia operativa):

```python
from research.alpha_arcanox_pine_v37.core import project
levels = project(aHigh=80000, aLow=79000, lHigh=81000, lLow=79500)
# HIGH81000, LOW79000; anclajes79970 /79545; targets81970 /77545.
# B PAPER usa81770 /77745 para R/R, conservando ambos targets originales.
```

No hay runner continuo, API, exchange client, sender ni integración con I-GOD.
`paper_plan(...).accepted` solo expresa un filtro aritmético offline; devuelve
también `operational_paper_authorized=False` y `actual_fill=None` siempre.
La comprobación matemática externa ya cubre los2 pares citados; no activa
un proceso PAPER continuo, ni concede autoridad de trading.
