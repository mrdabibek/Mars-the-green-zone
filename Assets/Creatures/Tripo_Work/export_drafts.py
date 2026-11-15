"""Export individual draft FBX clips; requires independent Unreal verification."""
import bpy,importlib,bpy_extras.io_utils as io,io_scene_fbx,sys,os
old=io.orientation_helper
def fix(*args,**kwargs):
 d=old(*args,**kwargs)
 def apply(cls):
  a=dict(cls.__annotations__);cls=d(cls);cls.__annotations__={**a,**cls.__annotations__};return cls
 return apply
io_scene_fbx.unregister();io.orientation_helper=fix;importlib.reload(io_scene_fbx);io_scene_fbx.register()
path=sys.argv[sys.argv.index('--')+1];bpy.ops.wm.open_mainfile(filepath=path)
scene=bpy.context.scene;arm=next(o for o in scene.objects if o.type=='ARMATURE')
name=os.path.basename(path).split('_')[0]; out=os.path.join(os.path.dirname(path),'Export_DRAFT');os.makedirs(out,exist_ok=True)
bpy.ops.object.select_all(action='DESELECT')
arm.select_set(True)
for o in scene.objects:
 if o.type=='MESH':o.select_set(True)
bpy.context.view_layer.objects.active=arm
for label in ('walk','idle'):
 candidates=[a for a in bpy.data.actions if ('walk' in a.name.lower() if label=='walk' else a.name=='Idle_DRAFT')]
 if not candidates:continue
 a=candidates[0];arm.animation_data.action=a;scene.frame_start=round(a.frame_range[0]);scene.frame_end=round(a.frame_range[1]);scene.frame_set(scene.frame_start)
 dest=os.path.join(out,name+'_'+label+'_DRAFT.fbx')
 bpy.ops.export_scene.fbx(filepath=dest,use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,path_mode='COPY',embed_textures=True)
 print('EXPORTED',dest,os.path.getsize(dest),flush=True)
