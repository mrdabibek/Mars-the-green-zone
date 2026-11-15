"""Run in UE editor with -ExecutePythonScript to import intro meshes and tune intro/creature materials."""
import os
import unreal

EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary
ASSET_TOOLS = unreal.AssetToolsHelpers.get_asset_tools()

root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Assets", "Intro"))
for name in ("SM_Intro_EarthWhole", "SM_Intro_EarthCore", "SM_Intro_EarthShard", "SM_Intro_DropLander"):
    path = os.path.join(root, name + ".fbx")
    if not os.path.isfile(path):
        raise RuntimeError("Missing " + path)
    options = unreal.FbxImportUI()
    options.import_as_skeletal = False
    options.import_mesh = True
    options.import_materials = True
    options.import_textures = False
    options.static_mesh_import_data.combine_meshes = True
    task = unreal.AssetImportTask()
    task.filename = path
    task.destination_path = "/Game/Intro"
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    task.options = options
    ASSET_TOOLS.import_asset_tasks([task])
    if not EAL.does_asset_exist("/Game/Intro/" + name):
        raise RuntimeError("Import failed: " + name)
    unreal.log("INC11 imported " + name)


def make_emissive_mat(mat_pkg, base_rgb, emissive_rgb, roughness=0.45, metallic=0.1):
    mat_dir, mat_name = mat_pkg.rsplit("/", 1)
    mat = EAL.load_asset(mat_pkg)
    if mat is None:
        mat = ASSET_TOOLS.create_asset(mat_name, mat_dir, unreal.Material, unreal.MaterialFactoryNew())
    MEL.delete_all_material_expressions(mat)
    col = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -300, -180)
    col.set_editor_property("parameter_name", "Color")
    col.set_editor_property("default_value", unreal.LinearColor(*base_rgb, 1.0))
    MEL.connect_material_property(col, "", unreal.MaterialProperty.MP_BASE_COLOR)

    r_c = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 0)
    r_c.r = float(roughness)
    MEL.connect_material_property(r_c, "", unreal.MaterialProperty.MP_ROUGHNESS)

    m_c = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 90)
    m_c.r = float(metallic)
    MEL.connect_material_property(m_c, "", unreal.MaterialProperty.MP_METALLIC)

    em = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -300, 220)
    em.set_editor_property("parameter_name", "EmissiveColor")
    em.set_editor_property("default_value", unreal.LinearColor(*emissive_rgb, 1.0))
    MEL.connect_material_property(em, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    MEL.recompile_material(mat)
    EAL.save_asset(mat_pkg, only_if_is_dirty=False)
    return mat


intro_mats = {
    "SM_Intro_EarthWhole": ("/Game/Intro/M_Intro_EarthWhole", (0.12, 0.42, 0.92), (0.28, 0.72, 1.65), 0.35, 0.05),
    "SM_Intro_EarthCore": ("/Game/Intro/M_Intro_EarthCore", (1.0, 0.55, 0.16), (6.0, 2.2, 0.45), 0.25, 0.0),
    "SM_Intro_EarthShard": ("/Game/Intro/M_Intro_EarthShard", (0.20, 0.12, 0.10), (1.8, 0.52, 0.12), 0.65, 0.15),
}
for mesh_name, (mat_pkg, b_rgb, e_rgb, rgh, met) in intro_mats.items():
    sm = EAL.load_asset(f"/Game/Intro/{mesh_name}")
    mat = make_emissive_mat(mat_pkg, b_rgb, e_rgb, rgh, met)
    if sm and mat and sm.static_materials:
        for i in range(len(sm.static_materials)):
            sm.set_material(i, mat)
        EAL.save_asset(f"/Game/Intro/{mesh_name}", only_if_is_dirty=False)
        unreal.log(f"INC11 tuned material {mat_pkg} on {mesh_name}")

# Ensure all skeletal creature materials have used_with_skeletal_mesh enabled cleanly
for kind in ("Raider", "Breaker", "Gunner"):
    mat_pkg = f"/Game/Creatures/{kind}/Materials/M_Alien_{kind}"
    mat = EAL.load_asset(mat_pkg)
    if mat and not mat.get_editor_property("used_with_skeletal_mesh"):
        mat.set_editor_property("used_with_skeletal_mesh", True)
        MEL.recompile_material(mat)
        EAL.save_asset(mat_pkg, only_if_is_dirty=False)
        unreal.log(f"Enabled used_with_skeletal_mesh on {mat_pkg}")
