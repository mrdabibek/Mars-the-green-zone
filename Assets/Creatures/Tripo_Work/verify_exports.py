import bpy,importlib,bpy_extras.io_utils as io,io_scene_fbx,glob,os,json
old=io.orientation_helper
def fix(*a,**kw):
 d=old(*a,**kw)
 def wrap(c):
  ann=dict(c.__annotations__);c=d(c);c.__annotations__={**ann,**c.__annotations__};return c
 return wrap
io_scene_fbx.unregister();io.orientation_helper=fix;importlib.reload(io_scene_fbx);io_scene_fbx.register()
root=os.path.join(os.path.dirname(__file__),'Export_DRAFT');results=[]
for f in sorted(glob.glob(root+'/*.fbx')):
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 for a in list(bpy.data.actions):bpy.data.actions.remove(a)
 bpy.ops.import_scene.fbx(filepath=f)
 arms=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'];meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];actions=list(bpy.data.actions)
 scene=bpy.context.scene
 if arms and actions:
  arm=arms[0];arm.animation_data.action=actions[0];start=int(actions[0].frame_range[0]);end=int(actions[0].frame_range[1]);scene.frame_set(start);bpy.context.view_layer.update();first={p.name:p.matrix.copy() for p in arm.pose.bones};scene.frame_set(start+(end-start)//4);bpy.context.view_layer.update();motion=max((first[p.name].translation-p.matrix.translation).length for p in arm.pose.bones)
 else: motion=0
 result={'motion_quarter_frame':motion,'file':os.path.basename(f),'armatures':len(arms),'bones':sum(len(o.data.bones) for o in arms),'meshes':len(meshes),'actions':[(a.name,list(a.frame_range)) for a in actions],'weighted_meshes':sum(bool(o.vertex_groups) for o in meshes)}
 results.append(result);print('ROUNDTRIP',json.dumps(result),flush=True)
with open(os.path.join(root,'roundtrip_results.json'),'w') as out:json.dump(results,out,indent=2)
