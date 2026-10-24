"""Blender 4.5 / MPFB build: actual skinned humans, CC0 skin and face targets.

Run with Blender --background --factory-startup --python this_file -- [actor-id].
Sources are installed in runtime/human-build; never edits original role cards.
"""
import sys,json,hashlib,math,struct,os
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from card_identity_presets import PRESETS

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

OUT=Path(os.getenv('CLINICAL_AVATAR_OUTPUT',str(ROOT/'runtime/card-avatar-candidate')));OUT.mkdir(parents=True,exist_ok=True)
FACE=['jawOpen','eyeBlinkLeft','eyeBlinkRight','mouthSmileLeft','mouthSmileRight','viseme_aa','viseme_O','viseme_PP','viseme_E','viseme_I','viseme_U']

def linear_color(color):
    rgb=[int(color[i:i+2],16)/255 for i in (1,3,5)]
    return tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb)

def recolor(obj,color):
    rgb=linear_color(color)
    for old in list(obj.data.materials):
        if old:
            mat=old.copy();mat.use_nodes=True;bs=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
            if bs:
                for link in list(bs.inputs['Base Color'].links):mat.node_tree.links.remove(link)
                bs.inputs['Base Color'].default_value=(*rgb,1);bs.inputs['Roughness'].default_value=.68
            obj.data.materials[obj.data.materials.find(old.name)]=mat

def attach(obj,rig,bone='head'):
    vg=obj.vertex_groups.new(name=bone);vg.add(list(range(len(obj.data.vertices))),1,'REPLACE')
    m=obj.modifiers.new('Accessory skeleton','ARMATURE');m.object=rig;obj.parent=rig

def tube(name,points,radius,color,rig,bone='head'):
    bpy.ops.object.select_all(action='DESELECT')
    c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=radius;c.bevel_resolution=3
    s=c.splines.new('POLY');s.points.add(len(points)-1)
    for p,v in zip(s.points,points):p.co=(*v,1)
    o=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(o)
    bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.convert(target='MESH');o=bpy.context.object
    mat=bpy.data.materials.new(name+' finish');mat.diffuse_color=(*linear_color(color),1);o.data.materials.append(mat)
    attach(o,rig,bone);return o

def accessories(base,rig,preset,actor):
    # Eyes are fitted by MPFB; derive glasses position from the actual eye meshes.
    if preset['glasses']:
        eyes=[o for o in bpy.context.scene.objects if o.type=='MESH' and 'high-poly' in o.name]
        pts=[o.matrix_world@v.co for o in eyes for v in o.data.vertices]
        if pts:
            z=sum(v.z for v in pts)/len(pts);front=min(v.y for v in pts)-.014
            width=max(v.x for v in pts)-min(v.x for v in pts);cx=width*.25;rx=width*.235;rz=rx*.58
            for sign in (-1,1):
                ps=[(sign*cx+rx*math.copysign(abs(math.cos(t*math.tau/48))**.55,math.cos(t*math.tau/48)),front,z+rz*math.copysign(abs(math.sin(t*math.tau/48))**.55,math.sin(t*math.tau/48))) for t in range(49)]
                tube('Card glasses lens frame',ps,.0025,'#393a35',rig)
                tube('Card glasses temple',[(sign*(cx+rx),front,z),(sign*(cx+rx+.005),front+.11,z)],.0023,'#393a35',rig)
            tube('Card glasses bridge',[(-cx+rx,front,z+.005),(cx-rx,front,z+.005)],.0023,'#393a35',rig)
    if actor['kind'] in ('clinician','support'):
        # ID is real volumetric geometry, attached to the torso bone.
        head=rig.data.bones['head'].head_local;shoulder=rig.data.bones['spine01'].head_local
        z=shoulder.z-.08
        bpy.ops.mesh.primitive_cube_add(size=1,location=(.085,-.127,z));badge=bpy.context.object;badge.name='Card clinical ID badge';badge.scale=(.045,.007,.064);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        mat=bpy.data.materials.new('ID white');mat.diffuse_color=(.92,.95,.97,1);badge.data.materials.append(mat);attach(badge,rig,'spine01')
        if actor['id']=='wang-pt':
            tube('Card green rehabilitation strap',[(.17,-.10,z+.22),(.12,-.15,z+.05),(.04,-.15,z-.22)],.018,preset['accent'],rig,'spine01')
        if actor['profession'] in ('MD','RN','DT','PT'):
            neck=rig.data.bones['neck01'].head_local.z
            tube('Card stethoscope',[(-.045,-.07,neck),(-.09,-.13,neck-.07),(-.085,-.17,z+.05),(-.045,-.18,z-.04),(0,-.18,z-.06),(.05,-.17,z-.02),(.09,-.15,z+.07),(.06,-.08,neck-.01)],.005,'#293b48',rig,'spine01')

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

def wardrobe_details(obj,rig,preset):
    chest=rig.data.bones['spine01'].head_local.z;neck=rig.data.bones['neck01'].head_local.z
    def material(name,color):
        m=bpy.data.materials.new(name);m.diffuse_color=(*linear_color(color),1);obj.data.materials.append(m);return len(obj.data.materials)-1
    inside=material('Card inner shirt',preset['accent']);trousers=material('Card trousers','#2e3744');tie=material('Card tie','#294568')
    texture=None
    if preset['clothes']=='male_elegantsuit01':
        image=bpy.data.images.load(str(ASSETS/'clothes/male_elegantsuit01/male_elegantsuit01_diffuse.png'),check_existing=True)
        texture=np.array(image.pixels[:],dtype=np.float32).reshape(image.size[1],image.size[0],4)
    uv_layer=obj.data.uv_layers.active
    for poly in obj.data.polygons:
        c=sum((obj.data.vertices[i].co for i in poly.vertices),Vector())/len(poly.vertices)
        if c.z<chest-.35:poly.material_index=trousers
        elif preset['coat'] and texture is not None and uv_layer:
            uv=sum((uv_layer.data[i].uv for i in poly.loop_indices),Vector((0,0)))/len(poly.loop_indices)
            x=min(texture.shape[1]-1,max(0,int(uv.x*texture.shape[1])));y=min(texture.shape[0]-1,max(0,int(uv.y*texture.shape[0])))
            color=texture[y,x,:3]
            if min(color)>.42:poly.material_index=inside
            elif .35<uv.x<.43 and .8<uv.y<.96 and color[2]>color[0]*1.15:poly.material_index=tie
        elif not preset['coat'] and c.z>neck-.07 and c.y<-.04:poly.material_index=inside

def build(actor):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    preset=PRESETS[actor['id']];male=actor['gender']=='male';age=actor.get('age_group','成人')
    skin_age='old' if preset['age']>.72 else 'middleage' if preset['age']>.5 else 'young'
    macro=TargetService.get_default_macro_info_dict()
    macro.update(gender=1.0 if male else 0.0,age=preset['age'],height=.67 if male else .54,weight=preset['weight'],muscle=.48)
    macro['race']={'asian':1.0,'caucasian':0.0,'african':0.0}
    base=HumanService.create_human(macro_detail_dict=macro);base.name='HumanBody'
    TargetService.bulk_load_targets(base,[{'target':preset['shape'],'value':preset['shape_weight']}])
    proportions=json.loads((ROOT/'data/characters/card-face-proportions.json').read_text(encoding='utf-8'))[actor['id']]
    # Modest controls preserve anatomical depth while matching observed card ratios.
    def bounded(x):return max(0,min(.4,x))
    controls=[{'target':'head-scale-vert-decr','value':bounded((1.36-proportions['head_aspect'])*1.2)},
              {'target':'head-scale-horiz-incr','value':bounded((.67-proportions['eye_spacing'])*2)},
              {'target':'mouth-scale-horiz-incr','value':bounded((proportions['mouth_width']-.35)*2)}]
    TargetService.bulk_load_targets(base,controls)
    rig=HumanService.add_builtin_rig(base,'default');rig.name='ClinicalHumanRig'
    skin=f"{skin_age}_asian_{'male' if male else 'female'}"
    HumanService.set_character_skin(str(ASSETS/'skins'/skin/(skin+'.mhmat')),base,skin_type='GAMEENGINE')
    TargetService.bulk_load_targets(base,[{'target':f,'value':0.0} for f in FACE])
    equip(base,'eyes','high-poly')
    equip(base,'teeth','teeth_base')
    tongue_dirs=[p for p in (ASSETS/'tongue').iterdir() if p.is_dir()]
    if tongue_dirs:equip(base,'tongue',tongue_dirs[0].name)
    hair=preset['hair']
    before=set(bpy.context.scene.objects);equip(base,'hair',hair)
    for obj in set(bpy.context.scene.objects)-before:
        if obj.type=='MESH':recolor(obj,preset['hair_color'])
    equip(base,'eyebrows','eyebrow004')
    equip(base,'eyelashes','eyelashes01')
    clothing=preset['clothes']
    before=set(bpy.context.scene.objects);equip(base,'clothes',clothing)
    for obj in set(bpy.context.scene.objects)-before:
        if obj.type=='MESH':recolor(obj,preset['color']);wardrobe_details(obj,rig,preset)
    equip(base,'clothes','shoes01')
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
    accessories(base,rig,preset,actor)
    rig.scale=(1.1,1.1,1.1)
    rig['clinical_actor_id']=actor['id'];rig['asset_license']='CC0-1.0';rig['visual_type']='skinned-realistic-human'
    if os.getenv('CLINICAL_FACE_PREP')=='1':
        from card_face_fit import prepare_render
        prepare_render(base,rig,actor,ROOT)
    for o in bpy.context.scene.objects:o.select_set(True)
    bpy.context.view_layer.objects.active=rig
    path=OUT/(actor['id']+'.glb')
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_animations=False,
        export_skins=True,export_morph=True,export_morph_normal=True,export_extras=True,export_apply=False,export_image_format='AUTO')
    # MPFB uses alpha blending for all game materials; opaque skin/clothes must write depth.
    raw=path.read_bytes();json_size=struct.unpack_from('<I',raw,12)[0];gltf=json.loads(raw[20:20+json_size])
    for mat in gltf['materials']:
        name=mat.get('name','')
        mat['alphaMode']='MASK' if any(x in name.lower() for x in ('short','bob','long','ponytail','eyebrow','eyelash')) else 'BLEND' if 'high-poly' in name else 'OPAQUE'
        if mat['alphaMode']=='MASK':mat['alphaCutoff']=.35
    encoded=json.dumps(gltf,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%4)
    binary=raw[20+json_size:];path.write_bytes(struct.pack('<4sII',b'glTF',2,20+len(encoded)+len(binary))+struct.pack('<I4s',len(encoded),b'JSON')+encoded+binary)
    record={'actor_id':actor['id'],'file':'card-matched-v3/'+path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'bytes':path.stat().st_size,'skin':skin,'hair':hair,'clothes':clothing,'license':'CC0-1.0',
        'source':'MakeHuman/MPFB core and CC0 system assets; faceunits01 and visemes02',
        'bones':len(rig.data.bones),'morph_targets':FACE,'geometry':'anatomical skinned mesh; no portrait plane',
        'card_sha256':actor['card_sha256'],'appearance_preset':preset,'reference_face_proportions':proportions,'face_controls':controls,'likeness_status':'artistic reconstruction from card; visual review required'}
    (OUT/(actor['id']+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CLINICAL_HUMAN_BUILT '+json.dumps(record,ensure_ascii=False),flush=True)

if __name__=='__main__':
    ids=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    actors=json.loads((ROOT/'data/characters/catalog.json').read_text(encoding='utf-8'))['actors']
    for actor in actors:
        if ids and actor['id'] not in ids:continue
        build(actor)
