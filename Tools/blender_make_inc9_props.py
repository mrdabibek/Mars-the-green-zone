"""Generate Increment 9 UE5-ready hard-surface & Mars environment props in Blender.

Outputs:
  - Assets/Props_Inc9/SM_Log_Terminal.fbx        (~70x60x135 cm)
  - Assets/Props_Inc9/SM_Habitat_WallPanel.fbx   (~100x40x300 cm)
  - Assets/Props_Inc9/SM_Habitat_FloorTile.fbx   (~100x100x20 cm)
  - Assets/Props_Inc9/SM_Greenhouse_GlassRoof.fbx (~100x100x20 cm)
  - Assets/Props_Inc9/SM_Mars_SolarArray.fbx     (~220x160x280 cm)
  - Assets/Props_Inc9/SM_Mars_RoverWreck.fbx     (~220x150x115 cm)
  - Assets/Props_Inc9/SM_Mars_TerrainSkirt.fbx   (~80000x80000x3500 cm, inner radius ~24500 cm, outer ~40000 cm)
  - Assets/Props_Inc9/Previews/Inc9_Props_sheet.png (1200x1200 multi-angle contact sheet)
  - Assets/Props_Inc9/manifest.json

Conventions:
  - Z-up, +X forward, ground-centered pivot with minZ = 0, Blender meters -> UE5 cm (1m = 100cm)
  - Clean bevel + angle-smoothed normals, smart-projected UVs, semantic multi-material slots

Run via:
  blender -b --factory-startup --python "Tools/blender_make_inc9_props.py"
"""

import importlib
import json
import math
import os

import bmesh
import bpy
import bpy_extras.io_utils as io_utils
import io_scene_fbx
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
INC9_ROOT = os.path.join(PROJECT_ROOT, "Assets", "Props_Inc9")
PREVIEW_DIR = os.path.join(INC9_ROOT, "Previews")


# ---------------------------------------------------------------------------
# Material library (procedural PBR shaders for previews + clean UE5 slots)
# ---------------------------------------------------------------------------

MAT_SPECS = {
    "M_Dev_Armor": {
        "base_color": (0.74, 0.72, 0.68, 1.0),
        "metallic": 0.22,
        "roughness": 0.42,
        "emissive": (0.0, 0.0, 0.0, 1.0),
        "emissive_strength": 0.0,
        "is_emissive": False,
        "noise_scale": 14.0,
        "rough_var": 0.10,
    },
    "M_Dev_MetalDark": {
        "base_color": (0.14, 0.15, 0.17, 1.0),
        "metallic": 0.85,
        "roughness": 0.36,
        "emissive": (0.0, 0.0, 0.0, 1.0),
        "emissive_strength": 0.0,
        "is_emissive": False,
        "noise_scale": 22.0,
        "rough_var": 0.12,
    },
    "M_Dev_Copper": {
        "base_color": (0.76, 0.42, 0.18, 1.0),
        "metallic": 0.90,
        "roughness": 0.28,
        "emissive": (0.0, 0.0, 0.0, 1.0),
        "emissive_strength": 0.0,
        "is_emissive": False,
        "noise_scale": 24.0,
        "rough_var": 0.08,
    },
    "M_EmissiveAccent": {
        "base_color": (0.06, 0.16, 0.20, 1.0),
        "metallic": 0.10,
        "roughness": 0.18,
        "emissive": (0.12, 0.78, 0.95, 1.0),
        "emissive_strength": 2.2,
        "is_emissive": True,
        "noise_scale": 10.0,
        "rough_var": 0.02,
    },
    "M_Habitat_Wall": {
        "base_color": (0.28, 0.31, 0.35, 1.0),
        "metallic": 0.35,
        "roughness": 0.55,
        "emissive": (0.0, 0.0, 0.0, 1.0),
        "emissive_strength": 0.0,
        "is_emissive": False,
        "noise_scale": 16.0,
        "rough_var": 0.08,
    },
    "M_Habitat_Floor": {
        "base_color": (0.22, 0.24, 0.27, 1.0),
        "metallic": 0.72,
        "roughness": 0.44,
        "emissive": (0.0, 0.0, 0.0, 1.0),
        "emissive_strength": 0.0,
        "is_emissive": False,
        "noise_scale": 26.0,
        "rough_var": 0.10,
    },
    "M_GlassRoof": {
        "base_color": (0.42, 0.74, 0.88, 0.32),
        "metallic": 0.05,
        "roughness": 0.08,
        "emissive": (0.16, 0.32, 0.38, 1.0),
        "emissive_strength": 0.35,
        "is_emissive": False,
        "is_translucent": True,
        "opacity": 0.28,
        "noise_scale": 8.0,
        "rough_var": 0.02,
    },
    "M_SolarCell": {
        "base_color": (0.09, 0.11, 0.15, 1.0),
        "metallic": 0.42,
        "roughness": 0.44,
        "emissive": (0.004, 0.014, 0.028, 1.0),
        "emissive_strength": 0.06,
        "is_emissive": False,
        "noise_scale": 34.0,
        "rough_var": 0.14,
    },
    "M_Mars_Ground": {
        "base_color": (0.42, 0.19, 0.11, 1.0),
        "metallic": 0.0,
        "roughness": 0.92,
        "emissive": (0.0, 0.0, 0.0, 1.0),
        "emissive_strength": 0.0,
        "is_emissive": False,
        "noise_scale": 18.0,
        "rough_var": 0.08,
    },
    "M_RegolithSoil": {
        "base_color": (0.25, 0.12, 0.08, 1.0),
        "metallic": 0.0,
        "roughness": 0.94,
        "emissive": (0.0, 0.0, 0.0, 1.0),
        "emissive_strength": 0.0,
        "is_emissive": False,
        "noise_scale": 28.0,
        "rough_var": 0.06,
    },
}


def get_material(name):
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get("mlg_built"):
        return mat
    spec = MAT_SPECS[name]
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat["mlg_built"] = True
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (380, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (80, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tex_coord = nt.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-600, 0)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.location = (-380, -80)
    noise.inputs["Scale"].default_value = spec["noise_scale"]
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.6
    nt.links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])

    mix_col = nt.nodes.new("ShaderNodeMix")
    mix_col.data_type = "RGBA"
    mix_col.location = (-150, 120)
    rgba_ins = [s for s in mix_col.inputs if s.type == "RGBA"]
    rgba_out = [s for s in mix_col.outputs if s.type == "RGBA"][0]
    bc = spec["base_color"]
    rgba_ins[0].default_value = bc
    rgba_ins[1].default_value = (bc[0] * 0.78, bc[1] * 0.78, bc[2] * 0.78, 1.0)
    nt.links.new(noise.outputs["Fac"], mix_col.inputs[0])
    nt.links.new(rgba_out, bsdf.inputs["Base Color"])

    map_r = nt.nodes.new("ShaderNodeMapRange")
    map_r.location = (-150, -100)
    r0 = max(0.04, spec["roughness"] - spec["rough_var"])
    r1 = min(0.98, spec["roughness"] + spec["rough_var"])
    map_r.inputs["To Min"].default_value = r0
    map_r.inputs["To Max"].default_value = r1
    nt.links.new(noise.outputs["Fac"], map_r.inputs["Value"])
    nt.links.new(map_r.outputs["Result"], bsdf.inputs["Roughness"])

    bsdf.inputs["Metallic"].default_value = spec["metallic"]
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = spec["emissive"]
        bsdf.inputs["Emission Strength"].default_value = spec["emissive_strength"]
    if spec.get("is_translucent") and "Alpha" in bsdf.inputs:
        bsdf.inputs["Alpha"].default_value = spec.get("opacity", 0.32)

    return mat


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for col in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.lights, bpy.data.cameras):
        for item in list(col):
            if item.users == 0:
                col.remove(item)


# ---------------------------------------------------------------------------
# BMesh Hard-Surface & Environment Part Builders
# ---------------------------------------------------------------------------

class MeshAssembler:
    """Accumulates labeled geometry parts with per-face material tags and clean normals."""

    def __init__(self, mat_order):
        self.bm = bmesh.new()
        self.mat_order = list(mat_order)
        self.mat_map = {name: idx for idx, name in enumerate(self.mat_order)}

    def add_box(self, size, center=(0, 0, 0), rot=(0, 0, 0), bevel=0.0, bevel_segs=2, mat="M_Dev_Armor"):
        sx, sy, sz = size
        tmp = bmesh.new()
        bmesh.ops.create_cube(tmp, size=1.0)
        for v in tmp.verts:
            v.co.x *= sx
            v.co.y *= sy
            v.co.z *= sz
        if bevel > 0.0:
            max_b = min(sx, sy, sz) * 0.42
            b_amt = min(bevel, max_b)
            if b_amt > 1e-4:
                bmesh.ops.bevel(
                    tmp,
                    geom=list(tmp.edges),
                    offset=b_amt,
                    segments=bevel_segs,
                    profile=0.5,
                    affect="EDGES",
                    clamp_overlap=True,
                )
        bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
        xform = Matrix.Translation(center) @ Euler(rot, "XYZ").to_matrix().to_4x4()
        self._merge_tmp(tmp, mat, xform)

    def add_tapered_box(self, size_bot, size_top, height, center_base=(0, 0, 0), rot=(0, 0, 0), bevel=0.0, mat="M_Dev_Armor"):
        bx, by = size_bot[0] * 0.5, size_bot[1] * 0.5
        tx, ty = size_top[0] * 0.5, size_top[1] * 0.5
        tmp = bmesh.new()
        v0 = tmp.verts.new((-bx, -by, 0.0))
        v1 = tmp.verts.new((bx, -by, 0.0))
        v2 = tmp.verts.new((bx, by, 0.0))
        v3 = tmp.verts.new((-bx, by, 0.0))
        v4 = tmp.verts.new((-tx, -ty, height))
        v5 = tmp.verts.new((tx, -ty, height))
        v6 = tmp.verts.new((tx, ty, height))
        v7 = tmp.verts.new((-tx, ty, height))
        tmp.faces.new((v3, v2, v1, v0))
        tmp.faces.new((v4, v5, v6, v7))
        tmp.faces.new((v0, v1, v5, v4))
        tmp.faces.new((v1, v2, v6, v5))
        tmp.faces.new((v2, v3, v7, v6))
        tmp.faces.new((v3, v0, v4, v7))
        if bevel > 0.0:
            bmesh.ops.bevel(
                tmp,
                geom=list(tmp.edges),
                offset=bevel,
                segments=2,
                profile=0.5,
                affect="EDGES",
                clamp_overlap=True,
            )
        bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
        xform = Matrix.Translation(center_base) @ Euler(rot, "XYZ").to_matrix().to_4x4()
        self._merge_tmp(tmp, mat, xform)

    def add_cylinder(self, r1, r2, depth, center=(0, 0, 0), rot=(0, 0, 0), segs=24, bevel=0.0, mat="M_Dev_MetalDark"):
        tmp = bmesh.new()
        bmesh.ops.create_cone(
            tmp,
            cap_ends=True,
            cap_tris=False,
            segments=segs,
            radius1=r1,
            radius2=r2,
            depth=depth,
        )
        if bevel > 0.0:
            cap_edges = [
                e for e in tmp.edges
                if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-4
            ]
            if cap_edges:
                bmesh.ops.bevel(
                    tmp,
                    geom=cap_edges,
                    offset=min(bevel, min(r1, r2, depth * 0.4) * 0.45),
                    segments=2,
                    profile=0.5,
                    affect="EDGES",
                    clamp_overlap=True,
                )
        bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
        xform = Matrix.Translation(center) @ Euler(rot, "XYZ").to_matrix().to_4x4()
        self._merge_tmp(tmp, mat, xform)

    def add_sphere(self, radius, center=(0, 0, 0), scale=(1, 1, 1), u_segs=18, v_segs=12, mat="M_EmissiveAccent"):
        tmp = bmesh.new()
        bmesh.ops.create_uvsphere(tmp, u_segments=u_segs, v_segments=v_segs, radius=radius)
        for v in tmp.verts:
            v.co.x *= scale[0]
            v.co.y *= scale[1]
            v.co.z *= scale[2]
        bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
        xform = Matrix.Translation(center)
        self._merge_tmp(tmp, mat, xform)

    def add_torus_ring(self, major_r, minor_r, center=(0, 0, 0), rot=(0, 0, 0), major_segs=28, minor_segs=10, mat="M_Dev_MetalDark"):
        tmp = bmesh.new()
        rings = []
        for i in range(major_segs):
            theta = (2.0 * math.pi * i) / major_segs
            ct, st = math.cos(theta), math.sin(theta)
            ring = []
            for j in range(minor_segs):
                phi = (2.0 * math.pi * j) / minor_segs
                r = major_r + minor_r * math.cos(phi)
                z = minor_r * math.sin(phi)
                ring.append(tmp.verts.new((r * ct, r * st, z)))
            rings.append(ring)
        for i in range(major_segs):
            ni = (i + 1) % major_segs
            for j in range(minor_segs):
                nj = (j + 1) % minor_segs
                tmp.faces.new((rings[i][j], rings[ni][j], rings[ni][nj], rings[i][nj]))
        bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
        xform = Matrix.Translation(center) @ Euler(rot, "XYZ").to_matrix().to_4x4()
        self._merge_tmp(tmp, mat, xform)

    def add_strut(self, p0, p1, radius, segs=10, mat="M_Dev_MetalDark"):
        v0 = Vector(p0)
        v1 = Vector(p1)
        vec = v1 - v0
        length = vec.length
        if length < 1e-5:
            return
        mid = (v0 + v1) * 0.5
        quat = vec.normalized().to_track_quat("Z", "Y")
        tmp = bmesh.new()
        bmesh.ops.create_cone(
            tmp, cap_ends=True, cap_tris=False, segments=segs, radius1=radius, radius2=radius, depth=length
        )
        bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
        xform = Matrix.Translation(mid) @ quat.to_matrix().to_4x4()
        self._merge_tmp(tmp, mat, xform)

    def add_parabolic_dish(self, radius, depth, thickness=0.015, center=(0, 0, 0), rot=(0, 0, 0), radial_segs=24, rings=5, mat="M_Dev_Armor"):
        tmp = bmesh.new()
        front_rings = []
        back_rings = []
        c_front = tmp.verts.new((0.0, 0.0, 0.0))
        c_back = tmp.verts.new((0.0, 0.0, -thickness))
        for ri in range(1, rings + 1):
            frac = ri / rings
            r = radius * frac
            z = depth * (frac * frac)
            fr = []
            br = []
            for si in range(radial_segs):
                ang = (2.0 * math.pi * si) / radial_segs
                x, y = r * math.cos(ang), r * math.sin(ang)
                fr.append(tmp.verts.new((x, y, z)))
                br.append(tmp.verts.new((x, y, z - thickness)))
            front_rings.append(fr)
            back_rings.append(br)
        for si in range(radial_segs):
            ns = (si + 1) % radial_segs
            tmp.faces.new((c_front, front_rings[0][si], front_rings[0][ns]))
            tmp.faces.new((c_back, back_rings[0][ns], back_rings[0][si]))
        for ri in range(rings - 1):
            for si in range(radial_segs):
                ns = (si + 1) % radial_segs
                tmp.faces.new((front_rings[ri][si], front_rings[ri + 1][si], front_rings[ri + 1][ns], front_rings[ri][ns]))
                tmp.faces.new((back_rings[ri][ns], back_rings[ri + 1][ns], back_rings[ri + 1][si], back_rings[ri][si]))
        for si in range(radial_segs):
            ns = (si + 1) % radial_segs
            tmp.faces.new((front_rings[-1][si], back_rings[-1][si], back_rings[-1][ns], front_rings[-1][ns]))
        bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
        xform = Matrix.Translation(center) @ Euler(rot, "XYZ").to_matrix().to_4x4()
        self._merge_tmp(tmp, mat, xform)

    def _merge_tmp(self, tmp, mat_name, xform):
        mat_idx = self.mat_map[mat_name]
        v_map = {}
        for v in tmp.verts:
            co = xform @ v.co
            v_map[v] = self.bm.verts.new(co)
        for f in tmp.faces:
            try:
                nf = self.bm.faces.new([v_map[v] for v in f.verts])
                nf.material_index = mat_idx
                nf.smooth = True
            except ValueError:
                pass
        tmp.free()

    def build_object(self, name, target_dims_m=None, center_xy=True, ground_z=True, uv_project="smart"):
        """Convert accumulated BMesh to Blender object, normalize pivot/bounds, smooth & UV unwrap."""
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)

        used_indices = sorted({f.material_index for f in self.bm.faces})
        remap = {old: new for new, old in enumerate(used_indices)}
        used_names = [self.mat_order[i] for i in used_indices]
        for f in self.bm.faces:
            f.material_index = remap[f.material_index]

        xs = [v.co.x for v in self.bm.verts]
        ys = [v.co.y for v in self.bm.verts]
        zs = [v.co.z for v in self.bm.verts]
        mn = Vector((min(xs), min(ys), min(zs)))
        mx = Vector((max(xs), max(ys), max(zs)))
        size = mx - mn

        sx = (target_dims_m[0] / size.x) if (target_dims_m and target_dims_m[0] and size.x > 1e-5) else 1.0
        sy = (target_dims_m[1] / size.y) if (target_dims_m and target_dims_m[1] and size.y > 1e-5) else 1.0
        sz = (target_dims_m[2] / size.z) if (target_dims_m and target_dims_m[2] and size.z > 1e-5) else 1.0

        cx = 0.5 * (mn.x + mx.x) if center_xy else 0.0
        cy = 0.5 * (mn.y + mx.y) if center_xy else 0.0
        cz = mn.z if ground_z else 0.0

        for v in self.bm.verts:
            v.co.x = (v.co.x - cx) * sx
            v.co.y = (v.co.y - cy) * sy
            v.co.z = (v.co.z - cz) * sz

        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()

        for mname in used_names:
            me.materials.append(get_material(mname))

        obj = bpy.data.objects.new(name, me)
        bpy.context.collection.objects.link(obj)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        if uv_project == "planar_z":
            # Fast planar top-down UV projection for large terrain meshes
            uv_layer = me.uv_layers.new(name="UVMap")
            me.uv_layers.active = uv_layer
            span_x = max(1e-3, (mx.x - mn.x) * sx)
            span_y = max(1e-3, (mx.y - mn.y) * sy)
            for poly in me.polygons:
                for li in poly.loop_indices:
                    vi = me.loops[li].vertex_index
                    co = me.vertices[vi].co
                    uv_layer.data[li].uv = ((co.x / span_x) + 0.5, (co.y / span_y) + 0.5)
        else:
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.015)
            bpy.ops.object.mode_set(mode="OBJECT")

        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(38))
        return obj


# ---------------------------------------------------------------------------
# 7 Increment 9 Asset Builders
# ---------------------------------------------------------------------------

def build_log_terminal():
    """1. SM_Log_Terminal.fbx (~70x60x135 cm): Ruggedized NASA-style Mars field computer terminal
    with angled telemetry screen (M_EmissiveAccent), keyboard deck, armored stand."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_Dev_Copper", "M_EmissiveAccent"])

    # Heavy bolted ground base plinth & 4 corner leveling pads
    m.add_box((0.66, 0.58, 0.06), center=(0.0, 0.0, 0.03), bevel=0.012, mat="M_Dev_MetalDark")
    for sx in (-0.28, 0.28):
        for sy in (-0.24, 0.24):
            m.add_cylinder(0.045, 0.055, 0.04, center=(sx, sy, 0.02), segs=12, bevel=0.005, mat="M_Dev_MetalDark")

    # Armored lower pedestal stand (Z=0.06..0.78) with recessed access hatch & side ribs
    m.add_tapered_box((0.46, 0.44), (0.40, 0.40), 0.72, center_base=(-0.03, 0.0, 0.06), bevel=0.016, mat="M_Dev_Armor")
    for sy in (-0.21, 0.21):
        m.add_box((0.28, 0.04, 0.66), center=(-0.03, sy, 0.42), bevel=0.008, mat="M_Dev_MetalDark")
    # Front lower data-core bay door + copper power conduit pipes
    m.add_box((0.04, 0.28, 0.38), center=(0.18, 0.0, 0.36), bevel=0.008, mat="M_Dev_MetalDark")
    m.add_box((0.02, 0.20, 0.03), center=(0.202, 0.0, 0.50), bevel=0.004, mat="M_EmissiveAccent")
    for sy in (-0.14, 0.14):
        m.add_cylinder(0.018, 0.018, 0.62, center=(-0.22, sy, 0.42), segs=12, mat="M_Dev_Copper")

    # Cantilevered keyboard & field telemetry deck (+X operator side, Z=0.78..0.88)
    m.add_box((0.58, 0.56, 0.08), center=(0.05, 0.0, 0.82), rot=(0, math.radians(8), 0), bevel=0.014, mat="M_Dev_MetalDark")
    # Tactile keyboard keybank + keycard reader pad + wrist guard bar
    m.add_box((0.18, 0.32, 0.03), center=(0.17, -0.05, 0.855), rot=(0, math.radians(8), 0), bevel=0.006, mat="M_Dev_Armor")
    m.add_box((0.10, 0.09, 0.025), center=(0.17, 0.18, 0.855), rot=(0, math.radians(8), 0), bevel=0.005, mat="M_EmissiveAccent")
    for sy in (-0.26, 0.26):
        m.add_strut((0.30, sy, 0.80), (0.12, sy, 0.83), 0.014, segs=10, mat="M_Dev_Copper")

    # Upper armored display housing & sun-visor hood (Z=0.84..1.28)
    tilt = math.radians(-22)
    m.add_box((0.28, 0.54, 0.40), center=(-0.05, 0.0, 1.06), rot=(0, tilt, 0), bevel=0.016, mat="M_Dev_Armor")
    # Dark bezel frame + glowing angled telemetry screen (+X facing)
    m.add_box((0.06, 0.48, 0.34), center=(0.07, 0.0, 1.07), rot=(0, tilt, 0), bevel=0.010, mat="M_Dev_MetalDark")
    m.add_box((0.03, 0.42, 0.27), center=(0.092, 0.0, 1.07), rot=(0, tilt, 0), bevel=0.005, mat="M_EmissiveAccent")
    # Protective top sun-hood visor over the screen
    m.add_box((0.16, 0.52, 0.035), center=(0.06, 0.0, 1.24), rot=(0, math.radians(6), 0), bevel=0.006, mat="M_Dev_MetalDark")

    # Top telemetry whip antenna & status beacon tip reaching Z=1.35
    m.add_cylinder(0.024, 0.018, 0.10, center=(-0.12, 0.20, 1.28), segs=12, mat="M_Dev_Copper")
    m.add_sphere(0.028, center=(-0.12, 0.20, 1.335), mat="M_EmissiveAccent")

    return m.build_object("SM_Log_Terminal", target_dims_m=(0.70, 0.60, 1.35))


def build_habitat_wall_panel():
    """2. SM_Habitat_WallPanel.fbx (~100x40x300 cm, unit-scalable modular wall bay):
    Ribbed sci-fi composite bulkhead wall with structural vertical ribs, recessed trim band,
    and subtle LED strip slot (M_EmissiveAccent)."""
    m = MeshAssembler(["M_Habitat_Wall", "M_Dev_MetalDark", "M_EmissiveAccent"])

    # Main composite bulkhead core (recessed slightly inside structural frame so panels have crisp depth)
    m.add_box((0.96, 0.30, 2.92), center=(0.0, 0.0, 1.50), bevel=0.010, mat="M_Habitat_Wall")

    # Heavy floor base kickplate (Z=0..0.24) and upper ceiling cornice beam (Z=2.76..3.00) spanning full 40 cm thickness
    m.add_box((1.00, 0.40, 0.24), center=(0.0, 0.0, 0.12), bevel=0.014, mat="M_Dev_MetalDark")
    m.add_box((1.00, 0.40, 0.24), center=(0.0, 0.0, 2.88), bevel=0.014, mat="M_Dev_MetalDark")

    # 3 vertical structural buttress ribs (left X=-0.45, center X=0.0, right X=+0.45) spanning full Y=0.40 thickness
    for rx, rw in ((-0.45, 0.10), (0.0, 0.09), (0.45, 0.10)):
        m.add_box((rw, 0.40, 2.60), center=(rx, 0.0, 1.50), bevel=0.012, mat="M_Dev_MetalDark")

    # Recessed composite wall cushions on both +Y and -Y faces (upper and lower bays between ribs)
    for sx in (-0.225, 0.225):
        for sy in (-0.165, 0.165):
            # Lower bay cushion (Z=0.28..1.22)
            m.add_box((0.32, 0.04, 0.88), center=(sx, sy, 0.75), bevel=0.012, mat="M_Habitat_Wall")
            # Upper bay cushion (Z=1.48..2.66)
            m.add_box((0.32, 0.04, 1.12), center=(sx, sy, 2.06), bevel=0.012, mat="M_Habitat_Wall")

    # Horizontal mid-wall structural utility band (Z=1.24..1.44) + subtle top LED channel bezel (Z=2.66..2.76)
    m.add_box((0.98, 0.38, 0.18), center=(0.0, 0.0, 1.34), bevel=0.010, mat="M_Dev_MetalDark")
    m.add_box((0.98, 0.37, 0.08), center=(0.0, 0.0, 2.70), bevel=0.008, mat="M_Dev_MetalDark")

    # Subtle recessed horizontal LED strip slot on both +Y and -Y faces at Z=2.70 (thin 2.2cm strip)
    for sy in (-0.182, 0.182):
        for sx in (-0.225, 0.225):
            m.add_box((0.30, 0.012, 0.022), center=(sx, sy, 2.70), bevel=0.003, mat="M_EmissiveAccent")

    return m.build_object("SM_Habitat_WallPanel", target_dims_m=(1.00, 0.40, 3.00))


def build_habitat_floor_tile():
    """3. SM_Habitat_FloorTile.fbx (~100x100x20 cm):
    Brushed metal sci-fi grating/deck plate with beveled seams."""
    m = MeshAssembler(["M_Habitat_Floor", "M_Dev_MetalDark"])

    # Heavy structural sub-deck foundation block (Z=0..0.186) with perimeter bevel
    m.add_box((1.00, 1.00, 0.186), center=(0.0, 0.0, 0.093), bevel=0.012, mat="M_Dev_MetalDark")

    # Perimeter flush border rails reaching Z=0.20
    rail_w = 0.06
    for sy in (-0.47, 0.47):
        m.add_box((1.00, rail_w, 0.024), center=(0.0, sy, 0.188), bevel=0.005, mat="M_Habitat_Floor")
    for sx in (-0.47, 0.47):
        m.add_box((rail_w, 0.88, 0.024), center=(sx, 0.0, 0.188), bevel=0.005, mat="M_Habitat_Floor")

    # 4 quadrant brushed-steel deck plates with beveled seams & anti-slip grating bars (top at Z=0.20)
    for qx in (-0.22, 0.22):
        for qy in (-0.22, 0.22):
            m.add_box((0.40, 0.40, 0.024), center=(qx, qy, 0.188), bevel=0.006, mat="M_Habitat_Floor")
            # Recessed grating slot detail inside each deck quadrant
            for gi in (-0.12, -0.04, 0.04, 0.12):
                m.add_box((0.28, 0.022, 0.008), center=(qx, qy + gi, 0.197), bevel=0.002, mat="M_Dev_MetalDark")

    # Central cross seam frame & corner latch bolts
    m.add_box((0.88, 0.03, 0.020), center=(0.0, 0.0, 0.186), bevel=0.004, mat="M_Dev_MetalDark")
    m.add_box((0.03, 0.88, 0.020), center=(0.0, 0.0, 0.186), bevel=0.004, mat="M_Dev_MetalDark")

    return m.build_object("SM_Habitat_FloorTile", target_dims_m=(1.00, 1.00, 0.20))


def build_greenhouse_glass_roof():
    """4. SM_Greenhouse_GlassRoof.fbx (~100x100x20 cm):
    Framed skylight truss panel (M_Dev_MetalDark frame + M_GlassRoof inner pane slot so players see
    the orange Martian sky through the greenhouse ceiling!)."""
    m = MeshAssembler(["M_Dev_MetalDark", "M_GlassRoof"])

    # Outer structural skylight perimeter truss frame (open center! 7.5 cm rim around 100x100x20 cm)
    rim = 0.075
    half = 0.50 - rim * 0.5
    m.add_box((1.00, rim, 0.20), center=(0.0, -half, 0.10), bevel=0.012, mat="M_Dev_MetalDark")
    m.add_box((1.00, rim, 0.20), center=(0.0, half, 0.10), bevel=0.012, mat="M_Dev_MetalDark")
    m.add_box((rim, 1.00 - 2.0 * rim, 0.20), center=(-half, 0.0, 0.10), bevel=0.012, mat="M_Dev_MetalDark")
    m.add_box((rim, 1.00 - 2.0 * rim, 0.20), center=(half, 0.0, 0.10), bevel=0.012, mat="M_Dev_MetalDark")

    # Slim central cross-mullion truss bars dividing the skylight into 4 large open window bays
    m.add_box((0.85, 0.045, 0.18), center=(0.0, 0.0, 0.10), bevel=0.008, mat="M_Dev_MetalDark")
    m.add_box((0.045, 0.85, 0.18), center=(0.0, 0.0, 0.10), bevel=0.008, mat="M_Dev_MetalDark")

    # Corner diagonal gusset braces (slim so >80% of skylight footprint remains pure unobstructed glass)
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            m.add_strut((sx * 0.42, sy * 0.28, 0.10), (sx * 0.28, sy * 0.42, 0.10), 0.018, segs=8, mat="M_Dev_MetalDark")

    # 4 unobstructed translucent skylight glass panes (M_GlassRoof) filling the open bays
    for qx in (-0.225, 0.225):
        for qy in (-0.225, 0.225):
            m.add_box((0.405, 0.405, 0.036), center=(qx, qy, 0.10), bevel=0.003, mat="M_GlassRoof")

    return m.build_object("SM_Greenhouse_GlassRoof", target_dims_m=(1.00, 1.00, 0.20))


def build_mars_solar_array():
    """5. SM_Mars_SolarArray.fbx (~220x160x280 cm):
    Tilted dual-wing Martian photovoltaic solar panel tower on tripod truss mast."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_SolarCell", "M_Dev_Copper", "M_EmissiveAccent"])

    # Tripod base with 3 splayed heavy structural legs & anchored footpads
    for k in range(3):
        ang = math.radians(k * 120.0 + 30.0)
        fx, fy = 0.62 * math.cos(ang), 0.62 * math.sin(ang)
        m.add_cylinder(0.12, 0.14, 0.06, center=(fx, fy, 0.03), segs=12, bevel=0.008, mat="M_Dev_MetalDark")
        m.add_cylinder(0.08, 0.09, 0.05, center=(fx, fy, 0.07), segs=12, bevel=0.006, mat="M_Dev_Armor")
        m.add_strut((fx, fy, 0.06), (0.14 * math.cos(ang), 0.14 * math.sin(ang), 0.78), 0.045, segs=10, mat="M_Dev_MetalDark")
        m.add_strut((fx * 0.65, fy * 0.65, 0.36), (0.0, 0.0, 0.42), 0.026, segs=8, mat="M_Dev_MetalDark")

    # Central power inverter box & mast pedestal collar (Z=0.45..1.15)
    m.add_cylinder(0.16, 0.14, 0.90, center=(0.0, 0.0, 0.68), segs=16, bevel=0.010, mat="M_Dev_Armor")
    m.add_box((0.36, 0.34, 0.42), center=(0.12, 0.0, 0.72), bevel=0.014, mat="M_Dev_Armor")
    m.add_box((0.04, 0.24, 0.12), center=(0.30, 0.0, 0.78), bevel=0.005, mat="M_EmissiveAccent")
    for sy in (-0.12, 0.12):
        m.add_cylinder(0.022, 0.022, 0.50, center=(-0.10, sy, 0.72), segs=10, mat="M_Dev_Copper")

    # Vertical lattice mast column rising to gimbal yoke (Z=1.10..2.22)
    m.add_cylinder(0.09, 0.08, 1.18, center=(0.0, 0.0, 1.68), segs=16, bevel=0.008, mat="M_Dev_MetalDark")
    for z_ring in (1.30, 1.62, 1.94):
        m.add_torus_ring(0.105, 0.016, center=(0.0, 0.0, z_ring), mat="M_Dev_Copper")

    # Sun-tracking gimbal head & elevation actuator at Z=2.24
    m.add_box((0.28, 0.32, 0.20), center=(0.0, 0.0, 2.24), bevel=0.012, mat="M_Dev_Armor")
    m.add_strut((0.08, 0.0, 1.96), (0.22, 0.0, 2.22), 0.024, segs=10, mat="M_Dev_Copper")

    # Tilted cross-boom & dual photovoltaic solar wings (tilted 26 deg around Y axis)
    tilt_y = math.radians(26.0)
    pivot = Vector((0.0, 0.0, 2.28))
    rot_m = Euler((0.0, tilt_y, 0.0), "XYZ").to_matrix()

    def wing_pos(lx, ly, lz):
        return tuple(pivot + rot_m @ Vector((lx, ly, lz)))

    # Central horizontal torque tube spanning Y in [-1.06, +1.06] (note: X=2.20m wingspan or Y=2.20m)
    # Wait: target_dims_m is (2.20, 1.60, 2.80) -> X=220cm wingspan, Y=160cm chord!
    # Let's orient the dual wings along X (+/-1.10m) and tilt around X axis so +Y/+X faces sun!
    tilt_x = math.radians(24.0)
    rot_wing = Euler((tilt_x, 0.0, 0.0), "XYZ")
    rot_wm = rot_wing.to_matrix()

    def wpos(lx, ly, lz):
        return tuple(pivot + rot_wm @ Vector((lx, ly, lz)))

    # Main wing spar along X (-1.08..+1.08)
    m.add_box((2.16, 0.08, 0.06), center=wpos(0.0, 0.0, 0.0), rot=tuple(rot_wing), bevel=0.008, mat="M_Dev_MetalDark")

    # Left and Right solar wings (X centered at -0.58 and +0.58, each 0.92m wide x 1.48m chord)
    for wx in (-0.58, 0.58):
        # Structural metallic wing frame
        m.add_box((0.94, 1.48, 0.045), center=wpos(wx, 0.0, 0.0), rot=tuple(rot_wing), bevel=0.008, mat="M_Dev_MetalDark")
        # 2x4 grid of photovoltaic solar cell submodules on upper surface + copper busbars
        for cx in (-0.22, 0.22):
            m.add_box((0.018, 1.38, 0.016), center=wpos(wx + cx, 0.0, 0.024), rot=tuple(rot_wing), mat="M_Dev_Copper")
            for cy in (-0.50, -0.17, 0.17, 0.50):
                m.add_box((0.40, 0.30, 0.014), center=wpos(wx + cx, cy, 0.023), rot=tuple(rot_wing), bevel=0.003, mat="M_SolarCell")

    # Top mast telemetry spire & glowing beacon tip reaching Z=2.80
    m.add_cylinder(0.024, 0.016, 0.44, center=(0.0, -0.06, 2.54), segs=12, mat="M_Dev_MetalDark")
    m.add_sphere(0.042, center=(0.0, -0.06, 2.77), mat="M_EmissiveAccent")

    return m.build_object("SM_Mars_SolarArray", target_dims_m=(2.20, 1.60, 2.80))


def build_mars_rover_wreck():
    """6. SM_Mars_RoverWreck.fbx (~220x150x115 cm):
    Weathered 6-wheel Mars exploration rover chassis with camera mast & solar deck
    (storytelling landmark outside base)."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_SolarCell", "M_Dev_Copper", "M_RegolithSoil", "M_EmissiveAccent"])

    # Wind-drifted Martian regolith sand mound partially burying the wrecked rover's lower wheels
    m.add_tapered_box((2.10, 1.42), (1.76, 1.14), 0.14, center_base=(0.0, 0.0, 0.0), bevel=0.04, mat="M_RegolithSoil")
    m.add_sphere(0.42, center=(0.45, -0.28, 0.06), scale=(1.5, 1.1, 0.28), mat="M_RegolithSoil")
    m.add_sphere(0.38, center=(-0.52, 0.24, 0.05), scale=(1.4, 1.2, 0.25), mat="M_RegolithSoil")

    # 6 cleated Mars rover bogie wheels (3 per side at X = -0.74, 0.0, +0.74; Y = +/-0.62)
    wheel_positions = [
        (-0.74, -0.60, 0.22, (0.08, 0.04, 0.05)),
        (0.00, -0.64, 0.23, (0.05, 0.0, -0.04)),
        (0.74, -0.58, 0.18, (0.28, -0.18, 0.22)),  # Front-right wheel canted/wrecked in sand
        (-0.74, 0.60, 0.24, (-0.04, 0.03, -0.05)),
        (0.00, 0.64, 0.25, (0.02, -0.02, 0.03)),
        (0.74, 0.60, 0.23, (-0.06, 0.08, -0.10)),
    ]
    for wx, wy, wz, wrot in wheel_positions:
        r_euler = (math.pi / 2 + wrot[0], wrot[1], wrot[2])
        # Outer cleated aluminum tire drum
        m.add_cylinder(0.22, 0.22, 0.18, center=(wx, wy, wz), rot=r_euler, segs=20, bevel=0.012, mat="M_Dev_MetalDark")
        # Inner wheel hub & brake actuator
        m.add_cylinder(0.13, 0.13, 0.20, center=(wx, wy, wz), rot=r_euler, segs=16, bevel=0.008, mat="M_Dev_Armor")
        m.add_cylinder(0.05, 0.05, 0.22, center=(wx, wy, wz), rot=r_euler, segs=12, mat="M_Dev_Copper")

    # Rocker-bogie titanium suspension struts connecting wheels to the central chassis
    for side_y in (-1.0, 1.0):
        y_w = side_y * 0.56
        y_c = side_y * 0.36
        pivot_rocker = (0.08, y_c, 0.48)
        pivot_bogie = (-0.38, y_w, 0.38)
        m.add_strut(pivot_rocker, (0.74, y_w, 0.21), 0.026, segs=10, mat="M_Dev_MetalDark")
        m.add_strut(pivot_rocker, pivot_bogie, 0.028, segs=10, mat="M_Dev_MetalDark")
        m.add_strut(pivot_bogie, (0.0, y_w, 0.24), 0.024, segs=10, mat="M_Dev_MetalDark")
        m.add_strut(pivot_bogie, (-0.74, y_w, 0.23), 0.024, segs=10, mat="M_Dev_MetalDark")
        m.add_cylinder(0.05, 0.05, 0.16, center=pivot_rocker, rot=(math.pi / 2, 0, 0), segs=12, mat="M_Dev_Armor")

    # Wrecked/listed Warm Electronics Box (WEB) rover body (tilted -6 deg roll, +4 deg pitch)
    chassis_rot = (math.radians(-6.5), math.radians(4.5), math.radians(-3.0))
    c_mat = Euler(chassis_rot, "XYZ").to_matrix()
    c_origin = Vector((-0.04, 0.0, 0.48))

    def cpos(lx, ly, lz):
        return tuple(c_origin + c_mat @ Vector((lx, ly, lz)))

    # Gold thermal blanket lower hull + armored composite upper chassis frame
    m.add_box((1.24, 0.74, 0.28), center=cpos(0.0, 0.0, 0.0), rot=chassis_rot, bevel=0.016, mat="M_Dev_Copper")
    m.add_box((1.30, 0.80, 0.10), center=cpos(0.0, 0.0, 0.15), rot=chassis_rot, bevel=0.012, mat="M_Dev_Armor")

    # Wide solar deck wings on top of rover body (with one cracked/drooping wing panel)
    m.add_box((1.16, 1.34, 0.035), center=cpos(-0.04, 0.0, 0.21), rot=chassis_rot, bevel=0.008, mat="M_Dev_MetalDark")
    for sx in (-0.34, 0.24):
        for sy in (-0.42, 0.0, 0.42):
            m.add_box((0.46, 0.36, 0.016), center=cpos(sx, sy, 0.228), rot=chassis_rot, bevel=0.004, mat="M_SolarCell")

    # Rear tilted MMRTG finned power generator pack (-X rear)
    rtg_rot = (math.radians(-6.5), math.radians(-22.0), 0.0)
    m.add_cylinder(0.14, 0.13, 0.46, center=cpos(-0.76, 0.0, 0.08), rot=rtg_rot, segs=16, bevel=0.01, mat="M_Dev_MetalDark")
    for fi in range(5):
        ang = math.radians(fi * 36.0)
        m.add_box((0.36, 0.34 * math.cos(ang) + 0.03, 0.02), center=cpos(-0.76, 0.0, 0.08), rot=rtg_rot, mat="M_Dev_Copper")

    # High-gain dish antenna on rear-left deck
    m.add_cylinder(0.025, 0.02, 0.22, center=cpos(-0.42, 0.28, 0.32), rot=chassis_rot, segs=10, mat="M_Dev_MetalDark")
    m.add_parabolic_dish(0.18, 0.05, center=cpos(-0.42, 0.28, 0.43), rot=(math.radians(28), math.radians(-18), 0.0), mat="M_Dev_Armor")

    # Front (+X) Remote Sensing Camera Mast (canted at a weathered angle) + twin glowing optical eyes
    mast_rot = (math.radians(-11.0), math.radians(10.0), math.radians(-8.0))
    m.add_cylinder(0.048, 0.040, 0.52, center=cpos(0.48, -0.16, 0.44), rot=mast_rot, segs=14, bevel=0.006, mat="M_Dev_Armor")
    m.add_box((0.18, 0.28, 0.14), center=cpos(0.53, -0.21, 0.68), rot=mast_rot, bevel=0.012, mat="M_Dev_Armor")
    m.add_box((0.04, 0.22, 0.09), center=cpos(0.61, -0.21, 0.68), rot=mast_rot, bevel=0.006, mat="M_Dev_MetalDark")
    for ey in (-0.27, -0.15):
        m.add_cylinder(0.032, 0.032, 0.04, center=cpos(0.625, ey, 0.68), rot=(0.0, math.pi / 2, 0.0), segs=14, mat="M_EmissiveAccent")

    # Front articulated robotic sample arm extending forward (+X)
    m.add_strut(cpos(0.58, 0.18, 0.02), (0.98, 0.26, 0.26), 0.030, segs=10, mat="M_Dev_MetalDark")
    m.add_strut((0.98, 0.26, 0.26), (0.86, 0.10, 0.10), 0.026, segs=10, mat="M_Dev_Armor")
    m.add_box((0.16, 0.14, 0.12), center=(0.86, 0.08, 0.09), bevel=0.01, mat="M_Dev_MetalDark")

    return m.build_object("SM_Mars_RoverWreck", target_dims_m=(2.20, 1.50, 1.15))


def build_mars_terrain_skirt():
    """7. SM_Mars_TerrainSkirt.fbx (~80000x80000x3500 cm, inner caldera edge ~3700 cm, outer ~40000 cm):
    Multi-tiered basalt caldera cliffs & terraced mesas immediately framing the playable [-3500..+3500] basin."""
    m = MeshAssembler(["M_Mars_Ground", "M_RegolithSoil"])
    bm = m.bm
    idx_ground = m.mat_map["M_Mars_Ground"]
    idx_cliff = m.mat_map["M_RegolithSoil"]

    n_ang = 180
    n_rad = 34
    r_inner = 37.0    # 3,700 cm: rises just outside the [-3500..+3500] playable basin!
    r_outer = 400.0   # 40,000 cm half-span -> 80,000 x 80,000 cm outer footprint

    def ridge_height(theta, u):
        """Multi-tiered Jezero caldera rim at R~40..85m (6..16m tall) + outer ridges (18..35m)."""
        if u <= 0.025 or u >= 0.96:
            return 0.0

        # Non-linear radial distribution puts dense mesh resolution near the inner caldera walls
        r_m = r_inner + (r_outer - r_inner) * (u ** 1.65)
        u_caldera = math.exp(-((r_m - 58.0) / 19.0) ** 2)
        u_mid_mesa = math.exp(-((r_m - 135.0) / 48.0) ** 2)
        u_outer = math.exp(-((r_m - 275.0) / 72.0) ** 2)

        h_wave = (
            0.58
            + 0.22 * math.sin(3.0 * theta + 0.45)
            + 0.16 * math.cos(5.0 * theta - 1.15)
            + 0.12 * math.sin(9.0 * theta + 2.10)
            + 0.08 * math.cos(14.0 * theta + 0.70)
            + 0.05 * math.sin(23.0 * theta - 0.50)
        )
        # Terraced mesa stepping characteristic of eroded Martian basalt strata
        mesa = min(0.95, max(0.24, h_wave))
        mesa = math.floor(mesa * 5.0) / 5.0 * 0.42 + mesa * 0.58

        h_outer = (
            0.66
            + 0.24 * math.cos(4.0 * theta + 1.2)
            + 0.18 * math.sin(7.0 * theta - 0.8)
            + 0.12 * math.cos(12.0 * theta + 1.9)
        )

        ramp_in = min(1.0, max(0.0, (u - 0.025) / 0.055)) ** 1.4
        ramp_out = min(1.0, max(0.0, (0.96 - u) / 0.08)) ** 1.4
        raw = ramp_in * ramp_out * (14.5 * u_caldera * mesa + 21.0 * u_mid_mesa * mesa + 35.0 * u_outer * max(0.25, h_outer))
        return max(0.0, raw)

    rings = []
    for ri in range(n_rad):
        u = ri / (n_rad - 1)
        # Dense near-basin spacing using u**1.65 so caldera cliffs at 40..90m have crisp geometry
        r_base = r_inner + (r_outer - r_inner) * (u ** 1.65)
        ring_verts = []
        for ai in range(n_ang):
            theta = (2.0 * math.pi * ai) / n_ang
            ct, st = math.cos(theta), math.sin(theta)
            sq_scale = 1.0 / max(abs(ct), abs(st), 0.7071)
            shape_blend = (u ** 1.4) * 0.35
            r_eff = r_base * (1.0 * (1.0 - shape_blend) + sq_scale * shape_blend)
            if 0.04 < u < 0.92:
                r_eff += (2.8 if r_base < 100.0 else 4.5) * math.sin(7.0 * theta + u * 9.0)
            z = ridge_height(theta, u)
            ring_verts.append(bm.verts.new((r_eff * ct, r_eff * st, z)))
        rings.append(ring_verts)

    for ri in range(n_rad - 1):
        u_mid = (ri + 0.5) / (n_rad - 1)
        for ai in range(n_ang):
            nai = (ai + 1) % n_ang
            v00 = rings[ri][ai]
            v10 = rings[ri + 1][ai]
            v11 = rings[ri + 1][nai]
            v01 = rings[ri][nai]
            f = bm.faces.new((v00, v10, v11, v01))
            f.smooth = True
            dz = abs(0.5 * (v10.co.z + v11.co.z) - 0.5 * (v00.co.z + v01.co.z))
            f.material_index = idx_cliff if (dz > 1.4 and 0.05 < u_mid < 0.88) else idx_ground

    return m.build_object(
        "SM_Mars_TerrainSkirt",
        target_dims_m=(800.0, 800.0, 35.0),
        center_xy=True,
        ground_z=True,
        uv_project="planar_z",
    )


def build_mars_basalt_cliff():
    """8. SM_Mars_BasaltCliff.fbx (~900x600x850 cm): Multi-tiered basalt mesa & iron-oxide ridge cluster."""
    m = MeshAssembler(["M_RegolithSoil", "M_Mars_Ground"])
    # Broad talus apron + 3 stepped basalt sedimentary mesa tiers
    tiers = [
        ((8.6, 5.6), (7.0, 4.4), 2.4, (0.0, 0.0, 0.0), 0.05, 0.28, "M_Mars_Ground"),
        ((6.8, 4.3), (5.2, 3.2), 2.8, (-0.35, 0.15, 2.2), -0.08, 0.22, "M_RegolithSoil"),
        ((5.0, 3.1), (3.6, 2.2), 2.2, (0.45, -0.20, 4.8), 0.10, 0.18, "M_RegolithSoil"),
        ((3.4, 2.1), (2.4, 1.5), 1.4, (0.15, 0.10, 6.8), -0.04, 0.14, "M_Mars_Ground"),
    ]
    for bot, top, h, c, yaw, bev, mat_name in tiers:
        m.add_tapered_box(bot, top, h, center_base=c, rot=(0.0, 0.0, yaw), bevel=bev, mat=mat_name)
    # Flanking basalt buttress spires
    for bx, by, bw, bh, yaw in ((-3.1, -1.5, 2.1, 4.6, 0.42), (3.0, 1.4, 2.3, 5.2, -0.35), (1.8, -2.0, 1.8, 3.4, 0.85)):
        m.add_tapered_box((bw, bw * 0.8), (bw * 0.5, bw * 0.42), bh, center_base=(bx, by, 0.0), rot=(0.0, 0.0, yaw), bevel=0.16, mat="M_RegolithSoil")
    return m.build_object("SM_Mars_BasaltCliff", target_dims_m=(9.0, 6.0, 8.5))


def build_comms_dish_tower():
    """9. SM_Comms_DishTower.fbx (~320x320x620 cm): Lattice deep-space comms tower with parabolic high-gain dish."""
    m = MeshAssembler(["M_Dev_MetalDark", "M_Dev_Armor", "M_EmissiveAccent"])
    # Concrete/steel anchor footings & 4-leg tapered lattice mast (Z = 0..4.2m)
    m.add_box((2.8, 2.8, 0.24), center=(0.0, 0.0, 0.12), bevel=0.04, mat="M_Dev_MetalDark")
    corners = ((-1.05, -1.05), (1.05, -1.05), (1.05, 1.05), (-1.05, 1.05))
    top_corners = ((-0.46, -0.46), (0.46, -0.46), (0.46, 0.46), (-0.46, 0.46))
    for (bx, by), (tx, ty) in zip(corners, top_corners):
        m.add_strut((bx, by, 0.24), (tx, ty, 4.10), 0.075, segs=10, mat="M_Dev_MetalDark")
    for lvl_idx, frac in enumerate((0.25, 0.55, 0.85)):
        next_frac = (0.55, 0.85, 1.0)[lvl_idx]
        for i in range(4):
            ni = (i + 1) % 4
            p0 = (corners[i][0] * (1 - frac) + top_corners[i][0] * frac,
                  corners[i][1] * (1 - frac) + top_corners[i][1] * frac, 0.24 + 3.86 * frac)
            p1 = (corners[ni][0] * (1 - frac) + top_corners[ni][0] * frac,
                  corners[ni][1] * (1 - frac) + top_corners[ni][1] * frac, 0.24 + 3.86 * frac)
            p2 = (corners[ni][0] * (1 - next_frac) + top_corners[ni][0] * next_frac,
                  corners[ni][1] * (1 - next_frac) + top_corners[ni][1] * next_frac, 0.24 + 3.86 * next_frac)
            m.add_strut(p0, p1, 0.045, segs=8, mat="M_Dev_Armor")
            m.add_strut(p0, p2, 0.038, segs=8, mat="M_Dev_MetalDark")
    # Catwalk deck & azimuth/elevation gimbal at Z = 4.15m
    m.add_cylinder(0.95, 0.95, 0.14, center=(0.0, 0.0, 4.15), segs=20, bevel=0.02, mat="M_Dev_Armor")
    m.add_torus_ring(0.92, 0.03, center=(0.0, 0.0, 4.55), mat="M_Dev_MetalDark")
    m.add_cylinder(0.28, 0.24, 0.65, center=(0.0, 0.0, 4.52), segs=16, mat="M_Dev_MetalDark")
    # Parabolic Dish tilted 38 deg toward Earth sky
    dish_rot = (0.0, math.radians(38.0), math.radians(-18.0))
    dish_center = (0.18, 0.0, 5.15)
    m.add_parabolic_dish(1.42, 0.42, thickness=0.05, center=dish_center, rot=dish_rot, radial_segs=28, rings=6, mat="M_Dev_Armor")
    # Feed horn & glowing transceiver emitter tip
    d_mat = Euler(dish_rot, "XYZ").to_matrix()
    feed_tip = tuple(Vector(dish_center) + d_mat @ Vector((0.0, 0.0, 0.95)))
    for ang_deg in (0.0, 120.0, 240.0):
        rad = math.radians(ang_deg)
        rim_pt = tuple(Vector(dish_center) + d_mat @ Vector((1.22 * math.cos(rad), 1.22 * math.sin(rad), 0.34)))
        m.add_strut(rim_pt, feed_tip, 0.028, segs=8, mat="M_Dev_MetalDark")
    m.add_sphere(0.11, center=feed_tip, mat="M_EmissiveAccent")
    return m.build_object("SM_Comms_DishTower", target_dims_m=(3.20, 3.20, 6.20))


def build_cryo_drill_rig():
    """10. SM_Cryo_DrillRig.fbx (~420x420x680 cm): Cryo-ice drill derrick tower with auger & manifold."""
    m = MeshAssembler(["M_Dev_MetalDark", "M_Dev_Armor", "M_Dev_Copper", "M_EmissiveAccent"])
    m.add_box((3.8, 3.8, 0.24), center=(0.0, 0.0, 0.12), bevel=0.04, mat="M_Dev_MetalDark")
    # 4 tapered derrick legs rising to crown cap at Z=6.3m
    bot = ((-1.45, -1.45), (1.45, -1.45), (1.45, 1.45), (-1.45, 1.45))
    top = ((-0.48, -0.48), (0.48, -0.48), (0.48, 0.48), (-0.48, 0.48))
    for (bx, by), (tx, ty) in zip(bot, top):
        m.add_strut((bx, by, 0.24), (tx, ty, 6.30), 0.09, segs=10, mat="M_Dev_MetalDark")
    for frac, next_f in ((0.2, 0.45), (0.45, 0.72), (0.72, 1.0)):
        for i in range(4):
            ni = (i + 1) % 4
            p0 = (bot[i][0] * (1 - frac) + top[i][0] * frac, bot[i][1] * (1 - frac) + top[i][1] * frac, 0.24 + 6.06 * frac)
            p1 = (bot[ni][0] * (1 - frac) + top[ni][0] * frac, bot[ni][1] * (1 - frac) + top[ni][1] * frac, 0.24 + 6.06 * frac)
            p2 = (bot[ni][0] * (1 - next_f) + top[ni][0] * next_f, bot[ni][1] * (1 - next_f) + top[ni][1] * next_f, 0.24 + 6.06 * next_f)
            m.add_strut(p0, p1, 0.052, segs=8, mat="M_Dev_Armor")
            m.add_strut(p0, p2, 0.042, segs=8, mat="M_Dev_MetalDark")
    # Crown pulley block + warning beacon
    m.add_box((1.15, 1.15, 0.34), center=(0.0, 0.0, 6.42), bevel=0.04, mat="M_Dev_Armor")
    m.add_cylinder(0.14, 0.14, 0.26, center=(0.0, 0.0, 6.68), segs=14, mat="M_EmissiveAccent")
    # Central rotary drill column & auger collars
    m.add_cylinder(0.22, 0.22, 6.10, center=(0.0, 0.0, 3.15), segs=18, mat="M_Dev_Armor")
    for z_ring in (0.65, 1.25, 1.85, 2.45):
        m.add_torus_ring(0.32, 0.07, center=(0.0, 0.0, z_ring), mat="M_Dev_Copper")
    # Rotary drive housing + cryo pump cylinder
    m.add_box((1.10, 1.10, 0.72), center=(0.0, 0.0, 3.60), bevel=0.06, mat="M_Dev_Copper")
    m.add_cylinder(0.42, 0.42, 1.60, center=(-1.05, 0.0, 1.05), segs=18, bevel=0.03, mat="M_Dev_Armor")
    m.add_cylinder(0.42, 0.42, 1.60, center=(1.05, 0.0, 1.05), segs=18, bevel=0.03, mat="M_Dev_Armor")
    return m.build_object("SM_Cryo_DrillRig", target_dims_m=(4.20, 4.20, 6.80))


def build_solar_dust_rack():
    """11. SM_Solar_DustRack.fbx (~240x180x190 cm): Mars-dust-toned tilted solar wing array rack."""
    m = MeshAssembler(["M_Dev_MetalDark", "M_SolarCell", "M_Dev_Copper", "M_EmissiveAccent"])
    m.add_box((2.10, 1.30, 0.12), center=(0.0, 0.0, 0.06), bevel=0.02, mat="M_Dev_MetalDark")
    for sx in (-0.82, 0.82):
        m.add_strut((sx, -0.45, 0.12), (sx, 0.0, 1.22), 0.065, segs=10, mat="M_Dev_MetalDark")
        m.add_strut((sx, 0.45, 0.12), (sx, 0.0, 1.22), 0.065, segs=10, mat="M_Dev_MetalDark")
    m.add_cylinder(0.06, 0.06, 2.25, center=(0.0, 0.0, 1.22), rot=(0.0, math.pi * 0.5, 0.0), segs=14, mat="M_Dev_Copper")
    tilt = (math.radians(-26.0), 0.0, 0.0)
    t_mat = Euler(tilt, "XYZ").to_matrix()
    origin = Vector((0.0, 0.0, 1.28))
    m.add_box((2.38, 1.72, 0.06), center=tuple(origin), rot=tilt, bevel=0.015, mat="M_Dev_MetalDark")
    for px in (-0.76, 0.0, 0.76):
        for py in (-0.42, 0.42):
            pt = tuple(origin + t_mat @ Vector((px, py, 0.036)))
            m.add_box((0.70, 0.76, 0.022), center=pt, rot=tilt, bevel=0.005, mat="M_SolarCell")
    m.add_box((0.52, 0.36, 0.42), center=(0.0, 0.45, 0.32), bevel=0.03, mat="M_Dev_MetalDark")
    m.add_box((0.36, 0.04, 0.08), center=(0.0, 0.64, 0.40), mat="M_EmissiveAccent")
    return m.build_object("SM_Solar_DustRack", target_dims_m=(2.40, 1.80, 1.90))


def build_crispr_sequencer():
    """12. SM_CRISPR_Sequencer.fbx (~190x130x210 cm): Greenhouse CRISPR Gene Sequencer & Bio-Incubator hood."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_GlassRoof", "M_EmissiveAccent"])
    m.add_box((1.88, 1.26, 0.14), center=(0.0, 0.0, 0.07), bevel=0.03, mat="M_Dev_MetalDark")
    # Rear cabinet chassis & twin flanking cryo-vial columns (open front -Y so AMLGDevice sits cleanly in front!)
    m.add_box((1.84, 0.42, 1.94), center=(0.0, 0.40, 1.04), bevel=0.04, mat="M_Dev_Armor")
    for sx in (-0.74, 0.74):
        m.add_box((0.26, 0.78, 1.88), center=(sx, -0.14, 1.02), bevel=0.03, mat="M_Dev_MetalDark")
        m.add_cylinder(0.10, 0.10, 1.20, center=(sx, -0.18, 1.12), segs=16, mat="M_GlassRoof")
        m.add_cylinder(0.05, 0.05, 1.10, center=(sx, -0.18, 1.12), segs=12, mat="M_EmissiveAccent")
    # Overhead optical scanner gantry hood & bio-laser manifold
    m.add_box((1.86, 1.18, 0.22), center=(0.0, 0.0, 1.98), bevel=0.04, mat="M_Dev_Armor")
    m.add_box((1.40, 0.16, 0.08), center=(0.0, -0.48, 1.88), mat="M_EmissiveAccent")
    return m.build_object("SM_CRISPR_Sequencer", target_dims_m=(1.90, 1.30, 2.10))


def build_sabatier_reactor():
    """13. SM_Sabatier_Reactor.fbx (~210x130x220 cm): Sabatier CO2 + 4H2 -> CH4 + 2H2O catalytic synthesis manifold."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_Dev_Copper", "M_EmissiveAccent"])
    m.add_box((2.06, 1.24, 0.14), center=(0.0, 0.0, 0.07), bevel=0.03, mat="M_Dev_MetalDark")
    m.add_box((1.98, 0.36, 1.88), center=(0.0, 0.42, 1.02), bevel=0.04, mat="M_Dev_MetalDark")
    # Twin vertical catalytic pressure vessels with copper heat-exchanger coils
    for sx in (-0.68, 0.68):
        m.add_cylinder(0.28, 0.26, 1.72, center=(sx, -0.04, 1.08), segs=20, bevel=0.03, mat="M_Dev_Armor")
        m.add_sphere(0.26, center=(sx, -0.04, 1.94), mat="M_Dev_Armor")
        for cz in (0.68, 0.96, 1.24, 1.52):
            m.add_torus_ring(0.31, 0.04, center=(sx, -0.04, cz), mat="M_Dev_Copper")
    # Overhead H2O condenser header & glowing cyan flow gauge
    m.add_cylinder(0.12, 0.12, 1.65, center=(0.0, 0.18, 2.04), rot=(0.0, math.pi * 0.5, 0.0), segs=16, mat="M_Dev_Copper")
    m.add_box((0.92, 0.06, 0.14), center=(0.0, 0.22, 1.62), mat="M_EmissiveAccent")
    return m.build_object("SM_Sabatier_Reactor", target_dims_m=(2.10, 1.30, 2.20))


# ---------------------------------------------------------------------------
# FBX Export & Roundtrip Verification + 1200x1200 Contact Sheet
# ---------------------------------------------------------------------------

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


def verify_fbx_roundtrip(fbx_path):
    """Re-import FBX in fresh scene and verify UE5 cm bounds, minZ=0, UVs, normals, and material slots."""
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
    slots = []
    for mat in imp.data.materials:
        mname = mat.name.split(".")[0] if mat else "None"
        slots.append(mname)

    return {
        "fbx": os.path.relpath(fbx_path, PROJECT_ROOT),
        "vertices": len(imp.data.vertices),
        "polygons": len(imp.data.polygons),
        "uv_layers": len(imp.data.uv_layers),
        "has_custom_normals": bool(imp.data.has_custom_normals),
        "ue_size_cm": size_cm,
        "ue_min_cm": mn,
        "ue_max_cm": mx,
        "material_slots": slots,
    }


def setup_preview_stage():
    """Create Mars studio lighting, floor plane, and camera for multi-angle contact sheets."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"

    if not scene.world:
        scene.world = bpy.data.worlds.new("PreviewWorld")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.14, 0.09, 0.07, 1.0)
        bg.inputs[1].default_value = 1.7

    lights = []
    for lname, rot, energy, col in [
        ("KeySun", (0.72, 0.22, 0.65), 3.5, (1.0, 0.92, 0.84)),
        ("FillSun", (-0.65, -0.30, -2.35), 1.8, (0.78, 0.88, 1.0)),
        ("RimSun", (0.45, -0.45, 2.8), 1.6, (1.0, 0.72, 0.52)),
    ]:
        ld = bpy.data.lights.new(lname, "SUN")
        ld.energy = energy
        ld.color = col
        lo = bpy.data.objects.new(lname, ld)
        lo.rotation_euler = rot
        bpy.context.collection.objects.link(lo)
        lights.append(lo)

    bpy.ops.mesh.primitive_plane_add(size=18.0, location=(0.0, 0.0, -0.002))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("PreviewFloor")
    fmat.use_nodes = True
    bsdf = fmat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.24, 0.13, 0.09, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.88
    floor.data.materials.append(fmat)

    cam_d = bpy.data.cameras.new("PreviewCam")
    cam_d.lens = 42.0
    cam_d.clip_start = 0.05
    cam_d.clip_end = 5000.0
    cam = bpy.data.objects.new("PreviewCam", cam_d)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    return floor, cam, lights


def render_contact_sheet(items, out_png):
    """Render 16 tiles (4x4 grid of 300x300 = 1200x1200 PNG) covering all 7 Inc9 props from multiple angles."""
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    clear_scene()
    floor, cam, lights = setup_preview_stage()

    cols, rows = 4, 4
    tile_w, tile_h = 300, 300
    scene = bpy.context.scene
    scene.render.resolution_x = tile_w
    scene.render.resolution_y = tile_h
    scene.render.resolution_percentage = 100

    tiles = []
    for spec in items:
        fbx_path = spec["fbx_abs"]
        name = spec["name"]
        bpy.ops.import_scene.fbx(filepath=fbx_path)
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and o != floor]
        imp = meshes[0]
        for idx, slot in enumerate(imp.material_slots):
            base_mname = slot.name.split(".")[0]
            if base_mname in MAT_SPECS:
                imp.data.materials[idx] = get_material(base_mname)

        pts = [imp.matrix_world @ v.co for v in imp.data.vertices]
        mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        center = (mn + mx) * 0.5
        span = max(mx.x - mn.x, mx.y - mn.y, mx.z - mn.z)
        dist = max(span * 1.55, 0.35)

        if len(items) > 7 and name != "SM_Mars_TerrainSkirt":
            off = Vector((dist * 0.78, -dist * 0.62, dist * 0.42))
            cam.location = center + off
            cam.rotation_euler = (center - cam.location).normalized().to_track_quat("-Z", "Y").to_euler()
            tmp = os.path.join(PREVIEW_DIR, f"_tmp_{name}_hero.png")
            scene.render.filepath = tmp
            bpy.ops.render.render(write_still=True)
            tiles.append(tmp)
        elif name == "SM_Mars_TerrainSkirt":
            floor.hide_render = True
            views = [
                ("overview", Vector((0.0, 0.0, 0.0)), Vector((640.0, -640.0, 420.0))),
                ("horizon", Vector((310.0, 0.0, 18.0)), Vector((20.0, -40.0, 14.0))),
                ("ridge_ne", Vector((240.0, 240.0, 16.0)), Vector((-80.0, -80.0, 26.0))),
                ("mesa_sw", Vector((-250.0, -230.0, 18.0)), Vector((90.0, 70.0, 24.0))),
            ]
            for tag, target_pt, cam_pt in views:
                cam.location = cam_pt
                cam.rotation_euler = (target_pt - cam.location).normalized().to_track_quat("-Z", "Y").to_euler()
                tmp = os.path.join(PREVIEW_DIR, f"_tmp_{name}_{tag}.png")
                scene.render.filepath = tmp
                bpy.ops.render.render(write_still=True)
                tiles.append(tmp)
            floor.hide_render = False
        elif name in ("SM_Habitat_FloorTile", "SM_Greenhouse_GlassRoof"):
            for tag, off in [
                ("top3q", Vector((dist * 0.72, -dist * 0.62, dist * 0.68))),
                ("angle3q", Vector((-dist * 0.68, dist * 0.62, dist * 0.42))),
            ]:
                cam.location = center + off
                cam.rotation_euler = (center - cam.location).normalized().to_track_quat("-Z", "Y").to_euler()
                tmp = os.path.join(PREVIEW_DIR, f"_tmp_{name}_{tag}.png")
                scene.render.filepath = tmp
                bpy.ops.render.render(write_still=True)
                tiles.append(tmp)
        else:
            for tag, off in [
                ("front3q", Vector((dist * 0.78, -dist * 0.62, dist * 0.40))),
                ("rear3q", Vector((-dist * 0.72, dist * 0.68, dist * 0.36))),
            ]:
                cam.location = center + off
                cam.rotation_euler = (center - cam.location).normalized().to_track_quat("-Z", "Y").to_euler()
                tmp = os.path.join(PREVIEW_DIR, f"_tmp_{name}_{tag}.png")
                scene.render.filepath = tmp
                bpy.ops.render.render(write_still=True)
                tiles.append(tmp)

        bpy.data.objects.remove(imp, do_unlink=True)

    total_w = cols * tile_w
    total_h = rows * tile_h
    sheet = bpy.data.images.new("Inc9Sheet", width=total_w, height=total_h, alpha=True)
    buf = [0.0] * (total_w * total_h * 4)

    for idx, img_path in enumerate(tiles[: cols * rows]):
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

    bpy.data.objects.remove(floor, do_unlink=True)
    bpy.data.objects.remove(cam, do_unlink=True)
    for lo in lights:
        bpy.data.objects.remove(lo, do_unlink=True)


def main():
    os.makedirs(INC9_ROOT, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)

    recipes = [
        ("SM_Log_Terminal", build_log_terminal),
        ("SM_Habitat_WallPanel", build_habitat_wall_panel),
        ("SM_Habitat_FloorTile", build_habitat_floor_tile),
        ("SM_Greenhouse_GlassRoof", build_greenhouse_glass_roof),
        ("SM_Mars_SolarArray", build_mars_solar_array),
        ("SM_Mars_RoverWreck", build_mars_rover_wreck),
        ("SM_Mars_TerrainSkirt", build_mars_terrain_skirt),
        ("SM_Mars_BasaltCliff", build_mars_basalt_cliff),
        ("SM_Comms_DishTower", build_comms_dish_tower),
        ("SM_Cryo_DrillRig", build_cryo_drill_rig),
        ("SM_Solar_DustRack", build_solar_dust_rack),
        ("SM_CRISPR_Sequencer", build_crispr_sequencer),
        ("SM_Sabatier_Reactor", build_sabatier_reactor),
    ]

    manifest = {"props_inc9": [], "materials": MAT_SPECS}
    verified_items = []

    for name, fn in recipes:
        clear_scene()
        obj = fn()
        fbx_path = os.path.join(INC9_ROOT, f"{name}.fbx")
        export_fbx(obj, fbx_path)
        info = verify_fbx_roundtrip(fbx_path)
        info["name"] = name
        info["fbx_abs"] = fbx_path
        assert abs(info["ue_min_cm"][2]) < 0.05, f"{name} minZ not grounded: {info['ue_min_cm']}"
        assert info["uv_layers"] >= 1, f"{name} missing UV layer"
        manifest["props_inc9"].append({k: v for k, v in info.items() if k != "fbx_abs"})
        verified_items.append(info)
        print(
            f"INC9_PROP_VERIFIED {name}: size_cm={info['ue_size_cm']} "
            f"min_cm={info['ue_min_cm']} max_cm={info['ue_max_cm']} slots={info['material_slots']}",
            flush=True,
        )

    sheet_path = os.path.join(PREVIEW_DIR, "Inc9_Props_sheet.png")
    render_contact_sheet(verified_items, sheet_path)
    manifest["previews"] = [os.path.relpath(sheet_path, PROJECT_ROOT)]

    manifest_path = os.path.join(INC9_ROOT, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"INC9_PROPS_DONE manifest={manifest_path} sheet={sheet_path}", flush=True)


if __name__ == "__main__":
    main()
