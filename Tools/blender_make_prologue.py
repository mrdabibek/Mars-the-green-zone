"""Build the prologue's Earth globe, continental tectonic crust plates, magma core, and ejecta (Blender, background mode)."""
from collections import deque
from math import atan2, asin, pi
from pathlib import Path

import bpy
from io_scene_fbx import export_fbx_bin
from mathutils import Vector, noise

ROOT = Path(__file__).resolve().parents[1] / "Assets" / "Intro"
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
materials = [bpy.data.materials.new("EarthSurface"), bpy.data.materials.new("ExposedMantle")]

bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1)
seed_obj = bpy.context.object
raw_seeds = [v.co.normalized() for v in seed_obj.data.vertices]
bpy.data.objects.remove(seed_obj, do_unlink=True)

# Asymmetric tectonic seed perturbation + weights so plates resemble irregular Earth continents/sub-plates.
seeds = []
seed_weights = [1.07, 0.91, 1.13, 0.87, 1.04, 0.94, 1.11, 0.89, 1.02, 0.92, 1.09, 0.95]
for idx, s in enumerate(raw_seeds):
    jitter = noise.noise_vector(s * 3.1 + Vector((idx * 1.37, 4.2, 7.9))) * 0.24
    seeds.append((s + jitter).normalized())

bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=6, radius=1)
source = bpy.context.object
points = [v.co.normalized() for v in source.data.vertices]
triangles = [tuple(p.vertices) for p in source.data.polygons]
bpy.data.objects.remove(source, do_unlink=True)


def warped_dir(p):
    """Multi-octave 3D noise warp for jagged-yet-smooth curved tectonic plate boundaries."""
    w1 = noise.noise_vector(p * 2.1 + Vector((1.7, 3.1, 5.3))) * 0.19
    w2 = noise.noise_vector(p * 5.4 + Vector((11.2, 7.4, 2.9))) * 0.072
    w3 = noise.noise_vector(p * 12.6 + Vector((4.6, 17.8, 9.1))) * 0.022
    return (p + w1 + w2 + w3).normalized()


def plate_score(w, plate_idx):
    target = w.dot(seeds[plate_idx]) * seed_weights[plate_idx]
    other = max(w.dot(seeds[j]) * seed_weights[j] for j in range(len(seeds)) if j != plate_idx)
    return target - other


def inner_radius(p):
    """Curved continental crust thickness (~12-17% radius) so plates form curved slabs over the magma core."""
    n1 = noise.noise(p * 3.8 + Vector((2.1, 4.7, 1.3)))
    n2 = noise.noise(p * 9.5 + Vector((7.9, 1.4, 6.2)))
    return 0.855 + 0.026 * n1 + 0.012 * n2


def tangent_basis(axis):
    up = Vector((0.0, 0.0, 1.0)) if abs(axis.z) < 0.92 else Vector((1.0, 0.0, 0.0))
    t = up.cross(axis).normalized()
    b = axis.cross(t).normalized()
    return t, b


def spherical_uvs(coords):
    us = [atan2(c.y, c.x) / (2.0 * pi) + 0.5 for c in coords]
    if max(us) - min(us) > 0.5:
        us = [u + 1.0 if u < 0.5 else u for u in us]
    return [(u, asin(max(-1.0, min(1.0, c.z))) / pi + 0.5) for u, c in zip(us, coords)]


warped_points = [warped_dir(p) for p in points]


def build_clipped_plate(plate_idx):
    """Clip the sphere mesh cleanly along the exact warped Voronoi fault line d_i(p) = 0."""
    scores = []
    for w in warped_points:
        s = plate_score(w, plate_idx)
        scores.append(1e-7 if abs(s) < 1e-7 else s)

    verts = list(points)
    cut_cache = {}

    def get_cut(u, v):
        key = (u, v) if u < v else (v, u)
        if key in cut_cache:
            return cut_cache[key]
        u_in, v_out = (u, v) if scores[u] > 0.0 else (v, u)
        lo, hi = 0.0, 1.0
        for _ in range(5):
            mid_t = 0.5 * (lo + hi)
            mid_p = points[u_in].lerp(points[v_out], mid_t).normalized()
            if plate_score(warped_dir(mid_p), plate_idx) > 0.0:
                lo = mid_t
            else:
                hi = mid_t
        t = min(max(0.5 * (lo + hi), 0.08), 0.92)
        idx = len(verts)
        verts.append(points[u_in].lerp(points[v_out], t).normalized())
        cut_cache[key] = idx
        return idx

    faces = []
    for a, b, c in triangles:
        ia, ib, ic = scores[a] > 0.0, scores[b] > 0.0, scores[c] > 0.0
        cnt = int(ia) + int(ib) + int(ic)
        if cnt == 0:
            continue
        if cnt == 3:
            faces.append((a, b, c))
            continue
        if cnt == 1:
            if ib:
                a, b, c = b, c, a
            elif ic:
                a, b, c = c, a, b
            faces.append((a, get_cut(a, b), get_cut(a, c)))
        else:
            if not ia:
                a, b, c = b, c, a
            elif not ib:
                a, b, c = c, a, b
            bc = get_cut(b, c)
            ac = get_cut(a, c)
            faces.append((a, b, bc))
            faces.append((a, bc, ac))

    # Keep only the largest connected component so no stray noise slivers remain.
    edge_to_tris = {}
    for fi, tri in enumerate(faces):
        for u, v in zip(tri, tri[1:] + tri[:1]):
            edge_to_tris.setdefault((u, v) if u < v else (v, u), []).append(fi)
    visited = [False] * len(faces)
    best_comp = []
    for start in range(len(faces)):
        if visited[start]:
            continue
        comp = []
        queue = deque([start])
        visited[start] = True
        while queue:
            cur = queue.popleft()
            comp.append(cur)
            tri = faces[cur]
            for u, v in zip(tri, tri[1:] + tri[:1]):
                for nb in edge_to_tris[(u, v) if u < v else (v, u)]:
                    if not visited[nb]:
                        visited[nb] = True
                        queue.append(nb)
        if len(comp) > len(best_comp):
            best_comp = comp
    faces = [faces[i] for i in best_comp]

    used = sorted({v for tri in faces for v in tri})
    remap = {v: i for i, v in enumerate(used)}
    verts = [verts[v] for v in used]
    faces = [tuple(remap[v] for v in tri) for tri in faces]
    return verts, faces


def extract_boundary_loops(faces):
    """Extract ordered closed CCW boundary vertex loops from outer manifold triangles."""
    directed = set()
    for tri in faces:
        for a, b in zip(tri, tri[1:] + tri[:1]):
            directed.add((a, b))
    next_map = {}
    for a, b in directed:
        if (b, a) not in directed:
            next_map.setdefault(a, []).append(b)
    loops = []
    while next_map:
        start = next(iter(next_map))
        loop = []
        cur = start
        while cur in next_map:
            nxt_list = next_map[cur]
            nxt = nxt_list.pop()
            if not nxt_list:
                del next_map[cur]
            loop.append(cur)
            cur = nxt
            if cur == start:
                break
        if len(loop) >= 3:
            loops.append(loop)
    return loops


def export_mesh(name, verts, faces, surface_count, wall_uvs=None, cap_basis=None, all_mantle=False):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(materials[0])
    mesh.materials.append(materials[1])
    mesh.validate()
    mesh.update()

    uv = mesh.uv_layers.new(name="Globe")
    for p in mesh.polygons:
        p.use_smooth = True
        if not all_mantle and p.index < surface_count:
            p.material_index = 0
            coords = [verts[v].normalized() for v in p.vertices]
            for loop, uvp in zip(p.loop_indices, spherical_uvs(coords)):
                uv.data[loop].uv = uvp
        else:
            p.material_index = 1 if not all_mantle else 0
            if wall_uvs is not None and p.index in wall_uvs:
                face_uv_map = wall_uvs[p.index]
                for loop, vi in zip(p.loop_indices, p.vertices):
                    uv.data[loop].uv = face_uv_map[vi]
            elif cap_basis is not None:
                t_ax, b_ax = cap_basis
                for loop, vi in zip(p.loop_indices, p.vertices):
                    vn = verts[vi].normalized()
                    uv.data[loop].uv = (0.5 + 0.5 * vn.dot(t_ax), 0.5 + 0.5 * vn.dot(b_ax))
            else:
                coords = [verts[v].normalized() for v in p.vertices]
                for loop, uvp in zip(p.loop_indices, spherical_uvs(coords)):
                    uv.data[loop].uv = uvp

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    reporter = type("Reporter", (), {"report": lambda self, kinds, message: print(message)})()
    export_fbx_bin.save(
        reporter,
        bpy.context,
        filepath=str(ROOT / (name + ".fbx")),
        use_selection=True,
        axis_forward="-Y",
        axis_up="Z",
        add_leaf_bones=False,
        mesh_smooth_type="FACE",
        use_triangles=True,
    )
    bpy.data.objects.remove(obj, do_unlink=True)
    print(f"PROLOGUE {name} triangles={len(faces)}")


def export_plate(name, plate_idx):
    verts, surface_faces = build_clipped_plate(plate_idx)
    surface_count = len(surface_faces)
    loops = extract_boundary_loops(surface_faces)

    # Single gentle smoothing pass keeps jagged tectonic fractures crisp while eliminating stair-step artifacts.
    for loop in loops:
        m = len(loop)
        updated = [
            (verts[loop[(k - 1) % m]] * 0.22 + verts[loop[k]] * 0.56 + verts[loop[(k + 1) % m]] * 0.22).normalized()
            for k in range(m)
        ]
        for k, pos in zip(loop, updated):
            verts[k] = pos

    # Beveled jagged lithosphere rim + curved mantle wall (depth ~14% of planet radius) with non-degenerate UVs.
    ring_profile = [
        (0.00, 0.004, 0.00),
        (0.08, -0.003, 0.08),
        (0.32, 0.004, 0.34),
        (0.60, 0.008, 0.62),
        (0.84, 0.011, 0.85),
        (1.00, 0.015, 1.00),
    ]

    faces = list(surface_faces)
    wall_uvs = {}
    boundary_to_inner_ring = {}

    for loop in loops:
        m = len(loop)
        base_dirs = [verts[vi].normalized() for vi in loop]
        inwards = []
        for k in range(m):
            tang = (base_dirs[(k + 1) % m] - base_dirs[(k - 1) % m]).normalized()
            nrm = base_dirs[k]
            inwards.append(nrm.cross(tang).normalized())

        for k, vi in enumerate(loop):
            verts[vi] = (base_dirs[k] + inwards[k] * ring_profile[0][1]).normalized()

        cum_arc = [0.0]
        for k in range(m):
            seg = (base_dirs[(k + 1) % m] - base_dirs[k]).length
            cum_arc.append(cum_arc[-1] + seg)
        total_arc = max(cum_arc[-1], 1e-6)

        rings = []
        for r_idx, (r_blend, inset, _) in enumerate(ring_profile):
            ring_verts = []
            for k in range(m):
                p0 = base_dirs[k]
                r_in = inner_radius(p0)
                r_val = 1.0 + (r_in - 1.0) * r_blend
                rock_jitter = 0.0
                if 1 <= r_idx < len(ring_profile) - 1:
                    rock_jitter = 0.012 * noise.noise(p0 * 16.0 + Vector((r_idx * 3.7, 1.9, 5.1)))
                pos_dir = (p0 + inwards[k] * (inset + rock_jitter)).normalized()
                ring_verts.append(len(verts))
                verts.append(pos_dir * r_val)
            rings.append(ring_verts)

        for k, vi in enumerate(loop):
            boundary_to_inner_ring[vi] = rings[-1][k]

        for r_idx in range(len(ring_profile) - 1):
            v0 = ring_profile[r_idx][2]
            v1 = ring_profile[r_idx + 1][2]
            for k in range(m):
                k2 = (k + 1) % m
                u0 = cum_arc[k] / total_arc
                u1 = cum_arc[k + 1] / total_arc
                a = rings[r_idx][k]
                b = rings[r_idx][k2]
                a_in = rings[r_idx + 1][k]
                b_in = rings[r_idx + 1][k2]

                f1 = len(faces)
                faces.append((b, a, a_in))
                wall_uvs[f1] = {b: (u1, v0), a: (u0, v0), a_in: (u0, v1)}

                f2 = len(faces)
                faces.append((b, a_in, b_in))
                wall_uvs[f2] = {b: (u1, v0), a_in: (u0, v1), b_in: (u1, v1)}

    inner_map = dict(boundary_to_inner_ring)
    outer_vert_count = max((max(tri) for tri in surface_faces), default=-1) + 1
    for vi in range(outer_vert_count):
        if vi not in inner_map:
            p0 = verts[vi].normalized()
            inner_map[vi] = len(verts)
            verts.append(p0 * inner_radius(p0))

    for tri in surface_faces:
        faces.append((inner_map[tri[2]], inner_map[tri[1]], inner_map[tri[0]]))

    export_mesh(
        name,
        verts,
        faces,
        surface_count,
        wall_uvs=wall_uvs,
        cap_basis=tangent_basis(seeds[plate_idx]),
    )


def export_core():
    """Export incandescent planetary mantle core inside the curved continental plates."""
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=1)
    core_obj = bpy.context.object
    core_verts = []
    for v in core_obj.data.vertices:
        d = v.co.normalized()
        swell = 0.825 + 0.018 * noise.noise(d * 4.5 + Vector((3.2, 1.1, 6.7)))
        core_verts.append(d * swell)
    core_faces = [tuple(p.vertices) for p in core_obj.data.polygons]
    bpy.data.objects.remove(core_obj, do_unlink=True)
    export_mesh("SM_Prologue_Core", core_verts, core_faces, 0, all_mantle=True)


def export_ejecta(count=6):
    """Export angular crustal asteroid ejecta fragments for tumbling 3D planetary breakup debris."""
    for idx in range(count):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1)
        obj = bpy.context.object
        axis_scale = Vector((
            1.15 - 0.12 * (idx % 3),
            0.82 + 0.15 * ((idx + 1) % 3),
            0.55 + 0.14 * (idx % 2),
        ))
        offset = Vector((idx * 5.7, idx * 9.3, idx * 3.1))
        e_verts = []
        for v in obj.data.vertices:
            d = v.co.normalized()
            crag = 0.72 + 0.38 * abs(noise.noise(d * 2.6 + offset))
            pos = Vector((d.x * axis_scale.x, d.y * axis_scale.y, d.z * axis_scale.z)) * crag * 0.14
            e_verts.append(pos)
        e_faces = [tuple(p.vertices) for p in obj.data.polygons]
        bpy.data.objects.remove(obj, do_unlink=True)
        export_mesh(f"SM_Prologue_Ejecta_{idx:02}", e_verts, e_faces, 0, all_mantle=True)


export_mesh("SM_Prologue_Earth", list(points), triangles, len(triangles))
for i in range(len(seeds)):
    export_plate(f"SM_Prologue_Crust_{i:02}", i)
export_core()
export_ejecta(6)
