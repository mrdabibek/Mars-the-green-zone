"""Create an explicitly experimental decimated humanoid rig from the user's Scavenger GLB."""
import bpy, math, json, os
from mathutils import Vector
from mathutils.geometry import intersect_point_line
src='/home/dabi/Downloads/NASA Downloads/Mars_Last_Green_Scavenger.glb'
out='/home/dabi/Documents/Mars Last Green/Assets/Creatures/Tripo_Work'
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=src)
mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
bpy.context.view_layer.objects.active=mesh;mesh.select_set(True)
bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
print('DECIMATING',len(mesh.data.vertices),len(mesh.data.polygons),flush=True)
mod=mesh.modifiers.new('Draft mesh reduction','DECIMATE');mod.ratio=0.07
bpy.ops.object.modifier_apply(modifier=mod.name)
print('DECIMATED',len(mesh.data.vertices),len(mesh.data.polygons),flush=True)
# Positions are approximate from the character's normalized bounds and must be artist-reviewed.
points={
'root':((0,0,0),(0,0,.08),None),
'pelvis':((0,0,.46),(0,0,.54),'root'),
'spine_01':((0,0,.54),(0,0,.65),'pelvis'),
'spine_02':((0,0,.65),(0,0,.78),'spine_01'),
'neck':((0,0,.78),(0,0,.84),'spine_02'),
'head':((0,0,.84),(0,0,.96),'neck')}
for suffix,sign in [('l',1),('r',-1)]:
 points.update({
 'upperarm_'+suffix:((sign*.12,0,.76),(sign*.18,0,.61),'spine_02'),
 'lowerarm_'+suffix:((sign*.18,0,.61),(sign*.22,0,.47),'upperarm_'+suffix),
 'hand_'+suffix:((sign*.22,0,.47),(sign*.235,-.01,.40),'lowerarm_'+suffix),
 'thigh_'+suffix:((sign*.07,0,.49),(sign*.095,0,.30),'pelvis'),
 'calf_'+suffix:((sign*.095,0,.30),(sign*.105,0,.095),'thigh_'+suffix),
 'foot_'+suffix:((sign*.105,0,.095),(sign*.105,-.075,.035),'calf_'+suffix)})
adata=bpy.data.armatures.new('Scavenger_Draft_Skeleton');arm=bpy.data.objects.new('Scavenger_Draft_Rig',adata);bpy.context.collection.objects.link(arm);bpy.context.view_layer.objects.active=arm;arm.select_set(True);mesh.select_set(False)
bpy.ops.object.mode_set(mode='EDIT')
for name,(head,tail,parent) in points.items():
 b=adata.edit_bones.new(name);b.head=head;b.tail=tail
 if parent:b.parent=adata.edit_bones[parent]
 if name=='root':b.use_deform=False
bpy.ops.object.mode_set(mode='OBJECT')
for name in points:
 if name!='root':mesh.vertex_groups.new(name=name)
# Spatial weights with coarse anatomy filtering and smooth influence mixing.
segs={n:(Vector(h),Vector(t)) for n,(h,t,_) in points.items() if n!='root'}
for v in mesh.data.vertices:
 x,y,z=v.co; side='l' if x>=0 else 'r'; ax=abs(x)
 if z<.35 or (z<.45 and ax<.17): choices=['thigh_'+side,'calf_'+side,'foot_'+side,'pelvis']
 elif ax>.145 and z<.79: choices=['upperarm_'+side,'lowerarm_'+side,'hand_'+side,'spine_02']
 else: choices=['pelvis','spine_01','spine_02','neck','head','upperarm_'+side,'thigh_'+side]
 weights=[]
 for n in choices:
  h,t=segs[n];vec=t-h;f=max(0,min(1,(v.co-h).dot(vec)/vec.length_squared));dist=(v.co-(h+f*vec)).length
  weights.append((1.0/(dist+.012)**4,n))
 weights.sort(reverse=True);weights=weights[:4];total=sum(w for w,n in weights)
 for w,n in weights:
  if w/total>.001:mesh.vertex_groups[n].add([v.index],w/total,'REPLACE')
mesh.parent=arm;md=mesh.modifiers.new('Scavenger rig','ARMATURE');md.object=arm
scene=bpy.context.scene;scene.render.fps=30

def animate(name,frames):
 arm.animation_data_clear()
 for frame in frames:
  scene.frame_set(frame); phase=2*math.pi*(frame-1)/(frames[-1]-1)
  for p in arm.pose.bones:
   p.rotation_mode='XYZ';p.rotation_euler=(0,0,0);p.location=(0,0,0)
   if name=='Idle_DRAFT':
    if p.name=='spine_02':p.rotation_euler.x=.025*math.sin(phase)
    if p.name=='head':p.rotation_euler.x=-.018*math.sin(phase)
   else:
    if p.name.startswith(('thigh_','upperarm_')):
     side=1 if p.name.endswith('_l') else -1
     if p.name.startswith('upperarm_'):side=-side
     p.rotation_euler.x=.22*side*math.sin(phase)
    if p.name.startswith('calf_'):
     side=1 if p.name.endswith('_l') else -1
     p.rotation_euler.x=.16*max(0,side*math.sin(phase))
    if p.name=='pelvis':p.location.z=.006*(1-math.cos(2*phase))
   p.keyframe_insert(data_path='rotation_euler',frame=frame,group=p.name)
   p.keyframe_insert(data_path='location',frame=frame,group=p.name)
 action=arm.animation_data.action;action.name=name;action.use_fake_user=True
 return action
idle=animate('Idle_DRAFT',[1,16,31,46,61]);walk=animate('Walk_DRAFT',[1,7,13,19,25,31]);scene.frame_start=1;scene.frame_end=31;scene.frame_set(1)
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'Scavenger_DRAFT.blend'))
print('RESULT',json.dumps({'vertices':len(mesh.data.vertices),'triangles':len(mesh.data.polygons),'bones':len(adata.bones),'actions':[a.name for a in bpy.data.actions]}),flush=True)
