"""Explicit axisymmetric interpretation, independent of CAD or transport."""
import math
from shapely.geometry import Polygon, LineString
from pydantic import BaseModel, Field

class Parameters(BaseModel):
    svg: str = Field(max_length=1_000_000)
    outer: str
    inner: str | None = None
    axis: float
    units: str = 'mm'
    scale: float = Field(gt=0, le=10000)  # chosen units per SVG unit
    min_wall: float = Field(gt=0, le=10000) # chosen units
    shrink_enabled: bool = False
    shrink_percent: float | None = Field(default=None, ge=0, lt=50)
    solid_confirmed: bool = False
    corrections: dict[str, list[list[float]]] = Field(default_factory=dict)


def interpret(data, params):
    if params.units not in ('mm', 'cm', 'in'):
        raise ValueError('Unità non supportata.')
    factor = params.scale * {'mm':1,'cm':10,'in':25.4}[params.units]
    if not math.isfinite(params.axis):
        raise ValueError('Asse mancante o non finito.')
    if params.shrink_enabled and params.shrink_percent is None:
        raise ValueError('Specificare il ritiro: nessun valore universale è assunto.')
    shrink = 1/(1-params.shrink_percent/100) if params.shrink_enabled else 1
    paths = {p['id']:p for p in data['paths']}
    def profile(key):
        if key not in paths:
            raise ValueError('Selezionare un profilo esistente.')
        pts = params.corrections.get(key, paths[key]['points'])
        if not 2 <= len(pts) <= 2000 or any(len(p)!=2 or not all(math.isfinite(v) for v in p) for p in pts):
            raise ValueError('Coordinate del profilo non valide.')
        pts = [((x-params.axis)*factor, -y*factor) for x,y in pts]
        if any(r < -1e-7 for r,z in pts):
            raise ValueError('Il profilo deve stare a destra dell’asse; correggere asse o contorno.')
        if pts[0][1] > pts[-1][1]:
            pts.reverse()
        if any(b[1] < a[1]-1e-7 for a,b in zip(pts,pts[1:])):
            raise ValueError('Profilo ambiguo: questo MVP richiede altezza monotona dal fondo al bordo, senza sottosquadri verticali.')
        if not LineString(pts).is_simple:
            raise ValueError('Profilo auto-intersecante.')
        return pts
    outer = profile(params.outer)
    inner = profile(params.inner) if params.inner is not None else None
    if inner and params.inner == params.outer:
        raise ValueError('Profili interno ed esterno devono essere distinti.')
    if not inner and not params.solid_confirmed:
        raise ValueError('Profilo interno assente: confermare esplicitamente un oggetto pieno oppure selezionare l’interno. Nessuno spessore viene inventato.')
    height = outer[-1][1]-outer[0][1]
    if height <= 1e-5:
        raise ValueError('Altezza nulla: asse o profilo errato.')
    if inner:
        if abs(outer[-1][1]-inner[-1][1]) > 0.01 or inner[0][1] <= outer[0][1]:
            raise ValueError('I bordi devono avere la stessa altezza e il fondo interno deve essere sopra quello esterno. Correggere i profili aperti.')
        if any(r <= 0 for r,z in inner):
            raise ValueError('Il profilo interno deve rimanere a destra dell’asse.')
        wall = min(LineString(outer).distance(LineString(inner)), inner[0][1]-outer[0][1])
        if wall + 1e-6 < params.min_wall * {'mm':1,'cm':10,'in':25.4}[params.units]:
            raise ValueError(f'Spessore sotto il minimo richiesto (stima sezionale: {wall:.3f} mm).')
        ring = outer + list(reversed(inner)) + [(0,inner[0][1]),(0,outer[0][1])]
    else:
        wall = None
        ring = outer + [(0,outer[-1][1]),(0,outer[0][1])]
    polygon = Polygon(ring)
    if not polygon.is_valid or polygon.area <= 1e-8:
        raise ValueError('Sezione aperta, auto-intersecante o degenerata: correggere i contorni.')
    return {'outer':outer,'inner':inner,'ring':ring,'factor':shrink,
            'dimensions':{'target_diameter_mm':2*max(r for r,z in outer), 'target_height_mm':height,
                          'model_diameter_mm':2*max(r for r,z in outer)*shrink, 'model_height_mm':height*shrink,
                          'section_min_wall_mm':wall},
            'outer_runs': paths[params.outer]['runs'] if len(outer)==len(paths[params.outer]['points']) else None,
            'outer_reversed': params.corrections.get(params.outer, paths[params.outer]['points'])[0][1] < params.corrections.get(params.outer, paths[params.outer]['points'])[-1][1],
            'inner_runs': paths[params.inner]['runs'] if inner and len(inner)==len(paths[params.inner]['points']) else None,
            'inner_reversed': bool(inner) and params.corrections.get(params.inner, paths[params.inner]['points'])[0][1] < params.corrections.get(params.inner, paths[params.inner]['points'])[-1][1],
            'curved':paths[params.outer]['curved'] or (inner is not None and paths[params.inner]['curved'])}
