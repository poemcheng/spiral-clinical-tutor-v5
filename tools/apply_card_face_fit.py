"""Blender: deform a rigged head and bake card appearance onto its skin UVs."""
import sys,json,math,hashlib,struct,os
from collections import Counter
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from card_identity_presets import PRESETS

def points(data):
    out=np.empty(len(data)*3,dtype=np.float32);data.foreach_get('co',out);return out.reshape(-1,3)

def inside_polygon(x,y,polygon):
    inside=False;j=len(polygon)-1
    for i in range(len(polygon)):
        xi,yi=polygon[i];xj,yj=polygon[j]
        if (yi>y)!=(yj>y) and x<(xj-xi)*(y-yi)/(yj-yi)+xi:inside=not inside
        j=i
    return inside

def edge_distance(point,polygon):
    p=np.array(point);a=np.array(polygon);b=np.roll(a,-1,axis=0);delta=b-a
    t=np.clip(np.sum((p-a)*delta,axis=1)/(np.sum(delta*delta,axis=1)+1e-12),0,1)
    return float(np.linalg.norm(p-(a+delta*t[:,None]),axis=1).min())

def fit_mesh(obj,fit,projection):
    matrix=np.array(obj.matrix_world);inverse=np.linalg.inv(matrix)
    source=np.array(fit['points']);weights=np.array(fit['weights']);affine=np.array(fit['affine'])
    scale=projection['ortho_scale'];center=projection['center_z']
    def warp(co):
        world=np.column_stack([co,np.ones(len(co))])@matrix.T
        uv=np.column_stack([world[:,0]/scale+.5,.5-(world[:,2]-center)/scale])
        dist=np.linalg.norm(uv[:,None,:]-source[None,:,:],axis=2)
        delta=(dist**2*np.log(dist+1e-9))@weights+np.column_stack([np.ones(len(uv)),uv])@affine
        delta=np.clip(delta,-.12,.12)
        # Front and temple surface move; the back of the head and neck stay stable.
        front=np.clip((.045-world[:,1])/.09,0,1)
        head=np.clip((world[:,2]-projection['neck']-.025)/.055,0,1)
        factor=front*head
        world[:,0]+=delta[:,0]*scale*factor;world[:,2]-=delta[:,1]*scale*factor
        return (world@inverse.T)[:,:3].astype(np.float32)
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:key.data.foreach_set('co',warp(points(key.data)).ravel())
        obj.data.vertices.foreach_set('co',points(obj.data.shape_keys.key_blocks[0].data).ravel())
    else:obj.data.vertices.foreach_set('co',warp(points(obj.data.vertices)).ravel())
    obj.data.update()

def bake_face(base,fit,projection,directory):
    mesh=base.data;original_name=mesh.uv_layers.active.name
    reference_name=mesh.uv_layers.new(name='ReferenceCardProjection').name
    colors=mesh.color_attributes.new(name='ReferenceFaceMask',type='FLOAT_COLOR',domain='CORNER')
    reference_uv=mesh.uv_layers[reference_name]
    source_image=bpy.data.images.load(str(ROOT/'data/characters'/fit['source_card']),check_existing=True)
    rotation=np.array(fit['reference_rotation']);rc=np.array(fit['reference_eye_center_px']);dc=np.array(fit['render_eye_center']);rs=fit['reference_scale'];size=np.array(fit['reference_size'])
    scale=projection['ortho_scale'];center=projection['center_z'];polygon=fit['target_face_oval']
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            v=mesh.vertices[mesh.loops[li].vertex_index];world=base.matrix_world@v.co
            uv=np.array([world.x/scale+.5,.5-(world.z-center)/scale])
            pixel=((uv-dc)/rs)@rotation.T+rc
            reference_uv.data[li].uv=(pixel[0]/size[0],1-pixel[1]/size[1])
            front=max(0,min(1,(-world.y+.005)/.025))
            # Feather the 3D mask at the card's face oval; never paint a face on the back.
            inside=inside_polygon(*uv,polygon)
            weight=front*min(1,edge_distance(uv,polygon)/.025) if inside else 0
            colors.data[li].color=(weight,weight,weight,1)
    output=bpy.data.images.new(fit['actor_id']+' fitted reference skin',width=2048,height=2048,alpha=False)
    output.filepath_raw=str(directory/'fitted-skin.png');output.file_format='PNG'
    saved=[]
    for mat in mesh.materials:
        if not mat or not mat.use_nodes:continue
        nodes=mat.node_tree.nodes;links=mat.node_tree.links
        bs=next(n for n in nodes if n.type=='BSDF_PRINCIPLED');surface=next(n for n in nodes if n.type=='OUTPUT_MATERIAL')
        old_color=bs.inputs['Base Color'].links[0].from_socket if bs.inputs['Base Color'].links else None
        ref=nodes.new('ShaderNodeTexImage');ref.image=source_image
        uvnode=nodes.new('ShaderNodeUVMap');uvnode.uv_map=reference_name;links.new(uvnode.outputs['UV'],ref.inputs['Vector'])
        attr=nodes.new('ShaderNodeVertexColor');attr.layer_name=colors.name
        mix=nodes.new('ShaderNodeMixRGB');links.new(attr.outputs['Color'],mix.inputs[0]);links.new(ref.outputs['Color'],mix.inputs[2])
        skin=fit['skin_color_srgb'];skin=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in skin]
        mix.inputs[1].default_value=(*skin,1)
        emit=nodes.new('ShaderNodeEmission');links.new(mix.outputs[0],emit.inputs['Color']);links.new(emit.outputs[0],surface.inputs['Surface'])
        target=nodes.new('ShaderNodeTexImage');target.image=output;nodes.active=target
        saved.append((mat,bs,surface,target,emit,mix,ref,attr,uvnode))
    mesh.uv_layers.active_index=mesh.uv_layers.find(original_name);mesh.uv_layers[original_name].active_render=True
    bpy.ops.object.select_all(action='DESELECT');base.select_set(True);bpy.context.view_layer.objects.active=base
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=1;scene.render.bake.margin=12
    bpy.ops.object.bake(type='EMIT',use_clear=True)
    output.save()
    # A clean standard material avoids stale bake-node dependencies in Cycles/glTF.
    baked=bpy.data.images.load(str(directory/'fitted-skin.png'),check_existing=False)
    baked.pack()
    material=bpy.data.materials.new('Card fitted anatomical skin');material.use_nodes=True
    bs=material.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.72
    texture=material.node_tree.nodes.new('ShaderNodeTexImage');texture.image=baked
    material.node_tree.links.new(texture.outputs['Color'],bs.inputs['Base Color'])
    mesh.materials.clear();mesh.materials.append(material)
    for poly in mesh.polygons:poly.material_index=0
    # Baked result uses the original body UV and keeps skin normals/roughness.
    mesh.uv_layers.remove(mesh.uv_layers[reference_name]);mesh.color_attributes.remove(mesh.color_attributes['ReferenceFaceMask'])
    mesh.uv_layers.active_index=mesh.uv_layers.find(original_name);mesh.uv_layers[original_name].active_render=True
    return output

def linear(hex_color):
    c=[int(hex_color[i:i+2],16)/255 for i in (1,3,5)]
    return tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in c)

def reference_glasses(base,rig,fit,projection):
    paths=fit.get('reference_glasses_paths',[])
    if len(paths)!=2:return
    for obj in list(bpy.context.scene.objects):
        if 'card glasses' in obj.name.lower():bpy.data.objects.remove(obj,do_unlink=True)
    bvh=BVHTree.FromObject(base,bpy.context.evaluated_depsgraph_get());inverse=base.matrix_world.inverted()
    scale=projection['ortho_scale'];center=projection['center_z'];rig_inverse=rig.matrix_world.inverted()
    head=[base.matrix_world@v.co for v in base.data.vertices if (base.matrix_world@v.co).z>projection['neck']+.06]
    ear_y=(min(v.y for v in head)+max(v.y for v in head))/2+.025
    material=bpy.data.materials.new('Reference card glasses rim');material.diffuse_color=(.025,.022,.019,1)
    def point(uv):
        x=(uv[0]-.5)*scale;z=center+(.5-uv[1])*scale
        origin=inverse@Vector((x,-2,z));direction=(inverse.to_3x3()@Vector((0,1,0))).normalized()
        hit=bvh.ray_cast(origin,direction)[0]
        world=base.matrix_world@hit if hit else Vector((x,-.12,z))
        world.y-=.005
        return world
    def tube(name,world_points,radius=None):
        if radius is None:radius=.00065 if fit['actor_id']=='auntie-lin' else .0009
        curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D';curve.bevel_depth=radius;curve.bevel_resolution=3
        spline=curve.splines.new('POLY');spline.points.add(len(world_points)-1)
        for p,world in zip(spline.points,world_points):p.co=(*(rig_inverse@world),1)
        obj=bpy.data.objects.new(name,curve);bpy.context.collection.objects.link(obj);obj.data.materials.append(material)
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj;bpy.ops.object.convert(target='MESH');obj=bpy.context.object
        group=obj.vertex_groups.new(name='head');group.add(list(range(len(obj.data.vertices))),1,'REPLACE');modifier=obj.modifiers.new('Glasses head skeleton','ARMATURE');modifier.object=rig;obj.parent=rig
        for poly in obj.data.polygons:poly.use_smooth=True
    rims=[]
    for path in paths:
        rim=[point(uv) for uv in path];tube('Card traced glasses rim',rim+[rim[0]]);rims.append(rim)
    left=min(rims,key=lambda r:sum(p.x for p in r)/len(r));right=max(rims,key=lambda r:sum(p.x for p in r)/len(r))
    inner_left=max(left,key=lambda p:p.x);inner_right=min(right,key=lambda p:p.x)
    tube('Card traced glasses bridge',[inner_left,Vector(((inner_left.x+inner_right.x)/2,min(inner_left.y,inner_right.y)-.008,max(inner_left.z,inner_right.z)+.003)),inner_right])
    for rim,sign in [(left,-1),(right,1)]:
        outer=min(rim,key=lambda p:p.x) if sign<0 else max(rim,key=lambda p:p.x)
        tube('Card traced glasses temple',[outer,Vector((sign*.09,outer.y+.04,outer.z)),Vector((sign*.088,ear_y,outer.z-.005))],.001)

def card_hair_shell(base,rig,fit,projection):
    """A closed, curved, skinned hairstyle volume with the card's actual silhouette."""
    hair=fit['reference_hair'];bvh=BVHTree.FromObject(base,bpy.context.evaluated_depsgraph_get())
    inverse=base.matrix_world.inverted();rig_inverse=rig.matrix_world.inverted();scale=projection['ortho_scale'];center=projection['center_z']
    silhouette=[((uv[0]-.5)*scale,center+(.5-uv[1])*scale) for uv in hair['points']]
    crown=max(z for x,z in silhouette);cx=(max(x for x,z in silhouette)+min(x for x,z in silhouette))/2
    rx=max(abs(x-cx) for x,z in silhouette);rz=(projection['head_top']-projection['neck'])*.58;cz=crown-rz
    head=[base.matrix_world@v.co for v in base.data.vertices if (base.matrix_world@v.co).z>projection['neck']+.06]
    cy=(min(v.y for v in head)+max(v.y for v in head))/2;ry=(max(v.y for v in head)-min(v.y for v in head))/2+.008
    scalp_rx=min(rx,(max(v.x for v in head)-min(v.x for v in head))/2+.008)
    front=[];back=[]
    for uv in hair['points']:
        x=(uv[0]-.5)*scale;z=center+(.5-uv[1])*scale
        hit=bvh.ray_cast(inverse@Vector((x,-2,z)),(inverse.to_3x3()@Vector((0,1,0))).normalized())[0]
        # Keep the crown continuous where a ray just misses the anatomical scalp.
        # Switching directly from a scalp hit to a shallow fallback folds triangles
        # through the forehead and leaves visible gaps along the fringe.
        crown_y=cy-ry*math.sqrt(max(0,1-((x-cx)/rx)**2-((z-cz)/rz)**2))
        y=min((base.matrix_world@hit).y-.008,crown_y) if hit else crown_y
        front.append(tuple(rig_inverse@Vector((x,y,z))))
        # A curved hair layer follows the scalp with strand-scale thickness.
        # The retained anatomical rear hairstyle supplies the back of the head;
        # extruding the frontal silhouette across the skull makes a box in profile.
        back.append(tuple(rig_inverse@Vector((x,y+.006,z))))
    count=len(front);front_faces=[]
    for f in hair['faces']:
        a,b,c=[Vector(front[i]) for i in f]
        front_faces.append(list(reversed(f)) if (b-a).cross(c-a).y>0 else f)
    faces=front_faces+[[i+count for i in reversed(f)] for f in front_faces]
    edges=Counter(tuple(sorted((a,b))) for f in front_faces for a,b in zip(f,f[1:]+f[:1]))
    for f in front_faces:
        for a,b in zip(f,f[1:]+f[:1]):
            if edges[tuple(sorted((a,b)))]==1:faces.append([a,b,b+count,a+count])
    mesh=bpy.data.meshes.new('Card hairstyle closed 3D volume');mesh.from_pydata(front+back,[],faces);mesh.update()
    obj=bpy.data.objects.new('Card hairstyle closed 3D volume',mesh);bpy.context.collection.objects.link(obj)
    uv_layer=mesh.uv_layers.new(name='HairCardUV')
    for poly in mesh.polygons:
        poly.use_smooth=True
        for li in poly.loop_indices:uv_layer.data[li].uv=hair['source_uv'][mesh.loops[li].vertex_index%count]
    mat=bpy.data.materials.new('Reference card hairstyle surface');mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.68
    image=mat.node_tree.nodes.new('ShaderNodeTexImage');image.image=bpy.data.images.load(str(ROOT/'runtime/card-face-fit'/fit['actor_id']/'fitted-hair.png'),check_existing=True)
    mat.node_tree.links.new(image.outputs['Color'],bs.inputs['Base Color']);mesh.materials.append(mat)
    group=obj.vertex_groups.new(name='head');group.add(list(range(len(mesh.vertices))),1,'REPLACE');modifier=obj.modifiers.new('Hairstyle head skeleton','ARMATURE');modifier.object=rig;obj.parent=rig
    # Fit a rounded rear scalp to the same head; never extrude the portrait's
    # silhouette into a slab or leave an unrelated rear hairstyle floating behind.
    rear_vertices=[];rear_faces=[];columns=72;rows=24
    actor_gender=next(a['gender'] for a in json.loads((ROOT/'data/characters/catalog.json').read_text(encoding='utf-8'))['actors'] if a['id']==fit['actor_id'])
    max_phi=math.pi*(.60 if actor_gender=='male' else .66 if fit['actor_id']=='auntie-lin' else .73)
    oval=np.array(fit['target_face_oval']);face_width=oval[:,0].max()-oval[:,0].min();eye=fit['render_eye_center']
    fringe=[uv[1] for uv in hair['points'] if abs(uv[0]-eye[0])<face_width*.12 and uv[1]<eye[1]-face_width*.15]
    hairline=max(fringe) if fringe else fit['target_face_oval'][0][1]
    forehead=center+(.5-hairline)*scale
    front_phi=max(math.pi*.15,min(math.pi*.35,math.acos(max(-1,min(1,(forehead-cz)/rz)))))
    for row in range(rows+1):
        rear_rx=scalp_rx*(1-.22*(row/rows)**4)
        for column in range(columns+1):
            theta=2*math.pi*column/columns
            frontness=max(0,-math.sin(theta));limit=max_phi*(1-frontness)+front_phi*frontness
            phi=.015+(limit-.015)*row/rows
            world=Vector((cx+rear_rx*math.cos(theta)*math.sin(phi),cy+ry*math.sin(theta)*math.sin(phi),cz+rz*math.cos(phi)))
            sign=-1 if math.sin(theta)<0 else 1
            scalp_hit=bvh.ray_cast(inverse@Vector((world.x,2*sign,world.z)),(inverse.to_3x3()@Vector((0,-sign,0))).normalized())[0]
            if scalp_hit:
                surface=(base.matrix_world@scalp_hit).y+sign*.007
                world.y=min(world.y,surface) if sign<0 else max(world.y,surface)
            rear_vertices.append(tuple(rig_inverse@world))
    for row in range(rows):
        for column in range(columns):
            a=row*(columns+1)+column;rear_faces.append([a,a+columns+1,a+columns+2,a+1])
    scalp_material=bpy.data.materials.new('Reference hairstyle scalp strands');scalp_material.use_nodes=True
    scalp_bs=scalp_material.node_tree.nodes.get('Principled BSDF');scalp_bs.inputs['Base Color'].default_value=(*linear(PRESETS[fit['actor_id']]['hair_color']),1);scalp_bs.inputs['Roughness'].default_value=.72
    rear_mesh=bpy.data.meshes.new('Reference fitted rounded rear hair');rear_mesh.from_pydata(rear_vertices,[],rear_faces);rear_mesh.materials.append(scalp_material);rear_mesh.update()
    rear=bpy.data.objects.new('Reference fitted rounded rear hair',rear_mesh);bpy.context.collection.objects.link(rear)
    rear_uv=rear_mesh.uv_layers.new(name='RearHairUV');rotation=np.array(fit['reference_rotation']);rc=np.array(fit['reference_eye_center_px']);dc=np.array(fit['render_eye_center']);size=np.array(fit['reference_size'])
    for polygon in rear_mesh.polygons:
        polygon.use_smooth=True
        for li in polygon.loop_indices:
            world=rig.matrix_world@rear_mesh.vertices[rear_mesh.loops[li].vertex_index].co
            projected=np.array([world.x/scale+.5,.5-(world.z-center)/scale]);pixel=((projected-dc)/fit['reference_scale'])@rotation.T+rc
            rear_uv.data[li].uv=(pixel[0]/size[0],1-pixel[1]/size[1])
    rear.vertex_groups.new(name='head').add(list(range(len(rear_mesh.vertices))),1,'REPLACE');rear.modifiers.new('Rear hair head skeleton','ARMATURE').object=rig;rear.parent=rig
    strands=bpy.data.curves.new('Reference fitted scalp hair strands','CURVE');strands.dimensions='3D';strands.bevel_depth=.00045;strands.bevel_resolution=1
    for column in range(columns):
        spline=strands.splines.new('POLY');spline.points.add(rows-2)
        for point,row in zip(spline.points,range(1,rows)):
            local=Vector(rear_vertices[row*(columns+1)+column]);world=rig.matrix_world@local
            direction=world-Vector((cx,cy,cz));world+=direction.normalized()*.0005
            point.co=(*(rig_inverse@world),1)
    strand_obj=bpy.data.objects.new('Reference fitted scalp hair strands',strands);bpy.context.collection.objects.link(strand_obj);strands.materials.append(scalp_material)
    bpy.ops.object.select_all(action='DESELECT');strand_obj.select_set(True);bpy.context.view_layer.objects.active=strand_obj;bpy.ops.object.convert(target='MESH');strand_obj=bpy.context.object
    strand_obj.vertex_groups.new(name='head').add(list(range(len(strand_obj.data.vertices))),1,'REPLACE');strand_obj.modifiers.new('Hair strands head skeleton','ARMATURE').object=rig;strand_obj.parent=rig
    for old in list(bpy.context.scene.objects):
        if old.type=='MESH' and any(x in old.name.lower() for x in ('short0','bob0','long01','ponytail')):
            bpy.data.objects.remove(old,do_unlink=True)
    return obj

def finish(actor_id):
    directory=ROOT/'runtime/card-face-fit'/actor_id
    bpy.ops.wm.open_mainfile(filepath=str(directory/'character.blend'))
    fit=json.loads((directory/'fit.json').read_text());projection=json.loads((directory/'projection.json').read_text())
    base=bpy.data.objects[projection['body']];rig=bpy.data.objects[projection['rig']]
    for obj in list(bpy.context.scene.objects):
        if obj.type=='MESH':fit_mesh(obj,fit,projection)
    bpy.context.view_layer.update();bake_face(base,fit,projection,directory)
    reference_glasses(base,rig,fit,projection)
    for obj in bpy.context.scene.objects:
        if obj.type=='MESH' and 'eyebrow004' in obj.name:obj.hide_render=True;obj.hide_viewport=True
    card_hair_shell(base,rig,fit,projection)
    # Preview uses the same rigged mesh; lower the very bright fitting lights.
    for obj in bpy.context.scene.objects:
        if obj.type=='LIGHT':obj.data.energy*=.38
    bpy.ops.wm.save_as_mainfile(filepath=str(directory/'fitted-character.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(directory/'fitted-character.blend'))
    rig=bpy.data.objects[projection['rig']]
    bpy.context.scene.render.filepath=str(directory/'fitted-preview.png');bpy.context.scene.render.engine='BLENDER_EEVEE_NEXT'
    bpy.ops.render.render(write_still=True)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type in ('MESH','ARMATURE') and not obj.hide_render:obj.select_set(True)
    bpy.context.view_layer.objects.active=rig
    output=Path(os.getenv('CLINICAL_AVATAR_OUTPUT',str(ROOT/'runtime/card-avatar-candidate')));output.mkdir(parents=True,exist_ok=True)
    path=output/(actor_id+'.glb')
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_animations=False,export_skins=True,export_morph=True,export_morph_normal=True,export_extras=True,export_apply=False,export_image_format='AUTO')
    raw=path.read_bytes();size=struct.unpack_from('<I',raw,12)[0];gltf=json.loads(raw[20:20+size])
    for mat in gltf['materials']:
        name=mat.get('name','').lower();hair=any(x in name for x in ('short','long01','bob0','ponytail','eyelash'))
        mat['alphaMode']='MASK' if hair else 'BLEND' if 'high-poly' in name else 'OPAQUE'
        if hair:mat['alphaCutoff']=.25
    encoded=json.dumps(gltf,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%4);binary=raw[20+size:]
    path.write_bytes(struct.pack('<4sII',b'glTF',2,20+len(encoded)+len(binary))+struct.pack('<I4s',len(encoded),b'JSON')+encoded+binary)
    record_path=path.with_suffix('.json');source_record=record_path if record_path.exists() else ROOT/'data/characters/card-matched-v3'/(actor_id+'.json');record=json.loads(source_record.read_text(encoding='utf-8'))
    record.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size,
        face_fitting={'landmarks':len(fit['landmark_indices']),'source_card_sha256':fit['source_card_sha256'],'method':fit['method'],'surface':'reference appearance baked to curved anatomical head UV; no portrait plane','hair':'closed curved hairstyle volume from reference silhouette, skinned to head'},
        likeness_status='reference fitted geometry, surface appearance and 3D hair; multi-view visual acceptance pending')
    record['license']='CC0 base human geometry; supplied fictional reference-card appearance retains its source rights'
    record_path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CARD_FACE_FITTED',actor_id,record['sha256'],flush=True)

if __name__=='__main__':
    for actor_id in sys.argv[sys.argv.index('--')+1:]:finish(actor_id)
