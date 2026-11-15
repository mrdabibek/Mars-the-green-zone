"""Export NASA reference GLBs (Draco-compressed) to UE5-ready static FBXs + textures.

Reads from Assets/References/*.glb (never modifying originals) and writes to
Assets/References/Export_FBX/.
"""
import importlib
import json
import math
import os
import pathlib
import sys

import bpy
import bpy_extras.io_utils as io_utils
import io_scene_fbx
from io_scene_gltf2.blender.imp import draco_compression_extension as imp_draco
from io_scene_gltf2.io.com import draco as gltf_draco
from mathutils import Matrix, Vector

# Process-local Blender 5.0 fixes (do not modify system files)
_orig_orientation = io_utils.orientation_helper


def _fixed_orientation(*args, **kwargs):
    dec = _orig_orientation(*args, **kwargs)

    def _wrap(cls):
        ann = dict(cls.__annotations__)
        cls = dec(cls)
        cls.__annotations__ = {**ann, **cls.__annotations__}
        return cls

    return _wrap


io_scene_fbx.unregister()
io_utils.orientation_helper = _fixed_orientation
importlib.reload(io_scene_fbx)
io_scene_fbx.register()

_DRACO_SO = pathlib.Path(
    "/usr/lib/blender/scripts/addons_core/io_scene_gltf2/"
    "libextern_draco.cpython-314-x86_64-linux-gnu.so"
)
if _DRACO_SO.exists():
    gltf_draco.dll_path = lambda: _DRACO_SO
    imp_draco.dll_path = lambda: _DRACO_SO


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for col in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.actions):
        for item in list(col):
            col.remove(item)


def world_bounds(meshes):
    deps = bpy.context.evaluated_depsgraph_get()
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    verts = 0
    polys = 0
    for m in meshes:
        ev = m.evaluated_get(deps)
        me = ev.to_mesh()
        verts += len(me.vertices)
        polys += len(me.polygons)
        for v in me.vertices:
            w = m.matrix_world @ v.co
            for i in range(3):
                mn[i] = min(mn[i], w[i])
                mx[i] = max(mx[i], w[i])
        ev.to_mesh_clear()
    return mn, mx, verts, polys


def export_reference(src_path, out_dir, out_name, target_height_m=None):
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=src_path)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No meshes in {src_path}")

    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    mn, mx, verts, polys = world_bounds(meshes)
    cur_h = max(mx.z - mn.z, 1e-4)
    scale_factor = (target_height_m / cur_h) if target_height_m else 1.0

    # Center XY at 0, ground Z at 0, apply uniform scale
    cx = 0.5 * (mn.x + mx.x)
    cy = 0.5 * (mn.y + mx.y)
    cz = mn.z
    for m in meshes:
        for v in m.data.vertices:
            v.co = (v.co - Vector((cx, cy, cz))) * scale_factor
        m.data.update()

    # Save unpacked textures alongside FBX
    tex_dir = os.path.join(out_dir, "Textures")
    os.makedirs(tex_dir, exist_ok=True)
    saved_textures = []
    for img in bpy.data.images:
        if img.size[0] == 0:
            continue
        clean_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in img.name)
        tex_path = os.path.join(tex_dir, f"{out_name}_{clean_name}.png")
        img.filepath_raw = tex_path
        img.file_format = "PNG"
        img.save()
        saved_textures.append(os.path.basename(tex_path))

    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]

    fbx_path = os.path.join(out_dir, f"{out_name}.fbx")
    bpy.ops.export_scene.fbx(
        filepath=fbx_path,
        use_selection=True,
        object_types={"MESH"},
        axis_forward="-Z",
        axis_up="Y",
        apply_unit_scale=True,
        bake_space_transform=True,
        mesh_smooth_type="FACE",
        path_mode="COPY",
        embed_textures=True,
    )

    mn2, mx2, _, _ = world_bounds(meshes)
    return {
        "name": out_name,
        "fbx": fbx_path,
        "textures": saved_textures,
        "vertices": verts,
        "polygons": polys,
        "ue_size_cm": [round((mx2[i] - mn2[i]) * 100.0, 2) for i in range(3)],
        "ue_min_cm": [round(mn2[i] * 100.0, 2) for i in range(3)],
    }


def main():
    root = "/home/dabi/Documents/Mars Last Green"
    ref_dir = os.path.join(root, "Assets", "References")
    out_dir = os.path.join(ref_dir, "Export_FBX")
    os.makedirs(out_dir, exist_ok=True)

    specs = [
        ("Z2_Spacesuit_NASA.glb", "SM_NASA_Z2_Spacesuit", 1.93),
        ("Habitat Demonstration Unit (part 1).glb", "SM_NASA_Habitat_Part1", 3.20),
        ("Habitat Demonstration Unit (part 2).glb", "SM_NASA_Habitat_Part2", 3.20),
    ]
    manifest = []
    for src, dst, h in specs:
        info = export_reference(os.path.join(ref_dir, src), out_dir, dst, target_height_m=h)
        manifest.append(info)
        print("REF_EXPORTED", json.dumps(info), flush=True)

    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    main()
