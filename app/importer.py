"""Untrusted SVG -> explicit, selectable geometric candidates, never annotations by inference."""
import xml.etree.ElementTree as ET
import math
from svgpathtools import parse_path

MAX_SIZE = 1_000_000

def read_svg(text: str):
    if len(text.encode()) > MAX_SIZE or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('SVG troppo grande o dichiarazioni XML non consentite.')
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise ValueError('XML SVG non valido.') from e
    if root.tag.split('}')[-1] != 'svg':
        raise ValueError('È richiesto un SVG. Convertire prima i PDF vettoriali in SVG; le scansioni non sono profili precisi.')
    candidates, warnings = [], []
    def visit(el, blocked=False):
        tag = el.tag.split('}')[-1]
        if tag in ('defs', 'clipPath', 'mask', 'symbol', 'pattern'):
            return
        if el.get('transform') or el.get('style','').find('transform') >= 0:
            raise ValueError('Trasformazioni SVG non supportate: applicare/appiattire le trasformazioni prima di importare.')
        if tag in ('use', 'image', 'text'):
            warnings.append(f'Elemento {tag} escluso. Raster e annotazioni non diventano geometria.')
        d = None
        if tag == 'path':
            d = el.get('d', '')
        elif tag == 'line':
            d = f"M {el.get('x1',0)} {el.get('y1',0)} L {el.get('x2',0)} {el.get('y2',0)}"
        elif tag in ('polyline', 'polygon'):
            d = 'M ' + el.get('points','') + (' Z' if tag == 'polygon' else '')
        if d:
            try:
                p = parse_path(d)
                if len(p) > 300:
                    raise ValueError('Troppi segmenti nel tracciato.')
                for part in p.continuous_subpaths():
                    points, runs = [], []
                    for seg in part:
                        # Curves sampled densely; CAD later interpolates a regular spline.
                        n = 1 if seg.__class__.__name__ == 'Line' else 48
                        if not points:
                            points.append([seg.start.real, seg.start.imag])
                        start = len(points)-1
                        points.extend([[seg.point(i/n).real, seg.point(i/n).imag] for i in range(1,n+1)])
                        runs.append({'start':start, 'end':len(points)-1, 'curved':n>1})
                    if any(not math.isfinite(v) or abs(v)>1e7 for pt in points for v in pt):
                        raise ValueError('Coordinate non finite o troppo grandi.')
                    if len(points) > 2000:
                        raise ValueError('Profilo troppo complesso: massimo 2000 punti campionati.')
                    if len(points) > 1:
                        candidates.append({'id': str(len(candidates)), 'label': el.get('id',tag),
                                           'points': points, 'curved': any(s.__class__.__name__ != 'Line' for s in part),
                                           'closed': part.isclosed(), 'runs': runs})
            except Exception as e:
                raise ValueError(f'Tracciato SVG non interpretabile: {e}') from e
        for child in el:
            visit(child)
    visit(root)
    if not candidates:
        raise ValueError('Nessun tracciato vettoriale utilizzabile. Una scansione richiede ricalco e verifica manuale della scala.')
    if len(candidates) > 150 or sum(len(p['points']) for p in candidates)>20000:
        raise ValueError('Troppi tracciati: isolare la vista desiderata.')
    return {'paths': candidates, 'warnings': list(dict.fromkeys(warnings)), 'viewBox': root.get('viewBox'),
            'notice': 'Nessuna scala dedotta. Selezionare solo i profili del prodotto; escludere quote, assi e linee nascoste.'}
