"""Reproduce offline evidence without original pictures or any network access."""
import json
from decimal import Decimal
from pathlib import Path
from .core import scan,stamp,atr14
from .data import read_csv,json_text,sha
from .render import reference_svg,session_svg,command_preview
from .risk import Costs,estimate


def main():
    root=Path(__file__).resolve().parent
    fixtures=root/'fixtures';out=root/'artifacts';out.mkdir(exist_ok=True)
    source=json.loads((fixtures/'owner_reference.json').read_text(encoding='utf-8'))
    csv_path=fixtures/'public_sessions_demo.csv'
    manifest=json.loads((fixtures/'public_data_manifest.json').read_text(encoding='utf-8'))
    if sha(csv_path)!=manifest['sha256']:raise ValueError('PUBLIC_DEMO_HASH_MISMATCH')
    bars=read_csv(csv_path)
    snap=scan(bars,'2026-09-02',stamp('2026-09-02',10))
    write=lambda p,s:p.write_text(s,encoding='utf-8',newline='\n')
    write(out/'observed_reference_levels.svg',reference_svg(source))
    write(out/'public_sessions_demo.svg',session_svg(bars,snap,'BTCUSDT USD-M 2026-09-02 — PUBLIC SESSION MECHANICS ONLY'))
    write(out/'public_sessions_snapshot.json',json_text(dict(role='NOT_ALPHA_EXAMPLE',data=manifest,snapshot=snap)))
    write(out/'killzone_OFFLINE_preview.txt',command_preview(snap,'BTCUSDT / BINANCE_USDM_PERPETUAL — DEMO, NO ES LA CAPTURA ALPHA'))
    # These controls do not feed scan(), cannot confer formula verification and
    # never claim to represent the original market example.
    costs=Costs(*(Decimal(x) for x in ('0.0006','0.0006','0.0005','0.0005','0')),
                provenance='ILLUSTRATIVE_ONLY: 6bp per-leg fee, 5bp adverse slippage; explicit zero funding SCENARIO, not account facts')
    controls={}
    for side,entry,h,l,target in [('LONG','101','100','90','110'),('SHORT','99','110','100','90'),('LONG','101','100','90','104')]:
        controls[side+'_'+target]=estimate(side,Decimal(entry),Decimal(h),Decimal(l),Decimal(target),Decimal(5),costs,Decimal(10000))
    write(out/'synthetic_risk_controls.json',json_text(dict(role='SYNTHETIC_UNIT_CONTROLS_NOT_BTC_NOT_ALPHA_NOT_PAPER_SIGNALS',controls=controls)))
    write(out/'index.html','<!doctype html><html lang="es"><meta charset="utf-8"><title>Alpha Arcanox — prototipo bloqueado</title><style>body{background:#101824;color:#edf1f7;font:16px Arial;margin:25px}a{color:#66ccec}img{width:100%;max-width:1400px}</style><h1>Alpha Arcanox — reglas del propietario V1</h1><p>NO-GO PAPER: cuatro fórmulas NO VERIFICADAS. Sin ticker/fecha exactos del ejemplo original.</p><h2>Referencia visual: solo etiquetas confirmadas, sin velas inventadas</h2><img src="observed_reference_levels.svg" alt="Cuatro valores observados, no calculados"><h2>Comprobación independiente de sesiones sobre datos públicos</h2><p>Esta fecha/venue son de prueba, NO la captura original. No se trasladan sus cuatro niveles a esta serie.</p><img src="public_sessions_demo.svg" alt="Sesiones cinco y cuatro velas con niveles desconocidos"><p><a href="public_sessions_snapshot.json">Snapshot bloqueado</a> · <a href="killzone_OFFLINE_preview.txt">Diseño /killzone, no integrado</a> · <a href="synthetic_risk_controls.json">Controles artificiales de riesgo</a></p><p>SHADOW ONLY. TRADE AUTHORITY: NONE.</p></html>\n')
    print(json_text(dict(paper_decision=snap['paper_decision'],reason_codes=snap['reason_codes'],
                         original_case_status='NOT_REPLAYABLE_WITH_CURRENT_EVIDENCE',trade_authority='NONE')))


if __name__=='__main__':main()
