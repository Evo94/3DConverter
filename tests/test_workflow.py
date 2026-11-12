from pathlib import Path
from io import BytesIO
import math
import pytest
import trimesh
import cadquery as cq
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.importer import read_svg
from app.interpretation import Parameters, interpret
from app.cad import build
from app.main import app

client = TestClient(app)
ROOT = Path(__file__).parent.parent

def params(name='vase', **kw):
    values=dict(svg=(ROOT/'examples'/f'{name}.svg').read_text(),outer='0',inner='1',axis=30,scale=1,min_wall=2)
    values.update(kw)
    return Parameters(**values)

def section(p):
    return interpret(read_svg(p.svg),p)

@pytest.mark.parametrize('name,inner,solid', [('vase','1',False),('curves','1',False),('solid',None,True)])
def test_valid_solids(name,inner,solid):
    p=params(name,inner=inner,solid_confirmed=solid)
    s=build(section(p))
    assert s.isValid() and len(s.Solids())==1 and s.Volume()>0

def test_cylinder_dimensions_volume():
    s=section(params())
    assert s['dimensions']['target_diameter_mm']==100
    assert s['dimensions']['target_height_mm']==160
    assert s['dimensions']['section_min_wall_mm']==6
    assert build(s).Volume()==pytest.approx(math.pi*(50**2*160-44**2*154),rel=1e-8)

@pytest.mark.parametrize('value',[0,-1,float('nan'),float('inf')])
def test_bad_scale(value):
    with pytest.raises(ValidationError): params('wrong-scale',scale=value)

def test_wrong_scale_violates_min_wall():
    with pytest.raises(ValueError,match='Spessore'): section(params('wrong-scale',scale=.01))

def test_invalid_profile():
    with pytest.raises(ValueError,match='monotona'): section(params('invalid',inner=None,solid_confirmed=True))

def test_missing_inner_no_guess():
    with pytest.raises(ValueError,match='confermare'): section(params(inner=None))

def test_missing_axis_scale():
    p=params().model_dump();p.pop('axis');p.pop('scale')
    assert client.post('/api/model',json=p).status_code==422

def test_missing_axis_on_wrong_side():
    with pytest.raises(ValueError,match='destra'): section(params(axis=100))

def test_incompatible_open_profiles():
    with pytest.raises(ValueError,match='stessa altezza'):
        section(params(corrections={'1':[[74,174],[74,21]]}))

def test_closed_profile_rejected():
    with pytest.raises(ValueError): section(params(corrections={'0':[[80,180],[80,20],[30,20],[80,180]]}))

def test_intersection():
    with pytest.raises(ValueError): section(params(corrections={'1':[[84,174],[74,20]]}))

def test_shrink_is_optional_and_explicit():
    plain=section(params(shrink_percent=12))
    compensated=section(params(shrink_enabled=True,shrink_percent=12))
    assert plain['factor']==1
    assert compensated['dimensions']['model_height_mm']==pytest.approx(160/.88)
    with pytest.raises(ValueError,match='ritiro'): section(params(shrink_enabled=True))

def test_units():
    assert section(params(units='cm',scale=.1,min_wall=.2))['dimensions']['target_height_mm']==160

@pytest.mark.parametrize('text', ['<svg><image href="scan.png"/></svg>','<svg><g transform="translate(3)"><path d="M0 0L1 1"/></g></svg>', '<!DOCTYPE svg><svg/>','not an svg'])
def test_unsupported_import(text):
    with pytest.raises(ValueError): read_svg(text)

def test_subpaths_separated_and_text_not_geometry():
    d=read_svg('<svg><text>100 mm</text><path d="M80 180L80 20 M74 174L74 20"/></svg>')
    assert len(d['paths'])==2 and d['warnings']

def test_upload():
    r=client.post('/api/import',files={'file':('test.svg',params().svg,'image/svg+xml')})
    assert r.status_code==200 and len(r.json()['paths'])==3
    r=client.post('/api/import',files={'file':('scan.pdf',b'%PDF not svg','application/pdf')})
    assert r.status_code==422

@pytest.mark.parametrize('name', ['vase','curves','solid'])
def test_model_and_exports(tmp_path,name):
    payload=params(name,inner=None if name=='solid' else '1',solid_confirmed=name=='solid').model_dump()
    r=client.post('/api/model',json=payload)
    assert r.status_code==200,r.text
    assert r.json()['triangles'] and r.json()['dimensions']['model_height_mm']==pytest.approx(160)
    stl=client.post('/api/export/stl',json=payload)
    assert stl.status_code==200,stl.text
    mesh=trimesh.load(BytesIO(stl.content),file_type='stl',force='mesh')
    assert mesh.is_watertight and mesh.is_volume
    step=client.post('/api/export/step',json=payload)
    assert step.status_code==200,step.text
    f=tmp_path/'model.step';f.write_bytes(step.content)
    solid=cq.importers.importStep(str(f)).val()
    assert solid.isValid() and len(solid.Solids())==1
    assert client.post('/api/export/obj',json=payload).status_code==400

def test_project_roundtrip():
    p=params('curves',shrink_percent=8,shrink_enabled=True)
    restored=Parameters.model_validate_json(p.model_dump_json())
    assert build(section(restored)).Volume()==pytest.approx(build(section(p)).Volume())

def test_no_export_invalid():
    p=params('invalid',inner=None,solid_confirmed=True)
    assert client.post('/api/export/stl',json=p.model_dump()).status_code==422


def test_nonfinite_svg_rejected():
    with pytest.raises(ValueError): read_svg('<svg><path d="M 1e999 20 L 80 180"/></svg>')

def test_curve_segment_boundaries_retained():
    svg='<svg><path d="M60 180 L80 140 C100 100 70 60 60 20"/></svg>'
    p=params(svg=svg,inner=None,solid_confirmed=True)
    s=section(p)
    assert len(s['outer_runs'])==2
    assert not s['outer_runs'][0]['curved']
    assert build(s).isValid()
