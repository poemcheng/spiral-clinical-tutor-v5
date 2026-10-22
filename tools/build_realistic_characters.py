"""Blender 4.5 / MPFB build: actual skinned humans, CC0 skin and face targets.

Run with Blender --background --factory-startup --python this_file -- [actor-id].
Sources are installed in runtime/human-build; never edits original role cards.
"""
import sys,json,hashlib,math,struct
from pathlib import Path
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'runtime/human-build';ASSETS=BUILD/'assets'
sys.path.insert(0,str(BUILD/'mpfb2-master/src'))
# Isolate this batch build from the user's installed Blender extension settings.
bpy.utils.extension_path_user=lambda *args,**kwargs:str(BUILD/'user')
import mpfb
bpy.context.preferences.addons.new().module='mpfb'
mpfb.register()
from mpfb.services.humanservice import HumanService
from mpfb.services.targetservice import TargetService
from mpfb.services.faceservice import FaceService
from mpfb.services.locationservice import LocationService
LocationService._user_data=str(ASSETS)

OUT=ROOT/'data/characters/realistic-v1';OUT.mkdir(exist_ok=True)
FACE=['jawOpen','eyeBlinkLeft','eyeBlinkRight','mouthSmileLeft','mouthSmileRight','viseme_aa','viseme_O','viseme_PP']

def coordinates(data):
    a=np.zeros(len(data)*3,dtype=np.float32);data.foreach_get('co',a);return a.reshape(-1,3)

def bake_phenotype(obj):
    if not obj.data.shape_keys:return
    keys=obj.data.shape_keys.key_blocks
    deltas={k.name:coordinates(k.data)-coordinates(k.relative_key.data) for k in keys if k.name.removeprefix('!ex-') in FACE}
    mixed=obj.shape_key_add(name='Baked phenotype',from_mix=True)
    co=coordinates(mixed.data);obj.shape_key_clear();obj.data.vertices.foreach_set('co',co.ravel());obj.data.update()
    obj.shape_key_add(name='Basis',from_mix=False)
    for name,delta in deltas.items():obj.shape_key_add(name=name,from_mix=False).data.foreach_set('co',(co+delta).ravel())

def bake_masks(obj):
    masks=[m for m in obj.modifiers if m.type=='MASK']
    if not masks:return
    shapes={k.name:coordinates(k.data) for k in obj.data.shape_keys.key_blocks} if obj.data.shape_keys else {}
    for k in obj.data.shape_keys.key_blocks if obj.data.shape_keys else []:k.value=0
    index=obj.data.attributes.new('_source_vertex','INT','POINT')
    index.data.foreach_set('value',np.arange(len(obj.data.vertices),dtype=np.int32))
    states={m.name:m.show_viewport for m in obj.modifiers}
    for m in obj.modifiers:m.show_viewport=m.type=='MASK'
    deps=bpy.context.evaluated_depsgraph_get();deps.update()
    evaluated=obj.evaluated_get(deps)
    mesh=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=deps)
    ids=np.zeros(len(mesh.vertices),dtype=np.int32);mesh.attributes['_source_vertex'].data.foreach_get('value',ids)
    obj.shape_key_clear();obj.data=mesh
    for m in list(obj.modifiers):
        if m.type=='MASK':obj.modifiers.remove(m)
        else:m.show_viewport=states[m.name]
    for name,co in shapes.items():
        key=obj.shape_key_add(name=name,from_mix=False);key.data.foreach_set('co',co[ids].ravel())
    mesh.attributes.remove(mesh.attributes['_source_vertex'])
    mesh.update()

def equip(base,kind,name):
    path=ASSETS/kind/name/(name+'.mhclo')
    return HumanService.add_mhclo_asset(str(path),base,asset_type={'hair':'Hair','eyes':'Eyes','eyebrows':'Eyebrows','eyelashes':'Eyelashes','teeth':'Teeth','tongue':'Tongue'}.get(kind,'Clothes'),subdiv_levels=0,material_type='GAMEENGINE')

def build(actor):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    male=actor['gender']=='male';age=actor.get('age_group','成人')
    skin_age='old' if age=='高齡' else 'middleage' if age=='中年' else 'young'
    macro=TargetService.get_default_macro_info_dict()
    macro.update(gender=1.0 if male else 0.0,age=.82 if age=='高齡' else .58 if age=='中年' else .35,height=.67 if male else .54,weight=.46,muscle=.48)
    macro['race']={'asian':1.0,'caucasian':0.0,'african':0.0}
    base=HumanService.create_human(macro_detail_dict=macro);base.name='HumanBody'
    rig=HumanService.add_builtin_rig(base,'default');rig.name='ClinicalHumanRig'
    skin=f"{skin_age}_asian_{'male' if male else 'female'}"
    HumanService.set_character_skin(str(ASSETS/'skins'/skin/(skin+'.mhmat')),base,skin_type='GAMEENGINE')
    TargetService.bulk_load_targets(base,[{'target':f,'value':0.0} for f in FACE])
    equip(base,'eyes','high-poly')
    equip(base,'teeth','teeth_base')
    tongue_dirs=[p for p in (ASSETS/'tongue').iterdir() if p.is_dir()]
    if tongue_dirs:equip(base,'tongue',tongue_dirs[0].name)
    hair='short02' if male else 'bob01'
    equip(base,'hair',hair)
    equip(base,'eyebrows','eyebrow004')
    equip(base,'eyelashes','eyelashes01')
    clothing='male_casualsuit01' if male else 'female_casualsuit01'
    if actor['profession']=='PT' and male:clothing='male_casualsuit04'
    equip(base,'clothes',clothing);equip(base,'clothes','shoes01')
    FaceService.interpolate_targets(base)
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    for obj in meshes:
        bake_phenotype(obj)
        bake_masks(obj)
        for p in obj.data.polygons:p.use_smooth=True
        for m in list(obj.modifiers):
            if m.type=='SUBSURF':obj.modifiers.remove(m)
        if obj.data.shape_keys:
            for key in obj.data.shape_keys.key_blocks:
                key.value=0;key.name=key.name.removeprefix('!ex-')
    for image in bpy.data.images:
        limit=2048 if 'lightskinned' in image.name or 'darkskinned' in image.name else 512
        if max(image.size)>limit:
            factor=limit/max(image.size);image.scale(round(image.size[0]*factor),round(image.size[1]*factor))
    rig.scale=(1.1,1.1,1.1)
    rig['clinical_actor_id']=actor['id'];rig['asset_license']='CC0-1.0';rig['visual_type']='skinned-realistic-human'
    for o in bpy.context.scene.objects:o.select_set(True)
    bpy.context.view_layer.objects.active=rig
    path=OUT/(actor['id']+'.glb')
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_animations=False,
        export_skins=True,export_morph=True,export_morph_normal=True,export_extras=True,export_apply=False,export_image_format='AUTO')
    # MPFB uses alpha blending for all game materials; opaque skin/clothes must write depth.
    raw=path.read_bytes();json_size=struct.unpack_from('<I',raw,12)[0];gltf=json.loads(raw[20:20+json_size])
    for mat in gltf['materials']:
        name=mat.get('name','')
        mat['alphaMode']='MASK' if any(x in name for x in ('short02','bob01','eyebrow','eyelash')) else 'BLEND' if 'high-poly' in name else 'OPAQUE'
        if mat['alphaMode']=='MASK':mat['alphaCutoff']=.35
    encoded=json.dumps(gltf,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%4)
    binary=raw[20+json_size:];path.write_bytes(struct.pack('<4sII',b'glTF',2,20+len(encoded)+len(binary))+struct.pack('<I4s',len(encoded),b'JSON')+encoded+binary)
    record={'actor_id':actor['id'],'file':'realistic-v1/'+path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'bytes':path.stat().st_size,'skin':skin,'hair':hair,'clothes':clothing,'license':'CC0-1.0',
        'source':'MakeHuman/MPFB core and CC0 system assets; faceunits01 and visemes02',
        'bones':len(rig.data.bones),'morph_targets':FACE,'geometry':'anatomical skinned mesh; no portrait plane'}
    (OUT/(actor['id']+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CLINICAL_HUMAN_BUILT '+json.dumps(record,ensure_ascii=False),flush=True)

if __name__=='__main__':
    ids=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    actors=json.loads((ROOT/'data/characters/catalog.json').read_text(encoding='utf-8'))['actors']
    for actor in actors:
        if ids and actor['id'] not in ids:continue
        build(actor)
