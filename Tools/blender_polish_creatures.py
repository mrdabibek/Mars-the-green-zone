"""Production Blender pipeline for Mars: Last Green creatures.

Generates UE5-ready Skeletal Mesh FBXs, 30fps frame-0-aligned Animation FBXs,
co-located basecolor + normal textures, roundtrip verification, and multi-pose
preview contact sheets under Assets/Creatures/Production/.

Usage:
    blender -b -P Tools/blender_polish_creatures.py
"""
import importlib
import json
import math
import os
import shutil

import bpy
import bpy_extras.io_utils as io_utils
import io_scene_fbx
from mathutils import Euler, Matrix, Quaternion, Vector

# Process-local Blender 5.0 io_scene_fbx orientation_helper fix
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

ROOT = "/home/dabi/Documents/Mars Last Green"
PROD_DIR = os.path.join(ROOT, "Assets/Creatures/Production")
SRC_DIR = os.path.join(PROD_DIR, "_source_extracted")
PREVIEW_DIR = os.path.join(PROD_DIR, "Previews")


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for col in (bpy.data.actions, bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for item in list(col):
            col.remove(item)


def evaluated_z_bounds(arm, mesh):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(deps)
    me = ev.to_mesh()
    zs = [(mesh.matrix_world @ v.co).z for v in me.vertices]
    ev.to_mesh_clear()
    return min(zs), max(zs)


def evaluated_world_bounds(mesh):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(deps)
    me = ev.to_mesh()
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for v in me.vertices:
        w = mesh.matrix_world @ v.co
        for i in range(3):
            mn[i] = min(mn[i], w[i])
            mx[i] = max(mx[i], w[i])
    ev.to_mesh_clear()
    return mn, mx


def get_bone_rest_rot(arm, bone_name):
    return (arm.matrix_world.to_3x3() @ arm.data.bones[bone_name].matrix_local.to_3x3()).to_quaternion()


def world_rot_to_local(arm, bone_name, world_quat):
    r_rest = get_bone_rest_rot(arm, bone_name)
    return r_rest.inverted() @ world_quat @ r_rest


def world_vec_to_local(arm, bone_name, world_vec):
    r_rest = get_bone_rest_rot(arm, bone_name)
    return r_rest.inverted() @ world_vec


def world_euler_quat(rx=0.0, ry=0.0, rz=0.0):
    return Euler((rx, ry, rz), "XYZ").to_quaternion()


def apply_world_rot(arm, pbone, rx=0.0, ry=0.0, rz=0.0, base_quat=None):
    q_world = world_euler_quat(rx, ry, rz)
    q_local = world_rot_to_local(arm, pbone.name, q_world)
    pbone.rotation_mode = "QUATERNION"
    pbone.rotation_quaternion = (base_quat @ q_local) if base_quat else q_local


def set_root_world_offset(arm, root_name, world_delta, base_loc=None):
    p = arm.pose.bones[root_name]
    local_delta = world_vec_to_local(arm, root_name, world_delta)
    p.location = (base_loc + local_delta) if base_loc else local_delta


def reset_pose(arm):
    for p in arm.pose.bones:
        p.rotation_mode = "QUATERNION"
        p.location = Vector((0.0, 0.0, 0.0))
        p.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
        p.scale = Vector((1.0, 1.0, 1.0))


def ground_clamp_frame(arm, mesh, root_name, min_clearance=0.0):
    bpy.context.view_layer.update()
    mn_z, _ = evaluated_z_bounds(arm, mesh)
    if mn_z < min_clearance:
        delta_z = min_clearance - mn_z
        p = arm.pose.bones[root_name]
        p.location += world_vec_to_local(arm, root_name, Vector((0.0, 0.0, delta_z)))
        bpy.context.view_layer.update()


def key_all_bones(arm, frame):
    for p in arm.pose.bones:
        p.keyframe_insert(data_path="location", frame=frame, group=p.name)
        p.keyframe_insert(data_path="rotation_quaternion", frame=frame, group=p.name)
        p.keyframe_insert(data_path="scale", frame=frame, group=p.name)


def build_action_from_fn(arm, mesh, root_name, name, frame_count, pose_fn, ground_clamp=True, loop=False):
    """Build a 30fps action spanning frames [0 .. frame_count] inclusive."""
    arm.animation_data_clear()
    arm.animation_data_create()
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    arm.animation_data.action = act

    scene = bpy.context.scene
    scene.render.fps = 30
    scene.frame_start = 0
    scene.frame_end = frame_count

    for f in range(frame_count + 1):
        t = f / float(frame_count) if frame_count > 0 else 0.0
        # For exact loops, evaluate frame_count identically to t=0.0
        if loop and f == frame_count:
            t = 0.0
        scene.frame_set(f)
        reset_pose(arm)
        pose_fn(arm, f, t)
        if ground_clamp:
            ground_clamp_frame(arm, mesh, root_name, 0.0)
        key_all_bones(arm, f)

    return act


def align_and_scale_tripo(fbx_path, z_rot_deg, target_height_m):
    """Import Tripo FBX, align to +X forward, Z up, target height, ground Z=0, identity transforms.

    Returns (arm, mesh, walk_poses_aligned) where walk_poses_aligned is a list of
    61 pose dicts (frames 0..60) extracted with exact similarity transform.
    """
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=fbx_path)
    scene = bpy.context.scene
    scene.render.fps = 30
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    mesh = next(o for o in scene.objects if o.type == "MESH")
    walk_act = arm.animation_data.action

    # Measure rest height
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    mn, mx = evaluated_world_bounds(mesh)
    rest_h = max(mx.z - mn.z, 1e-4)
    sc = target_height_m / rest_h

    # Sample source walk poses before modifying rig
    w_start, w_end = int(round(walk_act.frame_range[0])), int(round(walk_act.frame_range[1]))
    arm.data.pose_position = "POSE"
    arm.animation_data.action = walk_act
    raw_walk = []
    for f in range(w_start, w_end + 1):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        raw_walk.append({
            p.name: (p.location.copy(), p.rotation_quaternion.copy(), p.scale.copy())
            for p in arm.pose.bones
        })

    # Compute alignment matrix: rotate Z so creature faces +X, scale uniformly, ground Z=0, center XY
    m_rot_scale = Matrix.Scale(sc, 4) @ Matrix.Rotation(math.radians(z_rot_deg), 4, "Z")
    # Compute XY center and min Z of rest mesh after m_rot_scale
    mesh_to_tmp = m_rot_scale @ mesh.matrix_world
    xs = []
    ys = []
    zs = []
    for v in mesh.data.vertices:
        p = mesh_to_tmp @ v.co
        xs.append(p.x)
        ys.append(p.y)
        zs.append(p.z)
    shift = Vector((-0.5 * (min(xs) + max(xs)), -0.5 * (min(ys) + max(ys)), -min(zs)))
    m_align = Matrix.Translation(shift) @ m_rot_scale

    # Transform mesh vertices directly & clear transforms
    arm.animation_data.action = None
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    mesh_xform = m_align @ mesh.matrix_world
    mesh.parent = None
    mesh.matrix_world = Matrix.Identity(4)
    for v in mesh.data.vertices:
        v.co = mesh_xform @ v.co
    mesh.data.update()

    # Transform armature edit bones directly & clear transforms
    arm_xform = m_align @ arm.matrix_world
    arm.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bone_mats = {eb.name: (arm_xform @ eb.matrix, eb.length * sc) for eb in arm.data.edit_bones}
    for eb in arm.data.edit_bones:
        mat, length = bone_mats[eb.name]
        rot3 = mat.to_3x3().normalized()
        m4 = rot3.to_4x4()
        m4.translation = mat.translation
        eb.head = m4.translation
        eb.tail = m4.translation + rot3 @ Vector((0.0, length, 0.0))
        eb.matrix = m4
    bpy.ops.object.mode_set(mode="OBJECT")

    mesh.parent = arm
    arm.data.pose_position = "POSE"
    bpy.data.actions.remove(walk_act)

    # Rename bones to UE5-safe names (strip tripo:: and never start with digits)
    def clean_bone_name(bname):
        n = bname.replace("tripo::", "")
        n = n.replace("0_Right_Limb_", "Front_Right_Limb_")
        n = n.replace("0_Left_Limb_", "Front_Left_Limb_")
        n = n.replace("1_Right_Limb_", "Rear_Right_Limb_")
        n = n.replace("1_Left_Limb_", "Rear_Left_Limb_")
        explicit = {
            "bone_9": "Front_Right_Scapula",
            "bone_29": "Tail_0",
            "bone_30": "Tail_1",
            "bone_31": "Tail_2",
            "bone_14": "Tail_0",
            "bone_15": "Tail_1",
            "bone_16": "Tail_2",
        }
        return explicit.get(n, n)

    rename_map = {b.name: clean_bone_name(b.name) for b in arm.data.bones}
    for old_n, new_n in rename_map.items():
        if old_n != new_n:
            arm.data.bones[old_n].name = new_n
            if old_n in mesh.vertex_groups:
                mesh.vertex_groups[old_n].name = new_n

    # Convert sampled walk poses to aligned rig & resample cleanly to 0..60 (60 frames = 2.0s loop)
    # Note: raw_walk[-1] is the loop close frame matching raw_walk[0]
    n_src = len(raw_walk) - 1
    aligned_walk = []
    for i in range(61):
        u = (i / 60.0) * n_src
        i0 = int(math.floor(u)) % n_src
        i1 = (i0 + 1) % n_src
        alpha = u - math.floor(u)
        pose_dict = {}
        for old_bn in raw_walk[0]:
            new_bn = rename_map[old_bn]
            l0, q0, s0 = raw_walk[i0][old_bn]
            l1, q1, s1 = raw_walk[i1][old_bn]
            if q0.dot(q1) < 0:
                q1 = -q1
            loc = l0.lerp(l1, alpha) * sc
            rot = q0.slerp(q1, alpha)
            scl = s0.lerp(s1, alpha)
            pose_dict[new_bn] = (loc, rot, scl)
        aligned_walk.append(pose_dict)

    # Smooth any tiny seam delta over frames 57..60 so frame 60 == frame 0
    for bname in aligned_walk[0]:
        l0, q0, s0 = aligned_walk[0][bname]
        aligned_walk[60][bname] = (l0.copy(), q0.copy(), s0.copy())

    return arm, mesh, aligned_walk


def build_raider_actions(arm, mesh, walk_poses):
    root = "Root"
    actions = {}

    # 1. Idle (0..60 = 2.0s loop)
    def idle_fn(a, f, t):
        ph = 2.0 * math.pi * t
        breath = math.sin(ph)
        scan = math.sin(ph * 0.5)
        apply_world_rot(a, a.pose.bones["Spine_1"], ry=0.025 * breath)
        apply_world_rot(a, a.pose.bones["Spine_2"], ry=-0.02 * breath)
        apply_world_rot(a, a.pose.bones["Head_0"], ry=-0.04 * breath, rz=0.14 * scan)
        apply_world_rot(a, a.pose.bones["Head_1"], ry=0.02 * breath, rz=0.10 * scan)
        apply_world_rot(a, a.pose.bones["Tail_0"], rz=0.16 * math.sin(ph + 0.5), ry=-0.05 * breath)
        apply_world_rot(a, a.pose.bones["Tail_1"], rz=0.18 * math.sin(ph))
        apply_world_rot(a, a.pose.bones["Tail_2"], rz=0.14 * math.sin(ph - 0.5))
        set_root_world_offset(a, root, Vector((0, 0, -0.006 * (1.0 - math.cos(ph)))))

    actions["Idle"] = build_action_from_fn(arm, mesh, root, "AS_Raider_Idle", 60, idle_fn, loop=True)

    # 2. Walk (0..60 = 2.0s loop from Tripo walk, ground-clamped)
    def walk_fn(a, f, t):
        pose_d = walk_poses[f]
        for bn, (loc, rot, scl) in pose_d.items():
            p = a.pose.bones[bn]
            p.rotation_mode = "QUATERNION"
            p.location = loc.copy()
            p.rotation_quaternion = rot.copy()
            p.scale = scl.copy()

    actions["Walk"] = build_action_from_fn(arm, mesh, root, "AS_Raider_Walk", 60, walk_fn, loop=True)

    # 3. Run (0..21 = 0.70s energetic bounding quadruped gallop loop!)
    def run_fn(a, f, t):
        ph = 2.0 * math.pi * t
        # Front pair leads, hind pair opposite phase -> real bounding gallop
        f_l = math.sin(ph)
        f_r = math.sin(ph - 0.55)
        h_l = math.sin(ph + math.pi)
        h_r = math.sin(ph + math.pi - 0.55)
        spine_flex = math.cos(ph)

        set_root_world_offset(a, root, Vector((0, 0, 0.045 * max(0.0, math.sin(ph)) - 0.025)))
        apply_world_rot(a, a.pose.bones[root], ry=0.12 * spine_flex)
        apply_world_rot(a, a.pose.bones["Spine_0"], ry=0.18 * spine_flex)
        apply_world_rot(a, a.pose.bones["Spine_1"], ry=0.16 * spine_flex)
        apply_world_rot(a, a.pose.bones["Spine_2"], ry=-0.10 * spine_flex)
        apply_world_rot(a, a.pose.bones["Head_0"], ry=-0.15 * spine_flex + 0.08)
        apply_world_rot(a, a.pose.bones["Head_1"], ry=-0.08 * spine_flex)

        # Front limbs reach forward (negative ry) and tuck knees
        apply_world_rot(a, a.pose.bones["Front_Left_Limb_0"], ry=-0.65 * f_l - 0.15)
        apply_world_rot(a, a.pose.bones["Front_Left_Limb_1"], ry=0.55 * max(0.0, f_l))
        apply_world_rot(a, a.pose.bones["Front_Right_Limb_0"], ry=-0.65 * f_r - 0.15)
        apply_world_rot(a, a.pose.bones["Front_Right_Limb_1"], ry=0.55 * max(0.0, f_r))

        # Hind limbs drive powerfully backward (positive ry) and tuck forward
        apply_world_rot(a, a.pose.bones["Rear_Left_Limb_0"], ry=-0.70 * h_l + 0.10)
        apply_world_rot(a, a.pose.bones["Rear_Left_Limb_1"], ry=-0.45 * max(0.0, h_l))
        apply_world_rot(a, a.pose.bones["Rear_Right_Limb_0"], ry=-0.70 * h_r + 0.10)
        apply_world_rot(a, a.pose.bones["Rear_Right_Limb_1"], ry=-0.45 * max(0.0, h_r))

        # Tail whip counterbalance
        apply_world_rot(a, a.pose.bones["Tail_0"], ry=0.22 * spine_flex)
        apply_world_rot(a, a.pose.bones["Tail_1"], ry=0.20 * math.cos(ph - 0.5))
        apply_world_rot(a, a.pose.bones["Tail_2"], ry=0.18 * math.cos(ph - 1.0))

    actions["Run"] = build_action_from_fn(arm, mesh, root, "AS_Raider_Run", 21, run_fn, loop=True)

    # 4. Telegraph / Strike (0..21 = 0.70s matching TelegraphSeconds=0.7f)
    def telegraph_fn(a, f, t):
        if t < 0.55:
            u = math.sin((t / 0.55) * (math.pi * 0.5))  # coil back 0..0.385s
            coil = u
            lunge = 0.0
        elif t < 0.80:
            u = (t - 0.55) / 0.25  # fast strike 0.385..0.56s
            coil = 1.0 - 1.4 * u
            lunge = math.sin(u * math.pi * 0.5)
        else:
            u = (t - 0.80) / 0.20  # recover 0.56..0.70s
            coil = -0.4 * (1.0 - u)
            lunge = 1.0 - u

        set_root_world_offset(a, root, Vector((-0.09 * coil + 0.16 * lunge, 0.0, -0.05 * coil + 0.04 * lunge)))
        apply_world_rot(a, a.pose.bones[root], ry=-0.28 * coil + 0.15 * lunge)
        apply_world_rot(a, a.pose.bones["Spine_2"], ry=-0.22 * coil + 0.18 * lunge)
        apply_world_rot(a, a.pose.bones["Head_0"], ry=-0.30 * coil + 0.20 * lunge, rz=-0.12 * coil)
        apply_world_rot(a, a.pose.bones["Front_Right_Limb_0"], ry=-0.95 * coil - 0.65 * lunge, rx=-0.35 * coil)
        apply_world_rot(a, a.pose.bones["Front_Right_Limb_1"], ry=-0.75 * coil + 0.35 * lunge)
        apply_world_rot(a, a.pose.bones["Front_Left_Limb_0"], ry=-0.55 * coil - 0.35 * lunge, rx=0.25 * coil)
        apply_world_rot(a, a.pose.bones["Tail_0"], ry=0.25 * coil)

    actions["Telegraph"] = build_action_from_fn(arm, mesh, root, "AS_Raider_Telegraph", 21, telegraph_fn, loop=False)

    # 5. Hit / Stagger (0..14 = 0.467s covering StaggerSeconds=0.45f)
    def hit_fn(a, f, t):
        s = math.sin(t * math.pi) ** 0.7
        set_root_world_offset(a, root, Vector((-0.07 * s, 0.03 * s, 0.0)))
        apply_world_rot(a, a.pose.bones[root], rx=0.18 * s, ry=-0.20 * s, rz=0.15 * s)
        apply_world_rot(a, a.pose.bones["Spine_1"], ry=-0.22 * s, rz=-0.15 * s)
        apply_world_rot(a, a.pose.bones["Head_0"], ry=-0.35 * s, rz=0.30 * s)
        apply_world_rot(a, a.pose.bones["Front_Right_Limb_0"], ry=-0.35 * s)
        apply_world_rot(a, a.pose.bones["Front_Left_Limb_0"], ry=0.20 * s)

    actions["Hit"] = build_action_from_fn(arm, mesh, root, "AS_Raider_Hit", 14, hit_fn, loop=False)

    # 6. Death (0..45 = 1.50s grounded non-gory collapse)
    def death_fn(a, f, t):
        u = min(1.0, t / 0.78)
        e = 1.0 - (1.0 - u) ** 2.2
        # Roll onto side and tuck limbs inward/forward so the torso rests flat on Z=0 without propping
        apply_world_rot(a, a.pose.bones[root], rx=1.42 * e, ry=0.14 * e, rz=0.22 * e)
        set_root_world_offset(a, root, Vector((-0.05 * e, 0.0, -0.22 * e)))
        apply_world_rot(a, a.pose.bones["Spine_1"], ry=0.22 * e)
        apply_world_rot(a, a.pose.bones["Head_0"], ry=0.30 * e, rx=0.20 * e)
        apply_world_rot(a, a.pose.bones["Front_Right_Limb_0"], ry=-0.75 * e, rx=0.55 * e)
        apply_world_rot(a, a.pose.bones["Front_Right_Limb_1"], ry=0.65 * e)
        apply_world_rot(a, a.pose.bones["Front_Left_Limb_0"], ry=-0.55 * e, rx=0.85 * e)
        apply_world_rot(a, a.pose.bones["Front_Left_Limb_1"], ry=0.55 * e)
        apply_world_rot(a, a.pose.bones["Rear_Right_Limb_0"], ry=-0.65 * e, rx=0.50 * e)
        apply_world_rot(a, a.pose.bones["Rear_Right_Limb_1"], ry=0.55 * e)
        apply_world_rot(a, a.pose.bones["Rear_Left_Limb_0"], ry=-0.50 * e, rx=0.80 * e)
        apply_world_rot(a, a.pose.bones["Rear_Left_Limb_1"], ry=0.50 * e)
        apply_world_rot(a, a.pose.bones["Tail_0"], rx=0.25 * e, ry=0.18 * e)

    actions["Death"] = build_action_from_fn(arm, mesh, root, "AS_Raider_Death", 45, death_fn, loop=False)
    return actions


def build_breaker_actions(arm, mesh, walk_poses):
    root = "Root"
    actions = {}

    # 1. Idle (0..75 = 2.5s heavy armored breathing loop)
    def idle_fn(a, f, t):
        ph = 2.0 * math.pi * t
        breath = math.sin(ph)
        apply_world_rot(a, a.pose.bones["Spine_1"], ry=0.03 * breath)
        apply_world_rot(a, a.pose.bones["Spine_2"], ry=-0.025 * breath)
        apply_world_rot(a, a.pose.bones["Head_0"], ry=-0.04 * breath, rz=0.10 * math.sin(ph * 0.5))
        apply_world_rot(a, a.pose.bones["Tail_0"], rz=0.10 * math.sin(ph + 0.4))
        apply_world_rot(a, a.pose.bones["Tail_1"], rz=0.12 * math.sin(ph))
        set_root_world_offset(a, root, Vector((0, 0, -0.015 * (1.0 - math.cos(ph)))))

    actions["Idle"] = build_action_from_fn(arm, mesh, root, "AS_Breaker_Idle", 75, idle_fn, loop=True)

    # 2. Walk (0..60 = 2.0s loop from Tripo walk, ground-clamped)
    def walk_fn(a, f, t):
        pose_d = walk_poses[f]
        for bn, (loc, rot, scl) in pose_d.items():
            p = a.pose.bones[bn]
            p.rotation_mode = "QUATERNION"
            p.location = loc.copy()
            p.rotation_quaternion = rot.copy()
            p.scale = scl.copy()

    actions["Walk"] = build_action_from_fn(arm, mesh, root, "AS_Breaker_Walk", 60, walk_fn, loop=True)

    # 3. Run (0..30 = 1.0s heavy battering-ram stampede charge)
    def run_fn(a, f, t):
        ph = 2.0 * math.pi * t
        fl = math.sin(ph)
        fr = math.sin(ph - 0.5)
        hl = math.sin(ph + math.pi)
        hr = math.sin(ph + math.pi - 0.5)
        heave = math.cos(ph)

        set_root_world_offset(a, root, Vector((0, 0, 0.06 * abs(math.sin(ph)) - 0.04)))
        apply_world_rot(a, a.pose.bones[root], ry=0.08 * heave, rx=0.06 * math.sin(ph))
        apply_world_rot(a, a.pose.bones["Spine_1"], ry=0.10 * heave)
        apply_world_rot(a, a.pose.bones["Spine_2"], ry=0.14)  # armored hunch forward
        apply_world_rot(a, a.pose.bones["Head_0"], ry=0.22)   # ramming head low
        apply_world_rot(a, a.pose.bones["Front_Left_Limb_0"], ry=-0.45 * fl)
        apply_world_rot(a, a.pose.bones["Front_Left_Limb_1"], ry=0.35 * max(0.0, fl))
        apply_world_rot(a, a.pose.bones["Front_Right_Limb_0"], ry=-0.45 * fr)
        apply_world_rot(a, a.pose.bones["Front_Right_Limb_1"], ry=0.35 * max(0.0, fr))
        apply_world_rot(a, a.pose.bones["Rear_Left_Limb_0"], ry=-0.48 * hl)
        apply_world_rot(a, a.pose.bones["Rear_Right_Limb_0"], ry=-0.48 * hr)
        apply_world_rot(a, a.pose.bones["Tail_0"], ry=-0.10 * heave)

    actions["Run"] = build_action_from_fn(arm, mesh, root, "AS_Breaker_Run", 30, run_fn, loop=True)

    # 4. Telegraph / Heavy Overhead Slam (0..54 = 1.80s matching TelegraphSeconds=1.8f)
    def telegraph_fn(a, f, t):
        if t < 0.65:
            # Slow heavy rear-up exposing vulnerable belly (0..1.17s)
            u = math.sin((t / 0.65) * math.pi * 0.5)
            rear = u
            slam = 0.0
        elif t < 0.80:
            # Crushing downward slam (1.17..1.44s)
            u = (t - 0.65) / 0.15
            rear = 1.0 - 1.25 * (u ** 1.6)
            slam = math.sin(u * math.pi * 0.5)
        else:
            # Heavy impact settle & recovery (1.44..1.80s)
            u = (t - 0.80) / 0.20
            rear = -0.25 * (1.0 - u)
            slam = 1.0 - u

        set_root_world_offset(a, root, Vector((-0.18 * rear + 0.15 * slam, 0.0, 0.35 * rear - 0.12 * slam)))
        apply_world_rot(a, a.pose.bones[root], ry=-0.52 * rear + 0.14 * slam)
        apply_world_rot(a, a.pose.bones["Spine_1"], ry=-0.18 * rear + 0.10 * slam)
        apply_world_rot(a, a.pose.bones["Spine_2"], ry=-0.20 * rear + 0.15 * slam)
        apply_world_rot(a, a.pose.bones["Head_0"], ry=-0.28 * rear + 0.12 * slam)
        # Lift heavy forelimbs high overhead during rear, slam straight down on impact
        apply_world_rot(a, a.pose.bones["Front_Left_Limb_0"], ry=-0.60 * rear + 0.25 * slam, rx=0.25 * rear)
        apply_world_rot(a, a.pose.bones["Front_Right_Limb_0"], ry=-0.60 * rear + 0.25 * slam, rx=-0.25 * rear)
        # Brace hind legs against the ground as body rears
        apply_world_rot(a, a.pose.bones["Rear_Left_Limb_0"], ry=0.45 * rear)
        apply_world_rot(a, a.pose.bones["Rear_Right_Limb_0"], ry=0.45 * rear)

    actions["Telegraph"] = build_action_from_fn(arm, mesh, root, "AS_Breaker_Telegraph", 54, telegraph_fn, loop=False)

    # 5. Hit / Stagger (0..36 = 1.20s matching StaggerSeconds=1.2f)
    def hit_fn(a, f, t):
        # Sharp recoil peak around t=0.2, slow heavy recovery
        s = math.sin(min(1.0, t / 0.25) * math.pi * 0.5) * (1.0 - max(0.0, (t - 0.25) / 0.75)) ** 1.3
        shake = math.sin(t * math.pi * 4.0) * (1.0 - t)
        set_root_world_offset(a, root, Vector((-0.14 * s, 0.0, 0.05 * s)))
        apply_world_rot(a, a.pose.bones[root], ry=-0.26 * s, rx=0.14 * shake)
        apply_world_rot(a, a.pose.bones["Spine_1"], ry=-0.16 * s, rz=0.18 * shake)
        apply_world_rot(a, a.pose.bones["Head_0"], ry=-0.25 * s, rz=-0.35 * shake)
        apply_world_rot(a, a.pose.bones["Front_Left_Limb_0"], rx=0.25 * s, ry=-0.25 * s)
        apply_world_rot(a, a.pose.bones["Front_Right_Limb_0"], rx=-0.25 * s, ry=-0.25 * s)

    actions["Hit"] = build_action_from_fn(arm, mesh, root, "AS_Breaker_Hit", 36, hit_fn, loop=False)

    # 6. Death (0..45 = 1.50s heavy grounded collapse onto side/belly)
    def death_fn(a, f, t):
        u = min(1.0, t / 0.78)
        e = 1.0 - (1.0 - u) ** 2.0
        # Roll onto side and fold legs inward/forward so heavy armored body rests flat on Z=0
        apply_world_rot(a, a.pose.bones[root], rx=1.48 * e, ry=0.14 * e, rz=0.18 * e)
        set_root_world_offset(a, root, Vector((0.0, 0.0, -0.45 * e)))
        apply_world_rot(a, a.pose.bones["Spine_1"], ry=0.15 * e)
        apply_world_rot(a, a.pose.bones["Spine_2"], ry=0.20 * e)
        apply_world_rot(a, a.pose.bones["Head_0"], ry=0.22 * e, rx=0.18 * e)
        apply_world_rot(a, a.pose.bones["Front_Left_Limb_0"], rx=0.85 * e, ry=-0.85 * e)
        apply_world_rot(a, a.pose.bones["Front_Right_Limb_0"], rx=0.55 * e, ry=-0.90 * e)
        apply_world_rot(a, a.pose.bones["Rear_Left_Limb_0"], rx=0.80 * e, ry=-0.80 * e)
        apply_world_rot(a, a.pose.bones["Rear_Right_Limb_0"], rx=0.50 * e, ry=-0.85 * e)
        apply_world_rot(a, a.pose.bones["Tail_0"], rx=0.22 * e, ry=0.18 * e)

    actions["Death"] = build_action_from_fn(arm, mesh, root, "AS_Breaker_Death", 45, death_fn, loop=False)
    return actions


def pose_gunner_rifle_ready(arm, aim=0.0, recoil=0.0):
    """Blend Gunner upper body between low-ready carbine carry (aim=0) and shouldered aim (aim=1)."""
    # Right arm brings carbine across chest (aim=0) or straight forward to shoulder (aim=1)
    apply_world_rot(
        arm, arm.pose.bones["upperarm_r"],
        rx=0.10 * (1 - aim) + 0.05 * aim,
        ry=-0.55 * (1 - aim) - 1.25 * aim - 0.14 * recoil,
        rz=0.45 * (1 - aim) + 0.05 * aim,
    )
    apply_world_rot(
        arm, arm.pose.bones["lowerarm_r"],
        ry=-1.05 * (1 - aim) - 0.45 * aim - 0.10 * recoil,
        rz=0.55 * (1 - aim) + 0.05 * aim,
    )
    apply_world_rot(
        arm, arm.pose.bones["hand_r"],
        rx=0.25 * (1 - aim),
        ry=0.15 * (1 - aim) + 0.12 * aim,
        rz=0.25 * (1 - aim),
    )
    # Left arm supports foregrip across chest / under barrel
    apply_world_rot(
        arm, arm.pose.bones["upperarm_l"],
        rx=-0.12 * (1 - aim) - 0.25 * aim,
        ry=-0.65 * (1 - aim) - 1.15 * aim - 0.10 * recoil,
        rz=-0.55 * (1 - aim) - 0.40 * aim,
    )
    apply_world_rot(
        arm, arm.pose.bones["lowerarm_l"],
        ry=-1.00 * (1 - aim) - 0.55 * aim,
        rz=-0.50 * (1 - aim) - 0.25 * aim,
    )
    # Align weapon_r cleanly: across chest (-Y/+Y) in low-ready, dead-on +X when aimed!
    # In rest pose, weapon_r points +X while hanging at hand_r. When upperarm_r/lowerarm_r rotate
    # by (-0.55-1.05 = -1.60 rad around Y), weapon_r would point straight UP unless compensated!
    # Compute exact world rotation needed for weapon_r after parent rotations:
    bpy.context.view_layer.update()
    p_hand = arm.pose.bones["hand_r"]
    hand_world_rot = (arm.matrix_world.to_3x3() @ p_hand.matrix.to_3x3()).to_quaternion()
    wep_rest_rot = get_bone_rest_rot(arm, "weapon_r")
    # Desired weapon world orientation: +X forward when aim=1, yawed +38deg across chest & tilted -15deg down when aim=0
    desired_world_rot = world_euler_quat(
        rx=0.0,
        ry=0.28 * (1 - aim) - 0.10 * recoil,
        rz=0.68 * (1 - aim),
    ) @ wep_rest_rot
    # Since p_wep.matrix = hand_world * rel_rest * p_wep.matrix_basis,
    # Wait: p_wep.matrix_basis is relative to (p_hand.matrix @ p_hand.bone.matrix_local^-1 @ wep.bone.matrix_local)
    hand_rest_rot = get_bone_rest_rot(arm, "hand_r")
    parent_delta = hand_world_rot @ hand_rest_rot.inverted()
    needed_delta = desired_world_rot @ (parent_delta @ wep_rest_rot).inverted()
    p_wep = arm.pose.bones["weapon_r"]
    p_wep.rotation_mode = "QUATERNION"
    p_wep.rotation_quaternion = wep_rest_rot.inverted() @ needed_delta @ wep_rest_rot


def build_gunner_actions(arm, mesh):
    root = "pelvis"
    actions = {}

    # 1. Idle (0..60 = 2.0s tactical low-ready loop)
    def idle_fn(a, f, t):
        ph = 2.0 * math.pi * t
        breath = math.sin(ph)
        scan = math.sin(ph * 0.5)
        set_root_world_offset(a, root, Vector((0, 0, -0.025 + 0.008 * breath)))
        apply_world_rot(a, a.pose.bones["pelvis"], rz=-0.12)
        apply_world_rot(a, a.pose.bones["spine_01"], ry=0.06 + 0.02 * breath)
        apply_world_rot(a, a.pose.bones["spine_02"], ry=0.04 + 0.02 * breath, rz=0.10)
        apply_world_rot(a, a.pose.bones["head"], ry=-0.06 - 0.03 * breath, rz=0.18 * scan)
        # Athletic planted stance
        for sgn, s in [(1, "l"), (-1, "r")]:
            apply_world_rot(a, a.pose.bones[f"thigh_{s}"], ry=-0.16, rx=0.05 * sgn)
            apply_world_rot(a, a.pose.bones[f"calf_{s}"], ry=0.28)
            apply_world_rot(a, a.pose.bones[f"foot_{s}"], ry=-0.12, rx=-0.05 * sgn)
        pose_gunner_rifle_ready(a, aim=0.0)

    actions["Idle"] = build_action_from_fn(arm, mesh, root, "AS_Gunner_Idle", 60, idle_fn, loop=True)

    # 2. Walk (0..36 = 1.2s tactical stalk walk)
    def walk_fn(a, f, t):
        ph = 2.0 * math.pi * t
        sw_l = math.sin(ph)
        sw_r = -sw_l
        set_root_world_offset(a, root, Vector((0, 0, -0.04 + 0.02 * abs(math.cos(ph)))))
        apply_world_rot(a, a.pose.bones["pelvis"], rz=0.08 * sw_l)
        apply_world_rot(a, a.pose.bones["spine_01"], ry=0.10)
        apply_world_rot(a, a.pose.bones["spine_02"], rz=-0.12 * sw_l, ry=0.06)
        apply_world_rot(a, a.pose.bones["head"], ry=-0.12, rz=0.04 * sw_l)
        for sw, s in [(sw_l, "l"), (sw_r, "r")]:
            th = -0.38 * sw - 0.12
            kf = 0.55 * max(0.0, sw) + 0.18
            apply_world_rot(a, a.pose.bones[f"thigh_{s}"], ry=th)
            apply_world_rot(a, a.pose.bones[f"calf_{s}"], ry=kf)
            apply_world_rot(a, a.pose.bones[f"foot_{s}"], ry=-(th + kf) * 0.8)
        pose_gunner_rifle_ready(a, aim=0.15)

    actions["Walk"] = build_action_from_fn(arm, mesh, root, "AS_Gunner_Walk", 36, walk_fn, loop=True)

    # 3. Run (0..21 = 0.70s energetic forward-leaning sprint loop!)
    def run_fn(a, f, t):
        ph = 2.0 * math.pi * t
        sw_l = math.sin(ph)
        sw_r = -sw_l
        set_root_world_offset(a, root, Vector((0, 0, -0.09 + 0.045 * abs(math.sin(ph)))))
        apply_world_rot(a, a.pose.bones["pelvis"], ry=0.22, rz=0.14 * sw_l)
        apply_world_rot(a, a.pose.bones["spine_01"], ry=0.18)
        apply_world_rot(a, a.pose.bones["spine_02"], ry=0.14, rz=-0.20 * sw_l)
        apply_world_rot(a, a.pose.bones["head"], ry=-0.38, rz=0.06 * sw_l)
        for sw, s in [(sw_l, "l"), (sw_r, "r")]:
            th = -0.75 * sw - 0.20
            kf = 1.15 * max(0.0, sw) + 0.25
            apply_world_rot(a, a.pose.bones[f"thigh_{s}"], ry=th)
            apply_world_rot(a, a.pose.bones[f"calf_{s}"], ry=kf)
            apply_world_rot(a, a.pose.bones[f"foot_{s}"], ry=-(th + kf) * 0.7)
        pose_gunner_rifle_ready(a, aim=0.0)

    actions["Run"] = build_action_from_fn(arm, mesh, root, "AS_Gunner_Run", 21, run_fn, loop=True)

    # 4. Telegraph / Aimed Rifle Raise & Fire (0..27 = 0.90s matching TelegraphSeconds=0.9f)
    def telegraph_fn(a, f, t):
        if t < 0.30:
            aim = math.sin((t / 0.30) * math.pi * 0.5)
            recoil = 0.0
        elif t < 0.78:
            aim = 1.0
            recoil = 0.0
        elif t < 0.88:
            aim = 1.0
            recoil = math.sin(((t - 0.78) / 0.10) * math.pi)
        else:
            aim = 1.0 - (t - 0.88) / 0.12
            recoil = 0.0

        set_root_world_offset(a, root, Vector((-0.03 * aim, 0, -0.06 * aim)))
        apply_world_rot(a, a.pose.bones["pelvis"], rz=-0.22 * aim)
        apply_world_rot(a, a.pose.bones["spine_01"], ry=0.10 * aim - 0.08 * recoil)
        apply_world_rot(a, a.pose.bones["spine_02"], rz=0.20 * aim, ry=-0.06 * recoil)
        apply_world_rot(a, a.pose.bones["head"], ry=-0.06 * aim, rz=0.04 * aim)
        # Braced firing stance
        apply_world_rot(a, a.pose.bones["thigh_l"], ry=-0.32 * aim, rx=0.08 * aim)
        apply_world_rot(a, a.pose.bones["calf_l"], ry=0.45 * aim)
        apply_world_rot(a, a.pose.bones["foot_l"], ry=-0.13 * aim)
        apply_world_rot(a, a.pose.bones["thigh_r"], ry=0.18 * aim, rx=-0.08 * aim)
        apply_world_rot(a, a.pose.bones["calf_r"], ry=0.25 * aim)
        apply_world_rot(a, a.pose.bones["foot_r"], ry=-0.43 * aim)
        pose_gunner_rifle_ready(a, aim=aim, recoil=recoil)

    actions["Telegraph"] = build_action_from_fn(arm, mesh, root, "AS_Gunner_Telegraph", 27, telegraph_fn, loop=False)

    # 5. Cover Crouch Loop (0..60 = 2.00s matching Cover 2.0s)
    def cover_fn(a, f, t):
        ph = 2.0 * math.pi * t
        breath = math.sin(ph)
        peek = math.sin(ph * 0.5)
        set_root_world_offset(a, root, Vector((-0.05, 0, -0.44 + 0.015 * breath)))
        apply_world_rot(a, a.pose.bones["pelvis"], ry=0.15, rz=-0.15)
        apply_world_rot(a, a.pose.bones["spine_01"], ry=0.25 + 0.03 * breath)
        apply_world_rot(a, a.pose.bones["spine_02"], ry=0.18, rz=0.12)
        apply_world_rot(a, a.pose.bones["head"], ry=-0.38 - 0.04 * breath, rz=0.20 * peek)
        # Deep crouch legs planted
        apply_world_rot(a, a.pose.bones["thigh_l"], ry=-1.10, rx=0.12)
        apply_world_rot(a, a.pose.bones["calf_l"], ry=1.70)
        apply_world_rot(a, a.pose.bones["foot_l"], ry=-0.60, rx=-0.12)
        apply_world_rot(a, a.pose.bones["thigh_r"], ry=-0.95, rx=-0.12)
        apply_world_rot(a, a.pose.bones["calf_r"], ry=1.55)
        apply_world_rot(a, a.pose.bones["foot_r"], ry=-0.60, rx=0.12)
        pose_gunner_rifle_ready(a, aim=0.25)

    actions["Cover"] = build_action_from_fn(arm, mesh, root, "AS_Gunner_Cover", 60, cover_fn, loop=True)

    # 6. Hit / Stagger (0..15 = 0.50s matching StaggerSeconds=0.5f)
    def hit_fn(a, f, t):
        s = math.sin(t * math.pi) ** 0.75
        set_root_world_offset(a, root, Vector((-0.08 * s, 0.03 * s, -0.04 * s)))
        apply_world_rot(a, a.pose.bones["pelvis"], ry=-0.08 * s, rz=0.16 * s)
        apply_world_rot(a, a.pose.bones["spine_01"], ry=-0.14 * s, rz=-0.15 * s)
        apply_world_rot(a, a.pose.bones["spine_02"], ry=-0.12 * s, rx=-0.12 * s)
        apply_world_rot(a, a.pose.bones["head"], ry=-0.22 * s, rz=0.26 * s)
        apply_world_rot(a, a.pose.bones["thigh_l"], ry=-0.22 * s)
        apply_world_rot(a, a.pose.bones["calf_l"], ry=0.30 * s)
        pose_gunner_rifle_ready(a, aim=0.0)

    actions["Hit"] = build_action_from_fn(arm, mesh, root, "AS_Gunner_Hit", 15, hit_fn, loop=False)

    # 7. Death (0..45 = 1.50s grounded non-gory collapse)
    def death_fn(a, f, t):
        u = min(1.0, t / 0.78)
        e = 1.0 - (1.0 - u) ** 2.1
        # Knees buckle then collapses backward/sideways onto ground
        apply_world_rot(a, a.pose.bones["pelvis"], ry=-1.45 * e, rx=0.35 * e, rz=0.30 * e)
        set_root_world_offset(a, root, Vector((-0.18 * e, 0.0, -0.78 * e)))
        apply_world_rot(a, a.pose.bones["spine_01"], ry=-0.12 * e)
        apply_world_rot(a, a.pose.bones["head"], ry=0.25 * e, rz=-0.30 * e)
        apply_world_rot(a, a.pose.bones["thigh_l"], ry=-0.45 * e, rx=0.25 * e)
        apply_world_rot(a, a.pose.bones["calf_l"], ry=0.85 * e)
        apply_world_rot(a, a.pose.bones["thigh_r"], ry=-0.30 * e, rx=-0.25 * e)
        apply_world_rot(a, a.pose.bones["calf_r"], ry=0.70 * e)
        apply_world_rot(a, a.pose.bones["upperarm_l"], ry=-0.30 * e, rx=0.55 * e)
        apply_world_rot(a, a.pose.bones["upperarm_r"], ry=-0.20 * e, rx=-0.50 * e)

    actions["Death"] = build_action_from_fn(arm, mesh, root, "AS_Gunner_Death", 45, death_fn, loop=False)
    return actions


def export_creature_fbxs(arm, mesh, actions, out_dir, sk_name, prefix):
    os.makedirs(out_dir, exist_ok=True)
    scene = bpy.context.scene
    scene.render.fps = 30

    # Export Skeletal Mesh + Skeleton in clean REST pose
    arm.animation_data_clear()
    arm.data.pose_position = "REST"
    reset_pose(arm)
    bpy.context.view_layer.update()

    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = arm

    sk_path = os.path.join(out_dir, f"{sk_name}.fbx")
    bpy.ops.export_scene.fbx(
        filepath=sk_path,
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
        axis_forward="-Z",
        axis_up="Y",
        apply_unit_scale=True,
        bake_space_transform=False,
        mesh_smooth_type="FACE",
        use_armature_deform_only=False,
        add_leaf_bones=False,
        bake_anim=False,
        path_mode="COPY",
        embed_textures=True,
    )

    # Export each animation clip cleanly starting at frame 0
    arm.data.pose_position = "POSE"
    arm.animation_data_create()
    anim_info = {}
    for clip_name, act in actions.items():
        arm.animation_data.action = act
        f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
        scene.frame_start = f0
        scene.frame_end = f1
        scene.frame_set(f0)
        bpy.context.view_layer.update()

        bpy.ops.object.select_all(action="DESELECT")
        arm.select_set(True)
        bpy.context.view_layer.objects.active = arm

        anim_path = os.path.join(out_dir, f"AS_{prefix}_{clip_name}.fbx")
        bpy.ops.export_scene.fbx(
            filepath=anim_path,
            use_selection=True,
            object_types={"ARMATURE"},
            axis_forward="-Z",
            axis_up="Y",
            apply_unit_scale=True,
            bake_space_transform=False,
            use_armature_deform_only=False,
            add_leaf_bones=False,
            bake_anim=True,
            bake_anim_use_all_actions=False,
            bake_anim_use_nla_strips=False,
            bake_anim_step=1.0,
            bake_anim_simplify_factor=0.0,
        )
        anim_info[clip_name] = {
            "fbx": anim_path,
            "frames": [f0, f1],
            "num_keys": f1 - f0 + 1,
            "duration_s": round((f1 - f0) / 30.0, 4),
            "bytes": os.path.getsize(anim_path),
        }

    return sk_path, anim_info


def render_creature_contact_sheet(arm, mesh, actions, name, target_h, out_png):
    """Render a multi-angle + multi-pose contact sheet with a grounded Mars floor plane."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 400
    scene.render.resolution_y = 400

    # Setup world + 3-point lighting + grounded reference floor at Z=0
    if not scene.world:
        scene.world = bpy.data.worlds.new("PreviewWorld")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.16, 0.12, 0.10, 1.0)
        bg.inputs[1].default_value = 1.4

    lights = []
    for lname, rot, energy in [
        ("KeySun", (0.75, 0.20, 0.65), 3.0),
        ("FillSun", (-0.65, -0.30, -2.4), 1.4),
    ]:
        ld = bpy.data.lights.new(lname, "SUN")
        ld.energy = energy
        lo = bpy.data.objects.new(lname, ld)
        lo.rotation_euler = rot
        bpy.context.collection.objects.link(lo)
        lights.append(lo)

    bpy.ops.mesh.primitive_plane_add(size=10.0, location=(0.0, 0.0, -0.002))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("PreviewFloor")
    fmat.use_nodes = True
    bsdf = fmat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.28, 0.15, 0.10, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.85
    floor.data.materials.append(fmat)

    cam_d = bpy.data.cameras.new("PreviewCam")
    cam = bpy.data.objects.new("PreviewCam", cam_d)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam

    arm.data.pose_position = "REST"
    reset_pose(arm)
    bpy.context.view_layer.update()
    mn, mx = evaluated_world_bounds(mesh)
    span = max(mx.x - mn.x, mx.y - mn.y, mx.z - mn.z)
    dist = max(span * 1.45, target_h * 2.1, 2.0)
    center = Vector((0.0, 0.0, target_h * 0.45))

    def snap(tag, cam_offset):
        cam.location = center + cam_offset
        direction = (center - cam.location).normalized()
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        tmp = os.path.join(PREVIEW_DIR, f"_tmp_{name}_{tag}.png")
        scene.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        return tmp

    os.makedirs(PREVIEW_DIR, exist_ok=True)
    tiles = []

    # Tile 1-3: Rest pose Front (+X), Side (-Y), 3/4 view
    arm.data.pose_position = "REST"
    reset_pose(arm)
    bpy.context.view_layer.update()
    tiles.append(("Rest_Front", snap("rest_front", Vector((dist, 0.0, 0.1 * target_h)))))
    tiles.append(("Rest_Side", snap("rest_side", Vector((0.0, -dist, 0.1 * target_h)))))
    tiles.append(("Rest_3Q", snap("rest_3q", Vector((dist * 0.78, -dist * 0.65, 0.25 * target_h)))))

    # Pose key frames from production actions
    arm.data.pose_position = "POSE"
    arm.animation_data_create()
    pose_samples = [
        ("Walk", 0.25, Vector((dist * 0.72, -dist * 0.72, 0.20 * target_h))),
        ("Run", 0.25, Vector((dist * 0.65, -dist * 0.78, 0.20 * target_h))),
        ("Telegraph", 0.50 if name == "Raider" else (0.58 if name == "Breaker" else 0.55), Vector((dist * 0.78, -dist * 0.65, 0.25 * target_h))),
        ("Hit", 0.30, Vector((dist * 0.78, -dist * 0.65, 0.20 * target_h))),
        ("Death", 1.00, Vector((dist * 0.75, -dist * 0.70, 0.55 * target_h))),
    ]
    if "Cover" in actions:
        pose_samples.append(("Cover", 0.50, Vector((dist * 0.78, -dist * 0.65, 0.15 * target_h))))

    for cname, frac, cam_off in pose_samples:
        act = actions[cname]
        arm.animation_data.action = act
        f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
        f_eval = f0 + int(round((f1 - f0) * frac))
        scene.frame_set(f_eval)
        bpy.context.view_layer.update()
        tiles.append((cname, snap(cname, cam_off)))

    # Stitch tiles into 3x3 grid using Blender image pixels
    cols = 3
    rows = math.ceil(len(tiles) / cols)
    tw, th = 400, 400
    sheet = bpy.data.images.new(f"{name}_Sheet", width=cols * tw, height=rows * th, alpha=True)
    buf = [0.0] * (cols * tw * rows * th * 4)

    for idx, (_, img_path) in enumerate(tiles):
        r = idx // cols
        c = idx % cols
        # Place row 0 at top of image (Blender Y=0 is bottom)
        y_base = (rows - 1 - r) * th
        x_base = c * tw
        tile_img = bpy.data.images.load(img_path)
        px = list(tile_img.pixels)
        for y in range(th):
            src_off = y * tw * 4
            dst_off = ((y_base + y) * cols * tw + x_base) * 4
            buf[dst_off : dst_off + tw * 4] = px[src_off : src_off + tw * 4]
        bpy.data.images.remove(tile_img)
        os.remove(img_path)

    sheet.pixels = buf
    sheet.filepath_raw = out_png
    sheet.file_format = "PNG"
    sheet.save()
    bpy.data.images.remove(sheet)

    # Cleanup preview helpers
    bpy.data.objects.remove(floor, do_unlink=True)
    bpy.data.objects.remove(cam, do_unlink=True)
    for lo in lights:
        bpy.data.objects.remove(lo, do_unlink=True)


def verify_roundtrip(sk_path, anim_dict, expected_bones):
    """Re-import SK + each AS_*.fbx with anim_offset=0.0 to verify 0-based timing, skeleton, and motion."""
    results = {}
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=sk_path, anim_offset=0.0)
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    mesh = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    mn, mx = evaluated_world_bounds(mesh)
    results["skeleton"] = {
        "bones": len(arm.data.bones),
        "expected_bones": expected_bones,
        "vertices": len(mesh.data.vertices),
        "polygons": len(mesh.data.polygons),
        "weighted": bool(mesh.vertex_groups),
        "ue_size_cm": [round((mx[i] - mn[i]) * 100.0, 2) for i in range(3)],
        "ue_min_z_cm": round(mn.z * 100.0, 2),
        "bone_names": [b.name for b in arm.data.bones],
    }

    anim_checks = {}
    for cname, info in anim_dict.items():
        for a in list(bpy.data.actions):
            bpy.data.actions.remove(a)
        # Delete old imported objects and reimport anim FBX cleanly
        clear_scene()
        bpy.ops.import_scene.fbx(filepath=info["fbx"], anim_offset=0.0)
        a_arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
        act = bpy.data.actions[0]
        f0, f1 = act.frame_range[0], act.frame_range[1]
        a_arm.animation_data.action = act
        s = bpy.context.scene
        s.frame_set(int(round(f0)))
        bpy.context.view_layer.update()
        p0 = {p.name: p.matrix.copy() for p in a_arm.pose.bones}
        s.frame_set(int(round(f0 + (f1 - f0) * 0.25)))
        bpy.context.view_layer.update()
        q_mot = max((p0[k].translation - p.matrix.translation).length + p0[k].to_quaternion().rotation_difference(p.matrix.to_quaternion()).angle for k, p in a_arm.pose.bones.items())
        s.frame_set(int(round(f1)))
        bpy.context.view_layer.update()
        end_diff = max((p0[k].translation - p.matrix.translation).length + p0[k].to_quaternion().rotation_difference(p.matrix.to_quaternion()).angle for k, p in a_arm.pose.bones.items())
        anim_checks[cname] = {
            "roundtrip_frames": [round(f0, 3), round(f1, 3)],
            "quarter_motion": round(q_mot, 4),
            "end_vs_start_diff": round(end_diff, 4),
        }
    results["animations"] = anim_checks
    return results


def copy_textures(src_fbm_dir, dst_dir, names):
    os.makedirs(dst_dir, exist_ok=True)
    copied = []
    for n in names:
        src = os.path.join(src_fbm_dir, n)
        dst = os.path.join(dst_dir, n)
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def main():
    manifest = {}

    # 1. RAIDER (0.80m tall = 80cm, +X forward, Z=0 ground)
    r_src = os.path.join(SRC_DIR, "Raider/tripo_convert_52e2c664-d0d0-42f4-a60e-f676d754875b.fbx")
    r_fbm = os.path.join(SRC_DIR, "Raider/tripo_convert_52e2c664-d0d0-42f4-a60e-f676d754875b.fbm")
    r_out = os.path.join(PROD_DIR, "Raider")
    arm, mesh, r_walk = align_and_scale_tripo(r_src, z_rot_deg=180.0, target_height_m=0.80)
    r_actions = build_raider_actions(arm, mesh, r_walk)
    r_sk, r_anims = export_creature_fbxs(arm, mesh, r_actions, r_out, "SK_Alien_Raider", "Raider")
    r_tex = copy_textures(r_fbm, r_out, ["Mars_Last_Green_Raider_Animated_basecolor.jpg", "Mars_Last_Green_Raider_Animated_normal.jpg"])
    r_png = os.path.join(PREVIEW_DIR, "Raider_contact_sheet.png")
    render_creature_contact_sheet(arm, mesh, r_actions, "Raider", 0.80, r_png)
    r_rt = verify_roundtrip(r_sk, r_anims, 32)
    manifest["Raider"] = {"sk_fbx": r_sk, "textures": r_tex, "animations": r_anims, "preview_png": r_png, "roundtrip": r_rt}
    print("DONE_RAIDER", json.dumps(r_rt["skeleton"]["ue_size_cm"]), flush=True)

    # 2. BREAKER (2.00m tall = 200cm, +X forward, Z=0 ground)
    b_src = os.path.join(SRC_DIR, "Breaker/tripo_convert_a248d4ea-eedf-4384-96af-d67d7f427fc5.fbx")
    b_fbm = os.path.join(SRC_DIR, "Breaker/tripo_convert_a248d4ea-eedf-4384-96af-d67d7f427fc5.fbm")
    b_out = os.path.join(PROD_DIR, "Breaker")
    arm, mesh, b_walk = align_and_scale_tripo(b_src, z_rot_deg=90.0, target_height_m=2.00)
    b_actions = build_breaker_actions(arm, mesh, b_walk)
    b_sk, b_anims = export_creature_fbxs(arm, mesh, b_actions, b_out, "SK_Alien_Breaker", "Breaker")
    b_tex = copy_textures(b_fbm, b_out, ["Mars_Last_Green_Breacher_Animated_basecolor.jpg", "Mars_Last_Green_Breacher_Animated_normal.jpg"])
    b_png = os.path.join(PREVIEW_DIR, "Breaker_contact_sheet.png")
    render_creature_contact_sheet(arm, mesh, b_actions, "Breaker", 2.00, b_png)
    b_rt = verify_roundtrip(b_sk, b_anims, 23)
    manifest["Breaker"] = {"sk_fbx": b_sk, "textures": b_tex, "animations": b_anims, "preview_png": b_png, "roundtrip": b_rt}
    print("DONE_BREAKER", json.dumps(b_rt["skeleton"]["ue_size_cm"]), flush=True)

    # 3. GUNNER (1.80m tall = 180cm, +X forward, Z=0 ground, UE5-style humanoid rig + carbine)
    g_blend = os.path.join(SRC_DIR, "Gunner/Gunner_base.blend")
    g_out = os.path.join(PROD_DIR, "Gunner")
    clear_scene()
    bpy.ops.wm.open_mainfile(filepath=g_blend)
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    mesh = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    g_actions = build_gunner_actions(arm, mesh)
    g_sk, g_anims = export_creature_fbxs(arm, mesh, g_actions, g_out, "SK_Alien_Gunner", "Gunner")
    g_tex = [
        os.path.join(g_out, "Mars_Last_Green_Gunner_basecolor.png"),
        os.path.join(g_out, "Mars_Last_Green_Gunner_normal.png"),
    ]
    g_png = os.path.join(PREVIEW_DIR, "Gunner_contact_sheet.png")
    render_creature_contact_sheet(arm, mesh, g_actions, "Gunner", 1.80, g_png)
    g_rt = verify_roundtrip(g_sk, g_anims, 25)
    manifest["Gunner"] = {"sk_fbx": g_sk, "textures": g_tex, "animations": g_anims, "preview_png": g_png, "roundtrip": g_rt}
    print("DONE_GUNNER", json.dumps(g_rt["skeleton"]["ue_size_cm"]), flush=True)

    manifest_path = os.path.join(PROD_DIR, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print("MANIFEST_SAVED:", manifest_path, flush=True)


if __name__ == "__main__":
    main()
