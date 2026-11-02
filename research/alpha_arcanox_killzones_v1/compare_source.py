"""Local-only source montage. Original JPG bytes are never edited/published."""
import argparse
import base64
import json
from pathlib import Path
from .data import sha
from .render import reference_svg


def compare(source_dir,out):
    here=Path(__file__).resolve().parent
    repo=here.parents[1]
    if not out.resolve().is_relative_to((repo/'research/cache').resolve()):
        raise ValueError('RAW_SOURCE_COMPARISON_MUST_REMAIN_GITIGNORED')
    reference=json.loads((here/'fixtures/owner_reference.json').read_text(encoding='utf-8'))
    for name,expected in reference['source_images_sha256'].items():
        if sha(source_dir/name)!=expected:raise ValueError('ORIGINAL_SOURCE_HASH_MISMATCH')
    photo=base64.b64encode((source_dir/'01_captura_niveles_y_long.jpg').read_bytes()).decode('ascii')
    rebuilt=base64.b64encode(reference_svg(reference).encode('utf-8')).decode('ascii')
    s=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1120" viewBox="0 0 1800 1120">
<rect width="1800" height="1120" fill="#101824"/>
<style>text{{font:20px Arial;fill:#edf1f7}}</style>
<text x="30" y="40">Alpha Arcanox — original frente a reconstrucción PARCIAL verificable</text>
<text x="30" y="82">Izquierda: JPG intacto. Derecha: solo los cuatro valores leídos; NO fórmula ni replay de mercado.</text>
<text x="40" y="133">CAPTURA 01 ORIGINAL</text>
<text x="710" y="133">ETIQUETAS RECONSTRUIDAS — SIN VELAS INVENTADAS</text>
<image x="30" y="160" width="640" height="800" href="data:image/jpeg;base64,{photo}"/>
<image x="700" y="160" width="1080" height="800" href="data:image/svg+xml;base64,{rebuilt}"/>
<text x="30" y="1010">Diferencia: el marcador LONG está bajo un cuerpo que cruza HIGH; tu regla exige TODO EL CUERPO fuera.</text>
<text x="30" y="1052">No convertir el precio con cuenta atrás en un cierre confirmado. Fecha, ticker, OHLC y ATR exactos: pendientes.</text>
<text x="30" y="1094">PAPER BLOQUEADO — NO VERIFICACIÓN DE FÓRMULAS — SHADOW ONLY — TRADE AUTHORITY: NONE</text>
</svg>\n'''
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(s,encoding='utf-8',newline='\n')
    for name,expected in reference['source_images_sha256'].items():
        if sha(source_dir/name)!=expected:raise ValueError('SOURCE_CHANGED_DURING_COMPARISON')
    print('LOCAL_ONLY_SOURCE_COMPARISON_WRITTEN; FIVE_ORIGINAL_HASHES_UNCHANGED')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();compare(a.source_dir,a.out)
