"""Import Increment 10 Tripo Pro 3D Hero Assets and PBR Materials in UE 5.2.

Run via:
  UnrealEditor-Cmd "<project>/MarsLastGreen.uproject" \
    -ExecutePythonScript="<project>/Tools/import_inc10_tripo.py" \
    -nullrhi -unattended -nop4
"""

import json
import os
import sys
import unreal

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TRIPO_DIR = os.path.join(PROJECT_ROOT, "Assets", "Tripo")

ASSET_TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary

TRIPO_MAP = {
    "SM_Tripo_DropLander": ("DropLander", (0.0, 0.0, 0.0)),
    "SM_Tripo_HeavyDropship": ("HeavyDropship", (0.01, 0.015, 0.02)),
    "SM_Tripo_BotanicalPod": ("BotanicalPod", (0.04, 0.22, 0.14)),
    "SM_Tripo_PulseRifle": ("PulseRifle", (0.02, 0.14, 0.22)),
    "SM_Tripo_AlienBeacon": ("AlienBeacon", (0.04, 0.26, 0.34)),
    "SM_Tripo_SentryTurret": ("SentryTurret", (0.02, 0.12, 0.18)),
    "SM_Tripo_OxygenHarvester": ("OxygenHarvester", (0.03, 0.18, 0.24)),
}


def log(msg):
    unreal.log("MLG_INC10_TRIPO: " + str(msg))


def warn(msg):
    unreal.log_warning("MLG_INC10_TRIPO: " + str(msg))


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


def import_texture(filepath, dest_path, dest_name, is_normal=False, srgb=True):
    if not filepath or not os.path.isfile(filepath):
        return None
    stem = os.path.splitext(os.path.basename(filepath))[0]
    for pre_pkg in (f"{dest_path}/{stem}", f"{dest_path}/{dest_name}"):
        if EAL.does_asset_exist(pre_pkg):
            EAL.delete_asset(pre_pkg)
    task = make_task(filepath, dest_path, dest_name, replace=True)
    ASSET_TOOLS.import_asset_tasks([task])
    imported_paths = list(task.get_editor_property("imported_object_paths") or [])
    candidates = imported_paths + [f"{dest_path}/{stem}", f"{dest_path}/{dest_name}"]
    tex = None
    pkg = None
    for cand in candidates:
        cand_pkg = cand.split(".")[0]
        if EAL.does_asset_exist(cand_pkg):
            tex = EAL.load_asset(cand_pkg)
            if tex is not None:
                pkg = cand_pkg
                break
    if tex:
        if is_normal:
            tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
            tex.set_editor_property("srgb", False)
        else:
            tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT)
            tex.set_editor_property("srgb", srgb)
        tex.set_editor_property("never_stream", True)
        EAL.save_loaded_asset(tex, only_if_is_dirty=False)
        actual_comp = tex.get_editor_property("compression_settings")
        actual_srgb = bool(tex.get_editor_property("srgb"))
        log(f"Bound texture {pkg} (normal={is_normal}, comp={actual_comp}, srgb={actual_srgb})")
    else:
        warn(f"Failed locating imported texture for {filepath} -> tried {candidates}")
    return tex


def sampler_type_for_texture(tex, want_normal=False):
    comp = tex.get_editor_property("compression_settings")
    if want_normal or comp == unreal.TextureCompressionSettings.TC_NORMALMAP:
        return unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
    if bool(tex.get_editor_property("srgb")):
        return unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
    return unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR


def get_or_create_material(mat_pkg_path):
    mat_dir, mat_name = mat_pkg_path.rsplit("/", 1)
    mat = EAL.load_asset(mat_pkg_path)
    if mat is None:
        mat = ASSET_TOOLS.create_asset(mat_name, mat_dir, unreal.Material, unreal.MaterialFactoryNew())
    MEL.delete_all_material_expressions(mat)
    return mat


def build_tripo_material(asset_name, tex_prefix, textures, subtle_emissive):
    mat_pkg = f"/Game/Tripo/Materials/M_Tripo_{tex_prefix}"
    mat = get_or_create_material(mat_pkg)
    EAL.save_loaded_asset(mat, only_if_is_dirty=False)
    tex_dest = "/Game/Tripo/Textures"

    base_tex = import_texture(
        os.path.join(PROJECT_ROOT, textures.get("base_color", "")),
        tex_dest, f"T_{tex_prefix}_D", is_normal=False, srgb=True
    )
    norm_tex = import_texture(
        os.path.join(PROJECT_ROOT, textures.get("normal", "")),
        tex_dest, f"T_{tex_prefix}_N", is_normal=True, srgb=False
    )
    rough_tex = import_texture(
        os.path.join(PROJECT_ROOT, textures.get("roughness", "")),
        tex_dest, f"T_{tex_prefix}_R", is_normal=False, srgb=False
    )
    met_tex = import_texture(
        os.path.join(PROJECT_ROOT, textures.get("metallic", "")),
        tex_dest, f"T_{tex_prefix}_M", is_normal=False, srgb=False
    )

    if base_tex:
        bc_samp = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -380, -180)
        bc_samp.texture = base_tex
        bc_samp.sampler_type = sampler_type_for_texture(base_tex, False)
        connect_prop(bc_samp, "", unreal.MaterialProperty.MP_BASE_COLOR)
    else:
        col = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -260, -180)
        col.set_editor_property("parameter_name", "Color")
        col.set_editor_property("default_value", unreal.LinearColor(0.75, 0.78, 0.82, 1.0))
        connect_prop(col, "", unreal.MaterialProperty.MP_BASE_COLOR)

    if norm_tex:
        n_samp = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -380, 40)
        n_samp.texture = norm_tex
        n_samp.sampler_type = sampler_type_for_texture(norm_tex, True)
        connect_prop(n_samp, "", unreal.MaterialProperty.MP_NORMAL)

    if rough_tex:
        r_samp = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -380, 240)
        r_samp.texture = rough_tex
        r_samp.sampler_type = sampler_type_for_texture(rough_tex, False)
        connect_prop(r_samp, "", unreal.MaterialProperty.MP_ROUGHNESS)
    else:
        r_c = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 240)
        r_c.r = 0.45
        connect_prop(r_c, "", unreal.MaterialProperty.MP_ROUGHNESS)

    if met_tex:
        m_samp = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -380, 420)
        m_samp.texture = met_tex
        m_samp.sampler_type = sampler_type_for_texture(met_tex, False)
        connect_prop(m_samp, "", unreal.MaterialProperty.MP_METALLIC)
    else:
        m_c = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 420)
        m_c.r = 0.25
        connect_prop(m_c, "", unreal.MaterialProperty.MP_METALLIC)

    # Subtle emissive parameter (keeps PBR look rich in Martian dusk and allows MID tinting)
    em_param = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -260, 600)
    em_param.set_editor_property("parameter_name", "EmissiveColor")
    em_param.set_editor_property("default_value", unreal.LinearColor(subtle_emissive[0], subtle_emissive[1], subtle_emissive[2], 1.0))
    connect_prop(em_param, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    MEL.recompile_material(mat)
    EAL.save_asset(mat_pkg, only_if_is_dirty=False)
    return mat


def make_static_mesh_options():
    opts = unreal.FbxImportUI()
    opts.import_mesh = True
    opts.import_as_skeletal = False
    opts.import_materials = False
    opts.import_textures = False
    opts.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
    sm = opts.static_mesh_import_data
    sm.combine_meshes = True
    sm.auto_generate_collision = True
    sm.build_nanite = False
    sm.import_uniform_scale = 1.0
    sm.convert_scene = True
    sm.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS
    return opts


def main():
    manifest_path = os.path.join(TRIPO_DIR, "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh).get("assets", {})

    EAL.make_directory("/Game/Tripo")
    EAL.make_directory("/Game/Tripo/Materials")
    EAL.make_directory("/Game/Tripo/Textures")

    opts = make_static_mesh_options()
    loaded_ok = 0
    for mesh_name, (tex_prefix, em_rgb) in TRIPO_MAP.items():
        if os.environ.get("MLG_ONLY_LANDER") == "1" and mesh_name != "SM_Tripo_DropLander":
            continue
        if os.environ.get("MLG_ONLY_HEAVY_DROPSHIP") == "1" and mesh_name != "SM_Tripo_HeavyDropship":
            continue
        entry = manifest.get(mesh_name, {})
        fbx_rel = entry.get("info", {}).get("fbx", f"Assets/Tripo/{mesh_name}.fbx")
        fbx_abs = os.path.join(PROJECT_ROOT, fbx_rel)
        if not os.path.isfile(fbx_abs):
            warn(f"Missing FBX: {fbx_abs}")
            continue

        mat = build_tripo_material(mesh_name, tex_prefix, entry.get("textures", {}), em_rgb)
        task = make_task(fbx_abs, "/Game/Tripo", mesh_name, options=opts, replace=True)
        ASSET_TOOLS.import_asset_tasks([task])

        pkg = f"/Game/Tripo/{mesh_name}"
        sm = EAL.load_asset(pkg)
        if not sm:
            warn(f"Failed to import/load {pkg}")
            continue

        for i in range(sm.get_num_sections(0) if hasattr(sm, "get_num_sections") else 1):
            pass
        if sm.static_materials and mat:
            for slot_idx in range(len(sm.static_materials)):
                sm.set_material(slot_idx, mat)

        try:
            b = sm.get_bounding_box()
            sz = b.max - b.min
            log(f"Imported {pkg}: size=({sz.x:.1f}, {sz.y:.1f}, {sz.z:.1f})cm minZ={b.min.z:.1f} tris~={entry.get('info',{}).get('triangles',0)}")
        except Exception:
            log(f"Imported {pkg}")

        EAL.save_asset(pkg, only_if_is_dirty=False)
        loaded_ok += 1

    log(f"TRIPO_IMPORT_DONE imported={loaded_ok}/{len(TRIPO_MAP)}")


if __name__ == "__main__":
    main()
