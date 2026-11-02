"""Actual per-frame reconstruction; observed, registered and hypothetical are distinct."""
import base64
import hashlib
from decimal import Decimal
from html import escape
from pathlib import Path
from .model import PixelPoint,clone_pixels


def drawing(case):
    if not case.get('original_upper') or not case.get('original_lower'):
        raise ValueError('ORIGINAL_CIRCLES_NOT_ANNOTATED')
    if case['case_id']=='ALPHA_LABEL_REFERENCE_78285_77517':
        raise ValueError('NEW_CAPTURE_MUST_HAVE_ITS_OWN_CASE_ID')
    width,height=case['image_size']
    if width<=0 or height<=0:raise ValueError('IMAGE_SIZE_INVALID')
    for key in ('upper_anchor_hypotheses','lower_anchor_hypotheses'):
        if key not in case:raise ValueError('ANCHOR_EVIDENCE_LIST_MISSING')
    def point(xy):return PixelPoint(case['case_id'],Decimal(str(xy[0])),Decimal(str(xy[1])))
    u,l=point(case['original_upper']),point(case['original_lower'])
    copies=[]
    for direction,key in (('UP','upper_anchor_hypotheses'),('DOWN','lower_anchor_hypotheses')):
        for hypothesis in case[key]:
            if not hypothesis.get('feature'):raise ValueError('ANCHOR_HYPOTHESIS_NEEDS_VISIBLE_FEATURE')
            anchor=point(hypothesis['point']);cu,cl=clone_pixels(u,l,anchor,direction)
            color=('#c69cff' if hypothesis.get('id')=='D_BOTTOM' else '#ef6fb5') if direction=='DOWN' else '#55dcef'
            copies.append((hypothesis,anchor,cu,cl,color))
    observed=case.get('observed_upper_copy')
    mapped=case.get('registered_upper_copy')
    points=[u,l]+[p for _,a,b,c,_ in copies for p in (a,b,c)]
    for copy in (observed,mapped):
        if copy:points += [point(copy['upper']),point(copy['lower'])]
    x0=min([0]+[float(p.x)-15 for p in points]);y0=min([0]+[float(p.y)-15 for p in points])
    x1=max([width]+[float(p.x)+15 for p in points]);y1=max([height]+[float(p.y)+15 for p in points])
    parts=[]
    def text(x,y,label,color='#edf1f7',size=11):
        parts.append(f'<text x="{x}" y="{y}" style="font-size:{size}px;fill:{color}">{escape(label)}</text>')
    def segment(a,b,color,dash=''):
        parts.append(f'<line x1="{a.x}" y1="{a.y}" x2="{b.x}" y2="{b.y}" stroke="{color}" stroke-width="2" stroke-dasharray="{dash}"/>')
        for p in (a,b):parts.append(f'<circle cx="{p.x}" cy="{p.y}" r="7" fill="none" stroke="{color}" stroke-width="1.5"/>')
    for box in case.get('rectangles',[]):
        left,top,right,bottom=box['bounds']
        parts.append(f'<rect x="{left}" y="{top}" width="{right-left}" height="{bottom-top}" fill="none" stroke="#c879e6" stroke-width="1"/>')
    direct=case.get('measurement_evidence','OBSERVED')=='OBSERVED'
    color='#4eabff' if direct else '#f6c36b'
    segment(u,l,color,'' if direct else '5 4')
    text(u.x+10,u.y-10,'A original' if direct else 'A registrado de 01',color)
    if observed:
        cu,cl=point(observed['upper']),point(observed['lower'])
        segment(cu,cl,'#55dcef')
        text(cu.x+10,cu.y-7,'B libre OBS.', '#55dcef')
        text(cl.x+10,cl.y+17,'B apoyo inferior OBS.', '#55dcef')
    if mapped:
        cu,cl=point(mapped['upper']),point(mapped['lower'])
        segment(cu,cl,'#55dcef','5 4')
        text(cu.x+10,cu.y-8,'B registrado de 02','#55dcef')
    for hypothesis,anchor,cu,cl,color in copies:
        segment(cu,cl,color,'6 4')
        text(anchor.x-12,anchor.y-11,hypothesis['id']+': HIP.',color)
        text(cl.x+9,cl.y+9,hypothesis['id']+' libre',color)
    for name,item in case.get('confirmation_lines',{}).items():
        if name not in ('HIGH','LOW'):raise ValueError('CONFIRMATION_LEVEL_NAME_INVALID')
        if item.get('evidence')=='OBSERVED':
            parts.append(f'<line x1="0" y1="{item["pixel_y"]}" x2="{width}" y2="{item["pixel_y"]}" stroke="#ead067" stroke-dasharray="8 5"/>')
    return '\n'.join(parts),(x0,y0,x1-x0,y1-y0)


def reconstruction(case):
    """Versionable source-derived vector geometry, no raw private image embedded."""
    body,bounds=drawing(case)
    v=' '.join(map(str,bounds))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000" viewBox="0 0 1000 1000">'
            '<rect width="1000" height="1000" fill="#101824"/><style>text{font:15px Arial;fill:#edf1f7}</style>'
            f'<text x="20" y="35">{escape(case.get("frame_id",case["case_id"]))}: TRAZADO DE LA CAPTURA REAL</text>'
            '<text x="20" y="68">Sin velas ni precios reconstruidos. Azul/cian observado; ámbar registrado; magenta hipótesis.</text>'
            f'<svg x="25" y="100" width="950" height="770" viewBox="{v}">{body}</svg>'
            '<text x="20" y="910">D_TOP: apoyo dentro del borde SUPERIOR del recuadro alto (hipótesis).</text>'
            '<text x="20" y="940">D_BOTTOM: apoyo dentro del borde INFERIOR del recuadro alto (hipótesis).</text>'
            '<text x="20" y="975">HIGH/LOW no identificados · Sin mezcla con 78285 · SHADOW ONLY · TRADE AUTHORITY: NONE</text></svg>\n')


def comparison(case,source):
    if not case.get('image') or not case.get('sha256'):raise ValueError('NEW_SOURCE_IMAGE_MISSING')
    raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=case['sha256']:raise ValueError('SOURCE_IMAGE_HASH_MISMATCH')
    mime={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp'}.get(source.suffix.lower())
    if mime is None:raise ValueError('UNSUPPORTED_IMAGE_TYPE')
    width,height=case['image_size'];body,bounds=drawing(case)
    uri='data:'+mime+';base64,'+base64.b64encode(raw).decode('ascii')
    v=' '.join(map(str,bounds))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1700" height="1150" viewBox="0 0 1700 1150">'
            '<rect width="1700" height="1150" fill="#101824"/><style>text{font:16px Arial;fill:#edf1f7}</style>'
            f'<text x="30" y="35">{escape(case.get("frame_id",case["case_id"]))} — ORIGINAL INTACTO / RECONSTRUCCIÓN SOBRE ESA CAPTURA</text>'
            '<text x="30" y="70">A azul original · B cian copia superior · ámbar: posición registrada · C magenta: dos hipótesis inferiores</text>'
            f'<svg x="25" y="110" width="780" height="860" viewBox="0 0 {width} {height}"><image width="{width}" height="{height}" href="{uri}"/></svg>'
            f'<svg x="875" y="110" width="780" height="860" viewBox="{v}"><image width="{width}" height="{height}" opacity=".32" href="{uri}"/>{body}</svg>'
            '<text x="30" y="1010">D_TOP: círculo superior dentro del borde alto del recuadro alto. D_BOTTOM: dentro del borde bajo. Ambas HIPÓTESIS.</text>'
            '<text x="30" y="1045">A observado en 01; B observado en 02. En la otra imagen se registran sus posiciones. C inferior: solo hipótesis.</text>'
            '<text x="30" y="1080">HIGH/LOW oficiales no identificados. Píxeles no son USDT; los cuatro niveles anteriores siguen sin vincular.</text>'
            '<text x="30" y="1120">SHADOW ONLY · TRADE AUTHORITY: NONE · Sin prolongaciones infinitas, señales operativas ni backtests</text></svg>\n')


def save_comparison(case,source,out):
    repo=Path(__file__).resolve().parents[3]
    if not out.resolve().is_relative_to((repo/'research/cache').resolve()):
        raise ValueError('ORIGINAL_SOURCE_OUTPUT_MUST_REMAIN_GITIGNORED')
    content=comparison(case,source)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(content,encoding='utf-8',newline='\n')
