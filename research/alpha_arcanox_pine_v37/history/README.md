# Killzone OWNER_B — historia offline y stress independiente

Base de esta fase:78a20d9, PR41 DRAFT. No cambia ninguna fórmula validada ni
los resultados de las fases anteriores. No se activa un proceso PAPER.

- [Informe completo mensual y total](artifacts/KILLZONE_OWNER_B_HISTORY_12M.md)
- [Escenario40x: requisitos y bloqueo](artifacts/STRESS_40X_NO_SL.md)
- [365 ciclos OWNER_B](artifacts/cycles_OWNER_B.csv)
- [36 operaciones OWNER_B](artifacts/trades_OWNER_B.csv)
- [Control cierre simple, todos los ciclos](artifacts/cycles_OWNER_B_CLOSE_ONLY_SENSITIVITY.csv)
- [Mensual de ambos modelos](artifacts/monthly.csv)
- [Curvas de equity sin reset](artifacts/equity.svg)
- [Protocolo fijado](specification.json) y [stress](stress_specification.json)
- [Corrección de reporting auditada](artifacts/reporting_fix_audit.json)

Fechas, fuente, reglas y costes se fijaron en046491f antes de descargar.
La caducidad en el límite del ciclo se precisó enb725a2d después de descargar
y antes de ver outcomes; se declara expresamente. Los manifests conservan el
hash del primer protocolo y el resultado el hash de análisis posterior.
No se escogieron parámetros después de resultados. No existe holdout virgen.

Reproducción, desde la raíz, Python3.12 y requests para descargar archivos públicos:

```sh
python -m research.alpha_arcanox_pine_v37.history.download --interval 1h
python -m research.alpha_arcanox_pine_v37.history.download --interval 1m
python -m research.alpha_arcanox_pine_v37.history.evaluate
python -m research.alpha_arcanox_pine_v37.history.report
python -m unittest research.alpha_arcanox_pine_v37.history.test_history -v
```

Las descargas son solo GET HTTPS a Binance Vision, sin claves ni endpoints de
cuenta. Se verifican25 checksums oficiales, todos los timestamps y esquema,
contigüidad y agregación exacta60min→1H. No se rellenan huecos ni se usa Futures
como sustituto Spot. Raw ZIP permanece local/ignorado. Los artifacts comprimidos
permiten revisar todos los datos H1/ledgers sin descargar en CI.

La salida anterior a la corrección exclusiva de la cota de DD está comprimida
y versionada; report.py comprueba que operaciones, fills, PnL, CI, clasificación
y curvas MTM son idénticos. Solo se añadió una métrica descriptiva emparejada y
se corrigió la cota adversa, sin cambiar la estrategia.

El 40x NO tiene resultados históricos válidos mientras falten los requisitos de
procedencia. No reutiliza los stops o los precios Spot como liquidaciones. Sus
campos quedan null, no0. El ladder50% es álgebra hipotética, no probabilidad.

SHADOW ONLY. TRADE AUTHORITY: NONE.
