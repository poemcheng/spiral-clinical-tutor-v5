"""Blender stages for fitting reference-card facial appearance to a curved head.

The head, facial blendshapes, eyes and hair remain skinned 3D geometry. Reference
color is a surface texture, never a camera-facing portrait plane.
"""
import json,math
from pathlib import Path
import bpy
from mathutils import Vector

def prepare_render(base,rig,actor,root):
    directory=root/'runtime/card-face-fit'/actor['id'];directory.mkdir(parents=True,exist_ok=True)
    bpy.context.view_layer.update()
    points=[base.matrix_world@v.co for v in base.data.vertices]
    top=max(p.z for p in points);neck=(rig.matrix_world@rig.data.bones['neck01'].head_local).z
    center=(top+neck)/2+.012
    scale=(top-neck)*1.3
    bpy.ops.object.camera_add(location=(0,-3,center))
    camera=bpy.context.object;camera.name='Reference fitting orthographic camera'
    camera.rotation_euler=(Vector((0,0,center))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO';camera.data.ortho_scale=scale;camera.data.lens=70
    scene=bpy.context.scene;scene.camera=camera;scene.render.engine='CYCLES';scene.cycles.samples=20
    scene.render.resolution_x=768;scene.render.resolution_y=768;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
    scene.world.color=(.35,.35,.35)
    scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast'
    for name,loc,power,size in [('Face soft key',(-1,-2,center+1),180,3),('Face soft fill',(1,-1,center),90,3)]:
        bpy.ops.object.light_add(type='AREA',location=loc);light=bpy.context.object;light.name=name;light.data.energy=power;light.data.shape='DISK';light.data.size=size;light.rotation_euler=(Vector((0,0,center))-light.location).to_track_quat('-Z','Y').to_euler()
    # Fit landmarks on the anatomical face before glasses/hair obscure the contour.
    hidden=[]
    for obj in scene.objects:
        if obj.type=='MESH' and any(x in obj.name.lower() for x in ('hair','short0','long01','bob0','ponytail','glasses')):
            hidden.append(obj);obj.hide_render=True
    scene.render.filepath=str(directory/'neutral-head.png');bpy.ops.render.render(write_still=True)
    for obj in hidden:obj.hide_render=False
    (directory/'projection.json').write_text(json.dumps({'actor_id':actor['id'],'center_z':center,'ortho_scale':scale,'resolution':768,'body':base.name,'rig':rig.name,'head_top':top,'neck':neck},indent=2))
    bpy.ops.wm.save_as_mainfile(filepath=str(directory/'character.blend'))
