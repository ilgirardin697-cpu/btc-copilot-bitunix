"""Optional original/reconstruction panels from explicit per-image annotations."""
import base64
import hashlib
from decimal import Decimal
from html import escape
from pathlib import Path
from .model import PixelPoint,clone_pixels


def comparison(case,source):
    """No auto endpoints, box extrema, HIGH/LOW mapping or price calibration."""
    if not case.get('image') or not case.get('sha256'):
        raise ValueError('NEW_SOURCE_IMAGE_MISSING')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=case['sha256']:
        raise ValueError('SOURCE_IMAGE_HASH_MISMATCH')
    if not case.get('original_upper') or not case.get('original_lower'):
        raise ValueError('ORIGINAL_CIRCLES_NOT_ANNOTATED')
    if case['case_id']=='ALPHA_LABEL_REFERENCE_78285_77517':
        raise ValueError('NEW_CAPTURE_MUST_HAVE_ITS_OWN_CASE_ID')
    width,height=case['image_size']
    if width<=0 or height<=0:raise ValueError('IMAGE_SIZE_INVALID')
    for name in ('upper_anchor_hypotheses','lower_anchor_hypotheses'):
        if name not in case:raise ValueError('ANCHOR_EVIDENCE_LIST_MISSING')
    def point(xy):return PixelPoint(case['case_id'],Decimal(str(xy[0])),Decimal(str(xy[1])))
    u,l=point(case['original_upper']),point(case['original_lower'])
    mime={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp'}.get(source.suffix.lower())
    if mime is None:raise ValueError('UNSUPPORTED_IMAGE_TYPE')
    encoded=base64.b64encode(source.read_bytes()).decode('ascii')
    uri='data:'+mime+';base64,'+encoded
    copies=[]
    for direction,key,color in (('UP','upper_anchor_hypotheses','#55dcef'),('DOWN','lower_anchor_hypotheses','#ef6fb5')):
        for hypothesis in case[key]:
            if not hypothesis.get('feature'):raise ValueError('ANCHOR_HYPOTHESIS_NEEDS_VISIBLE_FEATURE')
            anchor=point(hypothesis['point']);cu,cl=clone_pixels(u,l,anchor,direction)
            copies.append((hypothesis,anchor,cu,cl,color))
    points=[u,l]+[p for _,a,b,c,_ in copies for p in (a,b,c)]
    x0=min([0]+[float(p.x)-15 for p in points]);y0=min([0]+[float(p.y)-15 for p in points])
    x1=max([width]+[float(p.x)+15 for p in points]);y1=max([height]+[float(p.y)+15 for p in points])
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1150" viewBox="0 0 1600 1150"><rect width="1600" height="1150" fill="#101824"/><style>text{{font:16px Arial;fill:#edf1f7}}</style>',
         f'<text x="30" y="35">{escape(case["case_id"])} — ORIGINAL / RECONSTRUCCIÓN EN PÍXELES</text>',
         '<text x="30" y="70">A azul: medición · B cian: copia superior · C magenta: copia inferior · D amarillo: HIGH/LOW separados</text>',
         f'<svg x="25" y="110" width="730" height="900" viewBox="0 0 {width} {height}"><image width="{width}" height="{height}" href="{uri}"/></svg>',
         f'<svg x="825" y="110" width="730" height="900" viewBox="{x0} {y0} {x1-x0} {y1-y0}"><image width="{width}" height="{height}" opacity=".28" href="{uri}"/>']
    def segment(a,b,color,dash=''):
        svg.append(f'<line x1="{a.x}" y1="{a.y}" x2="{b.x}" y2="{b.y}" stroke="{color}" stroke-width="3" stroke-dasharray="{dash}"/>')
        for p in (a,b):svg.append(f'<circle cx="{p.x}" cy="{p.y}" r="7" fill="none" stroke="{color}" stroke-width="2"/>')
    segment(u,l,'#4eabff')
    for hypothesis,anchor,cu,cl,color in copies:
        segment(cu,cl,color,'6 4')
        svg.append(f'<text x="{anchor.x+9}" y="{anchor.y}">{escape(hypothesis["id"])}: {escape(hypothesis["feature"])}</text>')
    for name,item in case.get('confirmation_lines',{}).items():
        if name not in ('HIGH','LOW'):raise ValueError('CONFIRMATION_LEVEL_NAME_INVALID')
        if item.get('evidence')!='OBSERVED':continue
        y=item['pixel_y'];svg.append(f'<line x1="0" y1="{y}" x2="{width}" y2="{y}" stroke="#ead067" stroke-dasharray="8 5"/>')
    svg+=['</svg>','<text x="30" y="1050">Todas las hipótesis documentadas se muestran sin elegir la que mejor encaje. Ninguna genera señales.</text>',
          '<text x="30" y="1085">Píxeles ≠ USDT. Anclajes, precio H e identidad con SUPERIOR/INFERIOR requieren evidencia del MISMO setup.</text>',
          '<text x="30" y="1120">SHADOW ONLY · TRADE AUTHORITY: NONE · Sin prolongaciones infinitas ni backtests</text>','</svg>']
    return '\n'.join(svg)+'\n'


def save_comparison(case,source,out):
    repo=Path(__file__).resolve().parents[3]
    if not out.resolve().is_relative_to((repo/'research/cache').resolve()):
        raise ValueError('ORIGINAL_SOURCE_OUTPUT_MUST_REMAIN_GITIGNORED')
    content=comparison(case,source)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(content,encoding='utf-8',newline='\n')
