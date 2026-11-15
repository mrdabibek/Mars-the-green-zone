"""Build and enhance /Game/Maps/Base with Mars atmospheric lighting, landing pad, interior architecture, outpost framing, rocks, and NavMesh.

Run via:
  UnrealEditor-Cmd "<project>/MarsLastGreen.uproject" \
    -ExecutePythonScript="<project>/Tools/build_base_map.py" \
    -nullrhi -unattended -nop4
"""

import math
import unreal

ELL = unreal.EditorLevelLibrary
EAL = unreal.EditorAssetLibrary
ASSET_TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
MEL = unreal.MaterialEditingLibrary

DROPLANDER_PAD_X = -1850.0
DROPLANDER_PAD_Y = -900.0
DROPLANDER_CLEAR_RADIUS = 760.0


def log(msg):
    unreal.log("MLG_MAP: " + str(msg))


def warn(msg):
    unreal.log_warning("MLG_MAP: " + str(msg))


def set_prop(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception as exc:
        warn(f"Failed setting {obj.get_name()}.{name}={value}: {exc}")
        return False


def ensure_simple_material(pkg_path, base_rgb, metallic=0.3, roughness=0.5, emissive_rgb=(0.0, 0.0, 0.0), overwrite=True):
    """Create or update a clean PBR material with Color & EmissiveColor VectorParameters."""
    exists = EAL.does_asset_exist(pkg_path)
    if exists and not overwrite:
        return EAL.load_asset(pkg_path)
    if exists:
        mat = EAL.load_asset(pkg_path)
    else:
        mat_dir, mat_name = pkg_path.rsplit("/", 1)
        EAL.make_directory(mat_dir)
        mat = ASSET_TOOLS.create_asset(mat_name, mat_dir, unreal.Material, unreal.MaterialFactoryNew())
    if not mat:
        return None

    MEL.delete_all_material_expressions(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)

    col_param = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -420, -180)
    col_param.set_editor_property("parameter_name", "Color")
    col_param.set_editor_property("default_value", unreal.LinearColor(base_rgb[0], base_rgb[1], base_rgb[2], 1.0))
    MEL.connect_material_property(col_param, "", unreal.MaterialProperty.MP_BASE_COLOR)

    met = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 0)
    met.r = float(metallic)
    MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)

    rgh = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 100)
    rgh.r = float(roughness)
    MEL.connect_material_property(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)

    em_param = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -420, 240)
    em_param.set_editor_property("parameter_name", "EmissiveColor")
    em_param.set_editor_property("default_value", unreal.LinearColor(emissive_rgb[0], emissive_rgb[1], emissive_rgb[2], 1.0))
    MEL.connect_material_property(em_param, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    MEL.recompile_material(mat)
    EAL.save_asset(pkg_path, only_if_is_dirty=False)
    return mat


def spawn_static_mesh(label, mesh, loc, rot=unreal.Rotator(0.0, 0.0, 0.0), scale=unreal.Vector(1.0, 1.0, 1.0),
                      mat=None, collision="BlockAll", affect_nav=True, tags=None):
    if not mesh:
        warn(f"Skipping {label}: mesh is None")
        return None
    actor = ELL.spawn_actor_from_class(unreal.StaticMeshActor, loc, rot)
    if not actor:
        return None
    actor.set_actor_label(label)
    if tags:
        for tag in tags:
            actor.tags.append(tag)
    smc = actor.static_mesh_component
    smc.set_mobility(unreal.ComponentMobility.STATIC)
    smc.set_static_mesh(mesh)
    actor.set_actor_scale3d(scale)
    if mat:
        for i in range(max(1, smc.get_num_materials())):
            smc.set_material(i, mat)
    if collision:
        try:
            smc.set_collision_profile_name(collision)
        except Exception as exc:
            warn(f"Failed setting collision profile {collision} on {label}: {exc}")
    set_prop(smc, "can_ever_affect_navigation", affect_nav)
    return actor


# Balanced interior lighting scale (0.015) with dark slate-titanium walls & steel deck floors (zero white-out),
# and 0.03 for exterior landmark beacons/fills.
LIGHT_SCALE = 0.015
LIGHT_SCALE_INTERIOR = LIGHT_SCALE
LIGHT_SCALE_EXTERIOR = 0.03
INTERIOR_LABELS = (
    "PointLight_Habitat",
    "PointLight_Corridor",
    "PointLight_Greenhouse",
    "PointLight_GrowLamp",
    "PointLight_Workstation",
    "PointLight_GeneLab",
    "PointLight_SabatierSynth",
    "SpotLight_Gallery",
    "SM_Tripo_BotanicalPod_Showcase",
    "SM_Tripo_PulseRifle_Display",
)


def spawn_point_light(label, loc, col, intensity, radius, cast_shadows=False):
    intensity = intensity * (LIGHT_SCALE_INTERIOR if label.startswith(INTERIOR_LABELS) else LIGHT_SCALE_EXTERIOR)
    pl = ELL.spawn_actor_from_class(unreal.PointLight, loc)
    if not pl:
        return None
    pl.set_actor_label(label)
    plc = pl.point_light_component
    set_prop(plc, "mobility", unreal.ComponentMobility.MOVABLE)
    set_prop(plc, "light_color", col)
    set_prop(plc, "intensity", intensity)
    set_prop(plc, "attenuation_radius", radius)
    set_prop(plc, "cast_shadows", cast_shadows)
    return pl


def spawn_spot_light(label, loc, rot, col, intensity, radius, inner_cone=20.0, outer_cone=38.0, cast_shadows=False):
    intensity = intensity * (LIGHT_SCALE_INTERIOR if label.startswith(INTERIOR_LABELS) else LIGHT_SCALE_EXTERIOR)
    sl = ELL.spawn_actor_from_class(unreal.SpotLight, loc, rot)
    if not sl:
        return None
    sl.set_actor_label(label)
    slc = sl.spot_light_component
    set_prop(slc, "mobility", unreal.ComponentMobility.MOVABLE)
    set_prop(slc, "light_color", col)
    set_prop(slc, "intensity", intensity)
    set_prop(slc, "attenuation_radius", radius)
    set_prop(slc, "inner_cone_angle", inner_cone)
    set_prop(slc, "outer_cone_angle", outer_cone)
    set_prop(slc, "cast_shadows", cast_shadows)
    return sl


def is_clear_of_droplander_pad(x, y, extra_margin=0.0):
    """Keep a strict 760cm+ clearance radius around the Enterable DropShip pad at (-1850, -900)."""
    return math.hypot(x - DROPLANDER_PAD_X, y - DROPLANDER_PAD_Y) >= (DROPLANDER_CLEAR_RADIUS + extra_margin)


def is_clear_of_gameplay_lanes(x, y):
    """Keep all combat, device, player, DropShip, compound, and AI navigation lanes clear of rock/landmark obstacles."""
    if not is_clear_of_droplander_pad(x, y, extra_margin=120.0):
        return False
    # Main base footprint (Habitat + Corridor + Greenhouse)
    if -1100 <= x <= 1100 and -700 <= y <= 700:
        return False
    # West water line & Raider/Breaker spawn + approach corridor
    if -3300 <= x <= -950 and -850 <= y <= 850:
        return False
    # North-west Gunner flank & Solar Farm compound (-1700, 1400)
    if -2400 <= x <= -950 and 150 <= y <= 2100:
        return False
    # South ice field path, Cryo-Ice Rig (0, -2100), & Sabatier pipeline
    if -420 <= x <= 850 and -2450 <= y <= -550:
        return False
    # East comms relay path & Comms Array (2000, 400)
    if 900 <= x <= 2900 and -500 <= y <= 760:
        return False
    return True


def spawn_mars_rocks():
    rock1 = EAL.load_asset("/Game/Environment/SM_MarsRock_01") if EAL.does_asset_exist("/Game/Environment/SM_MarsRock_01") else None
    rock2 = EAL.load_asset("/Game/Environment/SM_MarsRock_02") if EAL.does_asset_exist("/Game/Environment/SM_MarsRock_02") else None
    meshes = [m for m in (rock1, rock2) if m is not None]
    if not meshes:
        warn("No SM_MarsRock_* assets found in /Game/Environment/; skipping rock scatter.")
        return 0

    placements = [
        # North ridge & horizon framing
        (-2800, 2350, 14.0, 25.0), (-2100, 2450, 18.0, 80.0), (-1300, 2300, 12.0, 140.0),
        (-500, 1350, 10.0, 45.0), (100, 1500, 14.0, 110.0), (750, 1300, 11.0, 200.0),
        (1450, 1950, 16.0, 15.0), (2200, 1400, 18.0, 95.0), (3050, 1200, 20.0, 260.0),
        # South-west & south canyon rim (clear of 760cm DropShip pad, Cryo-Ice Rig, and ice field)
        (-2800, -1450, 15.0, 35.0), (-2280, -1920, 18.0, 120.0), (-1450, -1820, 12.0, 210.0),
        (-850, -1620, 10.0, 65.0), (1250, -1300, 13.0, 175.0), (1950, -1550, 17.0, 310.0),
        (2750, -1250, 16.0, 50.0), (950, -2350, 16.0, 130.0), (-680, -2360, 14.0, 290.0),
        # Far-west alien horizon ridge (behind -2800 spawn line)
        (-3650, -1100, 22.0, 40.0), (-3750, -350, 16.0, 155.0), (-3600, 450, 18.0, 230.0),
        (-3700, 1250, 20.0, 75.0),
        # Far-east ridge (beyond +2560 comms relay)
        (3350, -650, 16.0, 115.0), (3450, 120, 20.0, 195.0), (3300, 780, 15.0, 300.0),
        # Smaller foreground/midground accent rocks outside nav lanes & DropLander pad
        (-1140, -1520, 6.0, 20.0), (1350, -800, 5.5, 145.0), (1550, 780, 6.5, 225.0),
        (-520, -1120, 5.0, 85.0), (1050, -1000, 5.5, 340.0), (2100, 850, 7.0, 170.0),
        (2150, -820, 6.0, 60.0), (-150, 950, 5.5, 120.0),
    ]

    placed = 0
    for idx, (x, y, scale, yaw) in enumerate(placements):
        if not is_clear_of_gameplay_lanes(x, y):
            warn(f"Skipping rock at ({x}, {y}): overlaps gameplay lane or DropLander clearance")
            continue
        mesh = meshes[idx % len(meshes)]
        b = mesh.get_bounding_box()
        z_offset = -b.min.z * scale - 4.0
        sx = scale * (1.0 + 0.15 * math.sin(idx * 1.7))
        sy = scale * (1.0 + 0.15 * math.cos(idx * 2.3))
        sz = scale * (0.9 + 0.2 * math.sin(idx * 0.9))
        actor = spawn_static_mesh(
            f"SM_MarsRock_{placed:02d}",
            mesh,
            unreal.Vector(x, y, z_offset),
            unreal.Rotator(0.0, yaw, 0.0),
            unreal.Vector(sx, sy, sz),
            affect_nav=(scale >= 8.0),
        )
        if actor:
            placed += 1
    return placed


def spawn_ice_field_landmarks():
    """Place icy crystal clusters and perimeter rim rocks framing the south ice field around (380, -1550)."""
    rock1 = EAL.load_asset("/Game/Environment/SM_MarsRock_01") if EAL.does_asset_exist("/Game/Environment/SM_MarsRock_01") else None
    rock2 = EAL.load_asset("/Game/Environment/SM_MarsRock_02") if EAL.does_asset_exist("/Game/Environment/SM_MarsRock_02") else None
    ice_mesh = EAL.load_asset("/Game/Environment/SM_Pickup_Ice") if EAL.does_asset_exist("/Game/Environment/SM_Pickup_Ice") else None
    cone_mesh = unreal.load_object(None, "/Engine/BasicShapes/Cone.Cone")

    ice_mat = ensure_simple_material(
        "/Game/Environment/Materials/M_MarsIceCrystal",
        base_rgb=(0.55, 0.88, 1.0),
        metallic=0.05,
        roughness=0.14,
        emissive_rgb=(0.12, 0.45, 0.78),
    )

    # Rim rocks framing the ice crater without blocking the north approach or pickups
    rim_rocks = [
        (-80, -1460, 7.5, 25.0),
        (-120, -1720, 9.0, 110.0),
        (70, -1960, 10.5, 195.0),
        (380, -2040, 12.0, 45.0),
        (720, -1940, 10.0, 275.0),
        (860, -1680, 8.5, 150.0),
        (830, -1380, 7.0, 310.0),
    ]
    rim_count = 0
    for idx, (x, y, scale, yaw) in enumerate(rim_rocks):
        mesh = rock1 if (idx % 2 == 0 and rock1) else (rock2 or rock1)
        if not mesh:
            continue
        b = mesh.get_bounding_box()
        z_offset = -b.min.z * scale - 4.0
        if spawn_static_mesh(
            f"SM_IceRimRock_{rim_count:02d}",
            mesh,
            unreal.Vector(x, y, z_offset),
            unreal.Rotator(0.0, yaw, 0.0),
            unreal.Vector(scale, scale * 1.1, scale * 0.95),
            affect_nav=False,
        ):
            rim_count += 1

    # Decorative subsurface ice crystal clusters around the perimeter of the ice pickups
    crystal_spots = [
        (110, -1730, 1.8, 15.0),
        (250, -1810, 2.1, 75.0),
        (510, -1800, 1.9, 140.0),
        (650, -1710, 1.7, 220.0),
        (115, -1390, 1.5, 305.0),
        (645, -1380, 1.6, 55.0),
    ]
    crystal_count = 0
    for idx, (x, y, scale, yaw) in enumerate(crystal_spots):
        if ice_mesh:
            b = ice_mesh.get_bounding_box()
            z_off = -b.min.z * scale - 2.0
            if spawn_static_mesh(
                f"SM_IceCrystalCluster_{crystal_count:02d}",
                ice_mesh,
                unreal.Vector(x, y, z_off),
                unreal.Rotator(0.0, yaw, 0.0),
                unreal.Vector(scale, scale, scale * 1.15),
                mat=ice_mat,
                collision="NoCollision",
                affect_nav=False,
            ):
                crystal_count += 1
        elif cone_mesh:
            for shard in range(3):
                ang = math.radians(yaw + shard * 120.0)
                sx_off = math.cos(ang) * 14.0 * scale
                sy_off = math.sin(ang) * 14.0 * scale
                s_scale = scale * (0.45 - shard * 0.08)
                spawn_static_mesh(
                    f"SM_IceCrystalCluster_{crystal_count:02d}_{shard}",
                    cone_mesh,
                    unreal.Vector(x + sx_off, y + sy_off, 25.0 * s_scale),
                    unreal.Rotator(12.0 * (shard - 1), yaw + shard * 40.0, 8.0),
                    unreal.Vector(s_scale * 0.6, s_scale * 0.6, s_scale * 1.4),
                    mat=ice_mat,
                    collision="NoCollision",
                    affect_nav=False,
                )
            crystal_count += 1
    log(f"Placed {rim_count} ice-field rim rocks and {crystal_count} crystal clusters around (380, -1550)")


def spawn_beacon_pylon(label, x, y, beacon_rgb, emissive_rgb, mat_alloy, mat_beacon, light_intensity=650.0, base_z=0.0, height=90.0, light_radius=420.0):
    """Spawn a sleek grounded perimeter marker pylon + glowing beacon cap + optional point light."""
    cyl = unreal.load_object(None, "/Engine/BasicShapes/Cylinder.Cylinder")
    sph = unreal.load_object(None, "/Engine/BasicShapes/Sphere.Sphere")
    if cyl:
        spawn_static_mesh(
            f"{label}_Post",
            cyl,
            unreal.Vector(x, y, base_z + height * 0.5),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.14, 0.14, height / 100.0),
            mat=mat_alloy,
            collision="NoCollision",
            affect_nav=False,
        )
    if sph:
        cap = spawn_static_mesh(
            f"{label}_Cap",
            sph,
            unreal.Vector(x, y, base_z + height + 6.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.22, 0.22, 0.22),
            mat=mat_beacon,
            collision="NoCollision",
            affect_nav=False,
        )
        if cap:
            smc = cap.static_mesh_component
            mid = smc.create_dynamic_material_instance(0, mat_beacon)
            if mid:
                mid.set_vector_parameter_value("Color", unreal.LinearColor(beacon_rgb[0], beacon_rgb[1], beacon_rgb[2], 1.0))
                mid.set_vector_parameter_value("EmissiveColor", unreal.LinearColor(emissive_rgb[0], emissive_rgb[1], emissive_rgb[2], 1.0))
    if light_intensity > 0.0:
        c = unreal.Color(
            int(min(255, beacon_rgb[0] * 255)),
            int(min(255, beacon_rgb[1] * 255)),
            int(min(255, beacon_rgb[2] * 255)),
            255,
        )
        spawn_point_light(f"{label}_Light", unreal.Vector(x, y, base_z + height + 22.0), c, light_intensity, light_radius)


def spawn_comms_and_perimeter_landmarks():
    """Place comms relay tower foundation/markers around (2500, 0) and exterior perimeter wayfinding beacons."""
    cyl = unreal.load_object(None, "/Engine/BasicShapes/Cylinder.Cylinder")
    mat_deck = ensure_simple_material(
        "/Game/Environment/Materials/M_OutpostDeck",
        base_rgb=(0.20, 0.22, 0.25),
        metallic=0.65,
        roughness=0.45,
    )
    mat_alloy = ensure_simple_material(
        "/Game/Environment/Materials/M_BeaconPost",
        base_rgb=(0.35, 0.38, 0.42),
        metallic=0.75,
        roughness=0.35,
    )
    mat_beacon = ensure_simple_material(
        "/Game/Environment/Materials/M_PerimeterBeacon",
        base_rgb=(0.3, 0.85, 1.0),
        metallic=0.1,
        roughness=0.2,
        emissive_rgb=(0.4, 1.6, 2.2),
    )

    # Comms relay foundation pad at (2500, 0)
    if cyl and mat_deck:
        spawn_static_mesh(
            "SM_CommsRelay_Foundation",
            cyl,
            unreal.Vector(2500.0, 0.0, 2.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(4.4, 4.4, 0.06),
            mat=mat_deck,
            collision="NoCollision",
            affect_nav=False,
        )
        spawn_static_mesh(
            "SM_CommsRelay_Plinth",
            cyl,
            unreal.Vector(2500.0, 0.0, 6.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(1.8, 1.8, 0.08),
            mat=mat_alloy,
            collision="NoCollision",
            affect_nav=False,
        )

    # 4 corner relay markers around (2500, 0)
    comms_markers = [
        ("CommsMarker_SW", 2300.0, -240.0),
        ("CommsMarker_NW", 2300.0, 240.0),
        ("CommsMarker_SE", 2720.0, -240.0),
        ("CommsMarker_NE", 2720.0, 240.0),
    ]
    for label, x, y in comms_markers:
        spawn_beacon_pylon(label, x, y, (0.25, 0.85, 1.0), (0.35, 1.5, 2.2), mat_alloy, mat_beacon, 550.0)

    # Exterior perimeter beacons: airlock west entrance, south ice trail, east comms trail
    perimeter_beacons = [
        ("Beacon_Airlock_S", -935.0, -175.0, (1.0, 0.55, 0.15), (2.0, 0.85, 0.18), 900.0),
        ("Beacon_Airlock_N", -935.0, 175.0, (1.0, 0.55, 0.15), (2.0, 0.85, 0.18), 900.0),
        ("Beacon_IceTrail_01", 140.0, -820.0, (0.45, 0.88, 1.0), (0.6, 1.6, 2.4), 600.0),
        ("Beacon_IceTrail_02", 220.0, -1180.0, (0.45, 0.88, 1.0), (0.6, 1.6, 2.4), 600.0),
        ("Beacon_CommsTrail_01", 1280.0, -240.0, (0.35, 0.90, 0.95), (0.4, 1.5, 1.8), 600.0),
        ("Beacon_CommsTrail_02", 1820.0, 240.0, (0.35, 0.90, 0.95), (0.4, 1.5, 1.8), 600.0),
    ]
    for label, x, y, bcol, ecol, lint in perimeter_beacons:
        spawn_beacon_pylon(label, x, y, bcol, ecol, mat_alloy, mat_beacon, lint)
    log("Placed comms relay foundation/markers and exterior perimeter beacons")


def spawn_droplander_pad():
    """Build the West Enterable DropShip / Lander Compound at (-1850, -900, 0):
    1) Expanded octagonal reinforced concrete/steel burn pad (LandingPad_*) + 8 perimeter amber approach beacons.
    2) Larger (~900x600x450cm) enterable multi-module DropShip (DropShip_*, all tagged 'DropShip' for MLGPrologue):
       weathered ceramic/steel heatshield hull, open +X boarding ramp at ground level, open aft hatchway,
       walkable cockpit/cargo interior clear around DropLocker (-1850,-900,60), flight consoles, cryo-lockers,
       seat frames, glowing amber/cyan instrument screens, and warm-amber interior floodlight."""
    cube = unreal.load_object(None, "/Engine/BasicShapes/Cube.Cube")
    cyl = unreal.load_object(None, "/Engine/BasicShapes/Cylinder.Cylinder")
    if not cube or not cyl:
        return

    mat_concrete = ensure_simple_material(
        "/Game/Environment/Materials/M_LandingPad_Concrete",
        base_rgb=(0.17, 0.18, 0.20),
        metallic=0.08,
        roughness=0.78,
        overwrite=False,
    )
    mat_scorch = ensure_simple_material(
        "/Game/Environment/Materials/M_LandingPad_Scorch",
        base_rgb=(0.045, 0.040, 0.038),
        metallic=0.22,
        roughness=0.86,
        overwrite=False,
    )
    mat_wall = ensure_simple_material(
        "/Game/Environment/Materials/M_Habitat_Wall",
        base_rgb=(0.088, 0.102, 0.126),
        metallic=0.42,
        roughness=0.44,
        overwrite=False,
    )
    mat_trim = ensure_simple_material(
        "/Game/Environment/Materials/M_Habitat_Trim",
        base_rgb=(0.095, 0.108, 0.128),
        metallic=0.76,
        roughness=0.38,
        overwrite=False,
    )
    mat_gunmetal = ensure_simple_material(
        "/Game/Environment/Materials/M_Metal_Gunmetal",
        base_rgb=(0.068, 0.076, 0.092),
        metallic=0.78,
        roughness=0.38,
        overwrite=False,
    )
    mat_deck = ensure_simple_material(
        "/Game/Environment/Materials/M_OutpostDeck",
        base_rgb=(0.10, 0.11, 0.13),
        metallic=0.68,
        roughness=0.45,
        overwrite=False,
    )
    mat_glass = ensure_simple_material(
        "/Game/Environment/Materials/M_Greenhouse_Glass",
        base_rgb=(0.14, 0.28, 0.36),
        metallic=0.10,
        roughness=0.12,
        emissive_rgb=(0.015, 0.035, 0.050),
        overwrite=False,
    )
    mat_alloy = ensure_simple_material(
        "/Game/Environment/Materials/M_BeaconPost",
        base_rgb=(0.35, 0.38, 0.42),
        metallic=0.75,
        roughness=0.35,
        overwrite=False,
    )
    mat_beacon = ensure_simple_material(
        "/Game/Environment/Materials/M_PerimeterBeacon",
        base_rgb=(0.3, 0.85, 1.0),
        metallic=0.1,
        roughness=0.2,
        emissive_rgb=(0.4, 1.6, 2.2),
        overwrite=False,
    )
    mat_amber_trim = ensure_simple_material(
        "/Game/Environment/Materials/M_LandingPad_AmberTrim",
        base_rgb=(0.85, 0.42, 0.08),
        metallic=0.2,
        roughness=0.32,
        emissive_rgb=(1.45, 0.62, 0.10),
    )
    mat_cyan = ensure_simple_material(
        "/Game/Environment/Materials/M_AccentCyan",
        base_rgb=(0.08, 0.45, 0.62),
        metallic=0.15,
        roughness=0.20,
        emissive_rgb=(0.14, 0.85, 1.15),
        overwrite=False,
    )

    cx, cy = DROPLANDER_PAD_X, DROPLANDER_PAD_Y

    # ------------------------------------------------------------------
    # 1. Static Ground Scarred Burn Pad (LandingPad_*, NOT tagged DropShip)
    # ------------------------------------------------------------------
    spawn_static_mesh(
        "LandingPad_ConcreteApron",
        cyl,
        unreal.Vector(cx, cy, 7.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(12.6, 12.6, 0.14),
        mat=mat_concrete,
        collision="NoCollision",
        affect_nav=False,
    )
    spawn_static_mesh(
        "LandingPad_SteelBlastDeck",
        cyl,
        unreal.Vector(cx, cy, 8.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(10.8, 10.8, 0.16),
        mat=mat_trim,
        collision="NoCollision",
        affect_nav=False,
    )
    spawn_static_mesh(
        "LandingPad_ScorchRing",
        cyl,
        unreal.Vector(cx, cy, 8.5),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(8.8, 8.8, 0.17),
        mat=mat_scorch,
        collision="NoCollision",
        affect_nav=False,
    )
    spawn_static_mesh(
        "LandingPad_CenterHub",
        cyl,
        unreal.Vector(cx, cy, 9.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(5.6, 5.6, 0.18),
        mat=mat_deck,
        collision="NoCollision",
        affect_nav=False,
    )

    # 7 Octagonal curbs + scorch trims (skipping i=0 east edge so +X boarding ramp is flush at ground level)
    apothem = 578.0
    for i in range(8):
        if i == 0:
            continue
        yaw = i * 45.0
        rad = math.radians(yaw)
        bx = cx + math.cos(rad) * apothem
        by = cy + math.sin(rad) * apothem
        spawn_static_mesh(
            f"LandingPad_OctagonCurb_{i:02d}",
            cube,
            unreal.Vector(bx, by, 11.0),
            unreal.Rotator(0.0, yaw, 0.0),
            unreal.Vector(0.56, 4.72, 0.22),
            mat=mat_concrete,
            collision="NoCollision",
            affect_nav=False,
        )
        tx = cx + math.cos(rad) * 524.0
        ty = cy + math.sin(rad) * 524.0
        spawn_static_mesh(
            f"LandingPad_ScorchTrim_{i:02d}",
            cube,
            unreal.Vector(tx, ty, 16.8),
            unreal.Rotator(0.0, yaw, 0.0),
            unreal.Vector(0.16, 2.20, 0.02),
            mat=mat_amber_trim,
            collision="NoCollision",
            affect_nav=False,
        )

    # 8 Perimeter Amber Approach Beacon Pylons at octagon vertices (radius = 695cm, clear of +X ramp & 880cm Tripo wingspan)
    for i in range(8):
        v_ang = math.radians(i * 45.0 + 22.5)
        vx = cx + math.cos(v_ang) * 695.0
        vy = cy + math.sin(v_ang) * 695.0
        spawn_beacon_pylon(
            f"LandingPad_Beacon_{i:02d}",
            vx,
            vy,
            (1.0, 0.56, 0.12),
            (2.2, 0.95, 0.14),
            mat_alloy,
            mat_beacon,
            light_intensity=360.0,
            base_z=14.0,
            height=74.0,
            light_radius=420.0,
        )

    # ------------------------------------------------------------------
    # 2. Enterable Heavy Tripo Pro Dropship (1260x880x520cm, tagged 'DropShip')
    #    Centered at (-1850, -900), cockpit nose facing -X, boarding ramp +X
    # ------------------------------------------------------------------
    ship_tags = ("DropShip",)

    def ship_mesh(suffix, mesh, loc, rot=unreal.Rotator(0.0, 0.0, 0.0),
                  scale=unreal.Vector(1.0, 1.0, 1.0), mat=mat_wall,
                  collision="BlockAll", affect_nav=True):
        return spawn_static_mesh(
            f"DropShip_{suffix}",
            mesh,
            loc,
            rot,
            scale,
            mat=mat,
            collision=collision,
            affect_nav=affect_nav,
            tags=ship_tags,
        )

    # 2a. Sculpted Tripo Pro Heavy Cargo Dropship Exterior Shell (hollowed aft bay for walk-in interior)
    tripo_ship = EAL.load_asset("/Game/Tripo/SM_Tripo_HeavyDropship")
    if tripo_ship is not None:
        ship_mesh(
            "TripoHull",
            tripo_ship,
            unreal.Vector(cx, cy, 16.0),
            rot=unreal.Rotator(0.0, 0.0, 0.0),
            scale=unreal.Vector(1.0, 1.0, 1.0),
            mat=None,  # keep SM_Tripo_HeavyDropship embedded M_Tripo_HeavyDropship
            collision="NoCollision",
            affect_nav=False,
        )
    else:
        warn("SM_Tripo_HeavyDropship missing! Run Tools/import_inc10_tripo.py first.")

    # Invisible structural colliders for Tripo nose & outrigger thruster nacelles (clear of interior bay)
    for c_name, cloc, cscale in (
        ("Col_Nose", unreal.Vector(cx - 475.0, cy, 160.0), unreal.Vector(2.8, 3.8, 3.0)),
        ("Col_ThrusterPort", unreal.Vector(cx + 390.0, cy - 335.0, 130.0), unreal.Vector(3.4, 2.0, 2.4)),
        ("Col_ThrusterStbd", unreal.Vector(cx + 390.0, cy + 335.0, 130.0), unreal.Vector(3.4, 2.0, 2.4)),
        ("Col_RoofCap", unreal.Vector(cx, cy, 415.0), unreal.Vector(8.2, 4.6, 2.0)),
    ):
        col_a = ship_mesh(c_name, cube, cloc, scale=cscale, mat=mat_gunmetal, collision="BlockAll", affect_nav=True)
        if col_a:
            col_a.set_actor_hidden_in_game(True)
            col_a.set_is_temporarily_hidden_in_editor(True)

    # 2b. Walkable Cabin Floor Deck (top Z=40.0 clears Tripo belly shell lip completely)
    ship_mesh(
        "CabinDeck",
        cube,
        unreal.Vector(cx + 35.0, cy, 31.0),
        scale=unreal.Vector(7.50, 3.80, 0.18),
        mat=mat_deck,
        collision="BlockAll",
        affect_nav=True,
    )

    # 2c. Open East Boarding Ramp (X = -1445 -> -1235, slope down +X at -9.93 deg pitch from Z=40 to Z=0)
    ship_mesh(
        "BoardingRamp",
        cube,
        unreal.Vector(cx + 510.0, cy, 16.5),
        rot=unreal.Rotator(-9.8, 0.0, 0.0),
        scale=unreal.Vector(2.22, 2.20, 0.10),
        mat=mat_deck,
        collision="BlockAll",
        affect_nav=True,
    )
    for r_side, y_off in (("Port", -108.0), ("Starboard", 108.0)):
        ship_mesh(
            f"RampGuide_{r_side}",
            cube,
            unreal.Vector(cx + 510.0, cy + y_off, 23.0),
            rot=unreal.Rotator(-9.8, 0.0, 0.0),
            scale=unreal.Vector(2.18, 0.06, 0.04),
            mat=mat_amber_trim,
            collision="NoCollision",
            affect_nav=False,
        )

    # 2d. Sleek Pressurized Cabin Bulkhead Liners (fit wholly inside Tripo curved hull; zero protrusion outside!)
    for h_side, y_off in (("Port", -186.0), ("Starboard", 186.0)):
        ship_mesh(
            f"HullWall_{h_side}",
            cube,
            unreal.Vector(cx + 15.0, cy + y_off, 142.0),
            scale=unreal.Vector(6.70, 0.10, 2.08),
            mat=mat_gunmetal,
            collision="BlockAll",
            affect_nav=True,
        )
    # Forward dark cockpit bulkhead behind flight consoles (seals curved nose interior view)
    ship_mesh(
        "CockpitFwdBulkhead",
        cube,
        unreal.Vector(cx - 324.0, cy, 142.0),
        scale=unreal.Vector(0.14, 3.68, 2.08),
        mat=mat_gunmetal,
        collision="BlockAll",
        affect_nav=True,
    )
    for a_side, y_off in (("L", -155.0), ("R", 155.0)):
        ab = ship_mesh(
            f"AftBulkhead_{a_side}",
            cube,
            unreal.Vector(cx + 398.0, cy + y_off, 148.0),
            scale=unreal.Vector(0.22, 0.96, 2.20),
            mat=mat_gunmetal,
            collision="BlockAll",
            affect_nav=True,
        )
        if ab:
            ab.set_actor_hidden_in_game(True)
    al = ship_mesh(
        "AftHatchLintel",
        cube,
        unreal.Vector(cx + 398.0, cy, 290.0),
        scale=unreal.Vector(0.26, 2.20, 0.44),
        mat=mat_trim,
        collision="BlockAll",
        affect_nav=False,
    )
    if al:
        al.set_actor_hidden_in_game(True)
    ship_mesh(
        "AftHatchBeacon",
        cube,
        unreal.Vector(cx + 412.0, cy, 272.0),
        scale=unreal.Vector(0.05, 1.85, 0.07),
        mat=mat_amber_trim,
        collision="NoCollision",
        affect_nav=False,
    )
    rd = ship_mesh(
        "RoofDeck",
        cube,
        unreal.Vector(cx + 15.0, cy, 256.0),
        scale=unreal.Vector(6.70, 3.68, 0.14),
        mat=mat_wall,
        collision="BlockAll",
        affect_nav=False,
    )
    if rd:
        rd.set_actor_hidden_in_game(True)

    # 2h. Walkable Cockpit & Cargo Interior (center aisle around DropLocker (-1850,-900,60) stays wide open!)
    # Pilot & Co-pilot flight consoles + glowing screens + seat frames at X = -2165..-2080
    for c_side, y_off in (("Port", -92.0), ("Stbd", 92.0)):
        ship_mesh(
            f"CockpitConsole_{c_side}",
            cube,
            unreal.Vector(cx - 315.0, cy + y_off, 74.0),
            rot=unreal.Rotator(0.0, 12.0 if y_off < 0 else -12.0, 0.0),
            scale=unreal.Vector(0.56, 0.94, 0.80),
            mat=mat_gunmetal,
            collision="BlockAll",
            affect_nav=False,
        )
        ship_mesh(
            f"CockpitScreen_{c_side}_Cyan",
            cube,
            unreal.Vector(cx - 310.0, cy + y_off - 14.0, 120.0),
            rot=unreal.Rotator(-18.0, 12.0 if y_off < 0 else -12.0, 0.0),
            scale=unreal.Vector(0.03, 0.42, 0.28),
            mat=mat_cyan,
            collision="NoCollision",
            affect_nav=False,
        )
        ship_mesh(
            f"CockpitScreen_{c_side}_Amber",
            cube,
            unreal.Vector(cx - 310.0, cy + y_off + 24.0, 118.0),
            rot=unreal.Rotator(-18.0, 12.0 if y_off < 0 else -12.0, 0.0),
            scale=unreal.Vector(0.03, 0.26, 0.22),
            mat=mat_amber_trim,
            collision="NoCollision",
            affect_nav=False,
        )
        ship_mesh(
            f"PilotSeatFrame_{c_side}",
            cube,
            unreal.Vector(cx - 230.0, cy + y_off, 68.0),
            scale=unreal.Vector(0.48, 0.56, 0.68),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )

    # Port & Starboard Emergency Cryo-Lockers tucked against cabin walls (clear aisle Y in [-1040..-760])
    for l_idx, lx_off in enumerate((-80.0, 130.0)):
        for l_side, ly_off in (("Port", -178.0), ("Stbd", 178.0)):
            ship_mesh(
                f"CryoLocker_{l_side}_{l_idx:02d}",
                cube,
                unreal.Vector(cx + lx_off, cy + ly_off, 116.0),
                scale=unreal.Vector(1.20, 0.52, 1.64),
                mat=mat_gunmetal,
                collision="BlockAll",
                affect_nav=True,
            )
            ship_mesh(
                f"CryoLockerStrip_{l_side}_{l_idx:02d}",
                cube,
                unreal.Vector(cx + lx_off, cy + ly_off + (27.5 if ly_off < 0 else -27.5), 148.0),
                scale=unreal.Vector(0.96, 0.03, 0.10),
                mat=mat_amber_trim if l_idx == 0 else mat_cyan,
                collision="NoCollision",
                affect_nav=False,
            )

    # Interior warm-amber cargo floodlight + cockpit cyan instrument light (both tagged 'DropShip')
    l_cargo = spawn_point_light(
        "DropShip_Light_Cargo",
        unreal.Vector(cx + 40.0, cy, 265.0),
        unreal.Color(255, 192, 124, 255),
        1450.0,
        560.0,
    )
    if l_cargo:
        l_cargo.tags.append("DropShip")
    l_cockpit = spawn_point_light(
        "DropShip_Light_Cockpit",
        unreal.Vector(cx - 265.0, cy, 185.0),
        unreal.Color(145, 225, 255, 255),
        820.0,
        380.0,
    )
    if l_cockpit:
        l_cockpit.tags.append("DropShip")

    log(f"Built Enterable DropShip Compound & octagonal scarred burn pad at ({cx:.0f}, {cy:.0f}, 0)")


def spawn_conduit_run(label_prefix, points, radius=4.0, z=4.0, mat=None, junction_mat=None):
    """Place ground-hugging or overhead cylinder conduit segments between 2D/3D points."""
    cyl = unreal.load_object(None, "/Engine/BasicShapes/Cylinder.Cylinder")
    cube = unreal.load_object(None, "/Engine/BasicShapes/Cube.Cube")
    if not cyl:
        return
    for idx in range(len(points) - 1):
        p0 = points[idx]
        p1 = points[idx + 1]
        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        dz = (p1[2] if len(p1) > 2 else z) - (p0[2] if len(p0) > 2 else z)
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length < 2.0:
            continue
        mx = 0.5 * (p0[0] + p1[0])
        my = 0.5 * (p0[1] + p1[1])
        mz = 0.5 * ((p0[2] if len(p0) > 2 else z) + (p1[2] if len(p1) > 2 else z))
        yaw = math.degrees(math.atan2(dy, dx))
        xy_len = math.hypot(dx, dy)
        pitch = math.degrees(math.atan2(dz, xy_len)) - 90.0
        d_scale = (radius * 2.0) / 100.0
        spawn_static_mesh(
            f"{label_prefix}_Seg_{idx:02d}",
            cyl,
            unreal.Vector(mx, my, mz),
            unreal.Rotator(pitch, yaw, 0.0),
            unreal.Vector(d_scale, d_scale, length / 100.0),
            mat=mat,
            collision="NoCollision",
            affect_nav=False,
        )
    if cube and junction_mat:
        for idx, pt in enumerate(points):
            pz = pt[2] if len(pt) > 2 else z
            spawn_static_mesh(
                f"{label_prefix}_Junc_{idx:02d}",
                cube,
                unreal.Vector(pt[0], pt[1], pz + 3.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(0.24, 0.24, 0.12),
                mat=junction_mat,
                collision="NoCollision",
                affect_nav=False,
            )


def spawn_interior_architecture():
    """Add Habitat/Corridor/Greenhouse ceiling ribs, trusses, overhead conduits, airlock strips,
    workstation desks/screens, hydroponic grow-bed frames & grow-light bars, and gallery showcases."""
    cube = unreal.load_object(None, "/Engine/BasicShapes/Cube.Cube")
    cyl = unreal.load_object(None, "/Engine/BasicShapes/Cylinder.Cylinder")
    if not cube or not cyl:
        return

    mat_ceil = ensure_simple_material(
        "/Game/Environment/Materials/M_Habitat_Ceiling",
        base_rgb=(0.074, 0.086, 0.106),
        metallic=0.40,
        roughness=0.46,
        overwrite=False,
    )
    mat_trim = ensure_simple_material(
        "/Game/Environment/Materials/M_Habitat_Trim",
        base_rgb=(0.095, 0.108, 0.128),
        metallic=0.76,
        roughness=0.38,
        overwrite=False,
    )
    mat_gunmetal = ensure_simple_material(
        "/Game/Environment/Materials/M_Metal_Gunmetal",
        base_rgb=(0.068, 0.076, 0.092),
        metallic=0.78,
        roughness=0.38,
        overwrite=False,
    )
    mat_copper = ensure_simple_material(
        "/Game/Environment/Materials/M_ConduitCopper",
        base_rgb=(0.68, 0.36, 0.16),
        metallic=0.86,
        roughness=0.30,
    )
    mat_cyan = ensure_simple_material(
        "/Game/Environment/Materials/M_AccentCyan",
        base_rgb=(0.08, 0.45, 0.62),
        metallic=0.15,
        roughness=0.20,
        emissive_rgb=(0.14, 0.85, 1.15),
    )
    mat_amber = ensure_simple_material(
        "/Game/Environment/Materials/M_AccentAmber",
        base_rgb=(0.82, 0.42, 0.08),
        metallic=0.15,
        roughness=0.22,
        emissive_rgb=(1.35, 0.58, 0.10),
    )
    mat_emerald = ensure_simple_material(
        "/Game/Environment/Materials/M_AccentEmerald",
        base_rgb=(0.10, 0.58, 0.38),
        metallic=0.15,
        roughness=0.20,
        emissive_rgb=(0.18, 1.15, 0.68),
    )
    mat_grow_warm = ensure_simple_material(
        "/Game/Environment/Materials/M_GrowBarWarm",
        base_rgb=(0.95, 0.78, 0.52),
        metallic=0.10,
        roughness=0.25,
        emissive_rgb=(1.45, 1.05, 0.62),
    )
    mat_grow_uv = ensure_simple_material(
        "/Game/Environment/Materials/M_GrowBarUV",
        base_rgb=(0.78, 0.35, 0.92),
        metallic=0.10,
        roughness=0.25,
        emissive_rgb=(1.15, 0.34, 1.75),
    )

    # 1. Architectural Ceiling Structural Ribs, Coffer Inlays & Knee Braces
    # Habitat ceiling inlay & ribs (X: -880..-120, Y: -480..480, roof underside Z=300)
    spawn_static_mesh(
        "Arch_Habitat_CeilingInlay",
        cube,
        unreal.Vector(-500.0, 0.0, 297.5),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(7.50, 9.50, 0.04),
        mat=mat_ceil,
        collision="NoCollision",
        affect_nav=False,
    )
    for idx, rx in enumerate((-760.0, -580.0, -400.0, -220.0)):
        spawn_static_mesh(
            f"Arch_Habitat_CeilingRib_{idx:02d}",
            cube,
            unreal.Vector(rx, 0.0, 286.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.22, 9.56, 0.22),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )
        for side_lbl, sy, pitch_dir in (("N", 460.0, -45.0), ("S", -460.0, 45.0)):
            spawn_static_mesh(
                f"Arch_Habitat_KneeBrace_{idx:02d}_{side_lbl}",
                cube,
                unreal.Vector(rx, sy, 260.0),
                unreal.Rotator(0.0, 0.0, pitch_dir),
                unreal.Vector(0.18, 0.62, 0.14),
                mat=mat_trim,
                collision="NoCollision",
                affect_nav=False,
            )
    for side_lbl, ly in (("S", -260.0), ("N", 260.0)):
        spawn_static_mesh(
            f"Arch_Habitat_LongBeam_{side_lbl}",
            cube,
            unreal.Vector(-500.0, ly, 289.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(7.56, 0.18, 0.16),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )
        spawn_static_mesh(
            f"Arch_Habitat_LightCove_{side_lbl}",
            cube,
            unreal.Vector(-500.0, ly * 0.94, 280.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(6.40, 0.05, 0.03),
            mat=mat_cyan,
            collision="NoCollision",
            affect_nav=False,
        )

    # Corridor ceiling inlay & arch ribs (X: -120..120, Y: -130..130)
    spawn_static_mesh(
        "Arch_Corridor_CeilingInlay",
        cube,
        unreal.Vector(0.0, 0.0, 297.5),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(2.36, 2.56, 0.04),
        mat=mat_ceil,
        collision="NoCollision",
        affect_nav=False,
    )
    for idx, cx in enumerate((-80.0, 0.0, 80.0)):
        spawn_static_mesh(
            f"Arch_Corridor_Rib_{idx:02d}",
            cube,
            unreal.Vector(cx, 0.0, 286.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.16, 2.56, 0.20),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )
        for side_lbl, sy in (("N", 122.0), ("S", -122.0)):
            spawn_static_mesh(
                f"Arch_Corridor_Pilaster_{idx:02d}_{side_lbl}",
                cube,
                unreal.Vector(cx, sy, 146.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(0.16, 0.14, 2.92),
                mat=mat_trim,
                collision="NoCollision",
                affect_nav=False,
            )

    # Greenhouse skylight arch trusses (X: 120..880, Y: -480..480, glass roof Z=295)
    for idx, gx in enumerate((250.0, 500.0, 750.0)):
        spawn_static_mesh(
            f"Arch_Greenhouse_Truss_{idx:02d}",
            cube,
            unreal.Vector(gx, 0.0, 284.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.20, 9.56, 0.18),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )
        for side_lbl, sy in (("N", 470.0), ("S", -470.0)):
            spawn_static_mesh(
                f"Arch_Greenhouse_Stanchion_{idx:02d}_{side_lbl}",
                cube,
                unreal.Vector(gx, sy, 146.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(0.18, 0.18, 2.92),
                mat=mat_trim,
                collision="NoCollision",
                affect_nav=False,
            )
    for side_lbl, gy in (("N", 470.0), ("S", -470.0)):
        spawn_static_mesh(
            f"Arch_Greenhouse_Cornice_{side_lbl}",
            cube,
            unreal.Vector(500.0, gy, 284.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(7.56, 0.18, 0.18),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )

    # 2. Overhead Conduit Pipes (Habitat -> Corridor -> Greenhouse)
    spawn_conduit_run("Conduit_Hab_North_Copper", [(-860.0, 446.0, 264.0), (-120.0, 446.0, 264.0)], radius=4.5, mat=mat_copper)
    spawn_conduit_run("Conduit_Hab_North_Steel", [(-860.0, 446.0, 248.0), (-120.0, 446.0, 248.0)], radius=3.2, mat=mat_trim)
    spawn_conduit_run("Conduit_Hab_South_Copper", [(-860.0, -446.0, 264.0), (-120.0, -446.0, 264.0)], radius=4.5, mat=mat_copper)
    spawn_conduit_run("Conduit_Hab_South_Steel", [(-860.0, -446.0, 248.0), (-120.0, -446.0, 248.0)], radius=3.2, mat=mat_trim)
    spawn_conduit_run("Conduit_Hab_Cross_W", [(-670.0, -446.0, 274.0), (-670.0, 446.0, 274.0)], radius=3.5, mat=mat_trim)
    spawn_conduit_run("Conduit_Hab_Cross_E", [(-310.0, -446.0, 274.0), (-310.0, 446.0, 274.0)], radius=3.5, mat=mat_copper)
    spawn_conduit_run("Conduit_Corr_N", [(-125.0, 112.0, 266.0), (125.0, 112.0, 266.0)], radius=3.8, mat=mat_copper)
    spawn_conduit_run("Conduit_Corr_S", [(-125.0, -112.0, 266.0), (125.0, -112.0, 266.0)], radius=3.8, mat=mat_trim)
    spawn_conduit_run("Conduit_GH_North", [(120.0, 446.0, 264.0), (860.0, 446.0, 264.0)], radius=4.0, mat=mat_copper)
    spawn_conduit_run("Conduit_GH_South", [(120.0, -446.0, 264.0), (860.0, -446.0, 264.0)], radius=4.0, mat=mat_trim)

    # 3. Airlock & Bulkhead Accent Frame Strips
    # West Airlock at X=-900 (clear doorway Y in [-112, 112])
    for side_lbl, ay in (("N", 126.0), ("S", -126.0)):
        spawn_static_mesh(
            f"Airlock_West_Jamb_{side_lbl}",
            cube,
            unreal.Vector(-900.0, ay, 148.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.52, 0.24, 2.96),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )
        for face_lbl, fx in (("In", -873.0), ("Out", -927.0)):
            spawn_static_mesh(
                f"Airlock_West_Strip_{side_lbl}_{face_lbl}",
                cube,
                unreal.Vector(fx, ay * 0.90, 136.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(0.04, 0.06, 2.36),
                mat=mat_amber,
                collision="NoCollision",
                affect_nav=False,
            )
    spawn_static_mesh(
        "Airlock_West_Lintel",
        cube,
        unreal.Vector(-900.0, 0.0, 278.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(0.56, 2.76, 0.42),
        mat=mat_trim,
        collision="NoCollision",
        affect_nav=False,
    )
    for face_lbl, fx in (("In", -871.0), ("Out", -929.0)):
        spawn_static_mesh(
            f"Airlock_West_HeaderStrip_{face_lbl}",
            cube,
            unreal.Vector(fx, 0.0, 260.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.04, 1.70, 0.05),
            mat=mat_amber,
            collision="NoCollision",
            affect_nav=False,
        )

    # Interior Corridor Transition Frames (X = -100 and X = +100)
    for b_lbl, bx in (("HabToCorr", -100.0), ("CorrToGH", 100.0)):
        for side_lbl, by in (("N", 136.0), ("S", -136.0)):
            spawn_static_mesh(
                f"Bulkhead_{b_lbl}_Jamb_{side_lbl}",
                cube,
                unreal.Vector(bx, by, 148.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(0.46, 0.18, 2.96),
                mat=mat_trim,
                collision="NoCollision",
                affect_nav=False,
            )
            spawn_static_mesh(
                f"Bulkhead_{b_lbl}_Strip_{side_lbl}",
                cube,
                unreal.Vector(bx, by * 0.92, 140.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(0.48, 0.04, 2.30),
                mat=mat_cyan,
                collision="NoCollision",
                affect_nav=False,
            )
        spawn_static_mesh(
            f"Bulkhead_{b_lbl}_Lintel",
            cube,
            unreal.Vector(bx, 0.0, 278.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.48, 2.90, 0.42),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )

    # 4. Illuminated Workstation Desks & Telemetry Screens beside Terminals
    def spawn_workstation(name, wx, wy, facing_yaw, desk_w=108.0, screen_mat=mat_cyan,
                          light_col=unreal.Color(125, 228, 255, 255), exterior=False):
        rad = math.radians(facing_yaw)
        fx, fy = math.cos(rad), math.sin(rad)
        rx, ry = -fy, fx
        # Tabletop at Z=76
        spawn_static_mesh(
            f"{name}_Top",
            cube,
            unreal.Vector(wx, wy, 76.0),
            unreal.Rotator(0.0, facing_yaw, 0.0),
            unreal.Vector(0.50, desk_w / 100.0, 0.05),
            mat=mat_gunmetal,
            collision="NoCollision",
            affect_nav=False,
        )
        # Support legs
        for side_lbl, sign in (("L", -1.0), ("R", 1.0)):
            lx = wx + rx * (desk_w * 0.42 * sign)
            ly = wy + ry * (desk_w * 0.42 * sign)
            spawn_static_mesh(
                f"{name}_Leg_{side_lbl}",
                cube,
                unreal.Vector(lx, ly, 38.0),
                unreal.Rotator(0.0, facing_yaw, 0.0),
                unreal.Vector(0.44, 0.06, 0.74),
                mat=mat_trim,
                collision="NoCollision",
                affect_nav=False,
            )
        # Dual-monitor bezel + illuminated screen offset slightly toward back edge
        mx = wx - fx * 14.0
        my = wy - fy * 14.0
        spawn_static_mesh(
            f"{name}_Bezel",
            cube,
            unreal.Vector(mx, my, 102.0),
            unreal.Rotator(-10.0, facing_yaw, 0.0),
            unreal.Vector(0.04, 0.76, 0.38),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )
        spawn_static_mesh(
            f"{name}_Screen",
            cube,
            unreal.Vector(mx + fx * 2.2, my + fy * 2.2, 102.5),
            unreal.Rotator(-10.0, facing_yaw, 0.0),
            unreal.Vector(0.02, 0.68, 0.31),
            mat=screen_mat,
            collision="NoCollision",
            affect_nav=False,
        )
        # Keyboard console deck
        spawn_static_mesh(
            f"{name}_Keyboard",
            cube,
            unreal.Vector(wx + fx * 10.0, wy + fy * 10.0, 79.5),
            unreal.Rotator(0.0, facing_yaw, 0.0),
            unreal.Vector(0.18, 0.44, 0.025),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )
        l_prefix = "PointLight_ExtWorkstation_" if exterior else "PointLight_Workstation_"
        spawn_point_light(
            f"{l_prefix}{name}",
            unreal.Vector(wx + fx * 24.0, wy + fy * 24.0, 118.0),
            light_col,
            440.0,
            220.0,
        )

    # Beside Habitat Log Terminal (-600, -460) facing +Y (yaw=90)
    spawn_workstation("HabSouth", -685.0, -452.0, 90.0, desk_w=108.0, screen_mat=mat_cyan)
    # Habitat North Science Desk (-520, 448) facing -Y (yaw=-90)
    spawn_workstation("HabNorth", -520.0, 448.0, -90.0, desk_w=120.0, screen_mat=mat_cyan)
    # Beside Exterior Comms Relay Terminal (2450, -150) facing +Y (yaw=90)
    spawn_workstation("CommsField", 2375.0, -165.0, 90.0, desk_w=84.0, screen_mat=mat_amber,
                      light_col=unreal.Color(255, 195, 110, 255), exterior=True)

    # 5. Hydroponic Grow-Bed Metallic Frames & Warm/UV Grow-Light Bars in Greenhouse
    grow_beds = ((400.0, -200.0), (400.0, 200.0), (700.0, -200.0), (700.0, 200.0))
    for idx, (bx, by) in enumerate(grow_beds):
        # 4 corner steel gantry posts outside the 150x150cm plant tray
        for cx_s in (-1.0, 1.0):
            for cy_s in (-1.0, 1.0):
                px = bx + cx_s * 84.0
                py = by + cy_s * 84.0
                spawn_static_mesh(
                    f"GrowBed_{idx:02d}_Post_{int(cx_s)}_{int(cy_s)}",
                    cube,
                    unreal.Vector(px, py, 106.0),
                    unreal.Rotator(0.0, 0.0, 0.0),
                    unreal.Vector(0.07, 0.07, 2.12),
                    mat=mat_trim,
                    collision="NoCollision",
                    affect_nav=False,
                )
        # Top perimeter gantry frame rails (Z = 212)
        for ry_s in (-1.0, 1.0):
            spawn_static_mesh(
                f"GrowBed_{idx:02d}_RailX_{int(ry_s)}",
                cube,
                unreal.Vector(bx, by + ry_s * 84.0, 212.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(1.75, 0.07, 0.08),
                mat=mat_trim,
                collision="NoCollision",
                affect_nav=False,
            )
        for rx_s in (-1.0, 1.0):
            spawn_static_mesh(
                f"GrowBed_{idx:02d}_RailY_{int(rx_s)}",
                cube,
                unreal.Vector(bx + rx_s * 84.0, by, 212.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(0.07, 1.75, 0.08),
                mat=mat_trim,
                collision="NoCollision",
                affect_nav=False,
            )
        # Dual suspended warm & UV grow-light bars (Z = 202)
        for bar_lbl, bar_off, bar_mat in (("Warm", -24.0, mat_grow_warm), ("UV", 24.0, mat_grow_uv)):
            spawn_static_mesh(
                f"GrowBed_{idx:02d}_Housing_{bar_lbl}",
                cube,
                unreal.Vector(bx, by + bar_off, 204.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(1.46, 0.12, 0.06),
                mat=mat_trim,
                collision="NoCollision",
                affect_nav=False,
            )
            spawn_static_mesh(
                f"GrowBed_{idx:02d}_Bar_{bar_lbl}",
                cube,
                unreal.Vector(bx, by + bar_off, 200.5),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(1.38, 0.07, 0.025),
                mat=bar_mat,
                collision="NoCollision",
                affect_nav=False,
            )

    # 6. Gallery Framing around SM_Tripo_BotanicalPod (790, 0) and SM_Tripo_PulseRifle (-520, -415)
    # Botanical Pod Gallery Plinth (top Z = 14.0)
    spawn_static_mesh(
        "Gallery_BotanicalPod_Plinth",
        cyl,
        unreal.Vector(790.0, 0.0, 7.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(1.84, 1.84, 0.14),
        mat=mat_trim,
        collision="NoCollision",
        affect_nav=False,
    )
    spawn_static_mesh(
        "Gallery_BotanicalPod_AccentRing",
        cyl,
        unreal.Vector(790.0, 0.0, 12.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(1.90, 1.90, 0.025),
        mat=mat_emerald,
        collision="NoCollision",
        affect_nav=False,
    )
    for sx in (-78.0, 78.0):
        for sy in (-78.0, 78.0):
            spawn_static_mesh(
                f"Gallery_BotanicalPod_Post_{int(sx)}_{int(sy)}",
                cyl,
                unreal.Vector(790.0 + sx, sy, 36.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(0.07, 0.07, 0.72),
                mat=mat_trim,
                collision="NoCollision",
                affect_nav=False,
            )
            spawn_static_mesh(
                f"Gallery_BotanicalPod_Cap_{int(sx)}_{int(sy)}",
                cyl,
                unreal.Vector(790.0 + sx, sy, 73.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(0.08, 0.08, 0.03),
                mat=mat_emerald,
                collision="NoCollision",
                affect_nav=False,
            )

    # Pulse Rifle Armory Showcase Pedestal at (-520, -415) (cradle top Z = 84.0)
    spawn_static_mesh(
        "Gallery_PulseRifle_Base",
        cube,
        unreal.Vector(-520.0, -415.0, 6.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(1.12, 0.52, 0.12),
        mat=mat_trim,
        collision="NoCollision",
        affect_nav=False,
    )
    spawn_static_mesh(
        "Gallery_PulseRifle_Column",
        cube,
        unreal.Vector(-520.0, -415.0, 44.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(0.86, 0.32, 0.64),
        mat=mat_gunmetal,
        collision="NoCollision",
        affect_nav=False,
    )
    spawn_static_mesh(
        "Gallery_PulseRifle_TrimCollar",
        cube,
        unreal.Vector(-520.0, -415.0, 78.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(0.92, 0.36, 0.04),
        mat=mat_cyan,
        collision="NoCollision",
        affect_nav=False,
    )
    for cx_off in (-26.0, 26.0):
        spawn_static_mesh(
            f"Gallery_PulseRifle_Cradle_{int(cx_off)}",
            cube,
            unreal.Vector(-520.0 + cx_off, -415.0, 84.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.05, 0.12, 0.10),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )
    spawn_static_mesh(
        "Gallery_PulseRifle_Backboard",
        cube,
        unreal.Vector(-520.0, -445.0, 108.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(1.04, 0.05, 0.66),
        mat=mat_gunmetal,
        collision="NoCollision",
        affect_nav=False,
    )
    spawn_static_mesh(
        "Gallery_PulseRifle_BackStrip",
        cube,
        unreal.Vector(-520.0, -441.5, 138.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(0.94, 0.02, 0.03),
        mat=mat_cyan,
        collision="NoCollision",
        affect_nav=False,
    )

    # Focused gallery spotlights
    spawn_spot_light(
        "SpotLight_Gallery_BotanicalPod",
        unreal.Vector(790.0, 0.0, 276.0),
        unreal.Rotator(-90.0, 0.0, 0.0),
        unreal.Color(195, 255, 228, 255),
        3200.0,
        420.0,
        inner_cone=18.0,
        outer_cone=34.0,
    )
    spawn_spot_light(
        "SpotLight_Gallery_PulseRifle",
        unreal.Vector(-520.0, -365.0, 266.0),
        unreal.Rotator(-72.0, -90.0, 0.0),
        unreal.Color(190, 238, 255, 255),
        2800.0,
        380.0,
        inner_cone=16.0,
        outer_cone=32.0,
    )

    # 6. Greenhouse Science Stations: CRISPR Gene Sequencer (560, 430) & Sabatier Reactor (560, -430)
    crispr_mesh = EAL.load_asset("/Game/Environment/SM_CRISPR_Sequencer") if EAL.does_asset_exist("/Game/Environment/SM_CRISPR_Sequencer") else None
    sabatier_mesh = EAL.load_asset("/Game/Environment/SM_Sabatier_Reactor") if EAL.does_asset_exist("/Game/Environment/SM_Sabatier_Reactor") else None

    spawn_static_mesh(
        "Lab_Gene_Pad",
        cube,
        unreal.Vector(560.0, 458.0, 2.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(1.45, 0.78, 0.04),
        mat=mat_gunmetal,
        collision="NoCollision",
        affect_nav=False,
    )
    if crispr_mesh:
        spawn_static_mesh(
            "Lab_CRISPR_Sequencer",
            crispr_mesh,
            unreal.Vector(560.0, 464.0, 0.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(1.0, 1.0, 1.0),
            collision="NoCollision",
            affect_nav=False,
        )
    spawn_static_mesh(
        "Lab_Gene_HeaderStrip",
        cube,
        unreal.Vector(560.0, 464.0, 224.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(1.22, 0.04, 0.03),
        mat=mat_emerald,
        collision="NoCollision",
        affect_nav=False,
    )
    spawn_point_light(
        "PointLight_GeneLab",
        unreal.Vector(560.0, 395.0, 200.0),
        unreal.Color(155, 255, 215, 255),
        2200.0,
        340.0,
    )

    spawn_static_mesh(
        "Lab_Sabatier_Pad",
        cube,
        unreal.Vector(560.0, -458.0, 2.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(1.45, 0.78, 0.04),
        mat=mat_gunmetal,
        collision="NoCollision",
        affect_nav=False,
    )
    if sabatier_mesh:
        spawn_static_mesh(
            "Lab_Sabatier_Reactor",
            sabatier_mesh,
            unreal.Vector(560.0, -464.0, 0.0),
            unreal.Rotator(0.0, 180.0, 0.0),
            unreal.Vector(1.0, 1.0, 1.0),
            collision="NoCollision",
            affect_nav=False,
        )
    spawn_static_mesh(
        "Lab_Sabatier_HeaderStrip",
        cube,
        unreal.Vector(560.0, -464.0, 224.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(1.22, 0.04, 0.03),
        mat=mat_cyan,
        collision="NoCollision",
        affect_nav=False,
    )
    spawn_point_light(
        "PointLight_SabatierSynth",
        unreal.Vector(560.0, -395.0, 200.0),
        unreal.Color(150, 232, 255, 255),
        2200.0,
        340.0,
    )

    # Overhead Sabatier-to-WaterPurifier copper/cyan synthesis manifold pipe (Z=268, well above player headroom)
    spawn_conduit_run(
        "Lab_Conduit_SabatierPurifier",
        [(-300.0, 400.0), (-300.0, 80.0), (140.0, 80.0), (140.0, -360.0), (560.0, -360.0), (560.0, -430.0)],
        radius=3.5,
        z=268.0,
        mat=mat_copper,
        junction_mat=mat_cyan,
    )
    log("Built interior ceiling ribs, trusses, conduits, airlock strips, workstations, grow frames, lab stations & gallery showcases")


def spawn_exterior_outpost_upgrade():
    """Frame SM_Tripo_OxygenHarvester (-1080, 460) and SM_Tripo_SentryTurret (-1060, -320) guarding the west approach
    with floodlit barricade bollards and clean power conduit links, clear of NavMesh paths and DropLander pad."""
    cube = unreal.load_object(None, "/Engine/BasicShapes/Cube.Cube")
    cyl = unreal.load_object(None, "/Engine/BasicShapes/Cylinder.Cylinder")
    if not cube or not cyl:
        return

    mat_deck = ensure_simple_material(
        "/Game/Environment/Materials/M_OutpostDeck",
        base_rgb=(0.20, 0.22, 0.25),
        metallic=0.65,
        roughness=0.45,
        overwrite=False,
    )
    mat_trim = ensure_simple_material(
        "/Game/Environment/Materials/M_Habitat_Trim",
        base_rgb=(0.095, 0.108, 0.128),
        metallic=0.76,
        roughness=0.38,
        overwrite=False,
    )
    mat_gunmetal = ensure_simple_material(
        "/Game/Environment/Materials/M_Metal_Gunmetal",
        base_rgb=(0.068, 0.076, 0.092),
        metallic=0.78,
        roughness=0.38,
        overwrite=False,
    )
    mat_amber = ensure_simple_material(
        "/Game/Environment/Materials/M_AccentAmber",
        base_rgb=(0.82, 0.42, 0.08),
        metallic=0.15,
        roughness=0.22,
        emissive_rgb=(1.35, 0.58, 0.10),
        overwrite=False,
    )
    mat_cyan = ensure_simple_material(
        "/Game/Environment/Materials/M_AccentCyan",
        base_rgb=(0.08, 0.45, 0.62),
        metallic=0.15,
        roughness=0.20,
        emissive_rgb=(0.14, 0.85, 1.15),
        overwrite=False,
    )
    mat_copper = ensure_simple_material(
        "/Game/Environment/Materials/M_ConduitCopper",
        base_rgb=(0.68, 0.36, 0.16),
        metallic=0.86,
        roughness=0.30,
        overwrite=False,
    )

    # 1. Oxygen Harvester equipment pad & corner bumper bollards at (-1080, 460)
    spawn_static_mesh(
        "Outpost_Harvester_Pad",
        cube,
        unreal.Vector(-1080.0, 460.0, 5.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(1.65, 1.65, 0.10),
        mat=mat_deck,
        collision="NoCollision",
        affect_nav=False,
    )
    for sx in (-86.0, 86.0):
        for sy in (-86.0, 86.0):
            spawn_static_mesh(
                f"Outpost_Harvester_Bollard_{int(sx)}_{int(sy)}",
                cyl,
                unreal.Vector(-1080.0 + sx, 460.0 + sy, 32.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(0.14, 0.14, 0.64),
                mat=mat_trim,
                collision="NoCollision",
                affect_nav=False,
            )
            spawn_static_mesh(
                f"Outpost_Harvester_BollardCap_{int(sx)}_{int(sy)}",
                cyl,
                unreal.Vector(-1080.0 + sx, 460.0 + sy, 66.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(0.15, 0.15, 0.06),
                mat=mat_amber,
                collision="NoCollision",
                affect_nav=False,
            )

    # 2. Sentry Turret guard bastion pad & angled barricade shields at (-1060, -320)
    spawn_static_mesh(
        "Outpost_Turret_BastionPad",
        cube,
        unreal.Vector(-1060.0, -320.0, 6.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(1.50, 1.50, 0.12),
        mat=mat_deck,
        collision="NoCollision",
        affect_nav=False,
    )
    for b_lbl, bx, by, byaw in (("SW", -1146.0, -365.0, -28.0), ("NW", -1146.0, -275.0, 28.0)):
        brad = math.radians(byaw)
        spawn_static_mesh(
            f"Outpost_Turret_Barricade_{b_lbl}",
            cube,
            unreal.Vector(bx, by, 38.0),
            unreal.Rotator(0.0, byaw, 0.0),
            unreal.Vector(0.22, 0.72, 0.76),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )
        spawn_static_mesh(
            f"Outpost_Turret_BarricadeStrip_{b_lbl}",
            cube,
            unreal.Vector(bx - 11.5 * math.cos(brad), by - 11.5 * math.sin(brad), 68.0),
            unreal.Rotator(0.0, byaw, 0.0),
            unreal.Vector(0.03, 0.56, 0.05),
            mat=mat_cyan,
            collision="NoCollision",
            affect_nav=False,
        )

    # 3. Floodlit Barricade Bollards flanking West Approach (leaving central Y in [-200, 200] wide open)
    flank_bollards = [
        ("Outpost_Bollard_N1", -970.0, 235.0, 18.0),
        ("Outpost_Bollard_N2", -1045.0, 285.0, 25.0),
        ("Outpost_Bollard_N3", -1135.0, 340.0, 32.0),
        ("Outpost_Bollard_S1", -970.0, -235.0, -18.0),
        ("Outpost_Bollard_S2", -1045.0, -258.0, -22.0),
    ]
    for b_lbl, bx, by, byaw in flank_bollards:
        brad = math.radians(byaw)
        spawn_static_mesh(
            b_lbl,
            cube,
            unreal.Vector(bx, by, 42.0),
            unreal.Rotator(0.0, byaw, 0.0),
            unreal.Vector(0.24, 0.52, 0.84),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )
        spawn_static_mesh(
            f"{b_lbl}_LightBar",
            cube,
            unreal.Vector(bx - 12.5 * math.cos(brad), by - 12.5 * math.sin(brad), 76.0),
            unreal.Rotator(0.0, byaw, 0.0),
            unreal.Vector(0.03, 0.40, 0.06),
            mat=mat_amber,
            collision="NoCollision",
            affect_nav=False,
        )

    # Twin Outpost Floodlight Towers at (-952, ±245) aiming out across the West Combat Yard
    for s_lbl, fy, fyaw in (("S", -245.0, 172.0), ("N", 245.0, -172.0)):
        spawn_static_mesh(
            f"Outpost_FloodTower_{s_lbl}",
            cyl,
            unreal.Vector(-952.0, fy, 118.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.16, 0.16, 2.36),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )
        spawn_static_mesh(
            f"Outpost_FloodHead_{s_lbl}",
            cube,
            unreal.Vector(-960.0, fy, 232.0),
            unreal.Rotator(-20.0, fyaw, 0.0),
            unreal.Vector(0.28, 0.36, 0.16),
            mat=mat_amber,
            collision="NoCollision",
            affect_nav=False,
        )
        spawn_spot_light(
            f"SpotLight_Outpost_West_{s_lbl}",
            unreal.Vector(-968.0, fy, 230.0),
            unreal.Rotator(-22.0, fyaw, 0.0),
            unreal.Color(255, 205, 145, 255),
            1800.0,
            1250.0,
            inner_cone=24.0,
            outer_cone=48.0,
        )

    # 4. Clean Power Conduit Links (all verified > 600 cm from DropLander Pad)
    spawn_conduit_run(
        "Outpost_Conduit_TurretWater",
        [(-900.0, -320.0), (-1060.0, -320.0), (-1300.0, -140.0), (-1300.0, -350.0)],
        radius=4.5,
        z=4.0,
        mat=mat_copper,
        junction_mat=mat_trim,
    )
    spawn_conduit_run(
        "Outpost_Conduit_HarvesterPipe",
        [(-900.0, 460.0), (-1080.0, 460.0), (-1260.0, 350.0), (-1400.0, 350.0)],
        radius=4.5,
        z=4.0,
        mat=mat_trim,
        junction_mat=mat_trim,
    )
    spawn_conduit_run(
        "Outpost_Conduit_SolarHDU",
        [(-1020.0, -1260.0), (-680.0, -1320.0), (-720.0, -830.0), (-840.0, -500.0)],
        radius=4.5,
        z=4.0,
        mat=mat_copper,
        junction_mat=mat_trim,
    )

    # 5. Interconnected Exterior Science & Defense Compounds + Basin-Rim Caldera Cliffs
    sphere = unreal.load_object(None, "/Engine/BasicShapes/Sphere.Sphere")
    mat_wall = ensure_simple_material(
        "/Game/Environment/Materials/M_Habitat_Wall",
        base_rgb=(0.145, 0.165, 0.195),
        metallic=0.35,
        roughness=0.52,
        overwrite=False,
    )
    mat_emerald = ensure_simple_material(
        "/Game/Environment/Materials/M_AccentEmerald",
        base_rgb=(0.10, 0.58, 0.38),
        metallic=0.15,
        roughness=0.20,
        emissive_rgb=(0.18, 1.15, 0.68),
        overwrite=False,
    )
    mat_ice = ensure_simple_material(
        "/Game/Environment/Materials/M_MarsIceCrystal",
        base_rgb=(0.45, 0.85, 1.0),
        metallic=0.15,
        roughness=0.18,
        emissive_rgb=(0.18, 0.55, 0.85),
        overwrite=False,
    )
    mat_rock = EAL.load_asset("/Game/Environment/Materials/M_MarsRock_01") if EAL.does_asset_exist("/Game/Environment/Materials/M_MarsRock_01") else None

    cryo_mesh = EAL.load_asset("/Game/Environment/SM_Cryo_DrillRig") if EAL.does_asset_exist("/Game/Environment/SM_Cryo_DrillRig") else None
    comms_mesh = EAL.load_asset("/Game/Environment/SM_Comms_DishTower") if EAL.does_asset_exist("/Game/Environment/SM_Comms_DishTower") else None
    solar_rack_mesh = EAL.load_asset("/Game/Environment/SM_Solar_DustRack") if EAL.does_asset_exist("/Game/Environment/SM_Solar_DustRack") else None
    cliff_mesh = EAL.load_asset("/Game/Environment/SM_Mars_BasaltCliff") if EAL.does_asset_exist("/Game/Environment/SM_Mars_BasaltCliff") else None
    rock01_mesh = EAL.load_asset("/Game/Environment/SM_MarsRock_01") if EAL.does_asset_exist("/Game/Environment/SM_MarsRock_01") else None
    rock02_mesh = EAL.load_asset("/Game/Environment/SM_MarsRock_02") if EAL.does_asset_exist("/Game/Environment/SM_MarsRock_02") else None

    # 5a. South Cryo-Ice Mining Rig & Sabatier Pipeline around CryoRig (0, -2100, 60)
    spawn_static_mesh(
        "CryoCompound_Pad",
        cube,
        unreal.Vector(0.0, -2100.0, 4.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(5.6, 5.6, 0.08),
        mat=mat_deck,
        collision="NoCollision",
        affect_nav=False,
    )
    if cryo_mesh:
        spawn_static_mesh(
            "CryoCompound_DrillRig",
            cryo_mesh,
            unreal.Vector(0.0, -2280.0, 0.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(1.0, 1.0, 1.0),
            collision="BlockAll",
            affect_nav=True,
        )
    if sphere:
        spawn_static_mesh(
            "CryoCompound_IceCore",
            sphere,
            unreal.Vector(0.0, -2240.0, 6.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(1.6, 1.4, 0.28),
            mat=mat_ice,
            collision="NoCollision",
            affect_nav=False,
        )
        for t_lbl, tx in (("W", -230.0), ("E", 230.0)):
            spawn_static_mesh(
                f"CryoCompound_TankCradle_{t_lbl}",
                cube,
                unreal.Vector(tx, -2120.0, 34.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(1.10, 1.10, 0.68),
                mat=mat_gunmetal,
                collision="BlockAll",
                affect_nav=True,
            )
            spawn_static_mesh(
                f"CryoCompound_H2OSphere_{t_lbl}",
                sphere,
                unreal.Vector(tx, -2120.0, 108.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(1.32, 1.32, 1.32),
                mat=mat_wall,
                collision="BlockAll",
                affect_nav=True,
            )
            spawn_static_mesh(
                f"CryoCompound_H2OCollar_{t_lbl}",
                cyl,
                unreal.Vector(tx, -2120.0, 108.0),
                unreal.Rotator(0.0, 0.0, 0.0),
                unreal.Vector(1.36, 1.36, 0.08),
                mat=mat_cyan,
                collision="NoCollision",
                affect_nav=False,
            )
    for b_lbl, bx, by, l_int in (
        ("NW", -265.0, -1835.0, 520.0),
        ("NE", 265.0, -1835.0, 520.0),
        ("SW", -265.0, -2365.0, 0.0),
        ("SE", 265.0, -2365.0, 0.0),
    ):
        spawn_beacon_pylon(
            f"CryoCompound_Bollard_{b_lbl}",
            bx,
            by,
            beacon_rgb=(1.0, 0.60, 0.14),
            emissive_rgb=(1.55, 0.72, 0.12),
            mat_alloy=mat_trim,
            mat_beacon=mat_amber,
            light_intensity=l_int,
            height=92.0,
            light_radius=460.0,
        )
    # Elevated Sabatier pipeline trestle offset along X=-75 (keeps X=0 player corridor wide open)
    spawn_conduit_run(
        "CryoCompound_Pipeline",
        [(-75.0, -1930.0), (-75.0, -540.0)],
        radius=9.0,
        z=185.0,
        mat=mat_wall,
        junction_mat=mat_cyan,
    )
    for st_idx, st_y in enumerate((-1820.0, -1480.0, -1140.0, -800.0, -560.0), start=1):
        spawn_static_mesh(
            f"CryoCompound_TrestleLeg_{st_idx:02d}",
            cube,
            unreal.Vector(-75.0, st_y, 92.5),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.18, 0.18, 1.85),
            mat=mat_gunmetal,
            collision="BlockAll",
            affect_nav=True,
        )
        spawn_static_mesh(
            f"CryoCompound_TrestleCollar_{st_idx:02d}",
            cube,
            unreal.Vector(-75.0, st_y, 185.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.32, 0.24, 0.24),
            mat=mat_amber,
            collision="NoCollision",
            affect_nav=False,
        )
    spawn_point_light(
        "PointLight_CryoCompound_Rig",
        unreal.Vector(0.0, -2100.0, 290.0),
        unreal.Color(140, 225, 255, 255),
        4600.0,
        1050.0,
    )

    # 5b. East Deep-Space Comms Array & Radar around CommsSub (2000, 400, 60)
    spawn_static_mesh(
        "CommsCompound_Pad",
        cube,
        unreal.Vector(2000.0, 400.0, 4.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(5.6, 5.0, 0.08),
        mat=mat_deck,
        collision="NoCollision",
        affect_nav=False,
    )
    if comms_mesh:
        spawn_static_mesh(
            "CommsCompound_DishTower",
            comms_mesh,
            unreal.Vector(2165.0, 550.0, 0.0),
            unreal.Rotator(0.0, -135.0, 0.0),
            unreal.Vector(1.0, 1.0, 1.0),
            collision="BlockAll",
            affect_nav=True,
        )
    spawn_static_mesh(
        "CommsCompound_Shelter",
        cube,
        unreal.Vector(1815.0, 540.0, 110.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(2.20, 1.65, 2.20),
        mat=mat_gunmetal,
        collision="BlockAll",
        affect_nav=True,
    )
    spawn_static_mesh(
        "CommsCompound_ShelterRoofTrim",
        cube,
        unreal.Vector(1815.0, 540.0, 224.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(2.30, 1.75, 0.08),
        mat=mat_trim,
        collision="NoCollision",
        affect_nav=False,
    )
    spawn_static_mesh(
        "CommsCompound_ShelterWindow",
        cube,
        unreal.Vector(1815.0, 456.0, 130.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(1.20, 0.04, 0.36),
        mat=mat_cyan,
        collision="NoCollision",
        affect_nav=False,
    )
    for a_lbl, ax in (("L", 1745.0), ("R", 1885.0)):
        spawn_static_mesh(
            f"CommsCompound_Antenna_{a_lbl}",
            cyl,
            unreal.Vector(ax, 540.0, 290.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.05, 0.05, 1.40),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )
    for b_lbl, bx, by in (("SW", 1740.0, 175.0), ("SE", 2260.0, 175.0)):
        spawn_beacon_pylon(
            f"CommsCompound_Beacon_{b_lbl}",
            bx,
            by,
            beacon_rgb=(0.20, 0.85, 1.0),
            emissive_rgb=(0.25, 1.45, 2.0),
            mat_alloy=mat_trim,
            mat_beacon=mat_cyan,
            light_intensity=520.0,
            height=98.0,
            light_radius=460.0,
        )
    for r_idx, (rx, ry, ryaw, r_mesh) in enumerate(
        (
            (1760.0, 210.0, 28.0, rock01_mesh),
            (2230.0, 240.0, 142.0, rock02_mesh or rock01_mesh),
        ),
        start=1,
    ):
        if r_mesh:
            spawn_static_mesh(
                f"CommsCompound_CoverRock_{r_idx:02d}",
                r_mesh,
                unreal.Vector(rx, ry, -8.0),
                unreal.Rotator(0.0, ryaw, 0.0),
                unreal.Vector(0.65, 0.65, 0.58),
                mat=mat_rock,
                collision="BlockAll",
                affect_nav=True,
            )
    spawn_point_light(
        "PointLight_CommsCompound_Array",
        unreal.Vector(2000.0, 400.0, 310.0),
        unreal.Color(150, 235, 255, 255),
        4400.0,
        1050.0,
    )

    # 5c. NW Solar Farm & Rover Maintenance Pad around SolarSub (-1700, 1400, 60)
    spawn_static_mesh(
        "SolarCompound_Pad",
        cube,
        unreal.Vector(-1700.0, 1400.0, 4.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(7.4, 5.6, 0.08),
        mat=mat_deck,
        collision="NoCollision",
        affect_nav=False,
    )
    if solar_rack_mesh:
        rack_idx = 1
        for ry in (1160.0, 1640.0):
            for rx in (-1960.0, -1700.0, -1440.0):
                spawn_static_mesh(
                    f"SolarCompound_Rack_{rack_idx:02d}",
                    solar_rack_mesh,
                    unreal.Vector(rx, ry, 0.0),
                    unreal.Rotator(0.0, 165.0, 0.0),
                    unreal.Vector(1.0, 1.0, 1.0),
                    collision="BlockAll",
                    affect_nav=True,
                )
                rack_idx += 1
    for b_idx, by in enumerate((1340.0, 1460.0), start=1):
        spawn_static_mesh(
            f"SolarCompound_BatteryBank_{b_idx:02d}",
            cube,
            unreal.Vector(-2020.0, by, 58.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.95, 0.85, 1.16),
            mat=mat_gunmetal,
            collision="BlockAll",
            affect_nav=True,
        )
        spawn_static_mesh(
            f"SolarCompound_BatteryStrip_{b_idx:02d}",
            cube,
            unreal.Vector(-1971.0, by, 92.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.03, 0.62, 0.05),
            mat=mat_emerald,
            collision="NoCollision",
            affect_nav=False,
        )
    for b_lbl, by in (("S", 1210.0), ("N", 1590.0)):
        spawn_static_mesh(
            f"SolarCompound_BlastBarrier_{b_lbl}",
            cube,
            unreal.Vector(-2090.0, by, 55.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.32, 1.75, 1.10),
            mat=mat_trim,
            collision="BlockAll",
            affect_nav=True,
        )
        spawn_static_mesh(
            f"SolarCompound_FloodPole_{b_lbl}",
            cyl,
            unreal.Vector(-1360.0, by, 130.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(0.14, 0.14, 2.60),
            mat=mat_trim,
            collision="NoCollision",
            affect_nav=False,
        )
        fyaw = 155.0 if b_lbl == "S" else -155.0
        spawn_spot_light(
            f"SpotLight_SolarCompound_{b_lbl}",
            unreal.Vector(-1368.0, by, 250.0),
            unreal.Rotator(-24.0, fyaw, 0.0),
            unreal.Color(255, 215, 160, 255),
            2400.0,
            1350.0,
            inner_cone=24.0,
            outer_cone=50.0,
        )

    # 5d. Inter-compound power conduits (all kept > 760 cm from DropShip center (-1850, -900))
    spawn_conduit_run(
        "Outpost_Conduit_WestSolarLink",
        [(-1080.0, 460.0), (-1240.0, 960.0), (-1700.0, 1140.0)],
        radius=4.5,
        z=4.0,
        mat=mat_copper,
        junction_mat=mat_trim,
    )
    spawn_conduit_run(
        "Outpost_Conduit_DropShipApproach",
        [(-1060.0, -320.0), (-1060.0, -880.0)],
        radius=4.5,
        z=4.0,
        mat=mat_copper,
        junction_mat=mat_amber,
    )
    spawn_conduit_run(
        "Outpost_Conduit_EastCommsLink",
        [(900.0, 140.0), (1460.0, 140.0), (1820.0, 400.0)],
        radius=4.5,
        z=4.0,
        mat=mat_cyan,
        junction_mat=mat_trim,
    )

    # 5e. Basin-Rim Basalt Caldera Cliffs & Mesas framing the Martian valley (R ~ 3820..4380)
    if cliff_mesh:
        for idx in range(16):
            ang_deg = idx * 22.5
            ang = math.radians(ang_deg)
            radius = 3840.0 + (idx % 3) * 230.0
            cx = math.cos(ang) * radius
            cy = math.sin(ang) * radius
            s_xy = 1.15 + (idx % 4) * 0.18
            s_z = 1.20 + ((idx * 3) % 5) * 0.16
            spawn_static_mesh(
                f"BasaltCliff_{idx + 1:02d}",
                cliff_mesh,
                unreal.Vector(cx, cy, -25.0),
                unreal.Rotator(0.0, ang_deg + 180.0 + ((idx % 2) * 18.0 - 9.0), 0.0),
                unreal.Vector(s_xy, s_xy * 1.12, s_z),
                mat=mat_rock,
                collision="BlockAll",
                affect_nav=False,
            )

    log("Upgraded exterior outpost framing, 4 interconnected compounds, caldera cliffs, floodlit bollards, and power conduit links")


def spawn_inc9_mars_landmarks():
    """Place distant crater rim (SM_Mars_TerrainSkirt), 3 SM_Mars_SolarArray towers near base, and SM_Mars_RoverWreck."""
    skirt_mesh = EAL.load_asset("/Game/Environment/SM_Mars_TerrainSkirt") if EAL.does_asset_exist("/Game/Environment/SM_Mars_TerrainSkirt") else None
    solar_mesh = EAL.load_asset("/Game/Environment/SM_Mars_SolarArray") if EAL.does_asset_exist("/Game/Environment/SM_Mars_SolarArray") else None
    rover_mesh = EAL.load_asset("/Game/Environment/SM_Mars_RoverWreck") if EAL.does_asset_exist("/Game/Environment/SM_Mars_RoverWreck") else None

    # 1. Distant crater rim (SM_Mars_TerrainSkirt) surrounding the 600m arena so there is NO black horizon void
    if skirt_mesh:
        b = skirt_mesh.get_bounding_box()
        raw_radius = max(abs(b.max.x), abs(b.min.x), abs(b.max.y), abs(b.min.y), 100.0)
        s_inner = 40000.0 / raw_radius
        spawn_static_mesh(
            "SM_Mars_TerrainSkirt_Inner",
            skirt_mesh,
            unreal.Vector(0.0, 0.0, -20.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            unreal.Vector(s_inner, s_inner, s_inner * 1.15),
            collision="NoCollision",
            affect_nav=False,
        )
        s_outer = 66000.0 / raw_radius
        spawn_static_mesh(
            "SM_Mars_TerrainSkirt_Outer",
            skirt_mesh,
            unreal.Vector(0.0, 0.0, -40.0),
            unreal.Rotator(0.0, 38.0, 0.0),
            unreal.Vector(s_outer, s_outer, s_outer * 1.45),
            collision="NoCollision",
            affect_nav=False,
        )
        log(f"Placed SM_Mars_TerrainSkirt (Inner scale={s_inner:.3f}, Outer scale={s_outer:.3f})")
    else:
        warn("SM_Mars_TerrainSkirt not found in /Game/Environment/ yet")

    # 2. 3 SM_Mars_SolarArray towers near the base (relocated clear of DropLander 550cm pad & all lanes)
    if solar_mesh:
        b = solar_mesh.get_bounding_box()
        z_off = -b.min.z
        solar_placements = [
            ("SM_Mars_SolarArray_01", -1020.0, -1260.0, 25.0),
            ("SM_Mars_SolarArray_02", -680.0, -1320.0, 25.0),
            ("SM_Mars_SolarArray_03", 1160.0, -760.0, -32.0),
        ]
        for label, sx, sy, yaw in solar_placements:
            if not is_clear_of_gameplay_lanes(sx, sy):
                warn(f"Solar array {label} at ({sx}, {sy}) overlaps lane or DropLander clearance!")
                continue
            spawn_static_mesh(
                label,
                solar_mesh,
                unreal.Vector(sx, sy, z_off),
                unreal.Rotator(0.0, yaw, 0.0),
                unreal.Vector(1.0, 1.0, 1.0),
                collision="BlockAll",
                affect_nav=True,
            )
        log("Placed 3 SM_Mars_SolarArray towers clear of DropLander pad and gameplay lanes")
    else:
        warn("SM_Mars_SolarArray not found in /Game/Environment/ yet")

    # 3. SM_Mars_RoverWreck along the east/south route
    if rover_mesh:
        b = rover_mesh.get_bounding_box()
        z_off = -b.min.z - 5.0
        rover_placements = [
            ("SM_Mars_RoverWreck_SouthEast", 1040.0, -680.0, -135.0, 4.0, -6.0),
            ("SM_Mars_RoverWreck_EastRoute", 1760.0, -580.0, 145.0, -3.0, 5.0),
        ]
        for label, rx, ry, yaw, pitch, roll in rover_placements:
            if not is_clear_of_gameplay_lanes(rx, ry):
                continue
            spawn_static_mesh(
                label,
                rover_mesh,
                unreal.Vector(rx, ry, z_off),
                unreal.Rotator(pitch, yaw, roll),
                unreal.Vector(1.0, 1.0, 1.0),
                collision="BlockAll",
                affect_nav=True,
            )
        spawn_point_light(
            "PointLight_RoverWreck",
            unreal.Vector(1040.0, -680.0, 150.0),
            unreal.Color(255, 165, 85, 255),
            1800.0,
            520.0,
        )
        log("Placed SM_Mars_RoverWreck landmarks along the east/south route")
    else:
        warn("SM_Mars_RoverWreck not found in /Game/Environment/ yet")


def ensure_mars_dust_streak_material():
    """Create translucent soft-edged Martian dust streak material with zero hard edges."""
    pkg_path = "/Game/Environment/Materials/M_Mars_DustStreak"
    if EAL.does_asset_exist(pkg_path):
        mat = EAL.load_asset(pkg_path)
    else:
        mat_dir, mat_name = pkg_path.rsplit("/", 1)
        EAL.make_directory(mat_dir)
        mat = ASSET_TOOLS.create_asset(mat_name, mat_dir, unreal.Material, unreal.MaterialFactoryNew())
    if not mat:
        return None

    MEL.delete_all_material_expressions(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    mat.set_editor_property("two_sided", True)

    col_param = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -460, -240)
    col_param.set_editor_property("parameter_name", "Color")
    col_param.set_editor_property("default_value", unreal.LinearColor(0.56, 0.27, 0.14, 1.0))
    MEL.connect_material_property(col_param, "", unreal.MaterialProperty.MP_BASE_COLOR)

    em_param = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -460, -60)
    em_param.set_editor_property("parameter_name", "EmissiveColor")
    em_param.set_editor_property("default_value", unreal.LinearColor(0.08, 0.036, 0.016, 1.0))
    MEL.connect_material_property(em_param, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    rgh = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 60)
    rgh.r = 0.96
    MEL.connect_material_property(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)

    opacity_node = MEL.create_material_expression(mat, unreal.MaterialExpressionCustom, -180, 220)
    opacity_node.set_editor_property("description", "MarsDustStreakOpacity")
    opacity_node.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    opacity_node.set_editor_property(
        "code",
        """
float2 p = UV * 2.0 - 1.0;
float ellip = saturate(1.0 - dot(p * float2(1.05, 1.35), p * float2(1.05, 1.35)));
float edge = pow(ellip, 1.9);
float streak = 0.62 + 0.38 * sin(UV.x * 9.42477 + sin(UV.y * 6.28318) * 1.4);
float band = smoothstep(0.05, 0.45, UV.y) * smoothstep(0.95, 0.52, UV.y);
return saturate(edge * streak * band * Opacity);
""".strip(),
    )
    pins = []
    for key in ("UV", "Opacity"):
        pin = unreal.CustomInput()
        pin.set_editor_property("input_name", key)
        pins.append(pin)
    opacity_node.set_editor_property("inputs", pins)

    uv_expr = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -520, 200)
    if not MEL.connect_material_expressions(uv_expr, "", opacity_node, "UV"):
        raise RuntimeError("Failed wiring UV into MarsDustStreakOpacity")

    op_param = MEL.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -520, 320)
    op_param.set_editor_property("parameter_name", "Opacity")
    op_param.set_editor_property("default_value", 0.14)
    if not MEL.connect_material_expressions(op_param, "", opacity_node, "Opacity"):
        raise RuntimeError("Failed wiring Opacity into MarsDustStreakOpacity")

    MEL.connect_material_property(opacity_node, "", unreal.MaterialProperty.MP_OPACITY)
    MEL.recompile_material(mat)
    EAL.save_asset(pkg_path, only_if_is_dirty=False)
    return mat


def spawn_mars_dust_streaks():
    """Place subtle translucent drifting Martian dust-streak cards around the crater perimeter."""
    plane_mesh = EAL.load_asset("/Engine/BasicShapes/Plane.Plane")
    if not plane_mesh:
        warn("Skipping Mars dust streaks: /Engine/BasicShapes/Plane not found")
        return 0
    dust_mat = ensure_mars_dust_streak_material()
    if not dust_mat:
        return 0

    streak_placements = [
        (-3200.0, -1850.0, 75.0, 78.0, 28.0, 8.0, 9.5, 1.6),
        (-3450.0, -450.0, 95.0, 81.0, 12.0, -6.0, 10.5, 1.8),
        (-3250.0, 950.0, 110.0, 76.0, -18.0, 9.0, 9.0, 1.7),
        (-2550.0, 1950.0, 88.0, 79.0, -42.0, -5.0, 8.8, 1.5),
        (-1450.0, 2250.0, 125.0, 82.0, -76.0, 7.0, 11.0, 1.9),
        (-150.0, 2350.0, 92.0, 77.0, -92.0, -8.0, 10.2, 1.6),
        (1150.0, 2200.0, 115.0, 80.0, -118.0, 6.0, 9.4, 1.8),
        (2250.0, 1850.0, 140.0, 76.0, -142.0, -7.0, 10.8, 2.0),
        (3150.0, 1050.0, 105.0, 82.0, -168.0, 5.0, 9.6, 1.6),
        (3350.0, -250.0, 85.0, 78.0, 174.0, -6.0, 10.4, 1.7),
        (3050.0, -1450.0, 130.0, 81.0, 146.0, 8.0, 11.2, 1.9),
        (1950.0, -2100.0, 90.0, 77.0, 118.0, -5.0, 9.2, 1.5),
        (550.0, -2250.0, 118.0, 80.0, 88.0, 7.0, 10.6, 1.8),
        (-850.0, -2200.0, 78.0, 76.0, 56.0, -6.0, 8.6, 1.5),
    ]
    spawned = 0
    for idx, (x, y, z, pitch, yaw, roll, sx, sy) in enumerate(streak_placements, start=1):
        if not is_clear_of_droplander_pad(x, y, 750.0):
            continue
        if -1050.0 <= x <= 1050.0 and -650.0 <= y <= 650.0:
            continue
        actor = spawn_static_mesh(
            f"Mars_DustStreak_{idx:02d}",
            plane_mesh,
            unreal.Vector(x, y, z),
            unreal.Rotator(pitch, yaw, roll),
            unreal.Vector(sx, sy, 1.0),
            mat=dust_mat,
            collision="NoCollision",
            affect_nav=False,
        )
        if actor:
            try:
                actor.static_mesh_component.set_cast_shadow(False)
            except Exception:
                pass
            spawned += 1
    log(f"Spawned {spawned} perimeter Martian dust-streak cards")
    return spawned


def verify_droplander_pad_clearance():
    """Verify zero non-pad StaticMeshActors intersect the 760cm radius around (-1850, -900)."""
    violations = []
    for actor in ELL.get_all_level_actors():
        if actor.get_class().get_name() != "StaticMeshActor":
            continue
        label = actor.get_actor_label()
        if label.startswith(("LandingPad_", "DropShip_", "SM_Mars_TerrainSkirt", "BasaltCliff_")):
            continue
        loc = actor.get_actor_location()
        dist = math.hypot(loc.x - DROPLANDER_PAD_X, loc.y - DROPLANDER_PAD_Y)
        if dist < DROPLANDER_CLEAR_RADIUS:
            violations.append((label, dist))
    if violations:
        raise RuntimeError(f"DropShip pad {int(DROPLANDER_CLEAR_RADIUS)}cm clearance violated by: {violations}")
    log(f"Verified 0 prop collisions within {int(DROPLANDER_CLEAR_RADIUS)}cm radius of DropShip pad (-1850, -900)")


def build_map():
    world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)

    # 1. NavMeshBoundsVolume covering entire arena:
    #    X: [-4150, +3850], Y: [-2800, +2800], Z: [-400, +800]
    nav = ELL.spawn_actor_from_class(unreal.NavMeshBoundsVolume, unreal.Vector(-150.0, 0.0, 200.0))
    if nav:
        nav.set_actor_label("NavMeshBoundsVolume_Arena")
        nav.set_actor_scale3d(unreal.Vector(40.0, 28.0, 6.0))
        log("Spawned NavMeshBoundsVolume (-150, 0, 200) scale (40, 28, 6)")

    # 2. DirectionalLight: Authentic Martian solar irradiance (~43% Earth flux) with crisp shadow relief
    sun = ELL.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 1000.0), unreal.Rotator(-24.0, 38.0, 0.0))
    if sun:
        sun.set_actor_label("DirectionalLight_MarsSun")
        lc = sun.light_component
        set_prop(lc, "mobility", unreal.ComponentMobility.MOVABLE)
        set_prop(lc, "intensity", 6.2)
        set_prop(lc, "light_color", unreal.Color(255, 224, 198, 255))
        set_prop(lc, "atmosphere_sun_light", True)
        set_prop(lc, "cast_shadows", True)
        log("Spawned DirectionalLight_MarsSun")

    # 2b. Cool dusty sky-bounce fill so shaded silhouettes retain separation without washing out solar shadows
    fill_dir = ELL.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 950.0), unreal.Rotator(-38.0, -138.0, 0.0))
    if fill_dir:
        fill_dir.set_actor_label("DirectionalLight_MarsDuskFill")
        flc = fill_dir.light_component
        set_prop(flc, "mobility", unreal.ComponentMobility.MOVABLE)
        set_prop(flc, "intensity", 2.6)
        set_prop(flc, "light_color", unreal.Color(196, 206, 228, 255))
        set_prop(flc, "atmosphere_sun_light", False)
        set_prop(flc, "cast_shadows", False)
        log("Spawned DirectionalLight_MarsDuskFill")

    # 3. SkyAtmosphere: Jezero Crater Mie-dominated salmon-butterscotch dust scattering
    sky = ELL.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0.0, 0.0, 0.0))
    if sky:
        sky.set_actor_label("SkyAtmosphere_Mars")
        sc = sky.get_component_by_class(unreal.SkyAtmosphereComponent)
        if sc:
            set_prop(sc, "rayleigh_scattering", unreal.LinearColor(0.32, 0.24, 0.22, 1.0))
            set_prop(sc, "mie_scattering", unreal.LinearColor(0.82, 0.44, 0.22, 1.0))
            set_prop(sc, "mie_absorption", unreal.LinearColor(0.18, 0.24, 0.30, 1.0))
            set_prop(sc, "mie_anisotropy", 0.72)
            set_prop(sc, "rayleigh_exponential_distribution", 4.0)
            set_prop(sc, "mie_exponential_distribution", 2.2)
            set_prop(sc, "atmosphere_height", 38.0)
            set_prop(sc, "ground_albedo", unreal.Color(148, 68, 34, 255))
        log("Spawned SkyAtmosphere_Mars")

    # 4. ExponentialHeightFog: Suspended iron-oxide ochre horizon fog + forward Mie sun glow
    fog = ELL.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0.0, 0.0, 200.0))
    if fog:
        fog.set_actor_label("ExponentialHeightFog_MarsDust")
        fc = fog.component
        set_prop(fc, "fog_density", 0.020)
        set_prop(fc, "fog_height_falloff", 0.14)
        set_prop(fc, "fog_inscattering_luminance", unreal.LinearColor(0.64, 0.33, 0.16, 1.0))
        set_prop(fc, "directional_inscattering_luminance", unreal.LinearColor(0.95, 0.56, 0.28, 1.0))
        set_prop(fc, "directional_inscattering_exponent", 5.0)
        set_prop(fc, "directional_inscattering_start_distance", 600.0)
        set_prop(fc, "fog_max_opacity", 0.86)
        set_prop(fc, "start_distance", 380.0)
        try:
            fc.set_volumetric_fog(True)
        except Exception:
            pass
        set_prop(fc, "volumetric_fog_scattering_distribution", 0.42)
        set_prop(fc, "volumetric_fog_albedo", unreal.Color(232, 162, 114, 255))
        set_prop(fc, "volumetric_fog_extinction_scale", 0.95)
        log("Spawned ExponentialHeightFog_MarsDust with suspended iron-oxide ochre scattering & volumetric fog")

    # 5. SkyLight: Cool dusty sky fill + warm ochre lower-hemisphere ground bounce
    skylight = ELL.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0.0, 0.0, 800.0))
    if skylight:
        skylight.set_actor_label("SkyLight_Mars")
        slc = skylight.light_component
        set_prop(slc, "mobility", unreal.ComponentMobility.MOVABLE)
        set_prop(slc, "real_time_capture", True)
        set_prop(slc, "intensity", 3.2)
        set_prop(slc, "light_color", unreal.Color(224, 210, 202, 255))
        set_prop(slc, "lower_hemisphere_color", unreal.LinearColor(0.24, 0.10, 0.045, 1.0))
        log("Spawned SkyLight_Mars (intensity=3.2)")

    # 6. PostProcessVolume: Unbound color/bloom polish
    ppv = ELL.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0.0, 0.0, 0.0))
    if ppv:
        ppv.set_actor_label("PostProcessVolume_Mars")
        set_prop(ppv, "unbound", True)
        settings = ppv.settings
        set_prop(settings, "override_bloom_intensity", True)
        set_prop(settings, "bloom_intensity", 0.36)
        set_prop(settings, "override_vignette_intensity", True)
        set_prop(settings, "vignette_intensity", 0.26)
        ppv.settings = settings
        log("Spawned PostProcessVolume_Mars")

    # 7. Interior & Landmark PointLights:
    #    Warm amber/cyan pools in habitat vs balanced botanical grow-light pools in greenhouse (scaled by LIGHT_SCALE = 0.015)
    point_lights = [
        ("PointLight_Habitat_Amber", unreal.Vector(-580.0, -140.0, 255.0), unreal.Color(255, 198, 132, 255), 4200.0, 920.0),
        ("PointLight_Habitat_Cyan", unreal.Vector(-420.0, 220.0, 250.0), unreal.Color(135, 228, 255, 255), 3600.0, 840.0),
        ("PointLight_Corridor", unreal.Vector(0.0, 0.0, 248.0), unreal.Color(255, 180, 105, 255), 2200.0, 580.0),
        ("PointLight_Greenhouse", unreal.Vector(500.0, 0.0, 260.0), unreal.Color(175, 232, 248, 255), 2600.0, 1050.0),
        ("PointLight_GrowLamp_SW", unreal.Vector(400.0, -200.0, 192.0), unreal.Color(248, 192, 230, 255), 1350.0, 340.0),
        ("PointLight_GrowLamp_NW", unreal.Vector(400.0, 200.0, 192.0), unreal.Color(248, 192, 230, 255), 1350.0, 340.0),
        ("PointLight_GrowLamp_SE", unreal.Vector(700.0, -200.0, 192.0), unreal.Color(248, 192, 230, 255), 1350.0, 340.0),
        ("PointLight_GrowLamp_NE", unreal.Vector(700.0, 200.0, 192.0), unreal.Color(248, 192, 230, 255), 1350.0, 340.0),
        ("PointLight_WestCombatYard", unreal.Vector(-1650.0, 0.0, 340.0), unreal.Color(255, 192, 142, 255), 3200.0, 1550.0),
        ("PointLight_CommsRelay", unreal.Vector(2500.0, 0.0, 260.0), unreal.Color(160, 225, 255, 255), 3600.0, 950.0),
        ("PointLight_IceField", unreal.Vector(380.0, -1550.0, 230.0), unreal.Color(175, 225, 255, 255), 2800.0, 950.0),
    ]
    for label, loc, col, intensity, radius in point_lights:
        spawn_point_light(label, loc, col, intensity, radius)

    # 8. Scattered Mars rocks + Ice-field & Comms-relay landmarks + Exterior beacons + Inc9 landmarks
    rocks_placed = spawn_mars_rocks()
    log(f"Placed {rocks_placed} Mars rock formations")
    spawn_ice_field_landmarks()
    spawn_comms_and_perimeter_landmarks()
    spawn_inc9_mars_landmarks()

    # 8a. Octagonal DropLander Landing Pad + Interior Architecture + Exterior Outpost Framing + Dust Streaks
    spawn_droplander_pad()
    spawn_interior_architecture()
    spawn_exterior_outpost_upgrade()
    spawn_mars_dust_streaks()

    # 8b. NASA Reference Props (suit rack in habitat + HDU Part 1 near west entrance + HDU Part 2 annex)
    z2_suit = EAL.load_asset("/Game/Environment/References/SM_NASA_Z2_Spacesuit") if EAL.does_asset_exist("/Game/Environment/References/SM_NASA_Z2_Spacesuit") else None
    if z2_suit:
        spawn_static_mesh(
            "SM_NASA_Z2_Spacesuit_Prop",
            z2_suit,
            unreal.Vector(-810.0, 220.0, 0.0),
            affect_nav=False,
        )
        log("Placed SM_NASA_Z2_Spacesuit_Prop at (-810, 220, 0)")

    hdu1 = EAL.load_asset("/Game/Environment/References/SM_NASA_Habitat_Part1") if EAL.does_asset_exist("/Game/Environment/References/SM_NASA_Habitat_Part1") else None
    if hdu1:
        spawn_static_mesh(
            "SM_NASA_HDU_Entrance",
            hdu1,
            unreal.Vector(-720.0, -830.0, 0.0),
            unreal.Rotator(0.0, 12.0, 0.0),
            affect_nav=True,
        )
        log("Placed SM_NASA_HDU_Entrance (Part1) near base entrance at (-720, -830, 0)")

    hdu2 = EAL.load_asset("/Game/Environment/References/SM_NASA_Habitat_Part2") if EAL.does_asset_exist("/Game/Environment/References/SM_NASA_Habitat_Part2") else None
    if hdu2:
        spawn_static_mesh(
            "SM_NASA_HDU_Annex",
            hdu2,
            unreal.Vector(1650.0, 1300.0, 0.0),
            unreal.Rotator(0.0, -35.0, 0.0),
            affect_nav=True,
        )
        log("Placed SM_NASA_HDU_Annex (Part2) at (1650, 1300, 0)")

    # 8c. Tripo Pro Hero Assets (seated cleanly onto gallery plinths and outpost pads)
    tripo_placements = [
        ("SM_Tripo_BotanicalPod_Showcase", "/Game/Tripo/SM_Tripo_BotanicalPod",
         unreal.Vector(790.0, 0.0, 14.0), unreal.Rotator(0.0, 180.0, 0.0), unreal.Vector(0.78, 0.78, 0.78),
         "NoCollision", False, (unreal.Vector(790.0, 0.0, 145.0), unreal.Color(125, 255, 195, 255), 1400.0, 380.0)),
        ("SM_Tripo_AlienBeacon_Monolith", "/Game/Tripo/SM_Tripo_AlienBeacon",
         unreal.Vector(2780.0, 140.0, 0.0), unreal.Rotator(0.0, 170.0, 0.0), unreal.Vector(1.20, 1.20, 1.20),
         "BlockAll", True, (unreal.Vector(2780.0, 140.0, 175.0), unreal.Color(85, 235, 255, 255), 3200.0, 700.0)),
        ("SM_Tripo_OxygenHarvester_Unit", "/Game/Tripo/SM_Tripo_OxygenHarvester",
         unreal.Vector(-1080.0, 460.0, 10.0), unreal.Rotator(0.0, -45.0, 0.0), unreal.Vector(0.90, 0.90, 0.90),
         "BlockAll", True, (unreal.Vector(-1020.0, 520.0, 175.0), unreal.Color(165, 232, 255, 255), 950.0, 460.0)),
        ("SM_Tripo_SentryTurret_GateGuard", "/Game/Tripo/SM_Tripo_SentryTurret",
         unreal.Vector(-1060.0, -320.0, 12.0), unreal.Rotator(0.0, 165.0, 0.0), unreal.Vector(0.92, 0.92, 0.92),
         "BlockAll", True, (unreal.Vector(-1095.0, -320.0, 145.0), unreal.Color(255, 195, 130, 255), 850.0, 420.0)),
        ("SM_Tripo_PulseRifle_Display", "/Game/Tripo/SM_Tripo_PulseRifle",
         unreal.Vector(-520.0, -415.0, 84.0), unreal.Rotator(0.0, 0.0, -8.0), unreal.Vector(0.85, 0.85, 0.85),
         "NoCollision", False, (unreal.Vector(-520.0, -395.0, 128.0), unreal.Color(150, 230, 255, 255), 550.0, 240.0)),
    ]
    tripo_placed = 0
    for label, pkg_path, loc, rot, scale, col_prof, nav, light_cfg in tripo_placements:
        sm = EAL.load_asset(pkg_path) if EAL.does_asset_exist(pkg_path) else None
        if sm:
            b = sm.get_bounding_box()
            seated_loc = unreal.Vector(loc.x, loc.y, loc.z - b.min.z * scale.z)
            spawn_static_mesh(label, sm, seated_loc, rot, scale, collision=col_prof, affect_nav=nav)
            if light_cfg is not None:
                l_loc, l_col, l_int, l_rad = light_cfg
                spawn_point_light(f"{label}_Light", l_loc, l_col, l_int, l_rad)
            tripo_placed += 1
            log(f"Placed Tripo hero asset {label} at ({seated_loc.x:.0f}, {seated_loc.y:.0f}, {seated_loc.z:.1f})")
    log(f"Placed {tripo_placed}/{len(tripo_placements)} Tripo Pro hero assets")

    verify_droplander_pad_clearance()

    # 9. Rebuild navigation, run MapCheck, & save map
    try:
        unreal.SystemLibrary.execute_console_command(world, "RebuildNavigation")
        unreal.SystemLibrary.execute_console_command(world, "MapCheck")
        log("MLG_MAP_CHECK_COMPLETE: RebuildNavigation + MapCheck executed")
    except Exception as exc:
        warn(f"RebuildNavigation/MapCheck console command note: {exc}")

    ok = unreal.EditorLoadingAndSavingUtils.save_map(world, "/Game/Maps/Base")
    log(f"MLG_MAP_SAVED={ok}")

    # Verify all /Game/ packages load cleanly with 0 errors
    asset_paths = EAL.list_assets("/Game/", recursive=True, include_folder=False)
    loaded = 0
    failed = []
    for asset_path in sorted(asset_paths):
        pkg = asset_path.split(".")[0]
        if pkg.startswith("/Game/Collections") or pkg.startswith("/Game/Developers"):
            continue
        obj = EAL.load_asset(pkg)
        if obj is not None:
            loaded += 1
        else:
            failed.append(pkg)
    log(f"PACKAGE_LOAD_CHECK loaded={loaded} failed={len(failed)} failed_list={failed}")


if __name__ == "__main__":
    build_map()
