"""Descriptive reuse of examined history; no new fit of PRICE or historical holdout claim."""
import csv
import hashlib
import json
import numpy as np
from .core import HERE,ANCHORS,CLASSES,verify_freeze,read_json,predict,fit_structure,structure_predict,scores,interval,class_calibration,ece_upper

OUT=HERE/'artifacts'


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def csv_rows(path,rows):
    names=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,names,lineterminator='\n');w.writeheader();w.writerows(rows)


def summary(p,y,refs):
    b,l=scores(p,y);out=dict(cycles=len(y),brier=float(b.mean()),logloss=float(l.mean()),
        class_counts=np.bincount(y,minlength=3).tolist(),calibration=class_calibration(p,y),gains={})
    for name,ref in refs.items():
        rb,rl=scores(ref,y);d=(rb-b).mean(axis=1);dl=(rl-l).mean(axis=1)
        out['gains'][name]=dict(brier=float(d.mean()),brier_ci95=interval(d),brier_ci97_5=interval(d,.975),
                               logloss=float(dl.mean()),logloss_ci95=interval(dl))
    out['classes']=[]
    for k,name in enumerate(CLASSES):
        truth=(y[:,None]==k);own=((p[:,:,k]-truth)**2).mean(axis=1)
        row=dict(class_name=name,cycles_with_outcome=int((y==k).sum()),binary_brier=float(own.mean()),
                 mean_probability=float(p[:,:,k].mean()),observed_rate=float((y==k).mean()),gains={})
        for ref_name,ref in refs.items():
            d=((ref[:,:,k]-truth)**2).mean(axis=1)-own
            row['gains'][ref_name]=dict(brier=float(d.mean()),ci95=interval(d))
        out['classes'].append(row)
    return out


def historical():
    verify_freeze();a=np.load(HERE.parent/'killzone_probability_radar/artifacts/features_and_labels.npz')
    x=a['X'][:,:,:6];y=a['Y'];days=a['days'];train=days<='2023-12-30'
    model=fit_structure(x[train],y[train]);OUT.mkdir(exist_ok=True)
    write_json(OUT/'frozen_STRUCTURE.json',model)
    pp=predict(x);prior=np.broadcast_to(read_json('frozen_PRIOR.json'),pp.shape).copy();structure=structure_predict(x,model)
    preds={'PRIOR':prior,'STRUCTURE':structure,'PRICE':pp}
    report=dict(mode='POST_HOC_DESCRIPTIVE_NOT_NEW_VALIDATION',freeze=read_json('freeze_manifest.json')['model_sha256'],
                historical_windows_already_examined=True,no_refit_PRICE=True,partitions={},monthly=[],anchors=[],
                prospective=dict(observed_cycles=0,eligible_cycles=0,real_tradingview_records=0,decision='B',
                    conclusion='PROMETEDOR PERO PENDIENTE DE DATOS PROSPECTIVOS',status='NOT_ACTIVATED_NO_FORWARD_DATA',
                    independent_parity='PENDING',visible_probabilities=False))
    for part,mask in [('train',train),('validation',(days>='2024-01-01')&(days<='2024-12-30')),('examined_test',days>='2025-01-01')]:
        refs={'PRIOR':prior[mask],'STRUCTURE':structure[mask]}
        report['partitions'][part]={name:summary(p[mask],y[mask],refs) for name,p in preds.items()}
    test=days>='2025-01-01'
    for minute in ANCHORS:
        refs={'PRIOR':prior[test,minute:minute+1],'STRUCTURE':structure[test,minute:minute+1]}
        for name,p in preds.items():
            r=summary(p[test,minute:minute+1],y[test],refs)
            report['anchors'].append(dict(minute=minute,model=name,**r))
    for month in sorted(set(str(s)[:7] for s in days)):
        mask=np.array([s.startswith(month) for s in days])
        for name,p in preds.items():
            b,l=scores(p[mask],y[mask]);c=class_calibration(p[mask],y[mask])
            report['monthly'].append(dict(month=month,model=name,cycles=int(mask.sum()),brier=float(b.mean()),
                                           logloss=float(l.mean()),macro_ece=c['macro_ece']))
    # Verify that no feature/weight/scoring change has altered the published PRICE result.
    test_months=sorted(set(str(d)[:7] for d in days[test]));positive_prior=positive_structure=positive_both=0
    for month in test_months:
        values={r['model']:r['brier'] for r in report['monthly'] if r['month']==month}
        a=values['PRICE']<values['PRIOR'];b=values['PRICE']<values['STRUCTURE']
        positive_prior+=a;positive_structure+=b;positive_both+=a and b
    report['examined_test_monthly_stability']=dict(months=len(test_months),positive_vs_prior=positive_prior,
        positive_vs_structure=positive_structure,positive_vs_both=positive_both)
    report['partitions']['examined_test']['PRICE']['calibration']['class_ece_upper95']=ece_upper(pp[test],y[test])
    parent=read_json('../killzone_probability_radar/artifacts/model_validation.json')
    for part,old in [('train','train'),('validation','validation'),('examined_test','test')]:
        actual=report['partitions'][part]['PRICE'];expected=parent['partitions'][old]['PRICE']
        if actual['brier']!=expected['brier'] or actual['logloss']!=expected['logloss']:
            raise ValueError('ORIGINAL_PRICE_RESULTS_CHANGED')
    write_json(OUT/'historical_comparison.json',report)
    write_json(OUT/'prospective_status.json',report['prospective'])
    csv_rows(OUT/'monthly.csv',report['monthly'])
    csv_rows(OUT/'anchor_minutes.csv',[dict(model=r['model'],minute=r['minute'],cycles=r['cycles'],
        brier=r['brier'],logloss=r['logloss'],macro_ece=r['calibration']['macro_ece'],
        gain_prior=r['gains']['PRIOR']['brier'],gain_structure=r['gains']['STRUCTURE']['brier']) for r in report['anchors']])
    price=report['partitions']['examined_test']['PRICE'];prior_score=report['partitions']['examined_test']['PRIOR']['brier']
    lines=['# PRICE congelado — seguimiento independiente', '',
        '**B. PROMETEDOR PERO PENDIENTE DE DATOS PROSPECTIVOS.**', '',
        'Selección de PRICE solicitada DESPUÉS de examinar PR #42: POST-HOC. No es nueva validación.',
        'No se cambian coeficientes, escalado, clipping o variables. No se reentrena ni recalibra.',
        'PR #41, PR #42, OWNER_B/C y las fórmulas originales permanecen intactos.', '',
        '## Qué significa precio solo', '',
        'Seis variables: minuto/60, posición en rango combinado parcial, desplazamiento Londres/Asia,',
        'ancho parcial Londres/Asia, cambio Asia/Asia y ancho combinado/ATR14 H1 confirmado.',
        '**ATR14 ya estaba en PRICE** como escala OHLC: no es un filtro direccional nuevo.',
        'Eliminarlo haría otro modelo; no se hace. No hay AO, ADX, DMI, BBWP o tendencia4H.',
        'No se añaden nuevas variables. Distancias y cambios de rango están representados solo',
        'por las seis transformaciones originales; no se amplía la lista después del test.', '',
        '## Congelamiento', '',
        'Protocolo y assets congelados en3c3f90a antes de ajustar/evaluar la nueva referencia estructural.',
        f"SHA modelo: `{verify_freeze()['model_sha256']}`.",
        f"SHA protocolo: `{verify_freeze()['protocol_sha256']}`.",
        'Referencia estructural: tres terciles FIJOS de posición en el rango parcial; frecuencias de',
        'clase aprendidas solo de2022–2023, ponderación1/60 por minuto y prior20 ciclos por tercil.',
        'No busca bins, suavizado, combinación o umbral ganador. PRIOR es el publicado, sin refit.', '',
        '## Comparación histórica ya vista — NO HOLDOUT VIRGEN', '',
        '| Modelo | n ciclos test visto | Brier | Log-loss | MacroECE |',
        '|---|---:|---:|---:|---:|']
    for name,r in report['partitions']['examined_test'].items():
        lines.append(f"|{name}|{r['cycles']}|{r['brier']:.6f}|{r['logloss']:.6f}|{r['calibration']['macro_ece']:.6f}|")
    lines += ['',f'Mejora PRICE frente a PRIOR: {(prior_score-price["brier"])/prior_score*100:.3f}% RELATIVA del Brier; no puntos de rentabilidad.',
              f"IC95 de ganancia absoluta: {price['gains']['PRIOR']['brier_ci95']}.",
              f"Frente a STRUCTURE: ganancia {price['gains']['STRUCTURE']['brier']:.6f}, IC95 {price['gains']['STRUCTURE']['brier_ci95']}.",
              '', '### SUPERIOR / INFERIOR / NINGUNO por separado', '',
              '| Clase | n ciclos de esa clase | Brier binario | Prob media | Frecuencia | ECE |',
              '|---|---:|---:|---:|---:|---:|']
    for k,r in enumerate(price['classes']):
        lines.append(f"|{r['class_name']}|{r['cycles_with_outcome']}|{r['binary_brier']:.6f}|{r['mean_probability']:.6f}|{r['observed_rate']:.6f}|{price['calibration']['class_ece'][k]:.6f}|")
    lines += ['', '### Cinco instantes predeclarados — precio congelado', '',
              '| Hora NY | n ciclos | Brier | Log-loss | ECE | Ganancia vs estructura |',
              '|---|---:|---:|---:|---:|---:|']
    for r in report['anchors']:
        if r['model']=='PRICE':lines.append(f"|05:{r['minute']:02}|{r['cycles']}|{r['brier']:.6f}|{r['logloss']:.6f}|{r['calibration']['macro_ece']:.6f}|{r['gains']['STRUCTURE']['brier']:.6f}|")
    lines += ['', 'Los60 minutos no son60 muestras independientes: IC por bloques circulares de7 ciclos,2000 réplicas.',
        'monthly.csv contiene todos los meses/modelos; historical_comparison.json conserva calibración',
        'por clase, bins, IC y comparaciones. No se escoge el minuto, mes o clase mejor.',
        f'Meses test con mejora Brier vs PRIOR:{positive_prior}/{len(test_months)}; vs STRUCTURE:{positive_structure}/{len(test_months)}; ambos:{positive_both}/{len(test_months)}.',
        f"Cotas superiores IC95 de ECE por clase, bootstrap por ciclos: {price['calibration']['class_ece_upper95']}.", '',
        '## Protocolo prospectivo aún sin activar', '',
        'Cohorte fija:2026-11-05 a2027-05-04,181 ciclos de calendario. Nada anterior entra como forward.',
        'Predicciones05:00/15/30/45/59 capturadas antes06:00; se conservan los demás minutos disponibles.',
        'La recepción debe ser real, antes de empezar el outcome y a<=120s del as-of. Logs importados',
        'tarde sirven como diagnóstico, NUNCA como evidencia prospectiva. No existe override de reloj CLI.',
        'El capturador es local/offline, de un escritor, no se ha conectado ni activado un servicio.',
        'Tras20:00, un registro separado añade el label calculado con datos públicos verificables.',
        'La igualdad de features con mercado se verifica entonces; no se reescriben las predicciones.',
        'El texto Pine Logs no autentica criptográficamente su origen; se requiere revisión externa.', '',
        'Mínimos:150 ciclos completos,30/clase y>=95% cobertura del calendario. Son mínimos operativos,',
        'NO una prueba automática. El análisis solo puede aprobarse tras terminar la cohorte fija.',
        'Brier: IC97.5% por bloques debe mejorar AMBOS baselines (Bonferroni dos comparaciones).',
        'Log-loss no peor; por clase Brier no peor y límite IC>=−.01; macroECE<=.05, cadaECE<=.08',
        'y límite superior IC95<=.10. Mejora en los cinco instantes y>=2/3 de meses elegibles.',
        'Se exigen>=5 meses con>=10 ciclos. No se recalibra para superar un gate fallido.',
        'Paridad real: compilación/realtime/recarga,>=3 ciclos distintos con cinco instantes por ciclo,',
        'features rtol/atol1e-8 y probabilidades atol1e-10. Comparaciones locales no cuentan como Pine real.',
        'Incluso un resultado suficiente requiere revisión y release nuevo; no hay interruptor de porcentajes.', '',
        '## Evidencia que existe ahora', '',
        '**Ciclos prospectivos:0. Logs reales PRICE comparados:0. Compilación TradingView: PENDIENTE.**',
        'No se ha descargado noviembre como si fuera evidencia prospectiva. No hay tareas automáticas',
        'de captura, órdenes, Telegram o Railway. Se entrega Pine completo para la prueba técnica manual.',
        'Las probabilidades internas experimentales de los logs están etiquetadas NO VALIDADAS;',
        'el panel no muestra porcentajes. El journal distingue captura tardía/replay de evidencia elegible.', '',
        'La mejora predictiva histórica no demuestra rentabilidad, ejecución ni oportunidad operativa.',
        'No hay resultados de trading, TP/SL nuevos o apalancamiento. No se modifica TP±200.', '',
        'SHADOW ONLY. TRADE AUTHORITY: NONE.']
    (OUT/'PRICE_RADAR_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(decision='B',price_brier=price['brier'],structure_brier=report['partitions']['examined_test']['STRUCTURE']['brier'],
        structure_gain_ci95=price['gains']['STRUCTURE']['brier_ci95'],prospective_cycles=0)))


def main():historical()


if __name__=='__main__':main()
