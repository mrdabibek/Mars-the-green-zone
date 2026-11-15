"""Upgrade interior (Habitat walls/floor/ceiling/trim, FP arms) & exterior (Mars ground/rocks/pad, creatures) UE materials.

Run via:
  UnrealEditor-Cmd "<project>/MarsLastGreen.uproject" \
    -ExecutePythonScript="<project>/Tools/tune_inc11_textures.py" \
    -nullrhi -unattended -nop4 -nosound
"""

import unreal

EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary
ASSET_TOOLS = unreal.AssetToolsHelpers.get_asset_tools()


def log(msg):
    unreal.log("MLG_INC11_TEX: " + str(msg))


def get_or_create_material(pkg_path):
    if EAL.does_asset_exist(pkg_path):
        return EAL.load_asset(pkg_path)
    mat_dir, mat_name = pkg_path.rsplit("/", 1)
    EAL.make_directory(mat_dir)
    return ASSET_TOOLS.create_asset(mat_name, mat_dir, unreal.Material, unreal.MaterialFactoryNew())


def make_custom_node(mat, name, x, y, code, inputs, output_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3):
    node = MEL.create_material_expression(mat, unreal.MaterialExpressionCustom, x, y)
    node.set_editor_property("description", name)
    node.set_editor_property("code", code)
    node.set_editor_property("output_type", output_type)
    pins = []
    for key, _, _ in inputs:
        pin = unreal.CustomInput()
        pin.set_editor_property("input_name", key)
        pins.append(pin)
    node.set_editor_property("inputs", pins)
    for idx, (key, cls, props) in enumerate(inputs):
        expr = MEL.create_material_expression(mat, cls, x - 340, y + idx * 120)
        for p, v in props.items():
            expr.set_editor_property(p, v)
        if not MEL.connect_material_expressions(expr, "", node, key):
            raise RuntimeError(f"Failed wiring {key} into {name}")
    return node


def add_emissive_param(mat, default_rgb=(0.0, 0.0, 0.0), y=380):
    em = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -220, y)
    em.set_editor_property("parameter_name", "EmissiveColor")
    em.set_editor_property(
        "default_value",
        unreal.LinearColor(default_rgb[0], default_rgb[1], default_rgb[2], 1.0),
    )
    MEL.connect_material_property(em, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)


def upgrade_habitat_wall():
    pkg = "/Game/Environment/Materials/M_Habitat_Wall"
    mat = get_or_create_material(pkg)
    if not mat:
        return
    MEL.delete_all_material_expressions(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("two_sided", False)

    inputs_bc = [
        ("WP", unreal.MaterialExpressionWorldPosition, {}),
        ("N", unreal.MaterialExpressionPixelNormalWS, {}),
        ("Color", unreal.MaterialExpressionVectorParameter,
         {"parameter_name": "Color", "default_value": unreal.LinearColor(1.0, 1.0, 1.0, 1.0)}),
    ]
    bc = make_custom_node(mat, "BrushedAlloyWall", -220, -180, """
float2 p = abs(N.z) > 0.7 ? WP.xy : (abs(N.x) > abs(N.y) ? WP.yz : WP.xz);
float brush = sin(p.x * 2.4 + sin(p.y * 0.32) * 1.8) * 0.5 + 0.5;
float fine = 0.5 + 0.28 * sin(p.x * 1.9 + cos(p.y * 0.65) * 2.1) + 0.22 * cos(p.y * 2.3 - sin(p.x * 1.1) * 1.7);
float macro = sin(p.x * 0.035) * cos(p.y * 0.041) * 0.5 + 0.5;
float v_seam = 1.0 - smoothstep(0.0, 3.2, abs(fmod(abs(p.x), 100.0) - 50.0));
float h_seam = 1.0 - smoothstep(0.0, 3.6, abs(fmod(abs(p.y), 150.0) - 75.0));
float seam = saturate(max(v_seam, h_seam));
float bevel = saturate(smoothstep(3.2, 10.0, abs(fmod(abs(p.x), 100.0) - 50.0)));
float3 alloy = float3(0.088, 0.102, 0.126)
    * (0.86 + 0.14 * brush + 0.08 * fine + 0.06 * macro)
    * (0.94 + 0.08 * bevel)
    * (1.0 - 0.34 * seam);
return alloy * lerp(float3(1, 1, 1), Color.rgb, 0.24);
""", inputs_bc)
    MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)

    rgh = make_custom_node(mat, "WallRoughness", -220, 140, """
float2 p = abs(N.z) > 0.7 ? WP.xy : (abs(N.x) > abs(N.y) ? WP.yz : WP.xz);
float grain = 0.5 + 0.30 * sin(p.x * 1.4 + cos(p.y * 0.55) * 1.8) + 0.20 * cos(p.y * 2.1 - sin(p.x * 0.9) * 1.5);
float brush = sin(p.x * 2.4 + sin(p.y * 0.32) * 1.8) * 0.5 + 0.5;
float v_seam = 1.0 - smoothstep(0.0, 3.5, abs(fmod(abs(p.x), 100.0) - 50.0));
float h_seam = 1.0 - smoothstep(0.0, 3.8, abs(fmod(abs(p.y), 150.0) - 75.0));
float seam = saturate(max(v_seam, h_seam));
return saturate(lerp(0.28, 0.54, grain * 0.65 + (1.0 - brush) * 0.35) + seam * 0.10);
""", [("WP", unreal.MaterialExpressionWorldPosition, {}),
      ("N", unreal.MaterialExpressionPixelNormalWS, {})],
        unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    MEL.connect_material_property(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)

    met = make_custom_node(mat, "WallMetallic", -220, 270, """
float2 p = abs(N.z) > 0.7 ? WP.xy : (abs(N.x) > abs(N.y) ? WP.yz : WP.xz);
float v_seam = 1.0 - smoothstep(0.0, 3.2, abs(fmod(abs(p.x), 100.0) - 50.0));
return lerp(0.46, 0.24, v_seam);
""", [("WP", unreal.MaterialExpressionWorldPosition, {}),
      ("N", unreal.MaterialExpressionPixelNormalWS, {})],
        unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)

    add_emissive_param(mat, y=380)
    MEL.recompile_material(mat)
    EAL.save_asset(pkg, only_if_is_dirty=False)
    log(f"Upgraded {pkg} with micro-grain, crisp panel seams & 0.28-0.64 roughness")


def upgrade_habitat_floor():
    pkg = "/Game/Environment/Materials/M_Habitat_Floor"
    mat = get_or_create_material(pkg)
    if not mat:
        return
    MEL.delete_all_material_expressions(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("two_sided", False)

    inputs_bc = [
        ("WP", unreal.MaterialExpressionWorldPosition, {}),
        ("Color", unreal.MaterialExpressionVectorParameter,
         {"parameter_name": "Color", "default_value": unreal.LinearColor(1.0, 1.0, 1.0, 1.0)}),
    ]
    bc = make_custom_node(mat, "TreadDeckFloor", -220, -180, """
float2 g = frac(WP.xy / 45.0) - 0.5;
float2 tile = frac(WP.xy / 135.0) - 0.5;
float stud = 1.0 - smoothstep(0.09, 0.15, max(abs(g.x), abs(g.y)));
float rib = smoothstep(0.43, 0.485, max(abs(g.x), abs(g.y)));
float seam = smoothstep(0.475, 0.495, max(abs(tile.x), abs(tile.y)));
float scuff = 0.5 + 0.32 * sin(WP.x * 0.27 + cos(WP.y * 0.31) * 2.2) + 0.18 * cos(WP.y * 0.61 - WP.x * 0.19);
float wear = smoothstep(-0.2, 0.7, sin(WP.x * 0.012) * cos(WP.y * 0.015));
float3 deck = float3(0.058, 0.068, 0.084)
    * (0.84 + 0.22 * stud - 0.16 * rib - 0.24 * seam + 0.09 * scuff + 0.08 * wear);
return deck * lerp(float3(1, 1, 1), Color.rgb, 0.22);
""", inputs_bc)
    MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)

    rgh = make_custom_node(mat, "FloorRoughness", -220, 120, """
float2 g = frac(WP.xy / 45.0) - 0.5;
float2 tile = frac(WP.xy / 135.0) - 0.5;
float stud = 1.0 - smoothstep(0.09, 0.15, max(abs(g.x), abs(g.y)));
float seam = smoothstep(0.47, 0.495, max(abs(tile.x), abs(tile.y)));
float grain = 0.5 + 0.30 * sin(WP.x * 0.52 + cos(WP.y * 0.44) * 1.9) + 0.20 * cos(WP.y * 0.87 - WP.x * 0.33);
float r = lerp(0.56, 0.26, stud) + (grain - 0.5) * 0.08 + seam * 0.09;
return clamp(r, 0.25, 0.65);
""", [("WP", unreal.MaterialExpressionWorldPosition, {})], unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    MEL.connect_material_property(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)

    met = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 260)
    met.r = 0.68
    MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)

    add_emissive_param(mat, y=360)
    MEL.recompile_material(mat)
    EAL.save_asset(pkg, only_if_is_dirty=False)
    log(f"Upgraded {pkg} with treadplate steel deck & 0.25-0.65 roughness variation")


def upgrade_habitat_ceiling_and_trim():
    # 1. Coffered architectural ceiling material
    ceil_pkg = "/Game/Environment/Materials/M_Habitat_Ceiling"
    ceil_mat = get_or_create_material(ceil_pkg)
    if ceil_mat:
        MEL.delete_all_material_expressions(ceil_mat)
        ceil_mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
        ceil_mat.set_editor_property("two_sided", False)
        bc = make_custom_node(ceil_mat, "CofferedCeiling", -220, -180, """
float2 cell = frac(WP.xy / 120.0) - 0.5;
float seam = smoothstep(0.45, 0.49, max(abs(cell.x), abs(cell.y)));
float coffer = smoothstep(0.32, 0.38, max(abs(cell.x), abs(cell.y)));
float grain = 0.5 + 0.30 * sin(WP.x * 1.1 + cos(WP.y * 0.7) * 1.8) + 0.20 * cos(WP.y * 1.4 - WP.x * 0.6);
float3 col = float3(0.074, 0.086, 0.106) * (0.88 + 0.10 * grain + 0.12 * coffer) * (1.0 - 0.28 * seam);
return col * lerp(float3(1, 1, 1), Color.rgb, 0.25);
""", [("WP", unreal.MaterialExpressionWorldPosition, {}),
      ("Color", unreal.MaterialExpressionVectorParameter,
       {"parameter_name": "Color", "default_value": unreal.LinearColor(1.0, 1.0, 1.0, 1.0)})])
        MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)

        rgh = make_custom_node(ceil_mat, "CeilingRoughness", -220, 120, """
float2 cell = frac(WP.xy / 120.0) - 0.5;
float seam = smoothstep(0.45, 0.49, max(abs(cell.x), abs(cell.y)));
float grain = 0.5 + 0.30 * sin(WP.x * 0.9 + cos(WP.y * 0.6) * 1.6) + 0.20 * cos(WP.y * 1.2 - WP.x * 0.5);
return clamp(lerp(0.34, 0.58, grain) + seam * 0.06, 0.28, 0.64);
""", [("WP", unreal.MaterialExpressionWorldPosition, {})], unreal.CustomMaterialOutputType.CMOT_FLOAT1)
        MEL.connect_material_property(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)

        met = MEL.create_material_expression(ceil_mat, unreal.MaterialExpressionConstant, -220, 260)
        met.r = 0.40
        MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
        add_emissive_param(ceil_mat, y=360)
        MEL.recompile_material(ceil_mat)
        EAL.save_asset(ceil_pkg, only_if_is_dirty=False)
        log(f"Upgraded {ceil_pkg} with coffered acoustic bulkhead grain")

    # 2. Structural anodized titanium trim material
    trim_pkg = "/Game/Environment/Materials/M_Habitat_Trim"
    trim_mat = get_or_create_material(trim_pkg)
    if trim_mat:
        MEL.delete_all_material_expressions(trim_mat)
        trim_mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
        trim_mat.set_editor_property("two_sided", False)
        bc = make_custom_node(trim_mat, "TitaniumTrim", -220, -180, """
float2 p = abs(N.z) > 0.7 ? WP.xy : (abs(N.x) > abs(N.y) ? WP.yz : WP.xz);
float brush = sin(p.x * 3.1 + p.y * 0.4) * 0.5 + 0.5;
float grain = 0.5 + 0.30 * sin(p.x * 1.6 + cos(p.y * 0.5) * 2.0) + 0.20 * cos(p.y * 2.1 - p.x * 0.8);
float seam = 1.0 - smoothstep(0.0, 2.5, abs(fmod(abs(p.x), 80.0) - 40.0));
float3 col = float3(0.095, 0.108, 0.128) * (0.88 + 0.14 * brush + 0.07 * grain) * (1.0 - 0.26 * seam);
return col * lerp(float3(1, 1, 1), Color.rgb, 0.45);
""", [("WP", unreal.MaterialExpressionWorldPosition, {}),
      ("N", unreal.MaterialExpressionPixelNormalWS, {}),
      ("Color", unreal.MaterialExpressionVectorParameter,
       {"parameter_name": "Color", "default_value": unreal.LinearColor(1.0, 1.0, 1.0, 1.0)})])
        MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)

        rgh = make_custom_node(trim_mat, "TrimRoughness", -220, 140, """
float2 p = WP.xy + WP.yz * 0.5;
float grain = 0.5 + 0.30 * sin(p.x * 1.3 + cos(p.y * 0.8) * 1.7) + 0.20 * cos(p.y * 1.9 - p.x * 0.7);
return clamp(lerp(0.26, 0.52, grain), 0.25, 0.60);
""", [("WP", unreal.MaterialExpressionWorldPosition, {})], unreal.CustomMaterialOutputType.CMOT_FLOAT1)
        MEL.connect_material_property(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)

        met = MEL.create_material_expression(trim_mat, unreal.MaterialExpressionConstant, -220, 260)
        met.r = 0.76
        MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
        add_emissive_param(trim_mat, y=360)
        MEL.recompile_material(trim_mat)
        EAL.save_asset(trim_pkg, only_if_is_dirty=False)
        log(f"Upgraded {trim_pkg} with anodized structural titanium grain")


def upgrade_landing_pad_materials():
    conc_pkg = "/Game/Environment/Materials/M_LandingPad_Concrete"
    conc = get_or_create_material(conc_pkg)
    if conc:
        MEL.delete_all_material_expressions(conc)
        conc.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
        bc = make_custom_node(conc, "ReinforcedConcrete", -220, -180, """
float2 grid = frac(WP.xy / 140.0) - 0.5;
float joint = smoothstep(0.47, 0.495, max(abs(grid.x), abs(grid.y)));
float agg = 0.5 + 0.32 * sin(WP.x * 0.75 + cos(WP.y * 0.65) * 2.3) + 0.18 * cos(WP.y * 1.3 - WP.x * 0.55);
float dust = smoothstep(-0.3, 0.7, sin(WP.x * 0.008) * cos(WP.y * 0.009));
float3 slab = lerp(float3(0.16, 0.17, 0.19), float3(0.24, 0.14, 0.09), dust * 0.25);
slab *= (0.86 + 0.18 * agg) * (1.0 - 0.30 * joint);
return slab * lerp(float3(1, 1, 1), Color.rgb, 0.35);
""", [("WP", unreal.MaterialExpressionWorldPosition, {}),
      ("Color", unreal.MaterialExpressionVectorParameter,
       {"parameter_name": "Color", "default_value": unreal.LinearColor(1.0, 1.0, 1.0, 1.0)})])
        MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)

        rgh = make_custom_node(conc, "ConcreteRoughness", -220, 120, """
float agg = 0.5 + 0.32 * sin(WP.x * 0.68 + cos(WP.y * 0.58) * 2.1) + 0.18 * cos(WP.y * 1.15 - WP.x * 0.48);
return clamp(lerp(0.62, 0.88, agg), 0.55, 0.90);
""", [("WP", unreal.MaterialExpressionWorldPosition, {})], unreal.CustomMaterialOutputType.CMOT_FLOAT1)
        MEL.connect_material_property(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)

        met = MEL.create_material_expression(conc, unreal.MaterialExpressionConstant, -220, 260)
        met.r = 0.08
        MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
        add_emissive_param(conc, y=360)
        MEL.recompile_material(conc)
        EAL.save_asset(conc_pkg, only_if_is_dirty=False)
        log(f"Upgraded {conc_pkg} with reinforced concrete slab grain & expansion joints")

    scorch_pkg = "/Game/Environment/Materials/M_LandingPad_Scorch"
    scorch = get_or_create_material(scorch_pkg)
    if scorch:
        MEL.delete_all_material_expressions(scorch)
        scorch.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
        bc = make_custom_node(scorch, "ThrusterScorchDeck", -220, -180, """
float2 d = WP.xy - float2(-1850.0, -900.0);
float r = length(d);
float ang = atan2(d.y, d.x);
float streak = sin(ang * 16.0 + r * 0.03) * 0.5 + 0.5;
float soot = 1.0 - smoothstep(90.0, 290.0, r);
float grit = 0.5 + 0.32 * sin(WP.x * 0.95 + cos(WP.y * 0.78) * 2.4) + 0.18 * cos(WP.y * 1.45 - WP.x * 0.62);
float3 base_c = lerp(float3(0.085, 0.088, 0.095), float3(0.028, 0.024, 0.022), saturate(soot * 0.85 + streak * 0.25));
return base_c * (0.84 + 0.20 * grit) * lerp(float3(1, 1, 1), Color.rgb, 0.25);
""", [("WP", unreal.MaterialExpressionWorldPosition, {}),
      ("Color", unreal.MaterialExpressionVectorParameter,
       {"parameter_name": "Color", "default_value": unreal.LinearColor(1.0, 1.0, 1.0, 1.0)})])
        MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)

        rgh = make_custom_node(scorch, "ScorchRoughness", -220, 120, """
float grit = 0.5 + 0.32 * sin(WP.x * 0.85 + cos(WP.y * 0.72) * 2.0) + 0.18 * cos(WP.y * 1.35 - WP.x * 0.55);
return lerp(0.66, 0.92, grit);
""", [("WP", unreal.MaterialExpressionWorldPosition, {})], unreal.CustomMaterialOutputType.CMOT_FLOAT1)
        MEL.connect_material_property(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)

        met = MEL.create_material_expression(scorch, unreal.MaterialExpressionConstant, -220, 260)
        met.r = 0.22
        MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
        add_emissive_param(scorch, y=360)
        MEL.recompile_material(scorch)
        EAL.save_asset(scorch_pkg, only_if_is_dirty=False)
        log(f"Upgraded {scorch_pkg} with thruster scorch streaks")

    deck_pkg = "/Game/Environment/Materials/M_OutpostDeck"
    deck = get_or_create_material(deck_pkg)
    if deck:
        MEL.delete_all_material_expressions(deck)
        deck.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
        deck.set_editor_property("two_sided", False)
        bc = make_custom_node(deck, "OutpostSteelDeck", -220, -180, """
float2 p = abs(N.z) > 0.7 ? WP.xy : (abs(N.x) > abs(N.y) ? WP.yz : WP.xz);
float2 tile = frac(p / 90.0) - 0.5;
float seam = smoothstep(0.46, 0.495, max(abs(tile.x), abs(tile.y)));
float rib = sin(p.x * 1.4 + p.y * 0.25) * 0.5 + 0.5;
float dust = smoothstep(-0.2, 0.7, sin(WP.x * 0.011) * cos(WP.y * 0.013));
float3 steel = lerp(float3(0.082, 0.092, 0.108), float3(0.20, 0.11, 0.07), dust * 0.22);
steel *= (0.86 + 0.14 * rib) * (1.0 - 0.30 * seam);
return steel * lerp(float3(1.0, 1.0, 1.0), Color.rgb, 0.35);
""", [("WP", unreal.MaterialExpressionWorldPosition, {}),
      ("N", unreal.MaterialExpressionPixelNormalWS, {}),
      ("Color", unreal.MaterialExpressionVectorParameter,
       {"parameter_name": "Color", "default_value": unreal.LinearColor(1.0, 1.0, 1.0, 1.0)})])
        MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
        rgh = make_custom_node(deck, "OutpostDeckRoughness", -220, 120, """
float grit = 0.5 + 0.32 * sin(WP.x * 0.92 + cos(WP.y * 0.68) * 2.1) + 0.18 * cos(WP.y * 1.25 - WP.x * 0.58);
return clamp(lerp(0.32, 0.62, grit), 0.28, 0.65);
""", [("WP", unreal.MaterialExpressionWorldPosition, {})], unreal.CustomMaterialOutputType.CMOT_FLOAT1)
        MEL.connect_material_property(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)
        met = MEL.create_material_expression(deck, unreal.MaterialExpressionConstant, -220, 260)
        met.r = 0.68
        MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
        add_emissive_param(deck, y=360)
        MEL.recompile_material(deck)
        EAL.save_asset(deck_pkg, only_if_is_dirty=False)
        log(f"Upgraded {deck_pkg} with riveted steel deck & Mars dust weathering")

    gun_pkg = "/Game/Environment/Materials/M_Metal_Gunmetal"
    gun = get_or_create_material(gun_pkg)
    if gun:
        MEL.delete_all_material_expressions(gun)
        gun.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
        gun.set_editor_property("two_sided", False)
        bc = make_custom_node(gun, "AerospaceGunmetal", -220, -180, """
float2 p = abs(N.z) > 0.7 ? WP.xy : (abs(N.x) > abs(N.y) ? WP.yz : WP.xz);
float brush = sin(p.x * 2.8 + p.y * 0.35) * 0.5 + 0.5;
float fine = 0.5 + 0.30 * sin(p.x * 1.8 + cos(p.y * 0.55) * 2.1) + 0.20 * cos(p.y * 2.2 - p.x * 0.85);
float seam = 1.0 - smoothstep(0.0, 2.4, abs(fmod(abs(p.x), 60.0) - 30.0));
float3 col = float3(0.068, 0.076, 0.092) * (0.86 + 0.16 * brush + 0.06 * fine) * (1.0 - 0.25 * seam);
return col * lerp(float3(1.0, 1.0, 1.0), Color.rgb, 0.35);
""", [("WP", unreal.MaterialExpressionWorldPosition, {}),
      ("N", unreal.MaterialExpressionPixelNormalWS, {}),
      ("Color", unreal.MaterialExpressionVectorParameter,
       {"parameter_name": "Color", "default_value": unreal.LinearColor(1.0, 1.0, 1.0, 1.0)})])
        MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
        rgh = make_custom_node(gun, "GunmetalRoughness", -220, 120, """
float2 p = WP.xy + WP.yz * 0.5;
float grain = 0.5 + 0.30 * sin(p.x * 1.4 + cos(p.y * 0.6) * 1.8) + 0.20 * cos(p.y * 1.9 - p.x * 0.7);
return clamp(lerp(0.28, 0.52, grain), 0.25, 0.58);
""", [("WP", unreal.MaterialExpressionWorldPosition, {})], unreal.CustomMaterialOutputType.CMOT_FLOAT1)
        MEL.connect_material_property(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)
        met = MEL.create_material_expression(gun, unreal.MaterialExpressionConstant, -220, 260)
        met.r = 0.78
        MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
        add_emissive_param(gun, y=360)
        MEL.recompile_material(gun)
        EAL.save_asset(gun_pkg, only_if_is_dirty=False)
        log(f"Upgraded {gun_pkg} with dark brushed aerospace gunmetal")


def upgrade_mars_ground():
    pkg = "/Game/Environment/Materials/M_Mars_Ground"
    mat = EAL.load_asset(pkg)
    rock_d = EAL.load_asset("/Game/Environment/Textures/T_MarsRock_01_D") if EAL.does_asset_exist("/Game/Environment/Textures/T_MarsRock_01_D") else None
    if not mat:
        return
    MEL.delete_all_material_expressions(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)

    uv_fine = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -680, -180)
    uv_fine.set_editor_property("u_tiling", 54.0)
    uv_fine.set_editor_property("v_tiling", 54.0)

    uv_macro = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureCoordinate, -680, -40)
    uv_macro.set_editor_property("u_tiling", 11.0)
    uv_macro.set_editor_property("v_tiling", 11.0)

    node = MEL.create_material_expression(mat, unreal.MaterialExpressionCustom, -200, -160)
    node.set_editor_property("description", "MarsRegolithDunes")
    node.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    custom_inputs = []
    input_names = ("WP", "Color") + (("RockFine", "RockMacro") if rock_d else ())
    for k in input_names:
        pin = unreal.CustomInput()
        pin.set_editor_property("input_name", k)
        custom_inputs.append(pin)
    node.set_editor_property("inputs", custom_inputs)

    wp_expr = MEL.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, -560, -320)
    col_expr = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -560, -180)
    col_expr.set_editor_property("parameter_name", "Color")
    col_expr.set_editor_property("default_value", unreal.LinearColor(0.42, 0.175, 0.09, 1.0))
    MEL.connect_material_expressions(wp_expr, "", node, "WP")
    MEL.connect_material_expressions(col_expr, "", node, "Color")

    if rock_d:
        tex_f = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -480, 60)
        tex_f.texture = rock_d
        tex_f.sampler_type = unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
        MEL.connect_material_expressions(uv_fine, "", tex_f, "UVs")
        MEL.connect_material_expressions(tex_f, "", node, "RockFine")

        tex_m = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -480, 220)
        tex_m.texture = rock_d
        tex_m.sampler_type = unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
        MEL.connect_material_expressions(uv_macro, "", tex_m, "UVs")
        MEL.connect_material_expressions(tex_m, "", node, "RockMacro")

    rock_term = "lerp(float3(0.84, 0.84, 0.84), (RockFine.rgb * 0.6 + RockMacro.rgb * 0.4) * 1.24, 0.62)" if rock_d else "float3(1, 1, 1)"
    node.set_editor_property("code", f"""
float ripple = sin(WP.x * 0.058 + sin(WP.y * 0.015) * 3.4) * 0.5 + 0.5;
float micro_ripple = sin(WP.x * 0.24 - WP.y * 0.07) * 0.5 + 0.5;
float grit = 0.5 + 0.30 * sin(WP.x * 0.55 + cos(WP.y * 0.45) * 2.2) + 0.20 * cos(WP.y * 0.78 - WP.x * 0.39);
float patch = smoothstep(-0.35, 0.65, sin(WP.x * 0.0022) * cos(WP.y * 0.0027));
float3 basalt = Color.rgb * float3(0.76, 0.72, 0.74);
float3 base_reg = lerp(Color.rgb, basalt, patch * 0.42);
float3 reg = base_reg * {rock_term} * (0.76 + 0.24 * ripple + 0.09 * micro_ripple + 0.14 * grit);
return reg;
""")
    MEL.connect_material_property(node, "", unreal.MaterialProperty.MP_BASE_COLOR)

    met = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -180, 80)
    met.r = 0.0
    MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)

    spec = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -180, 160)
    spec.r = 0.14
    MEL.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR)

    rgh = make_custom_node(mat, "MarsGroundRoughness", -200, 250, """
float grit = 0.5 + 0.30 * sin(WP.x * 0.48 + cos(WP.y * 0.38) * 1.9) + 0.20 * cos(WP.y * 0.67 - WP.x * 0.31);
float patch = smoothstep(-0.35, 0.65, sin(WP.x * 0.0022) * cos(WP.y * 0.0027));
return clamp(lerp(0.93, 0.68, patch * 0.55 + grit * 0.35), 0.62, 0.95);
""", [("WP", unreal.MaterialExpressionWorldPosition, {})], unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    MEL.connect_material_property(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)

    add_emissive_param(mat, y=380)
    MEL.recompile_material(mat)
    EAL.save_asset(pkg, only_if_is_dirty=False)
    log(f"Upgraded {pkg} with dual-scale Martian wind ripples, basalt grit & roughness variation")


def upgrade_mars_rocks():
    rock_cfgs = [
        ("M_MarsRock_01", "T_MarsRock_01_D", "T_MarsRock_01_N", "T_MarsRock_01_R", (0.68, 0.28, 0.14)),
        ("M_MarsRock_02", "T_MarsRock_02_D", "T_MarsRock_02_N", "T_MarsRock_02_R", (0.65, 0.26, 0.13)),
    ]
    for mat_name, d_name, n_name, r_name, tint in rock_cfgs:
        pkg = f"/Game/Environment/Materials/{mat_name}"
        mat = EAL.load_asset(pkg) if EAL.does_asset_exist(pkg) else None
        if not mat:
            continue
        tex_d = EAL.load_asset(f"/Game/Environment/Textures/{d_name}") if EAL.does_asset_exist(f"/Game/Environment/Textures/{d_name}") else None
        tex_n = EAL.load_asset(f"/Game/Environment/Textures/{n_name}") if EAL.does_asset_exist(f"/Game/Environment/Textures/{n_name}") else None
        tex_r = EAL.load_asset(f"/Game/Environment/Textures/{r_name}") if EAL.does_asset_exist(f"/Game/Environment/Textures/{r_name}") else None
        if not tex_d:
            continue

        MEL.delete_all_material_expressions(mat)
        mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)

        bc = MEL.create_material_expression(mat, unreal.MaterialExpressionCustom, -200, -180)
        bc.set_editor_property("description", "MarsRockDustBlend")
        bc.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
        bc_pins = []
        for k in ("Diff", "N", "WP", "Color"):
            pin = unreal.CustomInput()
            pin.set_editor_property("input_name", k)
            bc_pins.append(pin)
        bc.set_editor_property("inputs", bc_pins)

        samp_d = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -560, -240)
        samp_d.texture = tex_d
        samp_d.sampler_type = unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
        MEL.connect_material_expressions(samp_d, "", bc, "Diff")

        n_ws = MEL.create_material_expression(mat, unreal.MaterialExpressionVertexNormalWS, -560, -60)
        MEL.connect_material_expressions(n_ws, "", bc, "N")

        wp_expr = MEL.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, -560, 40)
        MEL.connect_material_expressions(wp_expr, "", bc, "WP")

        col_expr = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -560, 160)
        col_expr.set_editor_property("parameter_name", "Color")
        col_expr.set_editor_property("default_value", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
        MEL.connect_material_expressions(col_expr, "", bc, "Color")

        bc.set_editor_property("code", f"""
float grain = 0.5 + 0.30 * sin(WP.x * 0.65 + cos(WP.y * 0.52 + WP.z * 0.41) * 2.2) + 0.20 * cos(WP.y * 0.88 - WP.z * 0.57);
float3 rock = Diff.rgb * float3({tint[0]:.3f}, {tint[1]:.3f}, {tint[2]:.3f}) * (0.90 + 0.22 * grain);
float top_dust = smoothstep(0.32, 0.78, N.z);
float3 dust_col = float3(0.46, 0.20, 0.10) * (0.92 + 0.16 * grain);
return lerp(rock, dust_col, top_dust * 0.42) * Color.rgb;
""")
        MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)

        if tex_r:
            r_node = MEL.create_material_expression(mat, unreal.MaterialExpressionCustom, -200, 140)
            r_node.set_editor_property("description", "MarsRockRoughness")
            r_node.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT1)
            r_pins = []
            for k in ("RghTex", "N"):
                pin = unreal.CustomInput()
                pin.set_editor_property("input_name", k)
                r_pins.append(pin)
            r_node.set_editor_property("inputs", r_pins)

            samp_r = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -560, 320)
            samp_r.texture = tex_r
            samp_r.sampler_type = unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE
            MEL.connect_material_expressions(samp_r, "", r_node, "RghTex")
            MEL.connect_material_expressions(n_ws, "", r_node, "N")
            r_node.set_editor_property("code", """
float top_dust = smoothstep(0.35, 0.80, N.z);
float base_r = lerp(0.42, 0.78, RghTex.r);
return clamp(lerp(base_r, 0.90, top_dust * 0.45), 0.40, 0.92);
""")
            MEL.connect_material_property(r_node, "", unreal.MaterialProperty.MP_ROUGHNESS)
        else:
            rgh_c = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 140)
            rgh_c.r = 0.65
            MEL.connect_material_property(rgh_c, "", unreal.MaterialProperty.MP_ROUGHNESS)

        met = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 260)
        met.r = 0.04
        MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)

        if tex_n:
            samp_n = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -420, 440)
            samp_n.texture = tex_n
            samp_n.sampler_type = unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
            MEL.connect_material_property(samp_n, "", unreal.MaterialProperty.MP_NORMAL)

        add_emissive_param(mat, y=540)
        MEL.recompile_material(mat)
        EAL.save_asset(pkg, only_if_is_dirty=False)
        log(f"Upgraded {pkg} with Martian dust accumulation & mineral roughness")


def fix_fp_arms_and_creature_flags():
    # Fix M_UE4Man_Body Vulkan MatLayerBlend_NormalBlend failure by creating clean EVA Suit Sleeve shader
    arms_pkg = "/Game/FirstPersonArms/Character/Materials/M_UE4Man_Body"
    if EAL.does_asset_exist(arms_pkg):
        mat = EAL.load_asset(arms_pkg)
        if mat:
            MEL.delete_all_material_expressions(mat)
            mat.set_editor_property("used_with_skeletal_mesh", True)
            bc = make_custom_node(mat, "EVASuitWeave", -220, -140, """
float2 w = frac(UV * 42.0) - 0.5;
float weave = 0.85 + 0.15 * sign(w.x * w.y);
return float3(0.76, 0.78, 0.82) * weave;
""", [("UV", unreal.MaterialExpressionTextureCoordinate, {})])
            MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
            rgh = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 60)
            rgh.r = 0.55
            MEL.connect_material_property(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)
            met = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 140)
            met.r = 0.18
            MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
            MEL.recompile_material(mat)
            EAL.save_asset(arms_pkg, only_if_is_dirty=False)
            log(f"Fixed & upgraded EVA sleeve material {arms_pkg} for VULKAN_SM5")

    for kind in ("Raider", "Breaker", "Gunner"):
        pkg = f"/Game/Creatures/{kind}/Materials/M_Alien_{kind}"
        mat = EAL.load_asset(pkg) if EAL.does_asset_exist(pkg) else None
        if mat and not mat.get_editor_property("used_with_skeletal_mesh"):
            mat.set_editor_property("used_with_skeletal_mesh", True)
            MEL.recompile_material(mat)
            EAL.save_asset(pkg, only_if_is_dirty=False)
            log(f"Enabled used_with_skeletal_mesh on {pkg}")


def fix_tripo_materials_and_textures():
    """Fix Tripo normal/metallic/roughness Texture2D sRGB & compression flags and rebuild M_Tripo_* so Vulkan SM5 compiles 0 errors."""
    tripo_specs = [
        ("AlienBeacon", (0.04, 0.26, 0.34)),
        ("BotanicalPod", (0.04, 0.22, 0.14)),
        ("DropLander", (0.0, 0.0, 0.0)),
        ("OxygenHarvester", (0.03, 0.18, 0.24)),
        ("PulseRifle", (0.02, 0.14, 0.22)),
        ("SentryTurret", (0.02, 0.12, 0.18)),
    ]

    def load_first(cands):
        for p in cands:
            if EAL.does_asset_exist(p):
                obj = EAL.load_asset(p)
                if obj is not None:
                    return obj, p
        return None, None

    for prefix, em_rgb in tripo_specs:
        base_tex, _ = load_first([f"/Game/Tripo/Textures/T_{prefix}_BaseColor", f"/Game/Tripo/Textures/T_{prefix}_D"])
        norm_tex, _ = load_first([f"/Game/Tripo/Textures/T_{prefix}_Normal", f"/Game/Tripo/Textures/T_{prefix}_N"])
        rough_tex, _ = load_first([f"/Game/Tripo/Textures/T_{prefix}_Roughness", f"/Game/Tripo/Textures/T_{prefix}_R"])
        met_tex, _ = load_first([f"/Game/Tripo/Textures/T_{prefix}_Metallic", f"/Game/Tripo/Textures/T_{prefix}_M"])

        if base_tex:
            base_tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT)
            base_tex.set_editor_property("srgb", True)
            base_tex.set_editor_property("never_stream", True)
            EAL.save_loaded_asset(base_tex, only_if_is_dirty=False)
        if norm_tex:
            norm_tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
            norm_tex.set_editor_property("srgb", False)
            norm_tex.set_editor_property("never_stream", True)
            EAL.save_loaded_asset(norm_tex, only_if_is_dirty=False)
        for lin_tex in (rough_tex, met_tex):
            if lin_tex:
                lin_tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT)
                lin_tex.set_editor_property("srgb", False)
                lin_tex.set_editor_property("never_stream", True)
                EAL.save_loaded_asset(lin_tex, only_if_is_dirty=False)

        mat_pkg = f"/Game/Tripo/Materials/M_Tripo_{prefix}"
        mat = EAL.load_asset(mat_pkg) if EAL.does_asset_exist(mat_pkg) else None
        if not mat:
            continue
        MEL.delete_all_material_expressions(mat)
        mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)

        if base_tex:
            bc = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -380, -180)
            bc.texture = base_tex
            bc.sampler_type = unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
            MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
        else:
            col = MEL.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -260, -180)
            col.set_editor_property("parameter_name", "Color")
            col.set_editor_property("default_value", unreal.LinearColor(0.55, 0.58, 0.64, 1.0))
            MEL.connect_material_property(col, "", unreal.MaterialProperty.MP_BASE_COLOR)

        if norm_tex:
            ns = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -380, 40)
            ns.texture = norm_tex
            ns.sampler_type = unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
            MEL.connect_material_property(ns, "", unreal.MaterialProperty.MP_NORMAL)

        if rough_tex:
            rs = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -380, 240)
            rs.texture = rough_tex
            rs.sampler_type = unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR
            MEL.connect_material_property(rs, "", unreal.MaterialProperty.MP_ROUGHNESS)
        else:
            rc = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 240)
            rc.r = 0.45
            MEL.connect_material_property(rc, "", unreal.MaterialProperty.MP_ROUGHNESS)

        if met_tex:
            ms = MEL.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -380, 420)
            ms.texture = met_tex
            ms.sampler_type = unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR
            MEL.connect_material_property(ms, "", unreal.MaterialProperty.MP_METALLIC)
        else:
            mc = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 420)
            mc.r = 0.30
            MEL.connect_material_property(mc, "", unreal.MaterialProperty.MP_METALLIC)

        add_emissive_param(mat, default_rgb=em_rgb, y=600)
        MEL.recompile_material(mat)
        EAL.save_asset(mat_pkg, only_if_is_dirty=False)
        log(f"Fixed & compiled Tripo material {mat_pkg} with matched texture sampler types")


def upgrade_solar_dust_material():
    """Tone down solar cells with realistic Martian dust deposition & silicon grid seams."""
    pkg = "/Game/Environment/Materials/Props/M_SolarCell"
    mat = get_or_create_material(pkg)
    if not mat:
        return
    MEL.delete_all_material_expressions(mat)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    bc = make_custom_node(mat, "DustySolarSilicon", -220, -180, """
float2 cell = frac(WP.xy / 18.0) - 0.5;
float grid = smoothstep(0.45, 0.49, max(abs(cell.x), abs(cell.y)));
float dust = smoothstep(-0.2, 0.75, sin(WP.x * 0.025 + WP.y * 0.018) * cos(WP.y * 0.029));
float3 si = lerp(float3(0.055, 0.075, 0.125), float3(0.18, 0.14, 0.11), grid * 0.45);
float3 regolith_film = float3(0.32, 0.15, 0.09);
return lerp(si, regolith_film, dust * 0.34) * lerp(float3(1.0, 1.0, 1.0), Color.rgb, 0.30);
""", [("WP", unreal.MaterialExpressionWorldPosition, {}),
      ("Color", unreal.MaterialExpressionVectorParameter,
       {"parameter_name": "Color", "default_value": unreal.LinearColor(1.0, 1.0, 1.0, 1.0)})])
    MEL.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rgh = make_custom_node(mat, "DustySolarRoughness", -220, 120, """
float dust = smoothstep(-0.2, 0.75, sin(WP.x * 0.025 + WP.y * 0.018) * cos(WP.y * 0.029));
return clamp(lerp(0.28, 0.72, dust * 0.65), 0.25, 0.75);
""", [("WP", unreal.MaterialExpressionWorldPosition, {})], unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    MEL.connect_material_property(rgh, "", unreal.MaterialProperty.MP_ROUGHNESS)
    met = MEL.create_material_expression(mat, unreal.MaterialExpressionConstant, -220, 260)
    met.r = 0.45
    MEL.connect_material_property(met, "", unreal.MaterialProperty.MP_METALLIC)
    add_emissive_param(mat, default_rgb=(0.002, 0.008, 0.016), y=360)
    MEL.recompile_material(mat)
    EAL.save_asset(pkg, only_if_is_dirty=False)
    log(f"Upgraded {pkg} with Martian dust deposition & silicon grid seams")


def main():
    upgrade_habitat_wall()
    upgrade_habitat_floor()
    upgrade_habitat_ceiling_and_trim()
    upgrade_landing_pad_materials()
    upgrade_mars_ground()
    upgrade_mars_rocks()
    upgrade_solar_dust_material()
    fix_tripo_materials_and_textures()
    fix_fp_arms_and_creature_flags()
    log("INC11_TEXTURE_UPGRADE_DONE")


if __name__ == "__main__":
    main()
