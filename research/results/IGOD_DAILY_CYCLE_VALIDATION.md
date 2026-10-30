# I-GOD Daily Cycle V1 — validación exploratoria

**SHADOW ONLY. TRADE AUTHORITY: NONE. NO VIRGIN HOLDOUT.**

Definiciones fijadas en docs/IGOD_DAILY_SPECIFICATION.md antes de ejecutar estos outcomes. No búsqueda de parámetros.
Datos: BTCUSDT Binance USD-M perpetual, daily REST público, velas cerradas.
n velas=2609; primer open=1567900800000; último cierre=1793318400000; SHA256=37d711b9c2680c8af8a4e1912c47a2b8048b915986eec7aebe3b7a4f42f90862

## Episodios de fase

| Fase / horizonte | n | n direccional | media signed | mediana signed | falsos (signed≤0) | excursión abs media |
|---|---:|---:|---:|---:|---:|---:|
| ACELERACIÓN / H1 | 157 | 157 | -0.002242755746979897 | -0.001007070422292533 | 84 | 0.04013750452602754 |
| ACELERACIÓN / H3 | 157 | 157 | 0.0007051931761461652 | 0.0017951522121208985 | 77 | 0.06505608772606859 |
| ACELERACIÓN / H5 | 156 | 156 | 0.002634845231625036 | 0.001997769776632574 | 74 | 0.08238852896051921 |
| AGOTAMIENTO / H1 | 207 | 130 | -0.004805526190454201 | -0.00489099892716055 | 75 | 0.03484208519672094 |
| AGOTAMIENTO / H3 | 206 | 130 | -0.005430821814445886 | -0.005113112551919152 | 67 | 0.05897207451961704 |
| AGOTAMIENTO / H5 | 206 | 130 | -0.009524425151200354 | -0.00914482085654289 | 73 | 0.0831077309619177 |
| COMPRESIÓN / H1 | 61 | 0 | None | None | 0 | 0.02638972449376635 |
| COMPRESIÓN / H3 | 61 | 0 | None | None | 0 | 0.05094329284758228 |
| COMPRESIÓN / H5 | 61 | 0 | None | None | 0 | 0.06489464992237236 |
| POSIBLE INICIO / H1 | 30 | 30 | -0.002269807659713437 | -0.009198207476542763 | 17 | 0.04610695951799052 |
| POSIBLE INICIO / H3 | 30 | 30 | -0.0030413410804863337 | -0.019176736907235592 | 18 | 0.07788458442139948 |
| POSIBLE INICIO / H5 | 30 | 30 | 0.0013821091578640346 | -0.01847659749431213 | 17 | 0.09929163520117211 |
| POSIBLE REVERSIÓN / H1 | 69 | 69 | 0.004265593635491395 | -1.9971465768264807e-05 | 35 | 0.03491383728256284 |
| POSIBLE REVERSIÓN / H3 | 69 | 69 | 0.003938729673469786 | -0.0015738689745505852 | 35 | 0.05857167451234758 |
| POSIBLE REVERSIÓN / H5 | 68 | 68 | 0.007425372049170309 | 0.008763563834517096 | 27 | 0.08035483393991069 |

## Benchmark descriptivo no solapado, 5 días

Entrada al siguiente open teórico y salida a cinco cierres. NO es el plan de dos tramos ni una entrada observada en producción.
Equity normalizada 1×, sin stop/TP/funding. DD solo entre salidas; subestima riesgo intratrade.
ADX descendente no determina el lado. Compresión sin presión direccional se excluye del benchmark firmado.

| Fase | bps ida/vuelta | n | media net | mediana net | pérdidas | equity 1× | DD terminal |
|---|---:|---:|---:|---:|---:|---:|---:|
| ACELERACIÓN | 18.0 | 121 | 0.006436538115748538 | 0.004223140219706847 | 54 | 1.6255559480802881 | 0.5384143090654487 |
| AGOTAMIENTO | 18.0 | 110 | -0.012161547686919565 | -0.01094482085654289 | 64 | 0.19148735579962925 | 0.8408138704099699 |
| COMPRESIÓN | 18.0 | 0 | None | None | 0 | 1.0 | 0.0 |
| POSIBLE INICIO | 18.0 | 30 | -0.00041789084213596515 | -0.02027659749431213 | 17 | 0.8894137817582447 | 0.37772570572055164 |
| POSIBLE REVERSIÓN | 18.0 | 61 | 0.009512316406148419 | 0.007454178469204733 | 27 | 1.5273607195764491 | 0.3763807431302182 |
| ACELERACIÓN | 36.0 | 121 | 0.0046365381157485374 | 0.0024231402197068463 | 57 | 1.307605867175024 | 0.5530423841168649 |
| AGOTAMIENTO | 36.0 | 110 | -0.013961547686919566 | -0.01274482085654289 | 66 | 0.15649959973533892 | 0.8661366141324511 |
| COMPRESIÓN | 36.0 | 0 | None | None | 0 | 1.0 | 0.0 |
| POSIBLE INICIO | 36.0 | 30 | -0.0022178908421359657 | -0.02207659749431213 | 17 | 0.8422873944687171 | 0.39597292327236366 |
| POSIBLE REVERSIÓN | 36.0 | 61 | 0.007712316406148418 | 0.0056541784692047325 | 29 | 1.369056363533313 | 0.38254261170776194 |

## Estabilidad temporal

{"2020-2022": {"n": 217, "n_directional": 155, "mean_signed": -0.004425501558051887, "median_signed": -0.005410076622942572, "mean_abs": 0.1010098063535681, "false_signals": 84}, "2023-2024": {"n": 156, "n_directional": 125, "mean_signed": 0.002689913531989607, "median_signed": 7.223061264705066e-05, "mean_abs": 0.07539025458508174, "false_signals": 62}, "2025-2026": {"n": 148, "n_directional": 104, "mean_signed": 0.0006631029861183001, "median_signed": 0.004165957882832194, "mean_abs": 0.05874491088657311, "false_signals": 45}}

## Conclusión y límites

**INCONCLUSIVE — FORWARD OBSERVATION REQUIRED.** No se declara un edge ni se selecciona la fase más rentable.
Hay falsas señales y costes. No hay holdout virgen, corrección por selección histórica previa, intervalos inferenciales independientes ni validación prospectiva madura.
El benchmark no valida la geometría A/B, rechazos 15m futuros, funding, fills o riesgo conjunto del plan. Eso requiere observación adicional independiente.
Las observaciones forward del nuevo servicio comienzan en activación; no se importan estos episodios al journal prospectivo.

## CURRENT OBSERVATION — NOT PART OF VALIDATION

{"protocol": "IGOD_DAILY_CYCLE_V1_HYPOTHESIS", "phase": "INDETERMINADO", "available_at": 1793318400000, "ao": -2444.615294117655, "ao_slope": 70.75058823528525, "ao_sign": "BELOW ZERO", "ao_color": "GREEN", "adx": 17.894821873289587, "adx_slope": 0.7798502464957906, "prior_adx_slope": -0.5408475301125044, "prior_nonrising_days": 2, "adx_turn_up": false, "adx_turn_down": false, "plus_di": 14.983362584570159, "minus_di": 26.656101547849605, "pressure": "SHORT", "bbwp": 34.523809523809526, "bbwp_previous": 14.285714285714286, "bbwp_slope": 20.23809523809524, "volatility_compressed": false, "structural_break": "DOWN", "confirmed_support": 79178.6, "confirmed_resistance": 84875.2, "countertrend_rebound": false, "reversal_price_confirmation": false, "interpretation": "HYPOTHESIS — NOT VALIDATED"}

Esta lectura usa exclusivamente el último día cerrado. No es una orden ni una garantía.
