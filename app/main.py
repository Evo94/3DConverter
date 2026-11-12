from pathlib import Path
from tempfile import TemporaryDirectory
import threading
from io import BytesIO
import trimesh
import cadquery as cq
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from .importer import read_svg, MAX_SIZE
from .interpretation import Parameters, interpret
from .cad import build, mesh

app = FastAPI(title='Forma · Ceramic CAD')
lock = threading.Lock()

def error(e):
    return HTTPException(422, str(e))

@app.post('/api/import')
async def upload(file: UploadFile = File(...)):
    raw = await file.read(MAX_SIZE+1)
    if len(raw) > MAX_SIZE:
        raise error('File troppo grande (massimo 1 MB).')
    try:
        text = raw.decode('utf-8-sig')
        return {**read_svg(text), 'svg':text}
    except (ValueError, UnicodeError) as e:
        raise error(e)

@app.post('/api/model')
def model(p: Parameters):
    try:
        with lock:
            section = interpret(read_svg(p.svg),p)
            solid = build(section)
            box = solid.BoundingBox()
            section['dimensions']['model_diameter_mm'] = max(box.xlen,box.ylen)
            section['dimensions']['model_height_mm'] = box.zlen
            return {**mesh(solid), 'dimensions':section['dimensions'], 'volume_mm3':solid.Volume(),
                    'warnings':['Curve SVG approssimate con spline interpolate; verificare la fedeltà prima della produzione.',
                                'Lo spessore minimo è verificato sulla sezione campionata, non certificato sul BRep.']}
    except Exception as e:
        raise error(e)

@app.post('/api/export/{kind}')
def export(kind: str, p: Parameters):
    if kind not in ('step','stl'):
        raise HTTPException(400,'Formato non supportato.')
    try:
        with lock, TemporaryDirectory() as tmp:
            solid = build(interpret(read_svg(p.svg),p))
            path = str(Path(tmp)/f'forma.{kind}')
            cq.exporters.export(solid,path,exportType=kind.upper(), tolerance=0.08, angularTolerance=0.15)
            content = Path(path).read_bytes()
            if kind == 'stl':
                exported = trimesh.load(BytesIO(content),file_type='stl',force='mesh')
                if not exported.is_watertight or not exported.is_volume:
                    raise ValueError('La mesh STL esportata non è un volume chiuso orientato. Esportazione bloccata.')
            else:
                restored = cq.importers.importStep(path).val()
                if not restored.isValid() or len(restored.Solids()) != 1:
                    raise ValueError('STEP riletto non valido. Esportazione bloccata.')
            return Response(content,media_type='application/octet-stream',
                            headers={'Content-Disposition':f'attachment; filename="forma.{kind}"'})
    except Exception as e:
        raise error(e)

@app.get('/api/examples/{name}')
def example(name: str):
    if name not in ('vase','solid','curves','invalid','wrong-scale'):
        raise HTTPException(404)
    return Response((Path(__file__).parent.parent/'examples'/f'{name}.svg').read_text(),media_type='image/svg+xml')

web = Path(__file__).parent.parent/'web'/'dist'
if web.exists():
    app.mount('/',StaticFiles(directory=web,html=True),name='web')
