"""Add a small, editable breathing prototype while preserving the imported walk."""
import bpy, sys, math, json
from mathutils import Quaternion
path=sys.argv[sys.argv.index('--')+1]
bpy.ops.wm.open_mainfile(filepath=path)
scene=bpy.context.scene
arm=next(o for o in scene.objects if o.type=='ARMATURE')
walk=arm.animation_data.action
scene.frame_set(1); bpy.context.view_layer.update()
base={p.name:(p.location.copy(),p.rotation_quaternion.copy(),p.scale.copy()) for p in arm.pose.bones}
arm.animation_data.action=None
for frame,amount in ((1,0),(16,1),(31,0),(46,-1),(61,0)):
 scene.frame_set(frame)
 for p in arm.pose.bones:
  loc,rot,scale=base[p.name]; p.rotation_mode='QUATERNION';p.location=loc;p.rotation_quaternion=rot;p.scale=scale
  if p.name in ('tripo::Spine_1','tripo::Spine_2','tripo::Head_0'):
   factor=0.018 if 'Spine' in p.name else -0.025
   p.rotation_quaternion=rot @ Quaternion((1,0,0),factor*amount)
  p.keyframe_insert(data_path='location',frame=frame,group=p.name)
  p.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=p.name)
  p.keyframe_insert(data_path='scale',frame=frame,group=p.name)
idle=arm.animation_data.action;idle.name='Idle_DRAFT';idle.use_fake_user=True
arm.animation_data.action=walk
scene.frame_start=1;scene.frame_end=62;scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=path)
print('DRAFT_ACTIONS',json.dumps([a.name for a in bpy.data.actions]))
