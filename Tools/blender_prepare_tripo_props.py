"""Prepare all 5 Tripo Pro high-poly GLB assets for Unreal Engine 5.2.

Assets processed:
  1. Assets/Tripo/Mars_Hero_Botanical_Pod.glb -> Assets/Tripo/SM_Tripo_BotanicalPod.fbx
     - Bounds: 160.0 x 160.0 x 220.0 cm, +X forward, Z-up, minZ=0.0 (~32.5k tris)
     - Textures: Assets/Tripo/Textures/T_BotanicalPod_{BaseColor,Normal,Roughness,Metallic,RoughnessMetallic}.png
     - Preview:  Assets/Tripo/Previews/BotanicalPod_sheet.png (1200x1200)
  2. Assets/Tripo/Mars_Pulse_Rifle.glb -> Assets/Tripo/SM_Tripo_PulseRifle.fbx
     - Bounds: 80.0 x 13.4 x 36.6 cm, +X barrel forward, Z-up, grip/receiver pivot (~24.9k tris)
     - Textures: Assets/Tripo/Textures/T_PulseRifle_{BaseColor,Normal,Roughness,Metallic,RoughnessMetallic}.png
     - Preview:  Assets/Tripo/Previews/PulseRifle_sheet.png (1200x1200)
  3. Assets/Tripo/Mars_Alien_Monolith_Beacon.glb -> Assets/Tripo/SM_Tripo_AlienBeacon.fbx
     - Bounds: 130.0 x 130.0 x 260.0 cm, +X forward, Z-up, minZ=0.0 (~28.4k tris)
     - Textures: Assets/Tripo/Textures/T_AlienBeacon_{BaseColor,Normal,Roughness,Metallic,RoughnessMetallic}.png
     - Preview:  Assets/Tripo/Previews/AlienBeacon_sheet.png (1200x1200)
  4. Assets/Tripo/Mars_Sentry_Turret.glb -> Assets/Tripo/SM_Tripo_SentryTurret.fbx
     - Bounds: 110.0 x 110.0 x 145.0 cm, +X barrel forward, Z-up, minZ=0.0 (~28.5k tris)
     - Textures: Assets/Tripo/Textures/T_SentryTurret_{BaseColor,Normal,Roughness,Metallic,RoughnessMetallic}.png
     - Preview:  Assets/Tripo/Previews/SentryTurret_sheet.png (1200x1200)
  5. Assets/Tripo/Mars_Oxygen_Harvester.glb -> Assets/Tripo/SM_Tripo_OxygenHarvester.fbx
     - Bounds: 125.0 x 125.0 x 210.0 cm, +X forward, Z-up, minZ=0.0 (~28.1k tris)
     - Textures: Assets/Tripo/Textures/T_OxygenHarvester_{BaseColor,Normal,Roughness,Metallic,RoughnessMetallic}.png
     - Preview:  Assets/Tripo/Previews/OxygenHarvester_sheet.png (1200x1200)

Run via:
  blender -b --factory-startup --python "Tools/blender_prepare_tripo_props.py"
"""

import importlib
import json
import math
import os
import sys

import bmesh
import bpy
import bpy_extras.io_utils as io_utils
import io_scene_fbx
import numpy as np
from mathutils import Euler, Matrix, Vector

# Process-local Blender 5.0 io_scene_fbx orientation_helper annotation fix
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


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TRIPO_ROOT = os.path.join(PROJECT_ROOT, "Assets", "Tripo")
TEX_DIR = os.path.join(TRIPO_ROOT, "Textures")
PREVIEW_DIR = os.path.join(TRIPO_ROOT, "Previews")
OUT_MANIFEST = os.path.join(TRIPO_ROOT, "manifest.json")


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for col in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.lights, bpy.data.cameras):
        for item in list(col):
            if item.users == 0:
                col.remove(item)


def save_image_as_png(img, out_path, colorspace=None):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if colorspace:
        img.colorspace_settings.name = colorspace
    img.filepath_raw = out_path
    img.file_format = "PNG"
    img.save()
    return out_path


def save_numpy_rgba_png(arr_rgba, out_path, colorspace="sRGB"):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    h, w, _ = arr_rgba.shape
    im = bpy.data.images.new(os.path.basename(out_path), width=w, height=h, alpha=False)
    im.colorspace_settings.name = colorspace
    im.pixels.foreach_set(arr_rgba.astype(np.float32).ravel())
    im.filepath_raw = out_path
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)
    return out_path


def extract_channel_png(src_img, channel_idx, out_path):
    """Fast numpy extraction of a single channel (G=1 Roughness, B=2 Metallic) into a grayscale PNG."""
    w, h = src_img.size
    arr = np.empty(w * h * 4, dtype=np.float32)
    src_img.pixels.foreach_get(arr)
    arr = arr.reshape((h, w, 4))
    ch = arr[:, :, channel_idx]

    out = np.empty((h, w, 4), dtype=np.float32)
    out[:, :, 0] = ch
    out[:, :, 1] = ch
    out[:, :, 2] = ch
    out[:, :, 3] = 1.0
    return save_numpy_rgba_png(out, out_path, colorspace="Non-Color")


def build_pbr_material(mat_name, extracted):
    """Build clean PBR material wired to extracted/baked PNG textures."""
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (420, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    if "base_color" in extracted:
        n_bc = nt.nodes.new("ShaderNodeTexImage")
        n_bc.location = (-360, 220)
        n_bc.image = bpy.data.images.load(os.path.join(PROJECT_ROOT, extracted["base_color"]), check_existing=True)
        n_bc.image.colorspace_settings.name = "sRGB"
        nt.links.new(n_bc.outputs["Color"], bsdf.inputs["Base Color"])

    if "roughness" in extracted:
        n_r = nt.nodes.new("ShaderNodeTexImage")
        n_r.location = (-360, -20)
        n_r.image = bpy.data.images.load(os.path.join(PROJECT_ROOT, extracted["roughness"]), check_existing=True)
        n_r.image.colorspace_settings.name = "Non-Color"
        nt.links.new(n_r.outputs["Color"], bsdf.inputs["Roughness"])

    if "metallic" in extracted:
        n_m = nt.nodes.new("ShaderNodeTexImage")
        n_m.location = (-360, -260)
        n_m.image = bpy.data.images.load(os.path.join(PROJECT_ROOT, extracted["metallic"]), check_existing=True)
        n_m.image.colorspace_settings.name = "Non-Color"
        nt.links.new(n_m.outputs["Color"], bsdf.inputs["Metallic"])

    if "normal" in extracted:
        n_n = nt.nodes.new("ShaderNodeTexImage")
        n_n.location = (-560, -500)
        n_n.image = bpy.data.images.load(os.path.join(PROJECT_ROOT, extracted["normal"]), check_existing=True)
        n_n.image.colorspace_settings.name = "Non-Color"
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nmap.location = (-220, -500)
        nmap.inputs["Strength"].default_value = 1.0
        nt.links.new(n_n.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def export_fbx(obj, fbx_path):
    os.makedirs(os.path.dirname(fbx_path), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
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
        embed_textures=False,
    )


def verify_fbx_roundtrip(name, fbx_path):
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=fbx_path)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    assert len(meshes) == 1, f"Expected 1 mesh on re-import of {fbx_path}, got {len(meshes)}"
    imp = meshes[0]
    bpy.ops.object.select_all(action="DESELECT")
    imp.select_set(True)
    bpy.context.view_layer.objects.active = imp
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    pts = [imp.matrix_world @ v.co for v in imp.data.vertices]
    mn = [round(min(p[i] for p in pts) * 100.0, 2) for i in range(3)]
    mx = [round(max(p[i] for p in pts) * 100.0, 2) for i in range(3)]
    size_cm = [round(mx[i] - mn[i], 2) for i in range(3)]
    tris = sum(len(p.vertices) - 2 for p in imp.data.polygons)
    slots = [m.name.split(".")[0] if m else "None" for m in imp.data.materials]

    return {
        "name": name,
        "fbx": os.path.relpath(fbx_path, PROJECT_ROOT),
        "vertices": len(imp.data.vertices),
        "polygons": len(imp.data.polygons),
        "triangles": tris,
        "uv_layers": len(imp.data.uv_layers),
        "has_custom_normals": bool(imp.data.has_custom_normals),
        "ue_size_cm": size_cm,
        "ue_min_cm": mn,
        "ue_max_cm": mx,
        "material_slots": slots,
    }


def render_preview_sheet(fbx_path, mat_name, extracted, out_png, show_floor=True, custom_angles=None):
    """Render a 1200x1200 2x2 contact sheet (4 angles at 600x600 each)."""
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    clear_scene()

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    tile_w, tile_h = 600, 600
    cols, rows = 2, 2
    scene.render.resolution_x = tile_w
    scene.render.resolution_y = tile_h
    scene.render.resolution_percentage = 100

    if not scene.world:
        scene.world = bpy.data.worlds.new("PreviewWorld")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        # Dark studio background so metallic & bright highlights stand out with high contrast
        bg.inputs[0].default_value = (0.06, 0.045, 0.04, 1.0)
        bg.inputs[1].default_value = 1.2

    for lname, rot, energy, col in [
        ("KeySun", (0.72, 0.22, 0.65), 3.2, (1.0, 0.93, 0.86)),
        ("FillSun", (-0.65, -0.30, -2.35), 1.6, (0.75, 0.88, 1.0)),
        ("RimSun", (0.45, -0.45, 2.8), 2.2, (1.0, 0.68, 0.45)),
    ]:
        ld = bpy.data.lights.new(lname, "SUN")
        ld.energy = energy
        ld.color = col
        lo = bpy.data.objects.new(lname, ld)
        lo.rotation_euler = rot
        bpy.context.collection.objects.link(lo)

    floor = None
    if show_floor:
        bpy.ops.mesh.primitive_plane_add(size=12.0, location=(0.0, 0.0, -0.002))
        floor = bpy.context.active_object
        fmat = bpy.data.materials.new("PreviewFloor")
        fmat.use_nodes = True
        bsdf = fmat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (0.18, 0.10, 0.07, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.90
        floor.data.materials.append(fmat)

    cam_d = bpy.data.cameras.new("PreviewCam")
    cam_d.lens = 45.0
    cam_d.clip_start = 0.02
    cam_d.clip_end = 500.0
    cam = bpy.data.objects.new("PreviewCam", cam_d)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam

    bpy.ops.import_scene.fbx(filepath=fbx_path)
    imp = next(o for o in bpy.context.scene.objects if o.type == "MESH" and o != floor)
    pbr_mat = build_pbr_material(mat_name, extracted)
    if len(imp.data.materials) == 0:
        imp.data.materials.append(pbr_mat)
    else:
        for i in range(len(imp.data.materials)):
            imp.data.materials[i] = pbr_mat

    pts = [imp.matrix_world @ v.co for v in imp.data.vertices]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    center = (mn + mx) * 0.5
    span = max(mx.x - mn.x, mx.y - mn.y, mx.z - mn.z)
    dist = span * 1.48

    angles = custom_angles(dist) if custom_angles else [
        ("front_3q", Vector((dist * 0.80, -dist * 0.58, dist * 0.34))),
        ("front_x", Vector((dist * 1.02, 0.0, dist * 0.18))),
        ("side_y", Vector((dist * 0.25, dist * 0.96, dist * 0.28))),
        ("rear_3q", Vector((-dist * 0.76, dist * 0.62, dist * 0.38))),
    ]

    tiles = []
    for tag, off in angles:
        cam.location = center + off
        cam.rotation_euler = (center - cam.location).normalized().to_track_quat("-Z", "Y").to_euler()
        tmp = os.path.join(PREVIEW_DIR, f"_tmp_{mat_name}_{tag}.png")
        scene.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        tiles.append(tmp)

    total_w = cols * tile_w
    total_h = rows * tile_h
    sheet = bpy.data.images.new(f"{mat_name}_Sheet", width=total_w, height=total_h, alpha=True)
    buf = [0.0] * (total_w * total_h * 4)

    for idx, img_path in enumerate(tiles):
        r = idx // cols
        c = idx % cols
        y_base = (rows - 1 - r) * tile_h
        x_base = c * tile_w
        tile_img = bpy.data.images.load(img_path)
        px = list(tile_img.pixels)
        for y in range(tile_h):
            src_off = y * tile_w * 4
            dst_off = ((y_base + y) * total_w + x_base) * 4
            buf[dst_off : dst_off + tile_w * 4] = px[src_off : src_off + tile_w * 4]
        bpy.data.images.remove(tile_img)
        os.remove(img_path)

    sheet.pixels = buf
    sheet.filepath_raw = out_png
    sheet.file_format = "PNG"
    sheet.save()
    bpy.data.images.remove(sheet)


# ---------------------------------------------------------------------------
# High-Res Sculpt -> Game-Ready 2K PBR Baker (Normal + Pointiness/Zone EMIT)
# ---------------------------------------------------------------------------

def build_hi_surface_feature_material(z_min, z_max, x_min, x_max):
    """Build a Cycles shader on the 2M-poly sculpt that outputs:
      R = High-res sculpt Pointiness (0..1; <0.49 crevices/seams, >0.51 ridges/bevels)
      G = Normalized height Z (0 at z_min .. 1 at z_max)
      B = Normalized axial X (0 at x_min .. 1 at x_max) mixed with 3D surface noise
    """
    mat = bpy.data.materials.new("M_HiFeatureEmit")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])

    geom = nt.nodes.new("ShaderNodeNewGeometry")
    sep_xyz = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geom.outputs["Position"], sep_xyz.inputs["Vector"])

    map_z = nt.nodes.new("ShaderNodeMapRange")
    map_z.inputs["From Min"].default_value = float(z_min)
    map_z.inputs["From Max"].default_value = float(z_max)
    map_z.inputs["To Min"].default_value = 0.0
    map_z.inputs["To Max"].default_value = 1.0
    nt.links.new(sep_xyz.outputs["Z"], map_z.inputs["Value"])

    map_x = nt.nodes.new("ShaderNodeMapRange")
    map_x.inputs["From Min"].default_value = float(x_min)
    map_x.inputs["From Max"].default_value = float(x_max)
    map_x.inputs["To Min"].default_value = 0.0
    map_x.inputs["To Max"].default_value = 1.0
    nt.links.new(sep_xyz.outputs["X"], map_x.inputs["Value"])

    comb = nt.nodes.new("ShaderNodeCombineColor")
    nt.links.new(geom.outputs["Pointiness"], comb.inputs["Red"])
    nt.links.new(map_z.outputs["Result"], comb.inputs["Green"])
    nt.links.new(map_x.outputs["Result"], comb.inputs["Blue"])
    nt.links.new(comb.outputs["Color"], emit.inputs["Color"])
    return mat


def bake_sculpt_pbr_maps(hi_obj, lo_obj, prefix, palette_kind, cage_extrusion=0.018):
    """Bake 2048x2048 Tangent Normal + 2M-poly Pointiness/Zone map from hi_obj onto lo_obj,
    then synthesize rich, high-contrast 2K PBR BaseColor, Roughness, Metallic, and RM PNGs."""
    os.makedirs(TEX_DIR, exist_ok=True)
    res = 2048
    extracted = {}

    pts = [v.co for v in hi_obj.data.vertices]
    z_min, z_max = min(p.z for p in pts), max(p.z for p in pts)
    x_min, x_max = min(p.x for p in pts), max(p.x for p in pts)

    hi_mat = build_hi_surface_feature_material(z_min, z_max, x_min, x_max)
    hi_obj.data.materials.clear()
    hi_obj.data.materials.append(hi_mat)

    lo_mat = bpy.data.materials.new(f"M_BakeTarget_{prefix}")
    lo_mat.use_nodes = True
    lo_obj.data.materials.clear()
    lo_obj.data.materials.append(lo_mat)
    nt = lo_mat.node_tree
    bake_node = nt.nodes.new("ShaderNodeTexImage")
    bake_node.select = True
    nt.nodes.active = bake_node

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 1
    scene.render.bake.use_selected_to_active = True
    scene.render.bake.cage_extrusion = cage_extrusion
    scene.render.bake.max_ray_distance = cage_extrusion * 2.2
    scene.render.bake.margin = 6

    # 1. Bake 2048x2048 Tangent-Space Normal Map
    norm_img = bpy.data.images.new(f"T_{prefix}_Normal", width=res, height=res, alpha=False)
    norm_img.colorspace_settings.name = "Non-Color"
    bake_node.image = norm_img
    scene.render.bake.normal_space = "TANGENT"

    bpy.ops.object.select_all(action="DESELECT")
    hi_obj.select_set(True)
    lo_obj.select_set(True)
    bpy.context.view_layer.objects.active = lo_obj
    bpy.ops.object.bake(type="NORMAL")

    norm_path = os.path.join(TEX_DIR, f"T_{prefix}_Normal.png")
    save_image_as_png(norm_img, norm_path, colorspace="Non-Color")
    extracted["normal"] = os.path.relpath(norm_path, PROJECT_ROOT)

    # 2. Bake 2048x2048 High-Res Pointiness (R) + Z_norm (G) + X_norm (B)
    feat_img = bpy.data.images.new(f"T_{prefix}_Feat", width=res, height=res, alpha=False)
    feat_img.colorspace_settings.name = "Non-Color"
    bake_node.image = feat_img
    bpy.ops.object.bake(type="EMIT")

    norm_arr = np.empty(res * res * 4, dtype=np.float32)
    norm_img.pixels.foreach_get(norm_arr)
    norm_arr = norm_arr.reshape((res, res, 4))

    feat_arr = np.empty(res * res * 4, dtype=np.float32)
    feat_img.pixels.foreach_get(feat_arr)
    feat_arr = feat_arr.reshape((res, res, 4))

    bpy.data.images.remove(feat_img)
    bpy.data.images.remove(norm_img)

    # Extract per-texel features
    pt = feat_arr[:, :, 0]
    zn = feat_arr[:, :, 1]
    xn = feat_arr[:, :, 2]
    # Unmapped background texels have pt == 0; set neutral 0.5
    unmapped = pt < 0.01
    pt = np.where(unmapped, 0.5, pt)
    zn = np.where(unmapped, 0.5, zn)
    xn = np.where(unmapped, 0.5, xn)

    # Cavity (0..1 in crevices where pt < 0.495) and Ridge/Edge wear (0..1 on ridges where pt > 0.505)
    cavity = np.clip((0.498 - pt) * 28.0, 0.0, 1.0)
    edge = np.clip((pt - 0.503) * 26.0, 0.0, 1.0)
    nz = np.clip(norm_arr[:, :, 2] * 2.0 - 1.0, 0.0, 1.0)
    micro_bevel = np.clip(1.0 - nz, 0.0, 1.0) ** 0.7

    bc = np.ones((res, res, 4), dtype=np.float32)

    if palette_kind == "rifle":
        # Clean tangent normal (zero cage raycast self-intersection blotches across thin rails/trigger guard)
        flat_n = np.empty((res, res, 4), dtype=np.float32)
        flat_n[:, :, 0] = 0.5
        flat_n[:, :, 1] = 0.5
        flat_n[:, :, 2] = 1.0
        flat_n[:, :, 3] = 1.0
        save_numpy_rgba_png(flat_n, norm_path, colorspace="Non-Color")

        # Distinct multi-tone Mars Mk.IV Pulse Carbine livery:
        # Matte charcoal grip/stock/mag + dark slate lower receiver + silver-titanium barrel shroud + copper collar + cyan energy core
        is_grip_or_mag = (zn < 0.44) | ((xn < 0.28) & (zn < 0.66))
        is_upper_shroud = (xn > 0.46) & (zn >= 0.48) & (zn <= 0.84)
        is_optic_rail = zn > 0.78
        is_copper_trim = (xn > 0.40) & (xn <= 0.46) & (zn >= 0.46) & (zn <= 0.78)
        is_energy_vent = (xn > 0.50) & (xn < 0.86) & (zn > 0.50) & (zn < 0.75) & (cavity > 0.42)

        r = np.where(is_grip_or_mag, 0.10, np.where(is_copper_trim, 0.74, np.where(is_upper_shroud, 0.56, np.where(is_optic_rail, 0.16, 0.28))))
        g = np.where(is_grip_or_mag, 0.11, np.where(is_copper_trim, 0.42, np.where(is_upper_shroud, 0.59, np.where(is_optic_rail, 0.18, 0.31))))
        b = np.where(is_grip_or_mag, 0.13, np.where(is_copper_trim, 0.18, np.where(is_upper_shroud, 0.64, np.where(is_optic_rail, 0.21, 0.36))))

        r = r * (1.0 - 0.55 * cavity) + 0.22 * edge
        g = g * (1.0 - 0.55 * cavity) + 0.23 * edge
        b = b * (1.0 - 0.55 * cavity) + 0.25 * edge

        r = np.where(is_energy_vent, 0.12, r)
        g = np.where(is_energy_vent, 0.86, g)
        b = np.where(is_energy_vent, 1.00, b)

        rough = np.where(is_grip_or_mag, 0.62, 0.36) - 0.10 * edge + 0.18 * cavity
        metal = np.where(is_grip_or_mag, 0.18, 0.74) + 0.12 * edge - 0.20 * cavity

    elif palette_kind == "beacon":
        # Ancient Martian Alien Monolith: rusty regolith base + carved basalt-bronze spire + vivid glowing cyan runes
        dust_base = np.clip((0.24 - zn) * 4.5, 0.0, 1.0)
        is_rune = (zn > 0.18) & (cavity > 0.38)

        r = 0.22 * (1.0 - dust_base) + 0.48 * dust_base + 0.52 * edge - 0.08 * cavity
        g = 0.25 * (1.0 - dust_base) + 0.22 * dust_base + 0.38 * edge - 0.09 * cavity
        b = 0.30 * (1.0 - dust_base) + 0.13 * dust_base + 0.20 * edge - 0.10 * cavity

        r = np.where(is_rune, 0.12, r)
        g = np.where(is_rune, 0.90, g)
        b = np.where(is_rune, 1.00, b)

        rough = 0.40 * (1.0 - dust_base) + 0.86 * dust_base - 0.14 * edge + 0.16 * cavity
        metal = 0.52 * (1.0 - dust_base) + 0.34 * edge

    elif palette_kind == "turret":
        # Heavy Mars Perimeter Sentry Turret: dark tripod base + desert-ceramic upper armor + copper rings + cyan sensor
        dust = np.clip((0.18 - zn) * 5.5, 0.0, 1.0)
        is_base = zn < 0.42
        is_collar = (zn >= 0.42) & (zn <= 0.52)

        r = np.where(is_base, 0.16, np.where(is_collar, 0.68, 0.58))
        g = np.where(is_base, 0.17, np.where(is_collar, 0.38, 0.55))
        b = np.where(is_base, 0.19, np.where(is_collar, 0.16, 0.50))

        r = r * (1.0 - dust) + 0.40 * dust
        g = g * (1.0 - dust) + 0.19 * dust
        b = b * (1.0 - dust) + 0.11 * dust

        r = r * (1.0 - 0.68 * cavity) + 0.20 * edge
        g = g * (1.0 - 0.68 * cavity) + 0.20 * edge
        b = b * (1.0 - 0.68 * cavity) + 0.20 * edge

        rough = np.where(is_base, 0.46, 0.42) * (1.0 - dust) + 0.88 * dust - 0.12 * edge + 0.20 * cavity
        metal = np.where(is_base, 0.78, np.where(is_collar, 0.86, 0.38)) * (1.0 - dust) + 0.15 * edge

    elif palette_kind == "dropship":
        # NASA Heavy Mars Cargo Dropship: carbon heatshield belly, aerospace white thermal tiles,
        # hazard orange stripe, scorched gunmetal aft thrusters, Martian oxide lower landing dust
        dust = np.clip((0.12 - zn) * 7.5, 0.0, 1.0)
        is_belly_shield = zn < 0.21
        is_thruster_aft = xn > 0.76
        is_orange_stripe = (zn >= 0.38) & (zn <= 0.45) & (xn > 0.18) & (xn < 0.82)
        is_canopy_glass = (xn >= 0.16) & (xn <= 0.36) & (zn >= 0.60) & (zn <= 0.82) & (cavity > 0.32)

        r = np.where(is_belly_shield, 0.14, np.where(is_thruster_aft, 0.20, np.where(is_orange_stripe, 0.82, 0.74)))
        g = np.where(is_belly_shield, 0.14, np.where(is_thruster_aft, 0.21, np.where(is_orange_stripe, 0.32, 0.76)))
        b = np.where(is_belly_shield, 0.16, np.where(is_thruster_aft, 0.24, np.where(is_orange_stripe, 0.08, 0.79)))

        r = r * (1.0 - dust) + 0.42 * dust
        g = g * (1.0 - dust) + 0.20 * dust
        b = b * (1.0 - dust) + 0.11 * dust

        r = np.where(is_canopy_glass, 0.08, r * (1.0 - 0.62 * cavity) + 0.20 * edge)
        g = np.where(is_canopy_glass, 0.56, g * (1.0 - 0.62 * cavity) + 0.20 * edge)
        b = np.where(is_canopy_glass, 0.76, b * (1.0 - 0.62 * cavity) + 0.22 * edge)

        rough = np.where(is_canopy_glass, 0.12, np.where(is_belly_shield, 0.58, 0.38)) * (1.0 - dust) + 0.88 * dust - 0.10 * edge + 0.16 * cavity
        metal = np.where(is_thruster_aft, 0.84, np.where(is_canopy_glass, 0.10, np.where(is_orange_stripe, 0.25, 0.48))) * (1.0 - dust) + 0.15 * edge

    else:  # harvester
        # Mars Atmospheric Oxygen Harvester: dark base + aerospace white O2 pressure tanks + copper heat coils + cyan gauges
        dust = np.clip((0.16 - zn) * 6.0, 0.0, 1.0)
        is_base = zn < 0.24
        is_copper_band = ((zn > 0.44) & (zn < 0.56)) | ((zn > 0.74) & (zn < 0.82))
        is_vent = (cavity > 0.50) & (zn > 0.24)

        r = np.where(is_base, 0.15, np.where(is_copper_band, 0.72, 0.68))
        g = np.where(is_base, 0.16, np.where(is_copper_band, 0.40, 0.70))
        b = np.where(is_base, 0.18, np.where(is_copper_band, 0.18, 0.72))

        r = r * (1.0 - dust) + 0.40 * dust
        g = g * (1.0 - dust) + 0.19 * dust
        b = b * (1.0 - dust) + 0.11 * dust

        r = np.where(is_vent, 0.10, r * (1.0 - 0.60 * cavity) + 0.16 * edge)
        g = np.where(is_vent, 0.12, g * (1.0 - 0.60 * cavity) + 0.17 * edge)
        b = np.where(is_vent, 0.14, b * (1.0 - 0.60 * cavity) + 0.18 * edge)

        rough = np.where(is_copper_band, 0.30, 0.42) * (1.0 - dust) + 0.88 * dust - 0.10 * edge + 0.18 * cavity
        metal = np.where(is_base, 0.80, np.where(is_copper_band, 0.88, 0.28)) * (1.0 - dust) + 0.12 * edge

    bc[:, :, 0] = np.clip(r, 0.02, 0.98)
    bc[:, :, 1] = np.clip(g, 0.02, 0.98)
    bc[:, :, 2] = np.clip(b, 0.02, 0.98)
    bc[:, :, 3] = 1.0

    rough_ch = np.clip(rough, 0.12, 0.95)
    metal_ch = np.clip(metal, 0.04, 0.95)

    bc_path = os.path.join(TEX_DIR, f"T_{prefix}_BaseColor.png")
    save_numpy_rgba_png(bc, bc_path, colorspace="sRGB")
    extracted["base_color"] = os.path.relpath(bc_path, PROJECT_ROOT)

    for key, ch, fn in [
        ("roughness", rough_ch, f"T_{prefix}_Roughness.png"),
        ("metallic", metal_ch, f"T_{prefix}_Metallic.png"),
    ]:
        buf = np.empty((res, res, 4), dtype=np.float32)
        buf[:, :, 0] = ch
        buf[:, :, 1] = ch
        buf[:, :, 2] = ch
        buf[:, :, 3] = 1.0
        p = os.path.join(TEX_DIR, fn)
        save_numpy_rgba_png(buf, p, colorspace="Non-Color")
        extracted[key] = os.path.relpath(p, PROJECT_ROOT)

    rm_buf = np.empty((res, res, 4), dtype=np.float32)
    rm_buf[:, :, 0] = np.clip(1.0 - 0.55 * cavity, 0.25, 1.0)
    rm_buf[:, :, 1] = rough_ch
    rm_buf[:, :, 2] = metal_ch
    rm_buf[:, :, 3] = 1.0
    rm_path = os.path.join(TEX_DIR, f"T_{prefix}_RoughnessMetallic.png")
    save_numpy_rgba_png(rm_buf, rm_path, colorspace="Non-Color")
    extracted["roughness_metallic"] = os.path.relpath(rm_path, PROJECT_ROOT)

    print(f"BAKED_PBR_{prefix}: {extracted}", flush=True)
    return extracted


# ---------------------------------------------------------------------------
# Asset 1: Mars_Hero_Botanical_Pod.glb -> SM_Tripo_BotanicalPod.fbx
# ---------------------------------------------------------------------------

def process_botanical_pod(force_rebuild=False):
    pod_fbx = os.path.join(TRIPO_ROOT, "SM_Tripo_BotanicalPod.fbx")
    pod_sheet = os.path.join(PREVIEW_DIR, "BotanicalPod_sheet.png")
    extracted = {
        "base_color": "Assets/Tripo/Textures/T_BotanicalPod_BaseColor.png",
        "normal": "Assets/Tripo/Textures/T_BotanicalPod_Normal.png",
        "roughness_metallic": "Assets/Tripo/Textures/T_BotanicalPod_RoughnessMetallic.png",
        "roughness": "Assets/Tripo/Textures/T_BotanicalPod_Roughness.png",
        "metallic": "Assets/Tripo/Textures/T_BotanicalPod_Metallic.png",
    }
    if not force_rebuild and os.path.isfile(pod_fbx) and os.path.isfile(pod_sheet):
        info = verify_fbx_roundtrip("SM_Tripo_BotanicalPod", pod_fbx)
        print(f"TRIPO_POD_REUSED: {info}", flush=True)
        return info, extracted

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=os.path.join(TRIPO_ROOT, "Mars_Hero_Botanical_Pod.glb"))
    src_obj = next(o for o in bpy.context.scene.objects if o.type == "MESH" and "tripo" in o.name.lower())
    src_obj.name = "SM_Tripo_BotanicalPod"

    base_img = next((i for i in bpy.data.images if "basecolor" in i.name.lower()), None)
    rm_img = next((i for i in bpy.data.images if "_rm" in i.name.lower() or "rough" in i.name.lower()), None)
    norm_img = next((i for i in bpy.data.images if "normal" in i.name.lower()), None)

    if base_img:
        save_image_as_png(base_img, os.path.join(PROJECT_ROOT, extracted["base_color"]), colorspace="sRGB")
    if norm_img:
        save_image_as_png(norm_img, os.path.join(PROJECT_ROOT, extracted["normal"]), colorspace="Non-Color")
    if rm_img:
        save_image_as_png(rm_img, os.path.join(PROJECT_ROOT, extracted["roughness_metallic"]), colorspace="Non-Color")
        extract_channel_png(rm_img, 1, os.path.join(PROJECT_ROOT, extracted["roughness"]))
        extract_channel_png(rm_img, 2, os.path.join(PROJECT_ROOT, extracted["metallic"]))

    bpy.ops.object.select_all(action="DESELECT")
    src_obj.select_set(True)
    bpy.context.view_layer.objects.active = src_obj
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    for o in list(bpy.context.scene.objects):
        if o != src_obj:
            bpy.data.objects.remove(o, do_unlink=True)

    bm = bmesh.new()
    bm.from_mesh(src_obj.data)
    stray_verts = [v for v in bm.verts if v.co.x > 0.17 and v.co.z < 0.12]
    if stray_verts:
        bmesh.ops.delete(bm, geom=stray_verts, context="VERTS")
    bm.to_mesh(src_obj.data)
    bm.free()
    src_obj.data.update()

    rot_m = Matrix.Rotation(math.pi / 2.0, 3, "Z")
    pts_rot = [rot_m @ v.co for v in src_obj.data.vertices]
    min_x, max_x = min(p.x for p in pts_rot), max(p.x for p in pts_rot)
    min_y, max_y = min(p.y for p in pts_rot), max(p.y for p in pts_rot)
    min_z, max_z = min(p.z for p in pts_rot), max(p.z for p in pts_rot)

    target_x_m, target_y_m, target_z_m = 1.60, 1.60, 2.20
    sx = target_x_m / (max_x - min_x)
    sy = target_y_m / (max_y - min_y)
    sz = target_z_m / (max_z - min_z)
    cx, cy, cz = 0.5 * (min_x + max_x), 0.5 * (min_y + max_y), min_z

    for idx, v in enumerate(src_obj.data.vertices):
        p = pts_rot[idx]
        v.co = Vector(((p.x - cx) * sx, (p.y - cy) * sy, (p.z - cz) * sz))
    src_obj.data.update()

    dec = src_obj.modifiers.new("Decimate", "DECIMATE")
    dec.decimate_type = "COLLAPSE"
    dec.ratio = 0.017
    dec.delimit = {"UV", "MATERIAL"}
    bpy.ops.object.modifier_apply(modifier=dec.name)

    xs = [v.co.x for v in src_obj.data.vertices]
    ys = [v.co.y for v in src_obj.data.vertices]
    zs = [v.co.z for v in src_obj.data.vertices]
    mn = Vector((min(xs), min(ys), min(zs)))
    mx = Vector((max(xs), max(ys), max(zs)))
    span = mx - mn
    for v in src_obj.data.vertices:
        v.co.x = (v.co.x - 0.5 * (mn.x + mx.x)) * (target_x_m / span.x)
        v.co.y = (v.co.y - 0.5 * (mn.y + mx.y)) * (target_y_m / span.y)
        v.co.z = (v.co.z - mn.z) * (target_z_m / span.z)
    src_obj.data.update()

    pbr_mat = build_pbr_material("M_Tripo_BotanicalPod", extracted)
    src_obj.data.materials.clear()
    src_obj.data.materials.append(pbr_mat)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(42))

    export_fbx(src_obj, pod_fbx)
    info = verify_fbx_roundtrip("SM_Tripo_BotanicalPod", pod_fbx)
    render_preview_sheet(pod_fbx, "M_Tripo_BotanicalPod", extracted, pod_sheet, show_floor=True)
    return info, extracted


# ---------------------------------------------------------------------------
# Generic Sculpt Processor for PulseRifle, AlienBeacon, SentryTurret, OxygenHarvester
# ---------------------------------------------------------------------------

def process_sculpt_glb(
    glb_name,
    mesh_name,
    tex_prefix,
    mat_name,
    palette_kind,
    target_dims_m,
    decimate_ratio,
    ground_z=True,
    custom_pivot_raw=None,
    rot_z_rad=0.0,
    show_floor=True,
    custom_angles=None,
    carve_box_bounds=None,
    target_tris=32000.0,
):
    clear_scene()
    glb_path = os.path.join(TRIPO_ROOT, glb_name)
    fbx_path = os.path.join(TRIPO_ROOT, f"{mesh_name}.fbx")
    sheet_path = os.path.join(PREVIEW_DIR, f"{tex_prefix}_sheet.png")

    bpy.ops.import_scene.gltf(filepath=glb_path)
    hi_obj = next(o for o in bpy.context.scene.objects if o.type == "MESH" and "tripo" in o.name.lower())
    hi_obj.name = f"{mesh_name}_HighRes"

    bpy.ops.object.select_all(action="DESELECT")
    hi_obj.select_set(True)
    bpy.context.view_layer.objects.active = hi_obj
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    for o in list(bpy.context.scene.objects):
        if o != hi_obj:
            bpy.data.objects.remove(o, do_unlink=True)

    rot_m = Matrix.Rotation(rot_z_rad, 3, "Z")
    pts_rot = [rot_m @ v.co for v in hi_obj.data.vertices]
    min_x, max_x = min(p.x for p in pts_rot), max(p.x for p in pts_rot)
    min_y, max_y = min(p.y for p in pts_rot), max(p.y for p in pts_rot)
    min_z, max_z = min(p.z for p in pts_rot), max(p.z for p in pts_rot)

    if target_dims_m[1] is None:
        # Uniform scaling based on X length (for PulseRifle)
        scale = target_dims_m[0] / (max_x - min_x)
        sx = sy = sz = scale
    else:
        sx = target_dims_m[0] / (max_x - min_x)
        sy = target_dims_m[1] / (max_y - min_y)
        sz = target_dims_m[2] / (max_z - min_z)

    if custom_pivot_raw is not None:
        cx, cy, cz = custom_pivot_raw
    else:
        cx = 0.5 * (min_x + max_x)
        cy = 0.5 * (min_y + max_y)
        cz = min_z if ground_z else 0.5 * (min_z + max_z)

    for idx, v in enumerate(hi_obj.data.vertices):
        p = pts_rot[idx]
        v.co = Vector(((p.x - cx) * sx, (p.y - cy) * sy, (p.z - cz) * sz))
    hi_obj.data.update()

    # Duplicate high-res sculpt and decimate to game-ready polycount
    lo_obj = hi_obj.copy()
    lo_obj.data = hi_obj.data.copy()
    lo_obj.name = mesh_name
    bpy.context.collection.objects.link(lo_obj)

    bpy.ops.object.select_all(action="DESELECT")
    lo_obj.select_set(True)
    bpy.context.view_layer.objects.active = lo_obj
    dec = lo_obj.modifiers.new("Decimate", "DECIMATE")
    dec.decimate_type = "COLLAPSE"
    dec.ratio = min(1.0, float(target_tris) / max(1, sum(len(p.vertices) - 2 for p in hi_obj.data.polygons))) if decimate_ratio is None else decimate_ratio
    bpy.ops.object.modifier_apply(modifier=dec.name)

    # Exact post-decimation bounds normalization for grounded props
    if custom_pivot_raw is None and target_dims_m[1] is not None:
        xs = [v.co.x for v in lo_obj.data.vertices]
        ys = [v.co.y for v in lo_obj.data.vertices]
        zs = [v.co.z for v in lo_obj.data.vertices]
        mn = Vector((min(xs), min(ys), min(zs)))
        mx = Vector((max(xs), max(ys), max(zs)))
        span = mx - mn
        for v in lo_obj.data.vertices:
            v.co.x = (v.co.x - 0.5 * (mn.x + mx.x)) * (target_dims_m[0] / span.x)
            v.co.y = (v.co.y - 0.5 * (mn.y + mx.y)) * (target_dims_m[1] / span.y)
            v.co.z = (v.co.z - mn.z) * (target_dims_m[2] / span.z)
        lo_obj.data.update()

    if carve_box_bounds is not None:
        bx0, bx1, by0, by1, bz0, bz1 = carve_box_bounds
        bpy.ops.mesh.primitive_cube_add(
            size=1.0,
            location=((bx0 + bx1) * 0.5, (by0 + by1) * 0.5, (bz0 + bz1) * 0.5),
            scale=(bx1 - bx0, by1 - by0, bz1 - bz0),
        )
        cutter = bpy.context.active_object
        cutter.name = "_CabinCutter"
        bpy.ops.object.select_all(action="DESELECT")
        lo_obj.select_set(True)
        bpy.context.view_layer.objects.active = lo_obj
        bmod = lo_obj.modifiers.new("CarveCabin", "BOOLEAN")
        bmod.operation = "DIFFERENCE"
        bmod.solver = "FLOAT"
        bmod.object = cutter
        bpy.ops.object.modifier_apply(modifier=bmod.name)
        bpy.data.objects.remove(cutter, do_unlink=True)

    # Smart UV unwrap on the decimated mesh
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.008)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))

    # Bake 2K Normal + 2M-poly Pointiness/Zone PBR maps
    extracted = bake_sculpt_pbr_maps(hi_obj, lo_obj, tex_prefix, palette_kind)

    bpy.data.objects.remove(hi_obj, do_unlink=True)

    pbr_mat = build_pbr_material(mat_name, extracted)
    lo_obj.data.materials.clear()
    lo_obj.data.materials.append(pbr_mat)

    export_fbx(lo_obj, fbx_path)
    info = verify_fbx_roundtrip(mesh_name, fbx_path)
    if ground_z and custom_pivot_raw is None:
        assert abs(info["ue_min_cm"][2]) < 0.05, f"{mesh_name} minZ not grounded: {info['ue_min_cm']}"
    assert 15000 <= info["triangles"] <= 60000, f"{mesh_name} triangles {info['triangles']} outside target"

    render_preview_sheet(fbx_path, mat_name, extracted, sheet_path, show_floor=show_floor, custom_angles=custom_angles)
    print(f"TRIPO_SCULPT_VERIFIED {mesh_name}: {info}", flush=True)
    return info, extracted, os.path.relpath(sheet_path, PROJECT_ROOT)


def main():
    os.makedirs(TEX_DIR, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    if "--heavy-dropship" in sys.argv:
        def ship_angles(dist):
            return [
                ("cockpit_front_3q", Vector((-dist * 0.78, -dist * 0.62, dist * 0.34))),
                ("aft_ramp_bay", Vector((dist * 0.96, -dist * 0.20, dist * 0.24))),
                ("port_flank", Vector((-dist * 0.10, -dist * 0.98, dist * 0.30))),
                ("top_aft_3q", Vector((dist * 0.62, dist * 0.72, dist * 0.48))),
            ]

        info, textures, preview = process_sculpt_glb(
            glb_name="Mars_Heavy_Dropship.glb",
            mesh_name="SM_Tripo_HeavyDropship",
            tex_prefix="HeavyDropship",
            mat_name="M_Tripo_HeavyDropship",
            palette_kind="dropship",
            target_dims_m=(12.6, 8.8, 5.2),
            decimate_ratio=None,
            ground_z=True,
            rot_z_rad=math.pi * 0.5,
            show_floor=True,
            custom_angles=ship_angles,
            carve_box_bounds=(-3.40, 6.80, -2.02, 2.02, 0.34, 3.08),
            target_tris=46000.0,
        )
        with open(OUT_MANIFEST, encoding="utf-8") as fh:
            manifest = json.load(fh)
        manifest.setdefault("assets", {})["SM_Tripo_HeavyDropship"] = {
            "info": info,
            "textures": textures,
            "preview": preview,
        }
        with open(OUT_MANIFEST, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
        return
    if "--only-lander" in sys.argv:
        info, textures, preview = process_sculpt_glb(
            glb_name="Mars_Drop_Lander.glb", mesh_name="SM_Tripo_DropLander",
            tex_prefix="DropLander", mat_name="M_Tripo_DropLander", palette_kind="harvester",
            target_dims_m=(2.5, 2.5, 2.0), decimate_ratio=None, ground_z=True)
        with open(OUT_MANIFEST, encoding="utf-8") as fh:
            manifest = json.load(fh)
        manifest.setdefault("assets", {})["SM_Tripo_DropLander"] = {
            "info": info, "textures": textures, "preview": preview}
        with open(OUT_MANIFEST, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
        return
    force_pod = "--force-pod" in sys.argv

    pod_info, pod_tex = process_botanical_pod(force_rebuild=force_pod)

    def rifle_angles(dist):
        return [
            ("side_right_3q", Vector((dist * 0.42, -dist * 0.88, dist * 0.24))),
            ("side_profile", Vector((0.0, -dist * 0.96, dist * 0.10))),
            ("muzzle_front_3q", Vector((dist * 0.72, -dist * 0.64, dist * 0.26))),
            ("rear_left_3q", Vector((-dist * 0.56, dist * 0.82, dist * 0.28))),
        ]

    rifle_info, rifle_tex, rifle_sheet = process_sculpt_glb(
        glb_name="Mars_Pulse_Rifle.glb",
        mesh_name="SM_Tripo_PulseRifle",
        tex_prefix="PulseRifle",
        mat_name="M_Tripo_PulseRifle",
        palette_kind="rifle",
        target_dims_m=(0.80, None, None),
        decimate_ratio=0.013,
        ground_z=False,
        custom_pivot_raw=(-0.120, 0.0, 0.270),
        rot_z_rad=0.0,
        show_floor=False,
        custom_angles=rifle_angles,
    )

    beacon_info, beacon_tex, beacon_sheet = process_sculpt_glb(
        glb_name="Mars_Alien_Monolith_Beacon.glb",
        mesh_name="SM_Tripo_AlienBeacon",
        tex_prefix="AlienBeacon",
        mat_name="M_Tripo_AlienBeacon",
        palette_kind="beacon",
        target_dims_m=(1.30, 1.30, 2.60),
        decimate_ratio=0.0145,
        ground_z=True,
        rot_z_rad=0.0,
        show_floor=True,
    )

    turret_info, turret_tex, turret_sheet = process_sculpt_glb(
        glb_name="Mars_Sentry_Turret.glb",
        mesh_name="SM_Tripo_SentryTurret",
        tex_prefix="SentryTurret",
        mat_name="M_Tripo_SentryTurret",
        palette_kind="turret",
        target_dims_m=(1.10, 1.10, 1.45),
        decimate_ratio=0.0145,
        ground_z=True,
        rot_z_rad=0.0,
        show_floor=True,
    )

    harv_info, harv_tex, harv_sheet = process_sculpt_glb(
        glb_name="Mars_Oxygen_Harvester.glb",
        mesh_name="SM_Tripo_OxygenHarvester",
        tex_prefix="OxygenHarvester",
        mat_name="M_Tripo_OxygenHarvester",
        palette_kind="harvester",
        target_dims_m=(1.25, 1.25, 2.10),
        decimate_ratio=0.0145,
        ground_z=True,
        rot_z_rad=0.0,
        show_floor=True,
    )

    manifest = {
        "assets": {
            "SM_Tripo_BotanicalPod": {
                "info": pod_info,
                "textures": pod_tex,
                "preview": "Assets/Tripo/Previews/BotanicalPod_sheet.png",
            },
            "SM_Tripo_PulseRifle": {
                "info": rifle_info,
                "textures": rifle_tex,
                "preview": rifle_sheet,
            },
            "SM_Tripo_AlienBeacon": {
                "info": beacon_info,
                "textures": beacon_tex,
                "preview": beacon_sheet,
            },
            "SM_Tripo_SentryTurret": {
                "info": turret_info,
                "textures": turret_tex,
                "preview": turret_sheet,
            },
            "SM_Tripo_OxygenHarvester": {
                "info": harv_info,
                "textures": harv_tex,
                "preview": harv_sheet,
            },
        }
    }
    with open(OUT_MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"TRIPO_ALL_5_DONE manifest={OUT_MANIFEST}", flush=True)


if __name__ == "__main__":
    main()
