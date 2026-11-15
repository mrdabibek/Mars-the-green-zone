"""Generate reproducible introduction meshes and a contact sheet. Run with blender -b -t 2 -P this file."""
import bpy, math, os
from io_scene_fbx import export_fbx_bin
from mathutils import Vector
out = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Assets', 'Intro'))
os.makedirs(out, exist_ok=True)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
def mat(name, color, metallic=0):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.metallic=metallic; m.roughness=.5; return m
ocean=mat('Ocean',(.025,.13,.33)); land=mat('Land',(.12,.36,.16)); rock=mat('Molten',(.8,.16,.025)); hull=mat('Hull',(.64,.68,.68),.6); dark=mat('DarkMetal',(.09,.11,.13),.7); glow=mat('CockpitGlow',(.1,.65,.8))
def sphere(name, material, scale=(1,1,1)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16); o=bpy.context.object; o.name=name; o.scale=scale; o.data.materials.append(material); return o
def export(name, objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects: o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    export_fbx_bin.save(type("Reporter", (), {"report": lambda self, kinds, message: print(message)})(), bpy.context, filepath=os.path.join(out,name+'.fbx'), use_selection=True)
    for o in objects: o.hide_render=True; o.hide_set(True)
earth=sphere('Earth',ocean)
# Surface land patches follow the sphere; separate meshes share material slots on import.
parts=[earth]
for lat,lon,sx,sy in [(25,25,.35,.20),(45,95,.25,.17),(-25,150,.22,.15),(10,220,.22,.31),(-20,300,.18,.27)]:
    lat,lon=map(math.radians,(lat,lon)); pos=Vector((math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat)))
    o=sphere('Continent',land,(sx,sy,.025)); o.location=pos*1.002; o.rotation_euler=pos.to_track_quat('Z','Y').to_euler(); parts.append(o)
export('SM_Intro_EarthWhole',parts)
core=sphere('Core',rock); export('SM_Intro_EarthCore',[core])
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1); shard=bpy.context.object; shard.name='Shard'; shard.scale=(1,.65,.48); shard.data.materials.append(rock); export('SM_Intro_EarthShard',[shard])
lander=[]
def cube(name, loc, scale, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o=bpy.context.object; o.name=name; o.scale=scale; o.data.materials.append(material); lander.append(o); return o
cube('LanderBody',(0,0,1.25),(2.4,2,1),hull); cube('Cockpit',(0,-1.02,1.35),(1.4,.08,.48),glow); cube('HeatShield',(0,0,.68),(2.8,2.4,.18),dark)
for x in (-1,1):
 for y in (-1,1):
    o=cube('LandingLeg',(x*1.25,y*1.05,.38),(.15,.15,1),hull); o.rotation_euler[1]=x*.5
    cube('Foot',(x*1.5,y*1.05,.04),(.65,.55,.08),dark)
export('SM_Intro_DropLander',lander)
# Contact sheet, with the same exported objects arranged in a studio.
for o in parts+[core,shard]+lander: o.hide_render=False; o.hide_set(False)
for o in parts: o.location.x -= 4
core.location.x=-1.5; shard.location.x=1; 
for o in lander: o.location.x += 4
bpy.ops.object.camera_add(location=(0,-15,9)); camera=bpy.context.object; camera.rotation_euler=(Vector((0,0,.5))-camera.location).to_track_quat('-Z','Y').to_euler(); bpy.context.scene.camera=camera; camera.data.type='ORTHO'; camera.data.ortho_scale=12
bpy.context.scene.render.engine='BLENDER_WORKBENCH'; bpy.context.scene.display.shading.light='STUDIO'; bpy.context.scene.display.shading.color_type='MATERIAL'; bpy.context.scene.render.resolution_x=1400; bpy.context.scene.render.resolution_y=500; bpy.context.scene.render.resolution_percentage=100; bpy.context.scene.render.filepath=os.path.join(out,'inc11_preview.png'); bpy.ops.render.render(write_still=True)
