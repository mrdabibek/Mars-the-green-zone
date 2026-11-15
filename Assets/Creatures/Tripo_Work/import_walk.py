"""Import Tripo FBX with a process-local workaround for this Blender build."""
import bpy, importlib, bpy_extras.io_utils as io, io_scene_fbx
from mathutils import Vector
import os, sys, json
original=io.orientation_helper
def fixed(*args, **kwargs):
    decorator=original(*args, **kwargs)
    def wrap(cls):
        annotations=dict(cls.__annotations__)
        cls=decorator(cls)
        cls.__annotations__={**annotations, **cls.__annotations__}
        return cls
    return wrap
io_scene_fbx.unregister(); io.orientation_helper=fixed
importlib.reload(io_scene_fbx); io_scene_fbx.register()
args=sys.argv[sys.argv.index('--')+1:]
source,outdir,name=args
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=source)
scene=bpy.context.scene
arm=next(o for o in scene.objects if o.type=='ARMATURE')
mesh=next(o for o in scene.objects if o.type=='MESH')
action=arm.animation_data.action
assert action is not None
scene.frame_start=int(action.frame_range[0]); scene.frame_end=int(action.frame_range[1]);scene.render.fps=30
action.use_fake_user=True
first=scene.frame_start; last=scene.frame_end

def pose(frame):
    scene.frame_set(frame); bpy.context.view_layer.update()
    return {p.name:p.matrix.copy() for p in arm.pose.bones}
a=pose(first); b=pose(last); c=pose(first+(last-first)//4)
seam=max((a[k].translation-b[k].translation).length for k in a)
motion=max((a[k].translation-c[k].translation).length for k in a)
scene.frame_set(first)
try: bpy.ops.file.pack_all()
except RuntimeError: pass
os.makedirs(outdir,exist_ok=True)
output=os.path.join(outdir,name+'_walk.blend')
bpy.ops.wm.save_as_mainfile(filepath=output)
report={'source':os.path.basename(source),'name':name,'blend':os.path.basename(output),'action':action.name,'frames':[first,last],'fps':scene.render.fps,'bones':len(arm.data.bones),'vertices':len(mesh.data.vertices),'polygons':len(mesh.data.polygons),'seam_bone_translation_max':seam,'quarter_frame_bone_motion_max':motion,'note':'Imported Tripo walk, visual and Unreal validation required; motion metrics are in armature local units.'}
with open(os.path.join(outdir,name+'_inspection.json'),'w') as h: json.dump(report,h,indent=2)
print('MARS_INSPECTION',json.dumps(report),flush=True)
