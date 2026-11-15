"""Import Increment 9 Environment Props and Tune Materials in UE 5.2.

Run via:
  UnrealEditor-Cmd "<project>/MarsLastGreen.uproject" \
    -ExecutePythonScript="<project>/Tools/import_inc9_assets.py" \
    -nullrhi -unattended -nop4
"""

import json
import os
import sys
import unreal

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS_DIR = os.path.join(PROJECT_ROOT, "Assets")
PROPS_INC9_DIR = os.path.join(ASSETS_DIR, "Props_Inc9")

ASSET_TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary

EXPECTED_INC9_PROPS = [
    "SM_Log_Terminal",
    "SM_Habitat_WallPanel",
    "SM_Habitat_FloorTile",
    "SM_Greenhouse_GlassRoof",
    "SM_Mars_SolarArray",
    "SM_Mars_RoverWreck",
    "SM_Mars_TerrainSkirt",
    "SM_Mars_BasaltCliff",
    "SM_Comms_DishTower",
    "SM_Cryo_DrillRig",
    "SM_Solar_DustRack",
    "SM_CRISPR_Sequencer",
    "SM_Sabatier_Reactor",
]


def log(msg):
    unreal.log("MLG_INC9: " + str(msg))


def warn(msg):
    unreal.log_warning("MLG_INC9: " + str(msg))


def connect_expr(from_expr, from_pin, to_expr, to_pin):
    ok = MEL.connect_material_expressions(from_expr, from_pin, to_expr, to_pin)
    if not ok and from_pin != "":
        ok = MEL.connect_material_expressions(from_expr, "", to_expr, to_pin)
    if not ok:
        warn(f"Failed connect_expr {from_expr.get_name()}[{from_pin}] -> {to_expr.get_name()}[{to_pin}]")
    return ok


def connect_prop(from_expr, from_pin, prop):
    ok = MEL.connect_material_property(from_expr, from_pin, prop)
    if not ok and from_pin != "":
        ok = MEL.connect_material_property(from_expr, "", prop)
    if not ok:
        warn(f"Failed connect_prop {from_expr.get_name()}[{from_pin}] -> {prop}")
    return ok


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


def get_or_create_material(mat_pkg_path):
    mat_dir, mat_name = mat_pkg_path.rsplit("/", 1)
    if EAL.does_asset_exist(mat_pkg_path):
        mat = EAL.load_asset(mat_pkg_path)
    else:
        mat = ASSET_TOOLS.create_asset(mat_name, mat_dir, unreal.Material, unreal.MaterialFactoryNew())
    return mat


def create_environment_materials():
    """Create /Game/Environment/Materials/{M_Mars_Ground, M_Habitat_Wall, M_Habitat_Floor, M_Greenhouse_Glass}."""
    log("=== Creating & Tuning Core Environment Materials ===")
    mat_dir = "/Game/Environment/Materials"

    # 1. M_Mars_Ground: warm rusty regolith albedo + high roughness 0.92 (no MP_NORMAL so non-uniform 600x600x0.2 ground cube keeps clean +Z normal)
    m_ground_path = f"{mat_dir}/M_Mars_Ground"
    m_ground = get_or_create_material(m_ground_path)
    if m_ground:
        MEL.delete_all_material_expressions(m_ground)
        m_ground.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
        m_ground.set_editor_property("two_sided", False)

        col_param = MEL.create_material_expression(m_ground, unreal.MaterialExpressionVectorParameter, -520, -220)
        col_param.set_editor_property("parameter_name", "Color")
        col_param.set_editor_property("default_value", unreal.LinearColor(0.42, 0.175, 0.09, 1.0))

        rock_d = EAL.load_asset("/Game/Environment/Textures/T_MarsRock_01_D") if EAL.does_asset_exist("/Game/Environment/Textures/T_MarsRock_01_D") else None

        if rock_d:
            uv = MEL.create_material_expression(m_ground, unreal.MaterialExpressionTextureCoordinate, -760, -40)
            uv.set_editor_property("u_tiling", 42.0)
            uv.set_editor_property("v_tiling", 42.0)

            tex_d = MEL.create_material_expression(m_ground, unreal.MaterialExpressionTextureSample, -520, -40)
            tex_d.texture = rock_d
            tex_d.sampler_type = unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
            connect_expr(uv, "", tex_d, "UVs")

            # Modulate Color around [0.85 .. 1.15] using default "" output pin on all nodes
            c_scale = MEL.create_material_expression(m_ground, unreal.MaterialExpressionConstant, -520, 140)
            c_scale.r = 0.32
            tex_scaled = MEL.create_material_expression(m_ground, unreal.MaterialExpressionMultiply, -360, 40)
            connect_expr(tex_d, "", tex_scaled, "A")
            connect_expr(c_scale, "", tex_scaled, "B")

            c_bias = MEL.create_material_expression(m_ground, unreal.MaterialExpressionConstant, -360, 160)
            c_bias.r = 0.84
            tex_mod = MEL.create_material_expression(m_ground, unreal.MaterialExpressionAdd, -240, 60)
            connect_expr(tex_scaled, "", tex_mod, "A")
            connect_expr(c_bias, "", tex_mod, "B")

            mul = MEL.create_material_expression(m_ground, unreal.MaterialExpressionMultiply, -120, -120)
            connect_expr(col_param, "", mul, "A")
            connect_expr(tex_mod, "", mul, "B")
            connect_prop(mul, "", unreal.MaterialProperty.MP_BASE_COLOR)
        else:
            connect_prop(col_param, "", unreal.MaterialProperty.MP_BASE_COLOR)

        met = MEL.create_material_expression(m_ground, unreal.MaterialExpressionConstant, -180, 60)
        met.r = 0.0
        connect_prop(met, "", unreal.MaterialProperty.MP_METALLIC)

        spec = MEL.create_material_expression(m_ground, unreal.MaterialExpressionConstant, -180, 140)
        spec.r = 0.12
        connect_prop(spec, "", unreal.MaterialProperty.MP_SPECULAR)

        rgh = MEL.create_material_expression(m_ground, unreal.MaterialExpressionConstant, -180, 220)
        rgh.r = 0.92
        connect_prop(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)

        em_param = MEL.create_material_expression(m_ground, unreal.MaterialExpressionVectorParameter, -320, 340)
        em_param.set_editor_property("parameter_name", "EmissiveColor")
        em_param.set_editor_property("default_value", unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
        connect_prop(em_param, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

        MEL.recompile_material(m_ground)
        EAL.save_asset(m_ground_path, only_if_is_dirty=False)
        log(f"Saved {m_ground_path} (roughness=0.92, clean +Z normal)")

    # 2. M_Habitat_Wall: dark slate-titanium metallic 0.35, roughness 0.55
    m_wall_path = f"{mat_dir}/M_Habitat_Wall"
    m_wall = get_or_create_material(m_wall_path)
    if m_wall:
        MEL.delete_all_material_expressions(m_wall)
        m_wall.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
        m_wall.set_editor_property("two_sided", False)

        base_slate = MEL.create_material_expression(m_wall, unreal.MaterialExpressionConstant3Vector, -520, -220)
        base_slate.constant = unreal.LinearColor(0.088, 0.102, 0.126, 1.0)

        col_param = MEL.create_material_expression(m_wall, unreal.MaterialExpressionVectorParameter, -520, -40)
        col_param.set_editor_property("parameter_name", "Color")
        col_param.set_editor_property("default_value", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))

        white_c = MEL.create_material_expression(m_wall, unreal.MaterialExpressionConstant3Vector, -520, 140)
        white_c.constant = unreal.LinearColor(1.0, 1.0, 1.0, 1.0)
        blend_a = MEL.create_material_expression(m_wall, unreal.MaterialExpressionConstant, -520, 260)
        blend_a.r = 0.22

        tint_lerp = MEL.create_material_expression(m_wall, unreal.MaterialExpressionLinearInterpolate, -320, 40)
        connect_expr(white_c, "", tint_lerp, "A")
        connect_expr(col_param, "", tint_lerp, "B")
        connect_expr(blend_a, "", tint_lerp, "Alpha")

        mul = MEL.create_material_expression(m_wall, unreal.MaterialExpressionMultiply, -160, -120)
        connect_expr(base_slate, "", mul, "A")
        connect_expr(tint_lerp, "", mul, "B")
        connect_prop(mul, "", unreal.MaterialProperty.MP_BASE_COLOR)

        met = MEL.create_material_expression(m_wall, unreal.MaterialExpressionConstant, -180, 60)
        met.r = 0.35
        connect_prop(met, "", unreal.MaterialProperty.MP_METALLIC)

        rgh = MEL.create_material_expression(m_wall, unreal.MaterialExpressionConstant, -180, 160)
        rgh.r = 0.55
        connect_prop(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)

        em_param = MEL.create_material_expression(m_wall, unreal.MaterialExpressionVectorParameter, -320, 320)
        em_param.set_editor_property("parameter_name", "EmissiveColor")
        em_param.set_editor_property("default_value", unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
        connect_prop(em_param, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

        MEL.recompile_material(m_wall)
        EAL.save_asset(m_wall_path, only_if_is_dirty=False)
        log(f"Saved {m_wall_path} (metallic=0.35, roughness=0.55)")

    # 3. M_Habitat_Floor: dark steel deck
    m_floor_path = f"{mat_dir}/M_Habitat_Floor"
    m_floor = get_or_create_material(m_floor_path)
    if m_floor:
        MEL.delete_all_material_expressions(m_floor)
        m_floor.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
        m_floor.set_editor_property("two_sided", False)

        base_deck = MEL.create_material_expression(m_floor, unreal.MaterialExpressionConstant3Vector, -520, -220)
        base_deck.constant = unreal.LinearColor(0.058, 0.068, 0.084, 1.0)

        col_param = MEL.create_material_expression(m_floor, unreal.MaterialExpressionVectorParameter, -520, -40)
        col_param.set_editor_property("parameter_name", "Color")
        col_param.set_editor_property("default_value", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))

        white_c = MEL.create_material_expression(m_floor, unreal.MaterialExpressionConstant3Vector, -520, 140)
        white_c.constant = unreal.LinearColor(1.0, 1.0, 1.0, 1.0)
        blend_a = MEL.create_material_expression(m_floor, unreal.MaterialExpressionConstant, -520, 260)
        blend_a.r = 0.22

        tint_lerp = MEL.create_material_expression(m_floor, unreal.MaterialExpressionLinearInterpolate, -320, 40)
        connect_expr(white_c, "", tint_lerp, "A")
        connect_expr(col_param, "", tint_lerp, "B")
        connect_expr(blend_a, "", tint_lerp, "Alpha")

        mul = MEL.create_material_expression(m_floor, unreal.MaterialExpressionMultiply, -160, -120)
        connect_expr(base_deck, "", mul, "A")
        connect_expr(tint_lerp, "", mul, "B")
        connect_prop(mul, "", unreal.MaterialProperty.MP_BASE_COLOR)

        met = MEL.create_material_expression(m_floor, unreal.MaterialExpressionConstant, -180, 60)
        met.r = 0.65
        connect_prop(met, "", unreal.MaterialProperty.MP_METALLIC)

        rgh = MEL.create_material_expression(m_floor, unreal.MaterialExpressionConstant, -180, 160)
        rgh.r = 0.48
        connect_prop(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)

        em_param = MEL.create_material_expression(m_floor, unreal.MaterialExpressionVectorParameter, -320, 320)
        em_param.set_editor_property("parameter_name", "EmissiveColor")
        em_param.set_editor_property("default_value", unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
        connect_prop(em_param, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

        MEL.recompile_material(m_floor)
        EAL.save_asset(m_floor_path, only_if_is_dirty=False)
        log(f"Saved {m_floor_path} (metallic=0.65, roughness=0.48)")

    # 4. M_Greenhouse_Glass: translucent sky-tinted glass, opacity 0.28
    m_glass_path = f"{mat_dir}/M_Greenhouse_Glass"
    m_glass = get_or_create_material(m_glass_path)
    if m_glass:
        MEL.delete_all_material_expressions(m_glass)
        m_glass.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
        m_glass.set_editor_property("two_sided", True)
        try:
            m_glass.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE)
        except Exception:
            pass

        col_param = MEL.create_material_expression(m_glass, unreal.MaterialExpressionVectorParameter, -420, -200)
        col_param.set_editor_property("parameter_name", "Color")
        col_param.set_editor_property("default_value", unreal.LinearColor(0.36, 0.68, 0.86, 1.0))
        connect_prop(col_param, "", unreal.MaterialProperty.MP_BASE_COLOR)

        met = MEL.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -220, -40)
        met.r = 0.15
        connect_prop(met, "", unreal.MaterialProperty.MP_METALLIC)

        rgh = MEL.create_material_expression(m_glass, unreal.MaterialExpressionConstant, -220, 40)
        rgh.r = 0.12
        connect_prop(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)

        op_param = MEL.create_material_expression(m_glass, unreal.MaterialExpressionScalarParameter, -320, 140)
        op_param.set_editor_property("parameter_name", "Opacity")
        op_param.set_editor_property("default_value", 0.24)
        connect_prop(op_param, "", unreal.MaterialProperty.MP_OPACITY)

        em_param = MEL.create_material_expression(m_glass, unreal.MaterialExpressionVectorParameter, -420, 260)
        em_param.set_editor_property("parameter_name", "EmissiveColor")
        em_param.set_editor_property("default_value", unreal.LinearColor(0.015, 0.035, 0.050, 1.0))
        connect_prop(em_param, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

        MEL.recompile_material(m_glass)
        EAL.save_asset(m_glass_path, only_if_is_dirty=False)
        log(f"Saved {m_glass_path} (translucent, opacity=0.28)")

    return {
        "M_Mars_Ground": m_ground,
        "M_Habitat_Wall": m_wall,
        "M_Habitat_Floor": m_floor,
        "M_Greenhouse_Glass": m_glass,
    }


def tune_fp_weapon_material():
    """Tune /Game/FPWeapon/Materials/M_FPGun (and M_UE4Man_Body) to dark tactical gunmetal so rifle never glows white-blue."""
    log("=== Tuning /Game/FPWeapon/Materials/M_FPGun ===")
    gun_mat_path = "/Game/FPWeapon/Materials/M_FPGun"
    mat = get_or_create_material(gun_mat_path)
    if not mat:
        warn(f"Could not load or create {gun_mat_path}")
        return

    mask_tex = EAL.load_asset("/Game/FPWeapon/Textures/T_FPGun_M") if EAL.does_asset_exist("/Game/FPWeapon/Textures/T_FPGun_M") else None
    norm_tex = EAL.load_asset("/Game/FPWeapon/Textures/T_FPGun_N") if EAL.does_asset_exist("/Game/FPWeapon/Textures/T_FPGun_N") else None

    MEL.delete_all_material_expressions(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("two_sided", False)

    c_primary = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -520, -240)
    c_primary.constant = unreal.LinearColor(0.052, 0.058, 0.068, 1.0)

    c_delta = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -520, -80)
    c_delta.constant = unreal.LinearColor(0.045, 0.050, 0.058, 1.0)

    if mask_tex:
        m_sample = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -520, 80)
        m_sample.texture = mask_tex
        m_sample.sampler_type = unreal.MaterialSamplerType.SAMPLERTYPE_COLOR

        m_mul = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -320, -20)
        connect_expr(m_sample, "", m_mul, "A")
        connect_expr(c_delta, "", m_mul, "B")

        m_add = MEL.create_material_expression(mat, unreal.MaterialExpressionAdd, -160, -140)
        connect_expr(c_primary, "", m_add, "A")
        connect_expr(m_mul, "", m_add, "B")
        connect_prop(m_add, "", unreal.MaterialProperty.MP_BASE_COLOR)
    else:
        connect_prop(c_primary, "", unreal.MaterialProperty.MP_BASE_COLOR)

    met = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 40)
    met.r = 0.76
    connect_prop(met, "", unreal.MaterialProperty.MP_METALLIC)

    spec = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 120)
    spec.r = 0.28
    connect_prop(spec, "", unreal.MaterialProperty.MP_SPECULAR)

    rgh = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 200)
    rgh.r = 0.44
    connect_prop(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)

    if norm_tex:
        n_sample = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -420, 300)
        n_sample.texture = norm_tex
        n_sample.sampler_type = unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
        connect_prop(n_sample, "", unreal.MaterialProperty.MP_NORMAL)

    MEL.recompile_material(mat)
    EAL.save_asset(gun_mat_path, only_if_is_dirty=False)

    sk_gun = EAL.load_asset("/Game/FPWeapon/Mesh/SK_FPGun") if EAL.does_asset_exist("/Game/FPWeapon/Mesh/SK_FPGun") else None
    if sk_gun:
        new_mats = []
        for old_sm in sk_gun.get_editor_property("materials"):
            sm_copy = old_sm.copy()
            sm_copy.set_editor_property("material_interface", mat)
            new_mats.append(sm_copy)
        sk_gun.modify()
        sk_gun.set_editor_property("materials", new_mats)
        EAL.save_asset("/Game/FPWeapon/Mesh/SK_FPGun", only_if_is_dirty=False)
    log("Tuned /Game/FPWeapon/Materials/M_FPGun to tactical dark gunmetal")

    arms_mat_path = "/Game/FirstPersonArms/Character/Materials/M_UE4Man_Body"
    if EAL.does_asset_exist(arms_mat_path):
        arms_mat = EAL.load_asset(arms_mat_path)
        if arms_mat:
            MEL.delete_all_material_expressions(arms_mat)
            arms_mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
            sleeve_col = MEL.create_material_expression(arms_mat, unreal.MaterialExpressionConstant3Vector, -360, -140)
            sleeve_col.constant = unreal.LinearColor(0.11, 0.125, 0.145, 1.0)
            connect_prop(sleeve_col, "", unreal.MaterialProperty.MP_BASE_COLOR)
            s_met = MEL.create_material_expression(arms_mat, unreal.MaterialExpressionConstant, -200, 20)
            s_met.r = 0.25
            connect_prop(s_met, "", unreal.MaterialProperty.MP_METALLIC)
            s_rgh = MEL.create_material_expression(arms_mat, unreal.MaterialExpressionConstant, -200, 100)
            s_rgh.r = 0.52
            connect_prop(s_rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)
            MEL.recompile_material(arms_mat)
            EAL.save_asset(arms_mat_path, only_if_is_dirty=False)
            log("Tuned /Game/FirstPersonArms/Character/Materials/M_UE4Man_Body to tactical slate sleeve")


def force_reimport_texture(filepath, dest_path, dest_name, kind="color"):
    if not filepath or not os.path.isfile(filepath):
        return EAL.load_asset(f"{dest_path}/{dest_name}") if EAL.does_asset_exist(f"{dest_path}/{dest_name}") else None
    pkg = f"{dest_path}/{dest_name}"
    task = make_task(filepath, dest_path, dest_name, replace=True)
    ASSET_TOOLS.import_asset_tasks([task])
    tex = EAL.load_asset(pkg) if EAL.does_asset_exist(pkg) else None
    if not tex:
        imported = list(task.get_editor_property("imported_object_paths") or [])
        if imported:
            tex = unreal.load_object(None, str(imported[0]))
    if not tex:
        return None
    if kind == "normal_gl":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("flip_green_channel", True)
    elif kind == "normal_dx":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("flip_green_channel", False)
    else:
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT)
        tex.set_editor_property("srgb", True)
    EAL.save_asset(tex.get_path_name().split(".")[0], only_if_is_dirty=False)
    return tex


def tune_creature_materials():
    """Tune /Game/Creatures/{Raider,Breaker,Gunner}/Materials/M_Alien_* for rich dusk readability."""
    log("=== Tuning Creature Materials M_Alien_{Raider,Breaker,Gunner} ===")
    prod_dir = os.path.join(ASSETS_DIR, "Creatures", "Production")

    presets = {
        "Raider": {
            "albedo_boost": (2.75, 2.25, 1.90),
            "tex_sheen": (0.30, 0.18, 0.12),
            "emissive_default": (0.03, 0.015, 0.01),
        },
        "Breaker": {
            "albedo_boost": (2.65, 2.18, 1.82),
            "tex_sheen": (0.28, 0.17, 0.11),
            "emissive_default": (0.03, 0.015, 0.01),
        },
        "Gunner": {
            "albedo_boost": (2.60, 2.35, 2.28),
            "tex_sheen": (0.26, 0.17, 0.14),
            "emissive_default": (0.03, 0.015, 0.01),
        },
    }

    for kind, cfg in presets.items():
        kdir = os.path.join(prod_dir, kind)
        dest = f"/Game/Creatures/{kind}"
        tex_dest = f"{dest}/Textures"
        mat_dest = f"{dest}/Materials"
        mat_pkg = f"{mat_dest}/M_Alien_{kind}"

        base_tex_file = None
        norm_tex_file = None
        norm_kind = "normal_gl"
        if os.path.isdir(kdir):
            for root, _, files in os.walk(kdir):
                for fn in sorted(files):
                    low = fn.lower()
                    if not low.endswith((".png", ".jpg", ".jpeg", ".tga", ".exr")):
                        continue
                    if "preview" in low or "sheet" in low:
                        continue
                    full = os.path.join(root, fn)
                    if ("basecolor" in low or "albedo" in low or "diff" in low) and base_tex_file is None:
                        base_tex_file = full
                    elif ("normal" in low or "_nor" in low) and norm_tex_file is None:
                        norm_tex_file = full
                        if "_dx" in low:
                            norm_kind = "normal_dx"

        b_tex = force_reimport_texture(base_tex_file, tex_dest, f"T_Alien_{kind}_D", "color")
        n_tex = force_reimport_texture(norm_tex_file, tex_dest, f"T_Alien_{kind}_N", norm_kind)

        mat = get_or_create_material(mat_pkg)
        if not mat:
            warn(f"Failed to load/create {mat_pkg}")
            continue

        MEL.delete_all_material_expressions(mat)
        mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
        mat.set_editor_property("two_sided", False)

        boost_rgb = cfg["albedo_boost"]
        sheen_rgb = cfg["tex_sheen"]
        em_def = cfg["emissive_default"]

        em_param = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -560, 420)
        em_param.set_editor_property("parameter_name", "EmissiveColor")
        em_param.set_editor_property("default_value", unreal.LinearColor(em_def[0], em_def[1], em_def[2], 1.0))

        rim_floor = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -560, 600)
        rim_floor.constant = unreal.LinearColor(em_def[0], em_def[1], em_def[2], 1.0)

        if b_tex:
            base_sample = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -620, -240)
            base_sample.texture = b_tex
            base_sample.sampler_type = unreal.MaterialSamplerType.SAMPLERTYPE_COLOR

            boost_const = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -620, -40)
            boost_const.constant = unreal.LinearColor(boost_rgb[0], boost_rgb[1], boost_rgb[2], 1.0)

            base_mul = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -320, -160)
            connect_expr(base_sample, "", base_mul, "A")
            connect_expr(boost_const, "", base_mul, "B")
            connect_prop(base_mul, "", unreal.MaterialProperty.MP_BASE_COLOR)

            # Texture-modulated warm/alien subsurface-like sheen + EmissiveColor parameter (using "" output pin!)
            sheen_const = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -560, 260)
            sheen_const.constant = unreal.LinearColor(sheen_rgb[0], sheen_rgb[1], sheen_rgb[2], 1.0)

            sheen_mul = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -360, 260)
            connect_expr(base_sample, "", sheen_mul, "A")
            connect_expr(sheen_const, "", sheen_mul, "B")

            sheen_plus_floor = MEL.create_material_expression(mat, unreal.MaterialExpressionAdd, -240, 380)
            connect_expr(sheen_mul, "", sheen_plus_floor, "A")
            connect_expr(rim_floor, "", sheen_plus_floor, "B")

            em_total = MEL.create_material_expression(mat, unreal.MaterialExpressionAdd, -120, 420)
            connect_expr(em_param, "", em_total, "A")
            connect_expr(sheen_plus_floor, "", em_total, "B")
            connect_prop(em_total, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        else:
            fallback_col = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -360, -160)
            fallback_col.constant = unreal.LinearColor(0.45, 0.24, 0.14, 1.0)
            connect_prop(fallback_col, "", unreal.MaterialProperty.MP_BASE_COLOR)
            connect_prop(em_param, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

        met = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 20)
        met.r = 0.08
        connect_prop(met, "", unreal.MaterialProperty.MP_METALLIC)

        rgh = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 110)
        rgh.r = 0.65
        connect_prop(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)

        if n_tex:
            norm_sample = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -420, 140)
            norm_sample.texture = n_tex
            norm_sample.sampler_type = unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
            connect_prop(norm_sample, "", unreal.MaterialProperty.MP_NORMAL)

        MEL.recompile_material(mat)
        EAL.save_asset(mat_pkg, only_if_is_dirty=False)

        sk_pkg = f"{dest}/SK_Alien_{kind}"
        sk_mesh = EAL.load_asset(sk_pkg) if EAL.does_asset_exist(sk_pkg) else None
        if sk_mesh:
            new_mats = []
            for old_sm in sk_mesh.get_editor_property("materials"):
                sm_copy = old_sm.copy()
                slot_name = str(sm_copy.material_slot_name).lower()
                if "rifle" in slot_name or "weapon" in slot_name or "core" in slot_name:
                    new_mats.append(sm_copy)
                    continue
                sm_copy.set_editor_property("material_interface", mat)
                new_mats.append(sm_copy)
            sk_mesh.modify()
            sk_mesh.set_editor_property("materials", new_mats)
            EAL.save_asset(sk_pkg, only_if_is_dirty=False)
        log(f"Tuned {mat_pkg} (roughness=0.65, EmissiveColor default={em_def}, albedo_boost={boost_rgb})")


def load_inc9_manifest_materials():
    merged = {}
    for candidate in [
        os.path.join(ASSETS_DIR, "Props", "manifest.json"),
        os.path.join(PROPS_INC9_DIR, "manifest.json"),
    ]:
        if os.path.isfile(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                mats = data.get("materials", {})
                if mats:
                    merged.update(mats)
            except Exception as exc:
                warn(f"Could not read {candidate}: {exc}")
    return merged


def resolve_inc9_slot_pbr(slot_name, manifest_mats):
    spec = manifest_mats.get(slot_name)
    if spec:
        bc = spec.get("base_color", [0.45, 0.48, 0.52, 1.0])
        met = float(spec.get("metallic", 0.45))
        rgh = float(spec.get("roughness", 0.48))
        em = spec.get("emissive", [0.0, 0.0, 0.0, 1.0])
        strength = float(spec.get("emissive_strength", 0.0)) if spec.get("is_emissive", False) else 0.0
        return (
            (float(bc[0]), float(bc[1]), float(bc[2])),
            met,
            rgh,
            (float(em[0]) * strength, float(em[1]) * strength, float(em[2]) * strength),
        )

    s = slot_name.lower()
    if any(k in s for k in ("emissive", "status", "beacon", "visor", "screen", "glow", "led", "telemetry")):
        return ((0.06, 0.18, 0.24), 0.1, 0.18, (0.28, 1.65, 2.15))
    if "solar" in s or "cell" in s or "photovoltaic" in s:
        return ((0.09, 0.11, 0.15), 0.42, 0.44, (0.004, 0.014, 0.028))
    if "gold" in s or "foil" in s or "kapton" in s:
        return ((0.82, 0.54, 0.14), 0.88, 0.28, (0.0, 0.0, 0.0))
    if "copper" in s or "amber" in s or "orange" in s:
        return ((0.74, 0.38, 0.16), 0.80, 0.34, (0.0, 0.0, 0.0))
    if "wheel" in s or "tire" in s or "rubber" in s:
        return ((0.08, 0.08, 0.09), 0.25, 0.72, (0.0, 0.0, 0.0))
    if "dust" in s or "rust" in s or "regolith" in s or "mars" in s or "ground" in s or "skirt" in s or "soil" in s:
        return ((0.32, 0.14, 0.08), 0.0, 0.92, (0.0, 0.0, 0.0))
    if "dark" in s or "frame" in s or "truss" in s or "stand" in s:
        return ((0.11, 0.12, 0.14), 0.78, 0.40, (0.0, 0.0, 0.0))
    return ((0.22, 0.25, 0.29), 0.45, 0.48, (0.0, 0.0, 0.0))


def build_slot_material(mat_pkg_path, base_rgb, metallic, roughness, emissive_rgb):
    mat = get_or_create_material(mat_pkg_path)
    if not mat:
        return None
    MEL.delete_all_material_expressions(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("two_sided", False)

    col_param = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -480, -220)
    col_param.set_editor_property("parameter_name", "Color")
    col_param.set_editor_property("default_value", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))

    base_const = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -480, -40)
    base_const.constant = unreal.LinearColor(base_rgb[0], base_rgb[1], base_rgb[2], 1.0)

    base_mul = MEL.create_material_expression(mat, unreal.MaterialExpressionMultiply, -220, -140)
    connect_expr(base_const, "", base_mul, "A")
    connect_expr(col_param, "", base_mul, "B")
    connect_prop(base_mul, "", unreal.MaterialProperty.MP_BASE_COLOR)

    met_const = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 40)
    met_const.r = float(metallic)
    connect_prop(met_const, "", unreal.MaterialProperty.MP_METALLIC)

    rgh_const = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 140)
    rgh_const.r = float(roughness)
    connect_prop(rgh_const, "", unreal.MaterialProperty.MP_ROUGHNESS)

    em_param = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -420, 300)
    em_param.set_editor_property("parameter_name", "EmissiveColor")
    em_param.set_editor_property("default_value", unreal.LinearColor(emissive_rgb[0], emissive_rgb[1], emissive_rgb[2], 1.0))
    connect_prop(em_param, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    MEL.recompile_material(mat)
    EAL.save_asset(mat_pkg_path, only_if_is_dirty=False)
    return mat


def repair_all_existing_prop_materials():
    """Rebuild all /Game/Environment/Materials/Props/* materials with "" pin connections so EmissiveColor and Color work everywhere."""
    manifest_mats = load_inc9_manifest_materials()
    prop_mat_dir = "/Game/Environment/Materials/Props"
    if not EAL.does_directory_exist(prop_mat_dir):
        return
    for asset_path in sorted(EAL.list_assets(prop_mat_dir, recursive=False, include_folder=False)):
        pkg = asset_path.split(".")[0]
        slot_name = pkg.rsplit("/", 1)[-1]
        base_rgb, met, rgh, em_rgb = resolve_inc9_slot_pbr(slot_name, manifest_mats)
        build_slot_material(pkg, base_rgb, met, rgh, em_rgb)
        log(f"Rebuilt prop slot material {pkg} with verified pin connections")


def find_inc9_fbxs():
    found = {}
    if not os.path.isdir(PROPS_INC9_DIR):
        return found
    for root, _, files in os.walk(PROPS_INC9_DIR):
        for fn in sorted(files):
            if fn.lower().endswith(".fbx"):
                stem = os.path.splitext(fn)[0]
                found[stem] = os.path.join(root, fn)
    return found


def import_inc9_props(env_mats):
    log("=== Importing @argon_art Assets/Props_Inc9/ into /Game/Environment/ ===")
    found = find_inc9_fbxs()
    if not found:
        warn(f"No FBXs found in {PROPS_INC9_DIR} yet.")
        return []

    manifest_mats = load_inc9_manifest_materials()
    mesh_dest = "/Game/Environment"
    mat_dest = "/Game/Environment/Materials/Props"
    shared_mats = {}
    imported = []

    m_ground = env_mats.get("M_Mars_Ground") or EAL.load_asset("/Game/Environment/Materials/M_Mars_Ground")
    m_wall = env_mats.get("M_Habitat_Wall") or EAL.load_asset("/Game/Environment/Materials/M_Habitat_Wall")
    m_floor = env_mats.get("M_Habitat_Floor") or EAL.load_asset("/Game/Environment/Materials/M_Habitat_Floor")
    m_glass = env_mats.get("M_Greenhouse_Glass") or EAL.load_asset("/Game/Environment/Materials/M_Greenhouse_Glass")

    for prop_name in EXPECTED_INC9_PROPS:
        fbx_path = found.get(prop_name)
        if not fbx_path:
            warn(f"Missing expected Inc9 FBX: {prop_name}.fbx")
            continue

        is_skirt = (prop_name == "SM_Mars_TerrainSkirt")

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
        sm_data.auto_generate_collision = (not is_skirt)
        sm_data.generate_lightmap_u_vs = True
        sm_data.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
        sm_data.convert_scene = True
        sm_data.force_front_x_axis = False

        task = make_task(fbx_path, mesh_dest, prop_name, options=opts, replace=True)
        ASSET_TOOLS.import_asset_tasks([task])

        pkg = f"{mesh_dest}/{prop_name}"
        sm = EAL.load_asset(pkg)
        if not sm:
            warn(f"Failed to import StaticMesh {pkg} from {fbx_path}")
            continue

        # Collision setup
        try:
            esml = unreal.EditorStaticMeshLibrary
            if is_skirt:
                esml.remove_collisions(sm)
            elif esml.get_simple_collision_count(sm) == 0:
                esml.add_simple_collisions(sm, unreal.ScriptingCollisionShapeType.BOX)
        except Exception as exc:
            warn(f"Collision setup note on {prop_name}: {exc}")

        # Material assignment per prop and slot
        num_slots = len(sm.static_materials)
        slots = []
        glass_assigned = False

        for idx, sm_mat in enumerate(sm.static_materials):
            slot_name = str(sm_mat.material_slot_name)
            slot_low = slot_name.lower()
            slots.append(slot_name)
            assigned_mat = None

            if prop_name in ("SM_Mars_TerrainSkirt", "SM_Mars_BasaltCliff"):
                if "regolith" in slot_low or "soil" in slot_low:
                    assigned_mat = EAL.load_asset("/Game/Environment/Materials/M_MarsRock_01") if EAL.does_asset_exist("/Game/Environment/Materials/M_MarsRock_01") else None
                else:
                    assigned_mat = m_ground
            elif prop_name in ("SM_Greenhouse_GlassRoof", "SM_CRISPR_Sequencer"):
                if any(k in slot_low for k in ("glass", "pane", "window", "translucent", "sky")):
                    assigned_mat = m_glass
                    glass_assigned = True
                elif num_slots == 1 and prop_name == "SM_Greenhouse_GlassRoof":
                    assigned_mat = m_glass
                    glass_assigned = True
            elif prop_name == "SM_Habitat_WallPanel":
                if idx == 0 or any(k in slot_low for k in ("wall", "panel", "bulkhead", "hull", "slate", "primary")):
                    if not any(k in slot_low for k in ("emissive", "led", "glow", "strip", "accent")):
                        assigned_mat = m_wall
            elif prop_name == "SM_Habitat_FloorTile":
                if idx == 0 or any(k in slot_low for k in ("floor", "tile", "deck", "grating", "steel")):
                    if not any(k in slot_low for k in ("emissive", "led", "glow")):
                        assigned_mat = m_floor

            if assigned_mat is None:
                safe_slot = "".join(c if c.isalnum() or c == "_" else "_" for c in slot_name) or f"Slot{idx}"
                if safe_slot not in shared_mats:
                    base_rgb, met, rgh, em_rgb = resolve_inc9_slot_pbr(slot_name, manifest_mats)
                    shared_mats[safe_slot] = build_slot_material(
                        f"{mat_dest}/{safe_slot}",
                        base_rgb, met, rgh, em_rgb
                    )
                assigned_mat = shared_mats[safe_slot]

            if assigned_mat:
                sm.set_material(idx, assigned_mat)

        if prop_name == "SM_Greenhouse_GlassRoof" and not glass_assigned and num_slots > 0 and m_glass:
            target_idx = num_slots - 1
            sm.set_material(target_idx, m_glass)
            log(f"Assigned M_Greenhouse_Glass to fallback slot {target_idx} on SM_Greenhouse_GlassRoof")

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
    env_mats = create_environment_materials()
    tune_fp_weapon_material()
    tune_creature_materials()
    repair_all_existing_prop_materials()
    if "--materials-only" not in args:
        import_inc9_props(env_mats)
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    verify_all_game_packages()
    log("=== Increment 9 Asset & Material Pass Complete ===")


if __name__ == "__main__":
    main()
