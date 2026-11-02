"""Reproduce the two actual image observations; no market/price/strategy fitting."""
import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from .render import reconstruction,save_comparison
from ..data import json_text


def blue_components(width,height,pixel):
    """Fixed display-color mask, NOT a trading parameter or target search.

    Restrict to plot area to exclude the blue price tag. Circle-center readings
    come from connected ring-pixel bounding boxes, not desired price levels.
    """
    points=set()
    for y in range(height):
        for x in range(width):
            r,g,b=pixel(x,y)
            if b>150 and b>1.7*g and b>2*r and g<145:points.add((x,y))
    groups=[]
    while points:
        first=next(iter(points));points.remove(first);queue=[first]
        for x,y in queue:
            for dx,dy in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)):
                p=(x+dx,y+dy)
                if p in points:points.remove(p);queue.append(p)
        if len(queue)<12:continue
        xs=[p[0] for p in queue];ys=[p[1] for p in queue]
        groups.append(dict(pixels=len(queue),bounds=[min(xs),min(ys),max(xs),max(ys)],
                           center=[(min(xs)+max(xs))/2,(min(ys)+max(ys))/2]))
    return sorted(groups,key=lambda g:g['center'][1])


def registration_observations(manifest):
    a,b=manifest['cases'];landmarks=manifest['registration']['landmarks']
    vectors=[(p['target'][0]-p['source'][0],p['target'][1]-p['source'][1]) for p in landmarks]
    dx=sum(Decimal(x) for x,y in vectors)/len(vectors)
    dy=sum(Decimal(y) for x,y in vectors)/len(vectors)
    residual=max(max(abs(Decimal(x)-dx),abs(Decimal(y)-dy)) for x,y in vectors)
    u,l=a['original_upper'],a['original_lower']
    cu,cl=b['observed_upper_copy']['upper'],b['observed_upper_copy']['lower']
    ru=[Decimal(u[0])+dx,Decimal(u[1])+dy];rl=[Decimal(l[0])+dx,Decimal(l[1])+dy]
    # Copy translation uses ONLY the observed support (lower circle).
    # The observed upper circle is reserved for an independent endpoint check.
    move=[Decimal(cl[i])-rl[i] for i in range(2)]
    predicted=[ru[i]+move[i] for i in range(2)]
    return dict(scene_translation_px=[dx,dy],max_absolute_landmark_residual_px=residual,
                landmark_count=len(landmarks),scene_fit_uses='PURPLE_RECTANGLE_CORNERS_ONLY',
                registered_original_upper_px=ru,registered_original_lower_px=rl,
                original_height_px=Decimal(l[1])-Decimal(u[1]),copy_height_px=Decimal(cl[1])-Decimal(cu[1]),
                copy_translation_px=move,copy_fit_uses='OBSERVED_LOWER_SUPPORT_CIRCLE_ONLY',
                predicted_upper_px=predicted,observed_upper_px=cu,
                endpoint_residual_px=[Decimal(cu[i])-predicted[i] for i in range(2)],
                height_USDT=None,price_calibration_verified=False,old_four_level_setup_binding='UNVERIFIED',
                observed_lower_projection=False,operational_paper='BLOCKED',
                measured_edge_offsets_px=manifest['registration']['edge_offsets'])


def verify_sources(manifest,source_dir):
    # Optional Pillow is needed only for local source inspection. Runtime and
    # all formula/renderer logic remain stdlib; private source files are not in CI.
    from PIL import Image
    opened=[];readings=[]
    for case in manifest['cases']:
        source=source_dir/case['image'];raw=source.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=case['sha256']:raise ValueError('SOURCE_HASH_MISMATCH')
        image=Image.open(source).convert('RGB')
        if list(image.size)!=case['image_size']:raise ValueError('SOURCE_SIZE_MISMATCH')
        plot_width=min(image.width,620)
        px=image.load();groups=blue_components(plot_width,image.height,lambda x,y:px[x,y])
        if len(groups)!=2:raise ValueError('EXPECTED_TWO_BLUE_RING_COMPONENTS')
        expected=(case['original_upper'],case['original_lower']) if case['measurement_evidence']=='OBSERVED' else (
            case['observed_upper_copy']['upper'],case['observed_upper_copy']['lower'])
        if [g['center'] for g in groups]!=[list(p) for p in expected]:raise ValueError('CIRCLE_ANNOTATION_DIFFERS_FROM_PIXELS')
        opened.append(image);readings.append(dict(frame_id=case['frame_id'],sha256=case['sha256'],
            source_size=list(image.size),plot_mask_width=plot_width,blue_rings=groups))
    for landmark in manifest['registration']['landmarks']:
        for image,point in zip(opened,(landmark['source'],landmark['target'])):
            if image.getpixel(tuple(point))!=(156,39,176):raise ValueError('REGISTRATION_FEATURE_NOT_PURPLE_BOX_PIXEL')
    return readings


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-dir',type=Path,required=True)
    p.add_argument('--private-out',type=Path,required=True)
    args=p.parse_args()
    here=Path(__file__).resolve().parent
    manifest=json.loads((here/'cases.json').read_text(encoding='utf-8'))
    readings=verify_sources(manifest,args.source_dir)
    observed=registration_observations(manifest)
    art=here/'artifacts';art.mkdir(exist_ok=True)
    for i,case in enumerate(manifest['cases'],1):
        (art/f'frame_{i:02}_geometry.svg').write_text(reconstruction(case),encoding='utf-8',newline='\n')
        save_comparison(case,args.source_dir/case['image'],args.private_out/f'frame_{i:02}_comparison.svg')
    (art/'observations.json').write_text(json_text(dict(source_readings=readings,geometry=observed)),encoding='utf-8',newline='\n')
    (art/'index.html').write_text('<!doctype html><html lang="es"><meta charset="utf-8"><title>Dos capturas reales — geometría</title><style>body{background:#101824;color:#edf1f7;font:16px Arial;margin:25px}a{color:#55dcef}img{width:100%;max-width:1000px}</style><h1>Reconstrucción vectorial de las dos capturas REALES</h1><p>Originales privados no publicados. Cada trazado usa sus coordenadas observadas; no es el antiguo esquema simbólico. Las comparaciones con fotografía incrustada se generan por separado en research/cache.</p><p>Cian: copia superior observada o registrada. Magenta: dos apoyos inferiores hipotéticos, sin escoger ganador. HIGH/LOW no identificados. No se mezclan los niveles anteriores de 78285.</p><img src="frame_01_geometry.svg" alt="Geometría de captura 01"><img src="frame_02_geometry.svg" alt="Geometría de captura 02"><p><a href="observations.json">Mediciones reproducibles</a> · <a href="../SOURCE_REVIEW.md">Informe de las fuentes</a></p><p>SHADOW ONLY. TRADE AUTHORITY: NONE. Sin backtests, señales ni órdenes.</p></html>\n',encoding='utf-8',newline='\n')
    args.private_out.mkdir(parents=True,exist_ok=True)
    (args.private_out/'index.html').write_text('<!doctype html><html lang="es"><meta charset="utf-8"><title>Originales y reconstrucciones reales</title><style>body{background:#101824;color:#edf1f7;font:16px Arial;margin:20px}img{width:100%;max-width:1700px}</style><h1>Dos capturas originales y sus reconstrucciones</h1><p>No calibración de precios; dos hipótesis inferiores sin selección. Sin señales.</p><img src="frame_01_comparison.svg" alt="Original 01 y reconstrucción"><img src="frame_02_comparison.svg" alt="Original 02 y reconstrucción"><p>SHADOW ONLY. TRADE AUTHORITY: NONE.</p></html>\n',encoding='utf-8',newline='\n')
    # Verify that all source bytes survived untouched.
    for case in manifest['cases']:
        if hashlib.sha256((args.source_dir/case['image']).read_bytes()).hexdigest()!=case['sha256']:
            raise ValueError('ORIGINAL_CHANGED')
    print(json_text(observed))


if __name__=='__main__':main()
