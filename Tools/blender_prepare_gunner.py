"""Prepare high-detail, game-ready Gunner base mesh + baked 2K normal map + Energy Carbine.

Reads /home/dabi/Downloads/NASA Downloads/Mars_Last_Green_Scavenger.glb (unmodified),
orients to +X forward, Z up, 1.80m tall, grounded Z=0, decimates to ~48k tris,
bakes a 2048x2048 tangent normal map from the 1.92M-poly sculpt, adds UE5-style
humanoid armature + sci-fi Energy Carbine weighted to weapon_r + muzzle socket bone,
and saves Assets/Creatures/Production/_source_extracted/Gunner/Gunner_base.blend.
"""
import json
import math
import os

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for col in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.actions, bpy.data.armatures):
        for item in list(col):
            col.remove(item)


def build_energy_carbine(mat_body, mat_glow):
    """Create a realistic sci-fi Mars Energy Carbine centered with grip at origin, barrel along +X."""
    bm = bmesh.new()

    def add_box(cx, cy, cz, sx, sy, sz, mat_idx=0):
        ret = bmesh.ops.create_cube(bm, size=1.0)
        for v in ret["verts"]:
            v.co = Vector((v.co.x * sx + cx, v.co.y * sy + cy, v.co.z * sz + cz))
        for f in bm.faces:
            if all(v in ret["verts"] for v in f.verts):
                f.material_index = mat_idx

    # Main receiver body (grip near x=0, barrel toward +X, stock toward -X)
    add_box(0.08, 0.0, 0.04, 0.36, 0.048, 0.075, 0)
    # Upper rail & optic shroud
    add_box(0.10, 0.0, 0.092, 0.28, 0.032, 0.028, 0)
    # Optic sight housing
    add_box(0.04, 0.0, 0.122, 0.10, 0.026, 0.028, 0)
    # Barrel shroud + heavy forward emitter
    add_box(0.36, 0.0, 0.045, 0.24, 0.038, 0.052, 0)
    add_box(0.50, 0.0, 0.045, 0.08, 0.044, 0.058, 0)
    # Glow energy core strips along receiver & emitter
    add_box(0.16, 0.0, 0.045, 0.20, 0.052, 0.016, 1)
    add_box(0.42, 0.0, 0.045, 0.12, 0.042, 0.014, 1)
    # Buttstock
    add_box(-0.16, 0.0, 0.025, 0.16, 0.036, 0.068, 0)
    # Pistol grip (at origin)
    add_box(-0.02, 0.0, -0.045, 0.045, 0.034, 0.10, 0)
    # Foregrip / power cell magazine
    add_box(0.20, 0.0, -0.040, 0.055, 0.038, 0.095, 0)

    me = bpy.data.meshes.new("Gunner_Carbine_Mesh")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat_body)
    me.materials.append(mat_glow)

    # Simple box UV unwrap so UE5 lightmaps / PBR never complain about missing UVs
    uv_layer = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for loop_idx in poly.loop_indices:
            co = me.vertices[me.loops[loop_idx].vertex_index].co
            uv_layer.data[loop_idx].uv = (co.x + 0.5, co.z + 0.5)

    for poly in me.polygons:
        poly.use_smooth = False

    obj = bpy.data.objects.new("Gunner_Carbine", me)
    bpy.context.collection.objects.link(obj)
    return obj


def main():
    root = "/home/dabi/Documents/Mars Last Green"
    src_glb = "/home/dabi/Downloads/NASA Downloads/Mars_Last_Green_Scavenger.glb"
    work_dir = os.path.join(root, "Assets/Creatures/Production/_source_extracted/Gunner")
    prod_dir = os.path.join(root, "Assets/Creatures/Production/Gunner")
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(prod_dir, exist_ok=True)

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=src_glb)
    hi = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    hi.name = "Scavenger_HighRes"

    bpy.ops.object.select_all(action="DESELECT")
    hi.select_set(True)
    bpy.context.view_layer.objects.active = hi
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Rotate +90 deg Z (-Y front -> +X front), scale to 1.80m tall, ground Z=0, center XY
    rot_m = Matrix.Rotation(math.pi / 2.0, 3, "Z")
    zs = [v.co.z for v in hi.data.vertices]
    scale = 1.80 / (max(zs) - min(zs))
    xs_rot = []
    ys_rot = []
    zs_rot = []
    for v in hi.data.vertices:
        p = rot_m @ (v.co * scale)
        v.co = p
        xs_rot.append(p.x)
        ys_rot.append(p.y)
        zs_rot.append(p.z)
    cx = 0.5 * (min(xs_rot) + max(xs_rot))
    cy = 0.5 * (min(ys_rot) + max(ys_rot))
    cz = min(zs_rot)
    offset = Vector((cx, cy, cz))
    for v in hi.data.vertices:
        v.co -= offset
    hi.data.update()

    # Probe exact forearm/wrist/hand centroids for armature precision
    pts = [v.co for v in hi.data.vertices]
    for side, sgn in [("l", 1), ("r", -1)]:
        hand_pts = [p for p in pts if 0.68 <= p.z <= 0.85 and sgn * p.y > 0.30]
        if hand_pts:
            avg = sum(hand_pts, Vector((0, 0, 0))) / len(hand_pts)
            print(f"HAND_{side}: center=({avg.x:.3f}, {avg.y:.3f}, {avg.z:.3f}) minZ={min(p.z for p in hand_pts):.3f}", flush=True)

    # Export original basecolor PNG
    base_img = next((i for i in bpy.data.images if "basecolor" in i.name.lower()), None)
    base_tex_path = os.path.join(prod_dir, "Mars_Last_Green_Gunner_basecolor.png")
    if base_img:
        base_img.filepath_raw = base_tex_path
        base_img.file_format = "PNG"
        base_img.save()

    # Duplicate mesh for game-ready decimation (~48k tris)
    lo = hi.copy()
    lo.data = hi.data.copy()
    lo.name = "SK_Gunner_Body"
    bpy.context.collection.objects.link(lo)

    bpy.ops.object.select_all(action="DESELECT")
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
    dec = lo.modifiers.new("Decimate", "DECIMATE")
    dec.ratio = 0.025
    bpy.ops.object.modifier_apply(modifier=dec.name)
    for p in lo.data.polygons:
        p.use_smooth = True
    print(f"DECIMATED_GUNNER: verts={len(lo.data.vertices)} polys={len(lo.data.polygons)}", flush=True)

    # Bake 2048x2048 tangent-space normal map from 1.92M-poly sculpt onto 48k-poly mesh
    norm_tex_path = os.path.join(prod_dir, "Mars_Last_Green_Gunner_normal.png")
    norm_img = bpy.data.images.new("Mars_Last_Green_Gunner_normal", width=2048, height=2048, alpha=False)
    norm_img.colorspace_settings.name = "Non-Color"

    mat = lo.data.materials[0]
    mat.name = "M_Alien_Gunner"
    nt = mat.node_tree
    bake_node = nt.nodes.new("ShaderNodeTexImage")
    bake_node.image = norm_img
    bake_node.select = True
    nt.nodes.active = bake_node

    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = 1
    s.render.bake.use_selected_to_active = True
    s.render.bake.cage_extrusion = 0.025
    s.render.bake.max_ray_distance = 0.05
    s.render.bake.normal_space = "TANGENT"
    s.render.bake.margin = 4

    bpy.ops.object.select_all(action="DESELECT")
    hi.select_set(True)
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
    bpy.ops.object.bake(type="NORMAL")
    norm_img.filepath_raw = norm_tex_path
    norm_img.file_format = "PNG"
    norm_img.save()
    print("BAKED_NORMAL:", norm_tex_path, flush=True)

    # Wire normal map into M_Alien_Gunner Principled BSDF
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    norm_map = nt.nodes.new("ShaderNodeNormalMap")
    norm_map.inputs["Strength"].default_value = 1.0
    nt.links.new(bake_node.outputs["Color"], norm_map.inputs["Color"])
    nt.links.new(norm_map.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.65

    # Remove high-res sculpt from working scene
    bpy.data.objects.remove(hi, do_unlink=True)

    # Build UE5-style humanoid skeleton (+X forward, +Y left, -Y right, +Z up)
    bones_spec = {
        "root": ((0.0, 0.0, 0.0), (0.0, 0.0, 0.14), None, False),
        "pelvis": ((0.015, 0.0, 0.88), (0.020, 0.0, 1.00), "root", True),
        "spine_01": ((0.020, 0.0, 1.00), (0.025, 0.0, 1.15), "pelvis", True),
        "spine_02": ((0.025, 0.0, 1.15), (0.015, 0.0, 1.32), "spine_01", True),
        "spine_03": ((0.015, 0.0, 1.32), (0.010, 0.0, 1.44), "spine_02", True),
        "neck_01": ((0.010, 0.0, 1.44), (0.015, 0.0, 1.52), "spine_03", True),
        "head": ((0.015, 0.0, 1.52), (0.030, 0.0, 1.75), "neck_01", True),
    }
    for side, sgn in [("l", 1.0), ("r", -1.0)]:
        bones_spec.update({
            f"clavicle_{side}": ((0.005, sgn * 0.04, 1.38), (-0.015, sgn * 0.19, 1.37), "spine_03", True),
            f"upperarm_{side}": ((-0.018, sgn * 0.21, 1.37), (-0.014, sgn * 0.30, 1.10), f"clavicle_{side}", True),
            f"lowerarm_{side}": ((-0.014, sgn * 0.30, 1.10), (0.035, sgn * 0.37, 0.85), f"upperarm_{side}", True),
            f"hand_{side}": ((0.035, sgn * 0.37, 0.85), (0.045, sgn * 0.41, 0.72), f"lowerarm_{side}", True),
            f"thigh_{side}": ((0.020, sgn * 0.125, 0.84), (-0.055, sgn * 0.172, 0.515), "pelvis", True),
            f"calf_{side}": ((-0.055, sgn * 0.172, 0.515), (-0.072, sgn * 0.222, 0.136), f"thigh_{side}", True),
            f"foot_{side}": ((-0.072, sgn * 0.222, 0.136), (0.075, sgn * 0.232, 0.035), f"calf_{side}", True),
            f"ball_{side}": ((0.075, sgn * 0.232, 0.035), (0.175, sgn * 0.235, 0.025), f"foot_{side}", True),
        })
    # Weapon & muzzle bones attached to right hand
    bones_spec["weapon_r"] = ((0.042, -0.395, 0.78), (0.242, -0.395, 0.78), "hand_r", True)
    bones_spec["muzzle"] = ((0.582, -0.395, 0.825), (0.682, -0.395, 0.825), "weapon_r", False)

    adata = bpy.data.armatures.new("SK_Alien_Gunner_Skeleton")
    arm = bpy.data.objects.new("Armature", adata)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    lo.select_set(False)

    bpy.ops.object.mode_set(mode="EDIT")
    for bname, (head, tail, parent, deform) in bones_spec.items():
        eb = adata.edit_bones.new(bname)
        eb.head = head
        eb.tail = tail
        eb.use_deform = deform
        if parent:
            eb.parent = adata.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")

    # Anatomical skin weighting on Gunner body
    deform_bones = {
        bname: (Vector(head), Vector(tail))
        for bname, (head, tail, _, deform) in bones_spec.items()
        if deform and bname != "weapon_r"
    }
    for bname in deform_bones:
        lo.vertex_groups.new(name=bname)
    lo.vertex_groups.new(name="weapon_r")

    for v in lo.data.vertices:
        x, y, z = v.co
        side = "l" if y >= 0 else "r"
        ay = abs(y)
        if z < 0.12:
            choices = [f"foot_{side}", f"ball_{side}", f"calf_{side}"]
        elif z < 0.78 and ay < 0.30:
            choices = [f"thigh_{side}", f"calf_{side}", f"foot_{side}", "pelvis"]
        elif ay > 0.20 and z > 0.65 and z < 1.44:
            choices = [f"clavicle_{side}", f"upperarm_{side}", f"lowerarm_{side}", f"hand_{side}", "spine_03"]
        elif z >= 1.42:
            choices = ["spine_03", "neck_01", "head", f"clavicle_{side}"]
        else:
            choices = ["pelvis", "spine_01", "spine_02", "spine_03", f"clavicle_{side}", f"thigh_{side}"]

        weights = []
        for bn in choices:
            h, t = deform_bones[bn]
            seg = t - h
            f = max(0.0, min(1.0, (v.co - h).dot(seg) / max(seg.length_squared, 1e-6)))
            dist = (v.co - (h + f * seg)).length
            weights.append((1.0 / (dist + 0.018) ** 4, bn))
        weights.sort(reverse=True)
        weights = weights[:4]
        tot = sum(w for w, _ in weights)
        for w, bn in weights:
            if w / tot > 0.002:
                lo.vertex_groups[bn].add([v.index], w / tot, "REPLACE")

    # Build Gunner Energy Carbine & place in weapon_r rest frame
    mat_wep = bpy.data.materials.new("M_Gunner_Rifle")
    mat_wep.use_nodes = True
    bsdf_w = mat_wep.node_tree.nodes["Principled BSDF"]
    bsdf_w.inputs["Base Color"].default_value = (0.10, 0.11, 0.13, 1.0)
    bsdf_w.inputs["Metallic"].default_value = 0.85
    bsdf_w.inputs["Roughness"].default_value = 0.32

    mat_glow = bpy.data.materials.new("M_Gunner_RifleCore")
    mat_glow.use_nodes = True
    bsdf_g = mat_glow.node_tree.nodes["Principled BSDF"]
    bsdf_g.inputs["Base Color"].default_value = (0.15, 0.85, 1.0, 1.0)
    if "Emission Color" in bsdf_g.inputs:
        bsdf_g.inputs["Emission Color"].default_value = (0.2, 0.9, 1.0, 1.0)
        bsdf_g.inputs["Emission Strength"].default_value = 4.0

    carbine = build_energy_carbine(mat_wep, mat_glow)
    # Position carbine grip at weapon_r head (0.042, -0.395, 0.78)
    for v in carbine.data.vertices:
        v.co += Vector((0.042, -0.395, 0.78))
    carbine.data.update()

    # Join carbine into lo mesh or parent separately? Joining into one SkeletalMesh keeps 1 clean mesh!
    vg_wep = carbine.vertex_groups.new(name="weapon_r")
    vg_wep.add(list(range(len(carbine.data.vertices))), 1.0, "REPLACE")

    bpy.ops.object.select_all(action="DESELECT")
    lo.select_set(True)
    carbine.select_set(True)
    bpy.context.view_layer.objects.active = lo
    bpy.ops.object.join()

    lo.parent = arm
    mod = lo.modifiers.new("Armature", "ARMATURE")
    mod.object = arm

    bpy.ops.file.pack_all()
    blend_out = os.path.join(work_dir, "Gunner_base.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_out)
    print("SAVED_GUNNER_BASE:", blend_out, flush=True)


if __name__ == "__main__":
    main()
