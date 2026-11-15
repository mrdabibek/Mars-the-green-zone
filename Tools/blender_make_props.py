"""Generate 18 UE5-ready sci-fi Mars base props, botanical stages, pickups, and defenses.

Outputs:
  - Assets/Props/Devices/SM_Dev_*.fbx (8 meshes)
  - Assets/Props/Gameplay/SM_Plant*, SM_Pickup_*, SM_Defense_*.fbx (10 meshes)
  - Assets/Props/Previews/Props_Devices_sheet.png (1200x1200 multi-angle contact sheet)
  - Assets/Props/Previews/Props_Gameplay_sheet.png (1200x1200 multi-angle contact sheet)
  - Assets/Props/manifest.json (verified roundtrip bounds, pivot, UVs, and material slots)

Conventions:
  - Z-up, +X forward, ground base pivot minZ = 0, Blender meters -> UE5 cm (1m = 100cm)
  - Clean bevel + angle-smoothed normals, smart-projected UVs, dedicated EmissiveColor-ready slots

Run via:
  blender -b --factory-startup --python "Tools/blender_make_props.py"
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
PROPS_ROOT = os.path.join(PROJECT_ROOT, "Assets", "Props")
DEVICES_DIR = os.path.join(PROPS_ROOT, "Devices")
GAMEPLAY_DIR = os.path.join(PROPS_ROOT, "Gameplay")
PREVIEW_DIR = os.path.join(PROPS_ROOT, "Previews")


# ---------------------------------------------------------------------------
# Material library (procedural PBR shaders for realistic previews + clean UE5 slots)
# ---------------------------------------------------------------------------

MAT_SPECS = {
    "M_Dev_Armor": {
        "base_color": (0.76, 0.74, 0.70, 1.0),
        "metallic": 0.18,
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
        "base_color": (0.74, 0.39, 0.18, 1.0),
        "metallic": 0.90,
        "roughness": 0.28,
        "emissive": (0.0, 0.0, 0.0, 1.0),
        "emissive_strength": 0.0,
        "is_emissive": False,
        "noise_scale": 25.0,
        "rough_var": 0.08,
    },
    "M_EmissiveAccent": {
        "base_color": (0.06, 0.16, 0.20, 1.0),
        "metallic": 0.10,
        "roughness": 0.18,
        "emissive": (0.12, 0.78, 0.95, 1.0),
        "emissive_strength": 2.4,
        "is_emissive": True,
        "noise_scale": 10.0,
        "rough_var": 0.02,
    },
    "M_RegolithSoil": {
        "base_color": (0.20, 0.10, 0.07, 1.0),
        "metallic": 0.0,
        "roughness": 0.92,
        "emissive": (0.0, 0.0, 0.0, 1.0),
        "emissive_strength": 0.0,
        "is_emissive": False,
        "noise_scale": 32.0,
        "rough_var": 0.08,
    },
    "M_PlantFoliage": {
        "base_color": (0.14, 0.50, 0.16, 1.0),
        "metallic": 0.0,
        "roughness": 0.48,
        "emissive": (0.0, 0.0, 0.0, 1.0),
        "emissive_strength": 0.0,
        "is_emissive": False,
        "noise_scale": 18.0,
        "rough_var": 0.10,
    },
    "M_Pickup_PartsMat": {
        "base_color": (0.80, 0.54, 0.10, 1.0),
        "metallic": 0.22,
        "roughness": 0.38,
        "emissive": (0.0, 0.0, 0.0, 1.0),
        "emissive_strength": 0.0,
        "is_emissive": False,
        "noise_scale": 16.0,
        "rough_var": 0.10,
    },
    "M_Pickup_AmmoMat": {
        "base_color": (0.24, 0.30, 0.20, 1.0),
        "metallic": 0.35,
        "roughness": 0.40,
        "emissive": (0.0, 0.0, 0.0, 1.0),
        "emissive_strength": 0.0,
        "is_emissive": False,
        "noise_scale": 18.0,
        "rough_var": 0.10,
    },
    "M_IceCrystal": {
        "base_color": (0.56, 0.85, 0.97, 1.0),
        "metallic": 0.05,
        "roughness": 0.12,
        "emissive": (0.08, 0.28, 0.42, 1.0),
        "emissive_strength": 0.45,
        "is_emissive": True,
        "noise_scale": 12.0,
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

    # Subtle base-color variation using explicit RGBA sockets on Blender 5.0 ShaderNodeMix
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

    # Roughness variation around target
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

    return mat


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for col in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.lights, bpy.data.cameras):
        for item in list(col):
            if item.users == 0:
                col.remove(item)


# ---------------------------------------------------------------------------
# BMesh Hard-Surface & Organic Part Builders
# ---------------------------------------------------------------------------

class MeshAssembler:
    """Accumulates labeled geometry parts with per-face material tags and clean normals."""

    def __init__(self, mat_order):
        self.bm = bmesh.new()
        self.mat_order = list(mat_order)
        self.mat_map = {name: idx for idx, name in enumerate(self.mat_order)}

    def _tag_new(self, geom_verts_or_faces, mat_name, transform=None):
        mat_idx = self.mat_map[mat_name]
        faces = [g for g in geom_verts_or_faces if isinstance(g, bmesh.types.BMFace)]
        verts = [g for g in geom_verts_or_faces if isinstance(g, bmesh.types.BMVert)]
        if transform is not None and verts:
            bmesh.ops.transform(self.bm, matrix=transform, verts=verts)
        for f in faces:
            f.material_index = mat_idx
            f.smooth = True
        if faces:
            bmesh.ops.recalc_face_normals(self.bm, faces=faces)

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

    def add_capsule_tank(self, radius, cyl_height, center=(0, 0, 0), rot=(0, 0, 0), segs=24, mat="M_Dev_Armor"):
        tmp = bmesh.new()
        bmesh.ops.create_uvsphere(tmp, u_segments=segs, v_segments=16, radius=radius)
        half = cyl_height * 0.5
        for v in tmp.verts:
            if v.co.z > 1e-5:
                v.co.z += half
            elif v.co.z < -1e-5:
                v.co.z -= half
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

    def add_parabolic_dish(self, radius, depth, thickness=0.02, center=(0, 0, 0), rot=(0, 0, 0), radial_segs=32, rings=7, mat="M_Dev_Armor"):
        """Create solid parabolic dish opening along +Z before rotation."""
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

        # Center caps
        for si in range(radial_segs):
            ns = (si + 1) % radial_segs
            tmp.faces.new((c_front, front_rings[0][si], front_rings[0][ns]))
            tmp.faces.new((c_back, back_rings[0][ns], back_rings[0][si]))
        # Concentric rings
        for ri in range(rings - 1):
            for si in range(radial_segs):
                ns = (si + 1) % radial_segs
                tmp.faces.new((front_rings[ri][si], front_rings[ri + 1][si], front_rings[ri + 1][ns], front_rings[ri][ns]))
                tmp.faces.new((back_rings[ri][ns], back_rings[ri + 1][ns], back_rings[ri + 1][si], back_rings[ri][si]))
        # Outer rim
        for si in range(radial_segs):
            ns = (si + 1) % radial_segs
            tmp.faces.new((front_rings[-1][si], back_rings[-1][si], back_rings[-1][ns], front_rings[-1][ns]))

        bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
        xform = Matrix.Translation(center) @ Euler(rot, "XYZ").to_matrix().to_4x4()
        self._merge_tmp(tmp, mat, xform)

    def add_leaf(self, base_pos, direction, length, width, arch=0.25, mat="M_PlantFoliage"):
        """Sculpted thick botanical leaf with central midrib crease and gentle droop."""
        tmp = bmesh.new()
        dir_v = Vector(direction).normalized()
        quat = dir_v.to_track_quat("X", "Z")
        segs = 6
        rows = []
        thickness = max(0.0025, width * 0.04)
        for i in range(segs + 1):
            t = i / segs
            x = length * t
            # Leaf profile: narrow petiole -> broad belly -> pointed tip
            w = width * math.sin(math.pi * (t ** 0.72)) * (1.0 - 0.15 * t)
            z_curve = arch * length * math.sin(math.pi * t * 0.85) - 0.18 * arch * length * (t ** 2)
            v_l = tmp.verts.new((x, -w * 0.5, z_curve + w * 0.10))
            v_c = tmp.verts.new((x, 0.0, z_curve))
            v_r = tmp.verts.new((x, w * 0.5, z_curve + w * 0.10))
            v_b = tmp.verts.new((x, 0.0, z_curve - thickness))
            rows.append((v_l, v_c, v_r, v_b))
        for i in range(segs):
            a, b = rows[i], rows[i + 1]
            tmp.faces.new((a[0], b[0], b[1], a[1]))
            tmp.faces.new((a[1], b[1], b[2], a[2]))
            tmp.faces.new((a[2], b[2], b[3], a[3]))
            tmp.faces.new((a[3], b[3], b[0], a[0]))
        # Cap ends
        tmp.faces.new((rows[0][0], rows[0][1], rows[0][2], rows[0][3]))
        tmp.faces.new((rows[-1][3], rows[-1][2], rows[-1][1], rows[-1][0]))
        bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
        xform = Matrix.Translation(base_pos) @ quat.to_matrix().to_4x4()
        self._merge_tmp(tmp, mat, xform)

    def add_crystal_prism(self, base_pos, rot, radius, height, sides=6, mat="M_IceCrystal"):
        """Sharp faceted hexagonal/pentagonal Martian ice crystal spire."""
        tmp = bmesh.new()
        bot = []
        mid = []
        mid_h = height * 0.72
        for i in range(sides):
            ang = (2.0 * math.pi * i) / sides
            r_b = radius * (0.92 + 0.16 * math.sin(i * 2.1))
            r_m = radius * 0.84 * (0.92 + 0.14 * math.cos(i * 1.7))
            bot.append(tmp.verts.new((r_b * math.cos(ang), r_b * math.sin(ang), 0.0)))
            mid.append(tmp.verts.new((r_m * math.cos(ang), r_m * math.sin(ang), mid_h)))
        tip = tmp.verts.new((radius * 0.08, -radius * 0.05, height))
        tmp.faces.new(list(reversed(bot)))
        for i in range(sides):
            ni = (i + 1) % sides
            tmp.faces.new((bot[i], bot[ni], mid[ni], mid[i]))
            tmp.faces.new((mid[i], mid[ni], tip))
        bmesh.ops.bevel(tmp, geom=list(tmp.edges), offset=radius * 0.05, segments=1, affect="EDGES", clamp_overlap=True)
        bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
        xform = Matrix.Translation(base_pos) @ Euler(rot, "XYZ").to_matrix().to_4x4()
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

    def build_object(self, name, target_dims_m=None, center_xy=True, ground_z=True):
        """Convert accumulated BMesh to Blender object, normalize pivot/bounds, smooth & UV unwrap."""
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)

        # Prune unused materials while preserving order
        used_indices = sorted({f.material_index for f in self.bm.faces})
        remap = {old: new for new, old in enumerate(used_indices)}
        used_names = [self.mat_order[i] for i in used_indices]
        for f in self.bm.faces:
            f.material_index = remap[f.material_index]

        # Compute bounds
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

        # Smart UV Project for clean non-overlapping UV islands (lightmaps + PBR materials)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.015)
        bpy.ops.object.mode_set(mode="OBJECT")

        # Clean angle-based smooth/sharp normals (preserved across FBX export)
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(38))
        return obj


# ---------------------------------------------------------------------------
# 18 Prop Recipes (Dimensions in meters; 1.0 m = 100 cm in UE5)
# ---------------------------------------------------------------------------

def build_power_unit():
    """SM_Dev_PowerUnit (~80x80x120 cm): RTG/battery rack with cooling fins, conduit ports, status visor."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_Dev_Copper", "M_EmissiveAccent"])
    # Heavy base plinth & corner feet
    m.add_box((0.80, 0.80, 0.08), center=(0, 0, 0.04), bevel=0.012, mat="M_Dev_MetalDark")
    for sx in (-0.33, 0.33):
        for sy in (-0.33, 0.33):
            m.add_cylinder(0.045, 0.055, 0.05, center=(sx, sy, 0.025), mat="M_Dev_MetalDark")
    # Main RTG armored housing
    m.add_tapered_box((0.68, 0.68), (0.62, 0.62), 0.94, center_base=(0, 0, 0.08), bevel=0.02, mat="M_Dev_Armor")
    # Top armored cap & lifting lugs
    m.add_box((0.58, 0.58, 0.08), center=(0, 0, 1.06), bevel=0.015, mat="M_Dev_MetalDark")
    m.add_box((0.46, 0.46, 0.08), center=(0, 0, 1.14), bevel=0.012, mat="M_Dev_Armor")
    for sy in (-0.22, 0.22):
        m.add_box((0.12, 0.04, 0.06), center=(0, sy, 1.17), bevel=0.006, mat="M_Dev_MetalDark")
    # Cooling fins along +/-Y sides and -X rear
    for i in range(7):
        z = 0.22 + i * 0.11
        m.add_box((0.46, 0.78, 0.025), center=(-0.02, 0, z), bevel=0.004, mat="M_Dev_MetalDark")
    for i in range(5):
        y = -0.20 + i * 0.10
        m.add_box((0.09, 0.024, 0.72), center=(-0.35, y, 0.54), bevel=0.004, mat="M_Dev_Copper")
    # Front (+X) recessed bezel + emissive status visor slot + top LED bar
    m.add_box((0.06, 0.42, 0.28), center=(0.33, 0, 0.78), bevel=0.01, mat="M_Dev_MetalDark")
    m.add_box((0.04, 0.34, 0.18), center=(0.355, 0, 0.78), bevel=0.005, mat="M_EmissiveAccent")
    m.add_box((0.04, 0.36, 0.035), center=(0.25, 0, 1.14), bevel=0.004, mat="M_EmissiveAccent")
    # Lower front service door + dual heavy conduit ports
    m.add_box((0.04, 0.44, 0.36), center=(0.34, 0, 0.32), bevel=0.008, mat="M_Dev_Armor")
    for sy in (-0.15, 0.15):
        m.add_cylinder(0.065, 0.065, 0.10, center=(0.35, sy, 0.28), rot=(0, math.pi / 2, 0), bevel=0.008, mat="M_Dev_MetalDark")
        m.add_torus_ring(0.065, 0.015, center=(0.38, sy, 0.28), rot=(0, math.pi / 2, 0), mat="M_Dev_Copper")
    return m.build_object("SM_Dev_PowerUnit", target_dims_m=(0.80, 0.80, 1.20))


def build_oxygen_gen():
    """SM_Dev_OxygenGen (~80x80x120 cm): Dual cylindrical O2 tanks, regulator manifold, turbine grille."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_Dev_Copper", "M_EmissiveAccent"])
    # Base skid & side roll-cage uprights
    m.add_box((0.76, 0.80, 0.08), center=(0, 0, 0.04), bevel=0.012, mat="M_Dev_MetalDark")
    for sx in (-0.30, 0.30):
        for sy in (-0.34, 0.34):
            m.add_cylinder(0.024, 0.024, 1.06, center=(sx, sy, 0.60), mat="M_Dev_MetalDark")
    # Top cage frame
    m.add_box((0.64, 0.72, 0.05), center=(0, 0, 1.15), bevel=0.008, mat="M_Dev_MetalDark")
    # Dual vertical O2 cylindrical pressure tanks
    for sy in (-0.18, 0.18):
        m.add_capsule_tank(0.165, 0.62, center=(-0.03, sy, 0.56), segs=28, mat="M_Dev_Armor")
        for z_band in (0.34, 0.78):
            m.add_torus_ring(0.168, 0.014, center=(-0.03, sy, z_band), mat="M_Dev_MetalDark")
        # Tank neck valve
        m.add_cylinder(0.045, 0.045, 0.12, center=(-0.03, sy, 1.06), bevel=0.005, mat="M_Dev_Copper")
    # Regulator manifold bridging tanks at top
    m.add_box((0.20, 0.52, 0.10), center=(-0.03, 0, 1.10), bevel=0.012, mat="M_Dev_MetalDark")
    m.add_cylinder(0.06, 0.06, 0.04, center=(0.10, 0, 1.12), rot=(0, math.pi / 2, 0), bevel=0.005, mat="M_Dev_Copper")
    m.add_torus_ring(0.055, 0.012, center=(0.14, 0, 1.12), rot=(0, math.pi / 2, 0), mat="M_EmissiveAccent")
    # Front (+X) lower turbine intake grille box + louvered slats
    m.add_box((0.22, 0.54, 0.44), center=(0.24, 0, 0.30), bevel=0.015, mat="M_Dev_MetalDark")
    m.add_cylinder(0.16, 0.16, 0.06, center=(0.34, 0, 0.30), rot=(0, math.pi / 2, 0), bevel=0.008, mat="M_Dev_Armor")
    for k in range(5):
        z_slat = 0.19 + k * 0.055
        m.add_box((0.04, 0.28, 0.014), center=(0.37, 0, z_slat), rot=(0, 0.35, 0), mat="M_Dev_MetalDark")
    # Status bar above grille
    m.add_box((0.05, 0.40, 0.06), center=(0.33, 0, 0.58), bevel=0.006, mat="M_EmissiveAccent")
    return m.build_object("SM_Dev_OxygenGen", target_dims_m=(0.80, 0.80, 1.20))


def build_purifier():
    """SM_Dev_Purifier (~90x80x120 cm): Ice-melt hopper, vertical filtration canisters, pressure gauges."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_Dev_Copper", "M_EmissiveAccent"])
    # Base skid
    m.add_box((0.90, 0.80, 0.08), center=(0, 0, 0.04), bevel=0.012, mat="M_Dev_MetalDark")
    # Left/rear ice-melt hopper pedestal + flared hopper chute
    m.add_box((0.44, 0.56, 0.54), center=(-0.18, -0.06, 0.35), bevel=0.015, mat="M_Dev_Armor")
    m.add_tapered_box((0.36, 0.44), (0.50, 0.62), 0.48, center_base=(-0.18, -0.06, 0.62), bevel=0.012, mat="M_Dev_MetalDark")
    m.add_box((0.52, 0.64, 0.06), center=(-0.18, -0.06, 1.12), bevel=0.01, mat="M_Dev_Armor")
    # Dual vertical filtration canisters on +Y/+X side
    for idx, (cx, cy) in enumerate([(0.20, -0.18), (0.20, 0.18)]):
        m.add_cylinder(0.13, 0.13, 0.86, center=(cx, cy, 0.51), segs=24, bevel=0.015, mat="M_Dev_Armor")
        for z_ring in (0.22, 0.52, 0.84):
            m.add_torus_ring(0.135, 0.012, center=(cx, cy, z_ring), mat="M_Dev_MetalDark")
        # Sight-glass emissive slit
        m.add_box((0.04, 0.05, 0.36), center=(cx + 0.12, cy, 0.54), bevel=0.004, mat="M_EmissiveAccent")
        # Top cap & pipe bridge
        m.add_cylinder(0.06, 0.06, 0.12, center=(cx, cy, 1.00), mat="M_Dev_Copper")
    m.add_strut((0.20, -0.18, 1.04), (0.20, 0.18, 1.04), 0.032, mat="M_Dev_MetalDark")
    m.add_strut((-0.18, -0.06, 0.86), (0.20, 0.0, 0.86), 0.036, mat="M_Dev_Copper")
    # Front (+X) control gauge console
    m.add_box((0.12, 0.46, 0.28), center=(0.36, 0, 0.58), bevel=0.01, mat="M_Dev_MetalDark")
    for sy in (-0.12, 0.12):
        m.add_cylinder(0.065, 0.065, 0.04, center=(0.42, sy, 0.61), rot=(0, math.pi / 2, 0), bevel=0.005, mat="M_Dev_Armor")
        m.add_cylinder(0.048, 0.048, 0.02, center=(0.435, sy, 0.61), rot=(0, math.pi / 2, 0), mat="M_EmissiveAccent")
    m.add_box((0.03, 0.28, 0.04), center=(0.425, 0, 0.49), bevel=0.004, mat="M_EmissiveAccent")
    return m.build_object("SM_Dev_Purifier", target_dims_m=(0.90, 0.80, 1.20))


def build_greenhouse_seal():
    """SM_Dev_GreenhouseSeal (~80x80x120 cm): Airlock pressure bulkhead unit with seal valves."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_Dev_Copper", "M_EmissiveAccent"])
    # Heavy bolted base & main bulkhead casing
    m.add_box((0.80, 0.80, 0.10), center=(0, 0, 0.05), bevel=0.015, mat="M_Dev_MetalDark")
    m.add_box((0.68, 0.72, 0.98), center=(0, 0, 0.59), bevel=0.024, mat="M_Dev_Armor")
    m.add_box((0.56, 0.60, 0.12), center=(0, 0, 1.14), bevel=0.015, mat="M_Dev_MetalDark")
    # Front (+X) circular airlock pressure hatch plate + locking dog wheel
    m.add_torus_ring(0.28, 0.032, center=(0.33, 0, 0.62), rot=(0, math.pi / 2, 0), mat="M_Dev_MetalDark")
    m.add_cylinder(0.26, 0.26, 0.06, center=(0.34, 0, 0.62), rot=(0, math.pi / 2, 0), bevel=0.01, mat="M_Dev_Armor")
    m.add_torus_ring(0.13, 0.018, center=(0.39, 0, 0.62), rot=(0, math.pi / 2, 0), mat="M_Dev_Copper")
    for k in range(4):
        ang = k * math.pi * 0.5
        m.add_box((0.03, 0.03, 0.25), center=(0.385, 0, 0.62), rot=(ang, 0, 0), mat="M_Dev_MetalDark")
    # Twin side seal valves with handwheels
    for sy in (-0.38, 0.38):
        m.add_cylinder(0.06, 0.06, 0.10, center=(0.06, sy, 0.68), rot=(math.pi / 2, 0, 0), mat="M_Dev_MetalDark")
        m.add_torus_ring(0.09, 0.016, center=(0.06, sy * 1.12, 0.68), rot=(math.pi / 2, 0, 0), mat="M_Dev_Copper")
    # Pneumatic lock actuators & top beacon strip
    for sy in (-0.28, 0.28):
        m.add_cylinder(0.04, 0.04, 0.42, center=(0.32, sy, 0.34), mat="M_Dev_MetalDark")
    m.add_box((0.06, 0.44, 0.06), center=(0.30, 0, 1.14), bevel=0.008, mat="M_EmissiveAccent")
    m.add_box((0.04, 0.08, 0.34), center=(0.35, -0.30, 0.88), bevel=0.005, mat="M_EmissiveAccent")
    m.add_box((0.04, 0.08, 0.34), center=(0.35, 0.30, 0.88), bevel=0.005, mat="M_EmissiveAccent")
    return m.build_object("SM_Dev_GreenhouseSeal", target_dims_m=(0.80, 0.80, 1.20))


def build_water_tank():
    """SM_Dev_WaterTank (~160x160x160 cm): Ribbed pressurized cistern on cradle legs."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_Dev_Copper", "M_EmissiveAccent"])
    # 4 splayed heavy cradle legs + ground anchor pads
    for sx in (-1, 1):
        for sy in (-1, 1):
            p_bot = (sx * 0.70, sy * 0.70, 0.03)
            p_top = (sx * 0.50, sy * 0.52, 0.72)
            m.add_box((0.20, 0.20, 0.06), center=(sx * 0.70, sy * 0.70, 0.03), bevel=0.01, mat="M_Dev_MetalDark")
            m.add_strut(p_bot, p_top, 0.065, segs=12, mat="M_Dev_MetalDark")
    # Cross-bracing & cradle saddle ring
    m.add_box((1.16, 1.16, 0.08), center=(0, 0, 0.36), bevel=0.01, mat="M_Dev_MetalDark")
    m.add_box((1.06, 1.12, 0.12), center=(0, 0, 0.68), bevel=0.015, mat="M_Dev_MetalDark")
    # Horizontal ribbed pressurized cistern along X (length 1.56, radius 0.52, center Z=0.98)
    m.add_capsule_tank(0.52, 0.54, center=(0, 0, 0.96), rot=(0, math.pi / 2, 0), segs=32, mat="M_Dev_Armor")
    for rx in (-0.30, 0.0, 0.30):
        m.add_torus_ring(0.53, 0.028, center=(rx, 0, 0.96), rot=(0, math.pi / 2, 0), major_segs=32, mat="M_Dev_MetalDark")
    # Top inspection dome, pressure valve, and safety guard rail
    m.add_cylinder(0.22, 0.20, 0.16, center=(0, 0, 1.48), bevel=0.015, mat="M_Dev_MetalDark")
    m.add_cylinder(0.14, 0.14, 0.06, center=(0, 0, 1.57), bevel=0.008, mat="M_Dev_Copper")
    # Flanged inlet/outlet stub pipes on -Y / +X ends + emissive fluid level strip on +X/+Y
    m.add_cylinder(0.10, 0.10, 0.18, center=(0.72, 0, 0.96), rot=(0, math.pi / 2, 0), bevel=0.01, mat="M_Dev_MetalDark")
    m.add_cylinder(0.10, 0.10, 0.18, center=(-0.72, 0, 0.96), rot=(0, math.pi / 2, 0), bevel=0.01, mat="M_Dev_MetalDark")
    m.add_box((0.08, 0.08, 0.62), center=(0.0, -0.55, 0.96), bevel=0.008, mat="M_Dev_MetalDark")
    m.add_box((0.05, 0.05, 0.50), center=(0.0, -0.575, 0.96), bevel=0.004, mat="M_EmissiveAccent")
    return m.build_object("SM_Dev_WaterTank", target_dims_m=(1.60, 1.60, 1.60))


def build_water_pipe():
    """SM_Dev_WaterPipe (~300x40x40 cm): Flanged insulated conduit pipe section with valve collar."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_Dev_Copper", "M_EmissiveAccent"])
    # Main horizontal pipe along X (total X = 3.00 m, radius 0.135 m, center Z=0.20)
    m.add_cylinder(0.135, 0.135, 2.94, center=(0, 0, 0.20), rot=(0, math.pi / 2, 0), segs=24, mat="M_Dev_Armor")
    # End bolt flanges at X = +/-1.48
    for sx in (-1.47, 1.47):
        m.add_cylinder(0.195, 0.195, 0.05, center=(sx, 0, 0.20), rot=(0, math.pi / 2, 0), segs=24, bevel=0.008, mat="M_Dev_MetalDark")
        for bi in range(8):
            ang = (2.0 * math.pi * bi) / 8
            m.add_cylinder(0.014, 0.014, 0.08, center=(sx, 0.165 * math.cos(ang), 0.20 + 0.165 * math.sin(ang)), rot=(0, math.pi / 2, 0), segs=8, mat="M_Dev_Copper")
    # Ribbed insulation clamping bands along length
    for rx in (-1.10, -0.60, 0.60, 1.10):
        m.add_torus_ring(0.145, 0.016, center=(rx, 0, 0.20), rot=(0, math.pi / 2, 0), mat="M_Dev_MetalDark")
    # Two ground saddle support brackets touching Z=0
    for sx in (-0.95, 0.95):
        m.add_box((0.18, 0.38, 0.05), center=(sx, 0, 0.025), bevel=0.008, mat="M_Dev_MetalDark")
        m.add_box((0.14, 0.26, 0.14), center=(sx, 0, 0.11), bevel=0.008, mat="M_Dev_MetalDark")
    # Central valve collar + actuator + handwheel + status ring
    m.add_cylinder(0.175, 0.175, 0.26, center=(0, 0, 0.20), rot=(0, math.pi / 2, 0), segs=24, bevel=0.01, mat="M_Dev_MetalDark")
    m.add_torus_ring(0.180, 0.015, center=(0, 0, 0.20), rot=(0, math.pi / 2, 0), mat="M_EmissiveAccent")
    m.add_cylinder(0.04, 0.04, 0.14, center=(0, 0, 0.33), mat="M_Dev_Copper")
    m.add_torus_ring(0.095, 0.016, center=(0, 0, 0.385), mat="M_Dev_Copper")
    return m.build_object("SM_Dev_WaterPipe", target_dims_m=(3.00, 0.40, 0.40))


def build_comms_relay():
    """SM_Dev_CommsRelay (~120x120x260 cm): Tripod mast with parabolic Mars dish and beacon tip."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_Dev_Copper", "M_EmissiveAccent"])
    # Tripod legs spread within 120x120 cm at Z=0 converging to hub at Z=1.55
    for i in range(3):
        ang = math.radians(i * 120.0 + 30.0)
        fx, fy = 0.54 * math.cos(ang), 0.54 * math.sin(ang)
        m.add_cylinder(0.09, 0.10, 0.06, center=(fx, fy, 0.03), segs=12, bevel=0.008, mat="M_Dev_MetalDark")
        m.add_strut((fx, fy, 0.04), (0.14 * math.cos(ang), 0.14 * math.sin(ang), 1.45), 0.042, segs=12, mat="M_Dev_MetalDark")
    # Cross braces & equipment transceiver box
    for i in range(3):
        a0 = math.radians(i * 120.0 + 30.0)
        a1 = math.radians(((i + 1) % 3) * 120.0 + 30.0)
        m.add_strut((0.36 * math.cos(a0), 0.36 * math.sin(a0), 0.65), (0.36 * math.cos(a1), 0.36 * math.sin(a1), 0.65), 0.022, mat="M_Dev_MetalDark")
    m.add_box((0.34, 0.34, 0.42), center=(0, 0, 0.85), bevel=0.015, mat="M_Dev_Armor")
    m.add_box((0.05, 0.20, 0.08), center=(0.17, 0, 0.94), bevel=0.005, mat="M_EmissiveAccent")
    # Upper mast pole + dish azimuth gimbal at Z=1.65
    m.add_cylinder(0.07, 0.05, 1.05, center=(0, 0, 1.92), segs=16, mat="M_Dev_MetalDark")
    m.add_box((0.20, 0.22, 0.20), center=(0.06, 0, 1.65), bevel=0.012, mat="M_Dev_MetalDark")
    # Parabolic Mars dish tilted toward +X and slightly skyward (+62 deg around Y)
    dish_pos = (0.14, 0.0, 1.72)
    dish_rot = (0.0, math.radians(62.0), 0.0)
    m.add_parabolic_dish(0.50, 0.16, thickness=0.028, center=dish_pos, rot=dish_rot, mat="M_Dev_Armor")
    # Dish feed-horn struts + central LNB pod
    horn_tip = Vector(dish_pos) + Euler(dish_rot, "XYZ").to_matrix() @ Vector((0.0, 0.0, 0.42))
    m.add_cylinder(0.045, 0.032, 0.14, center=horn_tip, rot=dish_rot, mat="M_Dev_Copper")
    for k in range(3):
        ang = math.radians(k * 120.0)
        rim_pt = Vector(dish_pos) + Euler(dish_rot, "XYZ").to_matrix() @ Vector((0.44 * math.cos(ang), 0.44 * math.sin(ang), 0.13))
        m.add_strut(rim_pt, horn_tip, 0.012, segs=8, mat="M_Dev_MetalDark")
    # Top mast beacon tip reaching Z=2.60
    m.add_cylinder(0.045, 0.045, 0.08, center=(0, 0, 2.46), mat="M_Dev_MetalDark")
    m.add_sphere(0.06, center=(0, 0, 2.54), scale=(1, 1, 1.15), mat="M_EmissiveAccent")
    return m.build_object("SM_Dev_CommsRelay", target_dims_m=(1.20, 1.20, 2.60))


def build_transmitter():
    """SM_Dev_Transmitter (~100x80x130 cm): Angled dual-monitor comms terminal console."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_Dev_Copper", "M_EmissiveAccent"])
    # Heavy console pedestal base (facing +X)
    m.add_box((0.76, 0.96, 0.10), center=(0, 0, 0.05), bevel=0.015, mat="M_Dev_MetalDark")
    m.add_tapered_box((0.66, 0.88), (0.58, 0.88), 0.68, center_base=(-0.03, 0, 0.10), bevel=0.018, mat="M_Dev_Armor")
    # Sloped ergonomic control deck protruding +X
    m.add_box((0.52, 0.96, 0.10), center=(0.12, 0, 0.78), rot=(0, 0.18, 0), bevel=0.015, mat="M_Dev_MetalDark")
    m.add_box((0.26, 0.56, 0.03), center=(0.18, 0, 0.82), rot=(0, 0.18, 0), bevel=0.005, mat="M_Dev_Armor")
    # Transmit lever & indicator pads
    m.add_box((0.12, 0.14, 0.04), center=(0.16, 0.36, 0.82), rot=(0, 0.18, 0), mat="M_Dev_Copper")
    m.add_box((0.06, 0.10, 0.025), center=(0.18, -0.36, 0.83), rot=(0, 0.18, 0), mat="M_EmissiveAccent")
    # Angled dual-monitor hood & two widescreen recessed displays facing +X
    m.add_box((0.22, 0.94, 0.42), center=(-0.14, 0, 1.04), bevel=0.018, mat="M_Dev_Armor")
    for sy, yaw in [(-0.23, 0.14), (0.23, -0.14)]:
        m.add_box((0.08, 0.42, 0.32), center=(-0.02, sy, 1.05), rot=(0, -0.15, yaw), bevel=0.01, mat="M_Dev_MetalDark")
        m.add_box((0.04, 0.36, 0.25), center=(0.005, sy, 1.05), rot=(0, -0.15, yaw), bevel=0.004, mat="M_EmissiveAccent")
    # Corner comms whip antenna reaching Z=1.30
    m.add_cylinder(0.022, 0.012, 0.38, center=(-0.22, 0.40, 1.11), mat="M_Dev_MetalDark")
    m.add_sphere(0.024, center=(-0.22, 0.40, 1.29), mat="M_EmissiveAccent")
    return m.build_object("SM_Dev_Transmitter", target_dims_m=(0.80, 1.00, 1.30))


# ---------------------------------------------------------------------------
# Gameplay Props: Botanical, Pickups, Defenses
# ---------------------------------------------------------------------------

def build_plant_plot():
    """SM_PlantPlot (~180x180x40 cm): Hydroponic metal tray with recessed regolith soil bed."""
    m = MeshAssembler(["M_Dev_MetalDark", "M_Dev_Armor", "M_RegolithSoil", "M_EmissiveAccent"])
    # Outer tray base floor
    m.add_box((1.76, 1.76, 0.18), center=(0, 0, 0.09), bevel=0.018, mat="M_Dev_MetalDark")
    # 4 raised chamfered rim walls forming recessed hydroponic trough
    for sx in (-0.81, 0.81):
        m.add_box((0.18, 1.80, 0.26), center=(sx, 0, 0.27), bevel=0.016, mat="M_Dev_Armor")
    for sy in (-0.81, 0.81):
        m.add_box((1.48, 0.18, 0.26), center=(0, sy, 0.27), bevel=0.016, mat="M_Dev_Armor")
    # Corner bumper caps & hydroponic feed manifolds
    for sx in (-0.82, 0.82):
        for sy in (-0.82, 0.82):
            m.add_box((0.20, 0.20, 0.38), center=(sx, sy, 0.20), bevel=0.015, mat="M_Dev_MetalDark")
    # Nutrient pipes along +X and -X outer trim + subtle indicator bar
    m.add_cylinder(0.032, 0.032, 1.32, center=(0.89, 0, 0.20), rot=(math.pi / 2, 0, 0), mat="M_Dev_MetalDark")
    m.add_box((0.04, 0.48, 0.04), center=(0.89, 0, 0.34), bevel=0.004, mat="M_EmissiveAccent")
    # Recessed regolith soil bed (top around Z=0.27 with subtle mounding)
    m.add_box((1.44, 1.44, 0.12), center=(0, 0, 0.21), bevel=0.02, mat="M_RegolithSoil")
    for mx, my, mr in [(-0.28, -0.22, 0.28), (0.30, 0.24, 0.26), (0.0, 0.0, 0.34)]:
        m.add_sphere(mr, center=(mx, my, 0.24), scale=(1.2, 1.2, 0.22), mat="M_RegolithSoil")
    return m.build_object("SM_PlantPlot", target_dims_m=(1.80, 1.80, 0.40))


def build_plant_seed():
    """SM_Plant_Seed (~15x15x12 cm): Germinating sprout mound with tiny cotyledon leaves."""
    m = MeshAssembler(["M_PlantFoliage", "M_RegolithSoil"])
    # Small regolith germination mound at Z=0
    m.add_sphere(0.075, center=(0, 0, 0.016), scale=(1.0, 1.0, 0.36), u_segs=16, v_segs=10, mat="M_RegolithSoil")
    # Tender curved sprout stem
    m.add_strut((0, 0, 0.02), (0.006, 0, 0.065), 0.008, segs=10, mat="M_PlantFoliage")
    m.add_strut((0.006, 0, 0.065), (0.012, 0, 0.098), 0.006, segs=10, mat="M_PlantFoliage")
    # Twin opposing cotyledon leaves
    m.add_leaf((0.010, 0, 0.092), (0.85, 0.20, 0.45), length=0.065, width=0.038, arch=0.22, mat="M_PlantFoliage")
    m.add_leaf((0.010, 0, 0.092), (-0.85, -0.20, 0.48), length=0.062, width=0.036, arch=0.22, mat="M_PlantFoliage")
    return m.build_object("SM_Plant_Seed", target_dims_m=(0.15, 0.15, 0.12))


def build_plant_seedling():
    """SM_Plant_Seedling (~35x35x55 cm): Multi-stem young leafy Mars crop."""
    m = MeshAssembler(["M_PlantFoliage", "M_RegolithSoil"])
    # Root collar soil mound
    m.add_sphere(0.11, center=(0, 0, 0.025), scale=(1.1, 1.0, 0.35), u_segs=16, v_segs=10, mat="M_RegolithSoil")
    # 3 organic branching stems with staggered broad leaves
    stems = [
        [(0.0, 0.0, 0.03), (0.02, 0.01, 0.20), (0.05, 0.03, 0.40), (0.06, 0.04, 0.52)],
        [(0.0, 0.0, 0.03), (-0.04, 0.03, 0.18), (-0.08, 0.06, 0.35)],
        [(0.0, 0.0, 0.03), (0.03, -0.05, 0.17), (0.06, -0.09, 0.33)],
    ]
    for pts in stems:
        for i in range(len(pts) - 1):
            r = 0.014 * (1.0 - 0.25 * i)
            m.add_strut(pts[i], pts[i + 1], r, segs=10, mat="M_PlantFoliage")
    # Rich radial arrangement of sculpted leaves
    leaf_specs = [
        ((0.02, 0.01, 0.14), (0.9, 0.3, 0.25), 0.18, 0.115),
        ((-0.02, 0.02, 0.13), (-0.8, 0.5, 0.22), 0.17, 0.110),
        ((0.02, -0.03, 0.12), (0.4, -0.9, 0.24), 0.17, 0.110),
        ((-0.01, -0.02, 0.18), (-0.6, -0.7, 0.36), 0.16, 0.105),
        ((0.04, 0.02, 0.29), (0.7, -0.6, 0.42), 0.18, 0.115),
        ((-0.06, 0.05, 0.28), (-0.7, 0.6, 0.45), 0.17, 0.110),
        ((0.05, -0.08, 0.30), (0.2, -0.9, 0.48), 0.16, 0.100),
        ((0.05, 0.03, 0.41), (-0.4, -0.8, 0.58), 0.15, 0.095),
        ((0.06, 0.04, 0.49), (0.6, 0.5, 0.70), 0.14, 0.088),
        ((0.06, 0.04, 0.49), (-0.6, -0.2, 0.72), 0.13, 0.082),
    ]
    for base, d, length, width in leaf_specs:
        m.add_leaf(base, d, length=length, width=width, arch=0.25, mat="M_PlantFoliage")
    return m.build_object("SM_Plant_Seedling", target_dims_m=(0.35, 0.35, 0.55))


def build_pickup_parts():
    """SM_Pickup_Parts (~36x28x24 cm): Sci-fi repair parts crate with handle & latches."""
    m = MeshAssembler(["M_Pickup_PartsMat", "M_Dev_MetalDark", "M_EmissiveAccent"])
    # Main rugged case shell & ribbed lid
    m.add_box((0.36, 0.28, 0.16), center=(0, 0, 0.08), bevel=0.015, mat="M_Pickup_PartsMat")
    m.add_box((0.35, 0.27, 0.05), center=(0, 0, 0.185), bevel=0.012, mat="M_Pickup_PartsMat")
    # Rim gasket & protective corner bumpers
    m.add_box((0.365, 0.285, 0.02), center=(0, 0, 0.16), bevel=0.004, mat="M_Dev_MetalDark")
    for sx in (-0.15, 0.15):
        for sy in (-0.11, 0.11):
            m.add_box((0.065, 0.065, 0.21), center=(sx, sy, 0.105), bevel=0.008, mat="M_Dev_MetalDark")
    # Twin front (+X) latches & accent LED
    for sy in (-0.08, 0.08):
        m.add_box((0.03, 0.045, 0.07), center=(0.18, sy, 0.15), bevel=0.005, mat="M_Dev_MetalDark")
    m.add_box((0.025, 0.08, 0.025), center=(0.18, 0, 0.12), bevel=0.003, mat="M_EmissiveAccent")
    # Top carry handle arch (Z up to 0.24)
    m.add_box((0.035, 0.16, 0.024), center=(0, 0, 0.228), bevel=0.005, mat="M_Dev_MetalDark")
    for sy in (-0.07, 0.07):
        m.add_box((0.03, 0.022, 0.03), center=(0, sy, 0.215), mat="M_Dev_MetalDark")
    return m.build_object("SM_Pickup_Parts", target_dims_m=(0.36, 0.28, 0.24))


def build_pickup_ammo():
    """SM_Pickup_Ammo (~30x22x20 cm): Magazine/energy cell pack."""
    m = MeshAssembler(["M_Pickup_AmmoMat", "M_Dev_MetalDark", "M_EmissiveAccent"])
    # Sloped tactical magazine / energy cell housing
    m.add_box((0.30, 0.22, 0.05), center=(0, 0, 0.025), bevel=0.008, mat="M_Dev_MetalDark")
    m.add_tapered_box((0.28, 0.20), (0.25, 0.18), 0.12, center_base=(0, 0, 0.05), bevel=0.012, mat="M_Pickup_AmmoMat")
    # Top terminal cap & twin energy cell ribs
    for sy in (-0.055, 0.055):
        m.add_cylinder(0.038, 0.038, 0.04, center=(0.06, sy, 0.18), bevel=0.004, mat="M_Dev_MetalDark")
    m.add_box((0.14, 0.16, 0.03), center=(-0.05, 0, 0.185), bevel=0.005, mat="M_Dev_MetalDark")
    # Side grip ribs & glowing charge bar
    for rx in (-0.08, -0.02, 0.04):
        m.add_box((0.024, 0.21, 0.08), center=(rx, 0, 0.11), bevel=0.004, mat="M_Dev_MetalDark")
    m.add_box((0.03, 0.12, 0.035), center=(0.14, 0, 0.11), bevel=0.004, mat="M_EmissiveAccent")
    return m.build_object("SM_Pickup_Ammo", target_dims_m=(0.30, 0.22, 0.20))


def build_pickup_ice():
    """SM_Pickup_Ice (~45x40x38 cm): Faceted Martian subsurface ice crystal cluster."""
    m = MeshAssembler(["M_IceCrystal", "M_EmissiveAccent", "M_RegolithSoil"])
    # Frozen regolith mineral crust base
    m.add_sphere(0.19, center=(0, 0, 0.035), scale=(1.1, 0.95, 0.28), u_segs=14, v_segs=8, mat="M_RegolithSoil")
    # Clustered faceted hexagonal crystal spires
    crystals = [
        ((0.0, 0.0, 0.02), (0.08, -0.05, 0.2), 0.085, 0.36),
        ((0.09, 0.05, 0.02), (-0.28, 0.24, 0.9), 0.065, 0.28),
        ((-0.09, 0.07, 0.02), (0.32, 0.26, 2.1), 0.062, 0.26),
        ((-0.06, -0.09, 0.02), (0.28, -0.34, 4.0), 0.060, 0.24),
        ((0.08, -0.08, 0.02), (-0.36, -0.22, 5.2), 0.055, 0.21),
        ((0.01, 0.09, 0.02), (-0.18, 0.12, 1.3), 0.048, 0.20),
    ]
    for pos, rot, rad, h in crystals:
        m.add_crystal_prism(pos, rot, rad, h, sides=6, mat="M_IceCrystal")
    # Subtle inner cryo core facet
    m.add_crystal_prism((0.0, 0.0, 0.03), (0.08, -0.05, 0.2), 0.042, 0.18, sides=6, mat="M_EmissiveAccent")
    return m.build_object("SM_Pickup_Ice", target_dims_m=(0.45, 0.40, 0.38))


def build_pickup_seeds():
    """SM_Pickup_Seeds (~26x26x34 cm): Cryo seed-bank canister with glass-band accent."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_EmissiveAccent"])
    # Bottom & top octagonal armored endcaps
    m.add_cylinder(0.125, 0.125, 0.07, center=(0, 0, 0.035), segs=12, bevel=0.008, mat="M_Dev_MetalDark")
    m.add_cylinder(0.120, 0.115, 0.08, center=(0, 0, 0.26), segs=12, bevel=0.008, mat="M_Dev_Armor")
    # Inner cryo cylinder & glowing glass-band accent
    m.add_cylinder(0.095, 0.095, 0.16, center=(0, 0, 0.15), segs=24, mat="M_Dev_Armor")
    m.add_cylinder(0.102, 0.102, 0.085, center=(0, 0, 0.15), segs=24, bevel=0.004, mat="M_EmissiveAccent")
    # 3 protective cage ribs
    for k in range(3):
        ang = math.radians(k * 120.0)
        m.add_box((0.024, 0.024, 0.22), center=(0.112 * math.cos(ang), 0.112 * math.sin(ang), 0.15), rot=(0, 0, ang), bevel=0.004, mat="M_Dev_MetalDark")
    # Top carry handle loop
    m.add_box((0.03, 0.12, 0.025), center=(0, 0, 0.328), bevel=0.005, mat="M_Dev_MetalDark")
    for sy in (-0.05, 0.05):
        m.add_box((0.026, 0.02, 0.04), center=(0, sy, 0.31), mat="M_Dev_MetalDark")
    return m.build_object("SM_Pickup_Seeds", target_dims_m=(0.26, 0.26, 0.34))


def build_turret_base():
    """SM_Defense_TurretBase (~90x90x70 cm): Heavy tripod/pedestal mount with flat Z=70 swivel collar."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_EmissiveAccent"])
    # 3 splayed heavy tripod legs + bolted anchor footpads within 90x90 cm
    for k in range(3):
        ang = math.radians(k * 120.0)
        fx, fy = 0.36 * math.cos(ang), 0.36 * math.sin(ang)
        m.add_cylinder(0.11, 0.12, 0.06, center=(fx, fy, 0.03), segs=12, bevel=0.008, mat="M_Dev_MetalDark")
        m.add_strut((0.12 * math.cos(ang), 0.12 * math.sin(ang), 0.24), (fx, fy, 0.045), 0.068, segs=8, mat="M_Dev_Armor")
    # Central armored pedestal riser + power junction box
    m.add_cylinder(0.24, 0.19, 0.44, center=(0, 0, 0.26), segs=16, bevel=0.012, mat="M_Dev_Armor")
    m.add_box((0.28, 0.24, 0.24), center=(-0.12, 0, 0.28), bevel=0.012, mat="M_Dev_MetalDark")
    # Base status ring & machined top swivel bearing collar at Z=0.70
    m.add_torus_ring(0.21, 0.014, center=(0, 0, 0.48), mat="M_EmissiveAccent")
    m.add_cylinder(0.20, 0.18, 0.18, center=(0, 0, 0.61), segs=24, bevel=0.01, mat="M_Dev_MetalDark")
    return m.build_object("SM_Defense_TurretBase", target_dims_m=(0.90, 0.90, 0.70))


def build_turret_head():
    """SM_Defense_TurretHead (~70x40x36 cm, pivot at swivel base Z=0, +X barrel forward)."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_EmissiveAccent"])
    # Swivel neck collar centered at (0,0,0) with minZ=0
    m.add_cylinder(0.15, 0.16, 0.06, center=(0, 0, 0.03), segs=24, bevel=0.006, mat="M_Dev_MetalDark")
    # Main armored sentry gun housing centered around swivel X=0, extending rear to -0.22 and front to +0.18
    m.add_tapered_box((0.36, 0.34), (0.30, 0.28), 0.20, center_base=(-0.02, 0, 0.06), bevel=0.015, mat="M_Dev_Armor")
    # Rear ammo/power drum box
    m.add_box((0.14, 0.38, 0.18), center=(-0.15, 0, 0.17), bevel=0.012, mat="M_Dev_MetalDark")
    # Top optical targeting sensor pod with glowing targeting lens (+X)
    m.add_box((0.16, 0.14, 0.10), center=(0.02, 0, 0.31), bevel=0.01, mat="M_Dev_MetalDark")
    m.add_cylinder(0.038, 0.038, 0.04, center=(0.10, 0, 0.31), rot=(0, math.pi / 2, 0), bevel=0.004, mat="M_EmissiveAccent")
    # Twin parallel sentry barrels extending forward along +X to X=+0.48 (total span -0.22..+0.48 = 0.70 m)
    for sy in (-0.085, 0.085):
        m.add_cylinder(0.036, 0.032, 0.18, center=(0.22, sy, 0.16), rot=(0, math.pi / 2, 0), segs=16, bevel=0.005, mat="M_Dev_MetalDark")
        m.add_cylinder(0.022, 0.022, 0.26, center=(0.34, sy, 0.16), rot=(0, math.pi / 2, 0), segs=16, mat="M_Dev_MetalDark")
        m.add_cylinder(0.030, 0.028, 0.05, center=(0.455, sy, 0.16), rot=(0, math.pi / 2, 0), segs=16, bevel=0.004, mat="M_Dev_Armor")
    # Important: center_xy=False preserves exact swivel pivot at (0, 0, 0)!
    return m.build_object("SM_Defense_TurretHead", target_dims_m=None, center_xy=False, ground_z=True)


def build_defense_barrier():
    """SM_Defense_Barrier (~160x45x110 cm): Deployable shock-pylon energy barricade."""
    m = MeshAssembler(["M_Dev_Armor", "M_Dev_MetalDark", "M_EmissiveAccent"])
    # Heavy ground base beam & splayed stabilizer feet
    m.add_box((1.56, 0.36, 0.12), center=(0, 0, 0.06), bevel=0.015, mat="M_Dev_MetalDark")
    for sx in (-0.64, 0.0, 0.64):
        m.add_box((0.18, 0.45, 0.07), center=(sx, 0, 0.035), bevel=0.008, mat="M_Dev_MetalDark")
    # Central lower armored barricade shield (Z=0.12..0.56)
    m.add_tapered_box((1.16, 0.26), (1.10, 0.18), 0.44, center_base=(0, 0, 0.12), bevel=0.015, mat="M_Dev_Armor")
    # Twin flanking angled shock pylons at X = +/-0.66 rising to Z=1.10
    for sx in (-0.66, 0.66):
        m.add_box((0.24, 0.32, 0.84), center=(sx, 0, 0.54), bevel=0.018, mat="M_Dev_Armor")
        for z_coil in (0.64, 0.78, 0.92):
            m.add_box((0.27, 0.35, 0.045), center=(sx, 0, z_coil), bevel=0.006, mat="M_Dev_MetalDark")
        m.add_cylinder(0.065, 0.045, 0.14, center=(sx, 0, 1.03), segs=12, bevel=0.008, mat="M_EmissiveAccent")
    # Horizontal shock emitter energy bars spanning between pylons
    for z_bar in (0.66, 0.82, 0.96):
        m.add_cylinder(0.022, 0.022, 1.14, center=(0, 0, z_bar), rot=(0, math.pi / 2, 0), segs=12, mat="M_EmissiveAccent")
    return m.build_object("SM_Defense_Barrier", target_dims_m=(1.60, 0.45, 1.10))


# ---------------------------------------------------------------------------
# FBX Export & Roundtrip Verification + 1200x1200 Multi-Angle Contact Sheets
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
        bg.inputs[0].default_value = (0.12, 0.09, 0.08, 1.0)
        bg.inputs[1].default_value = 1.6

    lights = []
    for lname, rot, energy, col in [
        ("KeySun", (0.72, 0.22, 0.65), 3.4, (1.0, 0.92, 0.84)),
        ("FillSun", (-0.65, -0.30, -2.35), 1.7, (0.78, 0.88, 1.0)),
        ("RimSun", (0.45, -0.45, 2.8), 1.5, (1.0, 0.72, 0.52)),
    ]:
        ld = bpy.data.lights.new(lname, "SUN")
        ld.energy = energy
        ld.color = col
        lo = bpy.data.objects.new(lname, ld)
        lo.rotation_euler = rot
        bpy.context.collection.objects.link(lo)
        lights.append(lo)

    bpy.ops.mesh.primitive_plane_add(size=14.0, location=(0.0, 0.0, -0.002))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("PreviewFloor")
    fmat.use_nodes = True
    bsdf = fmat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.24, 0.13, 0.09, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.88
    floor.data.materials.append(fmat)

    cam_d = bpy.data.cameras.new("PreviewCam")
    cam_d.lens = 42.0
    cam = bpy.data.objects.new("PreviewCam", cam_d)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    return floor, cam, lights


def render_contact_sheet(items, cols, rows, tile_w, tile_h, out_png):
    """Render 2 angles (Front +X 3/4 and Rear/Side -X/-Y 3/4) per prop into a 1200x1200 PNG."""
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    clear_scene()
    floor, cam, lights = setup_preview_stage()

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
        # Re-bind rich procedural Blender materials by slot name so preview matches authoring look
        for idx, slot in enumerate(imp.material_slots):
            base_mname = slot.name.split(".")[0]
            if base_mname in MAT_SPECS:
                imp.data.materials[idx] = get_material(base_mname)

        pts = [imp.matrix_world @ v.co for v in imp.data.vertices]
        mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        center = (mn + mx) * 0.5
        span = max(mx.x - mn.x, mx.y - mn.y, mx.z - mn.z)
        dist = max(span * 1.65, 0.35)

        for tag, off in [
            ("front3q", Vector((dist * 0.78, -dist * 0.62, dist * 0.42))),
            ("rear3q", Vector((-dist * 0.72, dist * 0.68, dist * 0.36))),
        ]:
            cam.location = center + off
            cam.rotation_euler = (center - cam.location).normalized().to_track_quat("-Z", "Y").to_euler()
            tmp = os.path.join(PREVIEW_DIR, f"_tmp_{name}_{tag}.png")
            scene.render.filepath = tmp
            bpy.ops.render.render(write_still=True)
            tiles.append(tmp)

        bpy.data.objects.remove(imp, do_unlink=True)

    # Stitch into exact 1200x1200 sheet
    total_w = cols * tile_w
    total_h = rows * tile_h
    sheet = bpy.data.images.new("Sheet", width=total_w, height=total_h, alpha=True)
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

    bpy.data.objects.remove(floor, do_unlink=True)
    bpy.data.objects.remove(cam, do_unlink=True)
    for lo in lights:
        bpy.data.objects.remove(lo, do_unlink=True)


def main():
    os.makedirs(DEVICES_DIR, exist_ok=True)
    os.makedirs(GAMEPLAY_DIR, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)

    device_recipes = [
        ("SM_Dev_PowerUnit", build_power_unit),
        ("SM_Dev_OxygenGen", build_oxygen_gen),
        ("SM_Dev_Purifier", build_purifier),
        ("SM_Dev_GreenhouseSeal", build_greenhouse_seal),
        ("SM_Dev_WaterTank", build_water_tank),
        ("SM_Dev_WaterPipe", build_water_pipe),
        ("SM_Dev_CommsRelay", build_comms_relay),
        ("SM_Dev_Transmitter", build_transmitter),
    ]
    gameplay_recipes = [
        ("SM_PlantPlot", build_plant_plot),
        ("SM_Plant_Seed", build_plant_seed),
        ("SM_Plant_Seedling", build_plant_seedling),
        ("SM_Pickup_Parts", build_pickup_parts),
        ("SM_Pickup_Ammo", build_pickup_ammo),
        ("SM_Pickup_Ice", build_pickup_ice),
        ("SM_Pickup_Seeds", build_pickup_seeds),
        ("SM_Defense_TurretBase", build_turret_base),
        ("SM_Defense_TurretHead", build_turret_head),
        ("SM_Defense_Barrier", build_defense_barrier),
    ]

    manifest = {"devices": [], "gameplay": [], "materials": MAT_SPECS}
    device_items = []
    gameplay_items = []

    for cat_key, out_dir, recipes, bucket in [
        ("devices", DEVICES_DIR, device_recipes, device_items),
        ("gameplay", GAMEPLAY_DIR, gameplay_recipes, gameplay_items),
    ]:
        for name, fn in recipes:
            clear_scene()
            obj = fn()
            fbx_path = os.path.join(out_dir, f"{name}.fbx")
            export_fbx(obj, fbx_path)
            info = verify_fbx_roundtrip(fbx_path)
            info["name"] = name
            info["fbx_abs"] = fbx_path
            assert abs(info["ue_min_cm"][2]) < 0.05, f"{name} minZ not grounded: {info['ue_min_cm']}"
            assert info["uv_layers"] >= 1, f"{name} missing UV layer"
            manifest[cat_key].append({k: v for k, v in info.items() if k != "fbx_abs"})
            bucket.append(info)
            print(f"PROP_VERIFIED {name}: size_cm={info['ue_size_cm']} min_cm={info['ue_min_cm']} slots={info['material_slots']}", flush=True)

    # Render 1200x1200 multi-angle PNG contact sheets
    dev_sheet = os.path.join(PREVIEW_DIR, "Props_Devices_sheet.png")
    gp_sheet = os.path.join(PREVIEW_DIR, "Props_Gameplay_sheet.png")
    render_contact_sheet(device_items, cols=4, rows=4, tile_w=300, tile_h=300, out_png=dev_sheet)
    render_contact_sheet(gameplay_items, cols=4, rows=5, tile_w=300, tile_h=240, out_png=gp_sheet)

    manifest["previews"] = [
        os.path.relpath(dev_sheet, PROJECT_ROOT),
        os.path.relpath(gp_sheet, PROJECT_ROOT),
    ]
    manifest_path = os.path.join(PROPS_ROOT, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"PROPS_DONE manifest={manifest_path}", flush=True)


if __name__ == "__main__":
    main()
