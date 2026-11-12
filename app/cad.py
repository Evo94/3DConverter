"""OpenCascade solids of revolution; valid BRep required before any export."""
import cadquery as cq


def build(section):
    factor = section['factor']
    def coords(points):
        return [(r*factor,z*factor) for r,z in points]
    outer = coords(section['outer'])
    inner = coords(section['inner']) if section['inner'] else None
    w = cq.Workplane('XZ').moveTo(*outer[0])
    current = outer[0]
    def line(w, point):
        nonlocal current
        if abs(point[0]-current[0])+abs(point[1]-current[1]) > 1e-8:
            w = w.lineTo(*point)
            current = point
        return w
    def follow(w, points, runs, reverse):
        nonlocal current
        if runs:
            n = len(points)
            runs = ([{'start':n-1-r['end'],'end':n-1-r['start'],'curved':r['curved']} for r in reversed(runs)] if reverse else runs)
        else:
            runs = [{'start':0,'end':len(points)-1,'curved':section['curved']}]
        for run in runs:
            clean = []
            previous = current
            for p in points[run['start']+1:run['end']+1]:
                if abs(p[0]-previous[0])+abs(p[1]-previous[1]) > 1e-8:
                    clean.append(p)
                    previous = p
            if run['curved'] and len(clean) > 2:
                w = w.spline(clean, includeCurrent=True)
                current = clean[-1]
            else:
                for p in clean:
                    w = line(w,p)
        return w
    try:
        w = follow(w,outer,section['outer_runs'],section['outer_reversed'])
        if inner:
            w = line(w,inner[-1])
            w = follow(w,list(reversed(inner)),section['inner_runs'],not section['inner_reversed'])
            w = line(w,(0,inner[0][1]))
            w = line(w,(0,outer[0][1]))
        else:
            w = line(w,(0,outer[-1][1]))
            w = line(w,(0,outer[0][1]))
        result = w.close().revolve(360,(0,0),(0,1)).val()
        if not result.isValid() or len(result.Solids()) != 1 or result.Volume() <= 0:
            raise ValueError('Il risultato non è un singolo solido valido.')
        return result
    except Exception as e:
        raise ValueError(f'Costruzione CAD fallita: correggere il profilo. {e}') from e


def mesh(solid):
    vertices, triangles = solid.tessellate(0.08,0.15)
    return {'vertices':[[v.x,v.y,v.z] for v in vertices], 'triangles':[list(t) for t in triangles]}
