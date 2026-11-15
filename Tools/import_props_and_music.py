"""Import Adaptive Mars Music and @prop_blender Props into UE 5.2 Content/.

Run via:
  UnrealEditor-Cmd "<project>/MarsLastGreen.uproject" \
    -ExecutePythonScript="<project>/Tools/import_props_and_music.py" \
    -nullrhi -unattended -nop4
"""

import json
import os
import sys
import unreal

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS_DIR = os.path.join(PROJECT_ROOT, "Assets")

ASSET_TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary

EXPECTED_PROPS = [
    # Devices (8)
    "SM_Dev_PowerUnit",
    "SM_Dev_OxygenGen",
    "SM_Dev_Purifier",
    "SM_Dev_GreenhouseSeal",
    "SM_Dev_WaterTank",
    "SM_Dev_WaterPipe",
    "SM_Dev_CommsRelay",
    "SM_Dev_Transmitter",
    # Botanical (3)
    "SM_PlantPlot",
    "SM_Plant_Seed",
    "SM_Plant_Seedling",
    # Pickups (4)
    "SM_Pickup_Parts",
    "SM_Pickup_Ammo",
    "SM_Pickup_Ice",
    "SM_Pickup_Seeds",
    # Defenses (3)
    "SM_Defense_TurretBase",
    "SM_Defense_TurretHead",
    "SM_Defense_Barrier",
]

AUDIO_FILES = [
    "SFX_Intro_LanderBurn.wav",
    "SFX_Intro_EarthShatter.wav",
    # Existing 15 WAVs (matching MLGAssets::Audio::* and Tools/gen_audio.py / gen_music.py)
    "SFX_Rifle_Fire.wav",
    "SFX_Rifle_Reload.wav",
    "SFX_Hit_Marker.wav",
    "SFX_Alien_Raider_Telegraph.wav",
    "SFX_Alien_Breaker_Slam.wav",
    "SFX_Alien_Gunner_Charge.wav",
    "SFX_Alien_Hit.wav",
    "SFX_Alien_Death.wav",
    "SFX_Repair_Tick.wav",
    "SFX_Repair_Done.wav",
    "SFX_Alert_Low.wav",
    "SFX_Transmit.wav",
    "SFX_Mars_Wind_Loop.wav",
    "SFX_Music_Calm_Loop.wav",
    "SFX_Music_Combat_Loop.wav",
    # New 10 WAVs (Increment 10)
    "SFX_Footstep_Indoor.wav",
    "SFX_Footstep_Mars.wav",
    "SFX_Jump.wav",
    "SFX_Land.wav",
    "SFX_Player_Hurt.wav",
    "SFX_LowO2_Heartbeat.wav",
    "SFX_Turret_Fire.wav",
    "SFX_Pickup.wav",
    "SFX_Wave_Start.wav",
    "SFX_UI_Click.wav",
]


def log(msg):
    unreal.log("MLG_IMPORT_PM: " + str(msg))


def warn(msg):
    unreal.log_warning("MLG_IMPORT_PM: " + str(msg))


def make_task(filename, dest_path, dest_name=None, options=None, replace=True):
    task = unreal.AssetImportTask()
    task.filename = filename
    task.destination_path = dest_path
    if dest_name:
        task.destination_name = dest_name
    task.automated = True
    task.replace_existing = replace
    task.replace_existing_settings = True
    task.save = True
    if options is not None:
        task.options = options
    return task


def import_music():
    log("=== Importing All 25 Mars Audio & Music WAVs ===")
    audio_dir = os.path.join(ASSETS_DIR, "Audio")
    dest_path = "/Game/Audio"
    imported_paths = []
    for fn in AUDIO_FILES:
        wav_path = os.path.join(audio_dir, fn)
        if not os.path.isfile(wav_path):
            warn(f"Missing audio WAV: {wav_path}")
            continue
        stem = os.path.splitext(fn)[0]
        task = make_task(wav_path, dest_path, stem, replace=True)
        ASSET_TOOLS.import_asset_tasks([task])
        pkg = f"{dest_path}/{stem}"
        sw = EAL.load_asset(pkg)
        if sw:
            is_loop = "loop" in stem.lower()
            sw.set_editor_property("looping", is_loop)
            EAL.save_asset(pkg, only_if_is_dirty=False)
            log(f"Imported SoundWave {pkg} (dur={sw.duration:.3f}s, looping={sw.get_editor_property('looping')})")
            imported_paths.append(pkg)
        else:
            warn(f"Failed to load SoundWave {pkg}")
    log(f"Imported {len(imported_paths)}/{len(AUDIO_FILES)} SoundWaves into {dest_path}")
    return imported_paths


def load_manifest_materials():
    manifest_path = os.path.join(ASSETS_DIR, "Props", "manifest.json")
    if not os.path.isfile(manifest_path):
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("materials", {}) or {}
    except Exception as exc:
        warn(f"Could not read manifest.json materials: {exc}")
        return {}


def resolve_slot_pbr(slot_name, manifest_mats):
    """Return (base_rgb, metallic, roughness, emissive_rgb) for a material slot."""
    spec = manifest_mats.get(slot_name)
    if spec:
        bc = spec.get("base_color", [0.72, 0.75, 0.79, 1.0])
        met = float(spec.get("metallic", 0.4))
        rgh = float(spec.get("roughness", 0.45))
        em = spec.get("emissive", [0.0, 0.0, 0.0, 1.0])
        strength = float(spec.get("emissive_strength", 0.0)) if spec.get("is_emissive", False) else 0.0
        return (
            (float(bc[0]), float(bc[1]), float(bc[2])),
            met,
            rgh,
            (float(em[0]) * strength, float(em[1]) * strength, float(em[2]) * strength),
        )

    s = slot_name.lower()
    if any(k in s for k in ("emissive", "status", "beacon", "visor", "screen", "glow")):
        return ((0.06, 0.16, 0.20), 0.1, 0.18, (0.28, 1.85, 2.28))
    if "ice" in s or "crystal" in s:
        return ((0.56, 0.85, 0.97), 0.05, 0.12, (0.04, 0.13, 0.19))
    if "soil" in s:
        return ((0.20, 0.10, 0.07), 0.0, 0.92, (0.0, 0.0, 0.0))
    if "foliage" in s or "plant" in s:
        return ((0.14, 0.50, 0.16), 0.0, 0.48, (0.0, 0.0, 0.0))
    if "dark" in s or "metal" in s:
        return ((0.14, 0.15, 0.17), 0.85, 0.36, (0.0, 0.0, 0.0))
    if "copper" in s:
        return ((0.74, 0.39, 0.18), 0.90, 0.28, (0.0, 0.0, 0.0))
    return ((0.76, 0.74, 0.70), 0.18, 0.42, (0.0, 0.0, 0.0))


def build_prop_material(mat_pkg_path, base_rgb, metallic, roughness, emissive_rgb):
    mat_dir, mat_name = mat_pkg_path.rsplit("/", 1)
    if EAL.does_asset_exist(mat_pkg_path):
        mat = EAL.load_asset(mat_pkg_path)
    else:
        mat = ASSET_TOOLS.create_asset(mat_name, mat_dir, unreal.Material, unreal.MaterialFactoryNew())
    if not mat:
        warn(f"Could not create material {mat_pkg_path}")
        return None

    MEL.delete_all_material_expressions(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("two_sided", False)

    # Color VectorParameter (defaults to 1,1,1,1 so un-overridden material preserves slot albedo)
    col_param = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -480, -220)
    col_param.set_editor_property("parameter_name", "Color")
    col_param.set_editor_property("default_value", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))

    base_const = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -480, -40)
    base_const.constant = unreal.LinearColor(base_rgb[0], base_rgb[1], base_rgb[2], 1.0)

    base_mul = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -220, -140)
    MEL.connect_material_expressions(base_const, "", base_mul, "A")
    MEL.connect_material_expressions(col_param, "", base_mul, "B")
    MEL.connect_material_property(base_mul, "", unreal.MaterialProperty.MP_BASE_COLOR)

    met_const = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 40)
    met_const.r = float(metallic)
    MEL.connect_material_property(met_const, "", unreal.MaterialProperty.MP_METALLIC)

    rgh_const = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 140)
    rgh_const.r = float(roughness)
    MEL.connect_material_property(rgh_const, "", unreal.MaterialProperty.MP_ROUGHNESS)

    em_param = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -420, 300)
    em_param.set_editor_property("parameter_name", "EmissiveColor")
    em_param.set_editor_property("default_value", unreal.LinearColor(emissive_rgb[0], emissive_rgb[1], emissive_rgb[2], 1.0))
    MEL.connect_material_property(em_param, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    MEL.recompile_material(mat)
    EAL.save_asset(mat_pkg_path, only_if_is_dirty=False)
    return mat


def find_prop_fbxs():
    props_root = os.path.join(ASSETS_DIR, "Props")
    found = {}
    if not os.path.isdir(props_root):
        return found
    for root, _, files in os.walk(props_root):
        for fn in sorted(files):
            if fn.lower().endswith(".fbx"):
                stem = os.path.splitext(fn)[0]
                found[stem] = os.path.join(root, fn)
    return found


def import_props():
    log("=== Importing @prop_blender Props into /Game/Environment/ ===")
    found = find_prop_fbxs()
    if not found:
        warn("No FBX files found under Assets/Props/ yet.")
        return []

    manifest_mats = load_manifest_materials()
    mesh_dest = "/Game/Environment"
    mat_dest = "/Game/Environment/Materials/Props"
    shared_mats = {}
    imported = []

    for prop_name in EXPECTED_PROPS:
        fbx_path = found.get(prop_name)
        if not fbx_path:
            warn(f"Missing expected prop FBX: {prop_name}.fbx")
            continue

        opts = unreal.FbxImportUI()
        opts.import_mesh = True
        opts.import_as_skeletal = False
        opts.import_animations = False
        opts.import_materials = False
        opts.import_textures = False
        opts.automated_import_should_detect_type = False
        opts.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH

        sm_data = opts.static_mesh_import_data
        sm_data.combine_meshes = True
        sm_data.auto_generate_collision = True
        sm_data.generate_lightmap_u_vs = True
        sm_data.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
        sm_data.convert_scene = True
        sm_data.force_front_x_axis = False

        task = make_task(fbx_path, mesh_dest, prop_name, options=opts)
        ASSET_TOOLS.import_asset_tasks([task])

        pkg = f"{mesh_dest}/{prop_name}"
        sm = EAL.load_asset(pkg)
        if not sm:
            warn(f"Failed to import StaticMesh {pkg} from {fbx_path}")
            continue

        # Ensure simple collision exists
        try:
            esml = unreal.EditorStaticMeshLibrary
            if esml.get_simple_collision_count(sm) == 0:
                esml.add_simple_collisions(sm, unreal.ScriptingCollisionShapeType.BOX)
        except Exception as exc:
            warn(f"Collision check note on {prop_name}: {exc}")

        # Build & assign shared parameterized materials per semantic slot name
        slots = []
        for idx, sm_mat in enumerate(sm.static_materials):
            slot_name = str(sm_mat.material_slot_name)
            slots.append(slot_name)
            safe_slot = "".join(c if c.isalnum() or c == "_" else "_" for c in slot_name) or f"Slot{idx}"
            if safe_slot not in shared_mats:
                base_rgb, met, rgh, em_rgb = resolve_slot_pbr(slot_name, manifest_mats)
                shared_mats[safe_slot] = build_prop_material(
                    f"{mat_dest}/{safe_slot}",
                    base_rgb, met, rgh, em_rgb
                )
            mat = shared_mats[safe_slot]
            if mat:
                sm.set_material(idx, mat)

        EAL.save_asset(pkg, only_if_is_dirty=False)
        bounds = sm.get_bounding_box()
        ext = bounds.max - bounds.min
        log(
            f"Imported {pkg} size=({ext.x:.1f}, {ext.y:.1f}, {ext.z:.1f}) cm "
            f"minZ={bounds.min.z:.2f} slots={slots}"
        )
        imported.append(pkg)

    return imported


def verify_all_game_packages():
    """Load every asset under /Game/ to verify zero LogLinker / load errors."""
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
    return loaded, failed


def main():
    args = set(sys.argv[1:])
    if "--music-only" in args:
        import_music()
    elif "--props-only" in args:
        import_props()
    elif "--verify-only" in args:
        verify_all_game_packages()
        return
    else:
        import_music()
        import_props()

    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    verify_all_game_packages()
    log("=== Props & Music Import Complete ===")


if __name__ == "__main__":
    main()
