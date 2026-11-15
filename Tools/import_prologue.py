"""Import the prologue geometry, material graphs and available audio into /Game/Intro/Prologue."""
from pathlib import Path

import unreal

SOURCE = Path(__file__).resolve().parents[1] / "Assets" / "Intro"
DEST = "/Game/Intro/Prologue"
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
LIB = unreal.EditorAssetLibrary
GRAPH = unreal.MaterialEditingLibrary


def import_file(file, options=None):
    task = unreal.AssetImportTask()
    task.filename = str(file)
    task.destination_name = file.stem
    task.destination_path = DEST
    task.automated = True
    task.replace_existing = True
    task.replace_existing_settings = True
    task.save = True
    if options is not None:
        task.options = options
    TOOLS.import_asset_tasks([task])
    imported = list(task.get_editor_property("imported_object_paths") or [])
    candidates = [c.split(".")[0] for c in imported] + [f"{DEST}/{file.stem}"]
    asset = None
    for cand in candidates:
        if LIB.does_asset_exist(cand):
            asset = LIB.load_asset(cand)
            if asset is not None:
                break
    if asset is None:
        raise RuntimeError(f"Prologue import failed: {file} (tried {candidates})")
    return asset


def import_earth_texture(file):
    pkg = f"{DEST}/{file.stem}"
    if LIB.does_asset_exist(pkg):
        tex = LIB.load_asset(pkg)
        if isinstance(tex, unreal.Texture2D):
            tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT)
            tex.set_editor_property("srgb", True)
            tex.set_editor_property("never_stream", True)
            if LIB.save_asset(pkg, only_if_is_dirty=False) or LIB.save_loaded_asset(tex, only_if_is_dirty=False):
                unreal.log(f"PROLOGUE: verified {pkg} (never_stream={tex.get_editor_property('never_stream')})")
                return tex
        unreal.log_warning(f"PROLOGUE: {pkg} partial/unsaveable; clearing references and reimporting")
        mat_pkg = f"{DEST}/M_BlueMarble"
        if LIB.does_asset_exist(mat_pkg):
            old_mat = LIB.load_asset(mat_pkg)
            if old_mat is not None:
                GRAPH.delete_all_material_expressions(old_mat)
                LIB.save_loaded_asset(old_mat, only_if_is_dirty=False)
        LIB.delete_asset(pkg)

    task = unreal.AssetImportTask()
    task.filename = str(file)
    task.destination_name = file.stem
    task.destination_path = DEST
    task.automated = True
    task.replace_existing = LIB.does_asset_exist(pkg)
    task.replace_existing_settings = True
    task.save = True
    TOOLS.import_asset_tasks([task])

    imported = list(task.get_editor_property("imported_object_paths") or [])
    candidates = [c.split(".")[0] for c in imported] + [pkg]
    tex = None
    for cand in candidates:
        if LIB.does_asset_exist(cand):
            loaded = LIB.load_asset(cand)
            if isinstance(loaded, unreal.Texture2D):
                tex = loaded
                pkg = cand
                break
    if tex is None:
        raise RuntimeError(f"Prologue texture import failed: {file} (tried {candidates})")
    tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT)
    tex.set_editor_property("srgb", True)
    tex.set_editor_property("never_stream", True)
    if not (LIB.save_asset(pkg, only_if_is_dirty=False) or LIB.save_loaded_asset(tex, only_if_is_dirty=False)):
        raise RuntimeError(f"Prologue texture save failed: {pkg}")
    unreal.log(f"PROLOGUE: imported {pkg} (never_stream={tex.get_editor_property('never_stream')})")
    return tex


def material(name, inputs, shader, blend=unreal.BlendMode.BLEND_OPAQUE):
    mat = LIB.load_asset(f"{DEST}/{name}") if LIB.does_asset_exist(f"{DEST}/{name}") else None
    if mat is None:
        mat = TOOLS.create_asset(name, DEST, unreal.Material, unreal.MaterialFactoryNew())
    GRAPH.delete_all_material_expressions(mat)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("blend_mode", blend)
    mat.set_editor_property("two_sided", blend != unreal.BlendMode.BLEND_OPAQUE or name == "M_OrbitalBackdrop")
    custom = GRAPH.create_material_expression(mat, unreal.MaterialExpressionCustom, 0, 0)
    custom.set_editor_property("code", shader)
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    pins = []
    for key, cls, props in inputs:
        pin = unreal.CustomInput()
        pin.set_editor_property("input_name", key)
        pins.append(pin)
    custom.set_editor_property("inputs", pins)
    for i, (key, cls, props) in enumerate(inputs):
        if cls == unreal.MaterialExpressionTransformPosition:
            wp = GRAPH.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, -580, 120 * i)
            node = GRAPH.create_material_expression(mat, unreal.MaterialExpressionTransformPosition, -320, 120 * i)
            node.set_editor_property(
                "transform_source_type", unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD
            )
            node.set_editor_property(
                "transform_type", unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL
            )
            if not (
                GRAPH.connect_material_expressions(wp, "", node, "Input")
                or GRAPH.connect_material_expressions(wp, "", node, "")
            ):
                raise RuntimeError(f"Could not connect WorldPosition to TransformPosition for {name}")
        else:
            node = GRAPH.create_material_expression(mat, cls, -320, 120 * i)
            for prop, value in props.items():
                node.set_editor_property(prop, value)
        if not GRAPH.connect_material_expressions(node, "", custom, key):
            raise RuntimeError(f"Could not connect {key} to {name}")
    GRAPH.connect_material_property(custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    GRAPH.recompile_material(mat)
    LIB.save_loaded_asset(mat, only_if_is_dirty=False)
    return mat


uv = ("UV", unreal.MaterialExpressionTextureCoordinate, {})
normal = ("N", unreal.MaterialExpressionPixelNormalWS, {})
view = ("V", unreal.MaterialExpressionCameraVectorWS, {})
local_pos = ("LocalPos", unreal.MaterialExpressionTransformPosition, {})
crack_amount = (
    "CrackAmount",
    unreal.MaterialExpressionScalarParameter,
    {"parameter_name": "CrackAmount", "default_value": 0.0},
)
gain = ("Gain", unreal.MaterialExpressionScalarParameter, {"parameter_name": "Gain", "default_value": 1.0})
time_param = ("Time", unreal.MaterialExpressionScalarParameter, {"parameter_name": "Time", "default_value": 0.0})
tint = (
    "Tint",
    unreal.MaterialExpressionVectorParameter,
    {"parameter_name": "Tint", "default_value": unreal.LinearColor(1, 0.24, 0.06, 1)},
)

texture = import_earth_texture(SOURCE / "T_EarthBlueMarble.jpg")

surface = material(
    "M_BlueMarble",
    [
        uv,
        normal,
        view,
        crack_amount,
        time_param,
        local_pos,
        (
            "Albedo",
            unreal.MaterialExpressionTextureSample,
            {"texture": texture, "sampler_type": unreal.MaterialSamplerType.SAMPLERTYPE_COLOR},
        ),
    ],
    """
float3 Nw = normalize(N);
float3 Vw = normalize(V);
float mu = dot(Nw, normalize(float3(-0.68, 0.38, -0.22)));
float day = smoothstep(-0.22, 0.35, mu);
float limb = pow(max(1.0 - saturate(dot(Nw, Vw)), 1e-5), 2.8);
float sun = 0.085 + smoothstep(-0.14, 0.82, mu) * 1.68;
float3 oceanGlow = float3(0.08, 0.36, 0.96) * limb * (0.42 + 0.95 * day);
float3 baseEarth = Albedo * sun + oceanGlow;

float crackAmt = saturate(CrackAmount);
float3 p = normalize(LocalPos + float3(0.0, 0.0, 1e-5));
float3 w1 = float3(
    sin(p.y * 5.7 + cos(p.z * 4.3) * 1.4),
    sin(p.z * 6.1 + cos(p.x * 4.9) * 1.3),
    sin(p.x * 5.3 + cos(p.y * 6.4) * 1.5)
) * 0.22;
float3 w2 = float3(
    cos(p.z * 14.3 + p.x * 9.7),
    cos(p.x * 13.7 + p.y * 10.1),
    cos(p.y * 15.1 + p.z * 8.9)
) * 0.065;

// Primary tectonic Voronoi rifts (F2 - F1 in warped 3D local sphere space)
float3 wp1 = (p + w1 + w2) * 3.8;
float3 c1 = floor(wp1);
float3 f1v = frac(wp1);
float d1a = 8.0, d1b = 8.0;
for (int z1 = -1; z1 <= 1; z1++)
for (int y1 = -1; y1 <= 1; y1++)
for (int x1 = -1; x1 <= 1; x1++)
{
    float3 g1 = float3(x1, y1, z1);
    float3 id1 = c1 + g1;
    float3 rnd1 = frac(sin(float3(
        dot(id1, float3(127.1, 311.7, 74.7)),
        dot(id1, float3(269.5, 183.3, 246.1)),
        dot(id1, float3(113.5, 271.9, 124.6))
    )) * 43758.5453);
    float3 diff1 = g1 + (0.14 + 0.72 * rnd1) - f1v;
    float distSq1 = dot(diff1, diff1);
    if (distSq1 < d1a) { d1b = d1a; d1a = distSq1; }
    else if (distSq1 < d1b) { d1b = distSq1; }
}
float edge1 = sqrt(max(d1b, 1e-6)) - sqrt(max(d1a, 1e-6));

// Secondary branching magma fractures radiating off primary rifts
float3 wp2 = (p + w1 * 1.35 + w2 * 1.75) * 9.2;
float3 c2 = floor(wp2);
float3 f2v = frac(wp2);
float d2a = 8.0, d2b = 8.0;
for (int z2 = -1; z2 <= 1; z2++)
for (int y2 = -1; y2 <= 1; y2++)
for (int x2 = -1; x2 <= 1; x2++)
{
    float3 g2 = float3(x2, y2, z2);
    float3 id2 = c2 + g2;
    float3 rnd2 = frac(sin(float3(
        dot(id2, float3(191.3, 241.7, 93.1)),
        dot(id2, float3(157.7, 307.1, 179.3)),
        dot(id2, float3(283.9, 131.5, 227.7))
    )) * 43758.5453);
    float3 diff2 = g2 + (0.14 + 0.72 * rnd2) - f2v;
    float distSq2 = dot(diff2, diff2);
    if (distSq2 < d2a) { d2b = d2a; d2a = distSq2; }
    else if (distSq2 < d2b) { d2b = distSq2; }
}
float edge2 = sqrt(max(d2b, 1e-6)) - sqrt(max(d2a, 1e-6));

// Thermal shockwave front racing outward across dark oceans & continents
float3 epicenter = normalize(float3(-0.35, -0.78, 0.50));
float angDist = acos(clamp(dot(p, epicenter), -0.9999, 0.9999)) / 3.14159265;
float frontR = crackAmt * 1.18;
float waveReveal = smoothstep(frontR + 0.12, frontR - 0.16, angDist);
float shockFront = exp2(-95.0 * (angDist - frontR) * (angDist - frontR)) * smoothstep(0.02, 0.12, crackAmt);

float regionNoise = 0.5 + 0.5 * (
    0.55 * sin(p.x * 3.7 + p.y * 2.9 - p.z * 3.1) +
    0.45 * cos(p.y * 6.3 - p.z * 5.1 + p.x * 4.4)
);
float actPrim = saturate(smoothstep(0.04, 0.92, crackAmt * 1.40 + regionNoise * 0.40 - 0.30) * (0.25 + 0.75 * waveReveal));
float actSec  = saturate(smoothstep(0.16, 0.98, crackAmt * 1.25 + regionNoise * 0.35 - 0.38) * waveReveal);
float branchZone = saturate(0.32 + (1.0 - edge1 * 1.55));

float wPrim = 0.024 + 0.062 * crackAmt;
float wSec  = 0.015 + 0.034 * crackAmt;

float core1 = (1.0 - smoothstep(0.0, wPrim * 0.45, edge1)) * actPrim;
float rim1  = (1.0 - smoothstep(wPrim * 0.25, wPrim * 1.90, edge1)) * actPrim;
float halo1 = (1.0 - smoothstep(wPrim * 0.60, wPrim * 4.40, edge1)) * actPrim;

float core2 = (1.0 - smoothstep(0.0, wSec * 0.45, edge2)) * actSec * branchZone;
float rim2  = (1.0 - smoothstep(wSec * 0.25, wSec * 1.80, edge2)) * actSec * branchZone;

float core = saturate(core1 + core2 * 0.85);
float rim  = saturate(rim1 + rim2 * 0.75);
float cPow = pow(max(crackAmt, 1e-5), 1.25);
float pulse = 0.86 + 0.24 * sin(Time * 9.5 - edge1 * 18.0 - angDist * 6.5);

float3 crackGlow =
      halo1 * float3(1.25, 0.14, 0.018) * (0.55 + 0.45 * limb)
    + rim   * float3(6.20, 0.88, 0.065) * pulse
    + core  * float3(12.5, 4.80, 0.850) * pulse
    + shockFront * float3(3.40, 0.65, 0.10) * (0.45 + 0.55 * regionNoise);

float3 atmosHeat = float3(1.65, 0.28, 0.035) * limb * cPow;
float scorch = saturate(rim * 0.78 + halo1 * 0.40 + waveReveal * crackAmt * 0.38) * cPow;
float crackMask = step(0.001, crackAmt);
return baseEarth * (1.0 - scorch * 0.72 * crackMask) + (crackGlow * cPow + atmosHeat) * crackMask;
""",
)

mantle = material(
    "M_ExposedMantle",
    [uv, gain, time_param, local_pos],
    """
float3 p = LocalPos * 0.01;
float radialDepth = saturate((1.0 - length(p)) / 0.18);
float depth = lerp(radialDepth, UV.y, 0.38);

float3 w = float3(
    sin(p.y * 11.3 + cos(p.z * 7.1) * 1.3),
    sin(p.z * 12.7 + cos(p.x * 8.3) * 1.2),
    sin(p.x * 10.9 + cos(p.y * 9.7) * 1.4)
) * 0.14;

// Seamless 3D Voronoi molten magma channels
float3 mp1 = (p + w) * 8.4;
float3 mc1 = floor(mp1);
float3 mf1 = frac(mp1);
float m1a = 8.0, m1b = 8.0;
for (int z1 = -1; z1 <= 1; z1++)
for (int y1 = -1; y1 <= 1; y1++)
for (int x1 = -1; x1 <= 1; x1++)
{
    float3 g1 = float3(x1, y1, z1);
    float3 id1 = mc1 + g1;
    float3 rnd1 = frac(sin(float3(
        dot(id1, float3(127.1, 311.7, 74.7)),
        dot(id1, float3(269.5, 183.3, 246.1)),
        dot(id1, float3(113.5, 271.9, 124.6))
    )) * 43758.5453);
    float3 diff1 = g1 + (0.15 + 0.70 * rnd1) - mf1;
    float dsq1 = dot(diff1, diff1);
    if (dsq1 < m1a) { m1b = m1a; m1a = dsq1; }
    else if (dsq1 < m1b) { m1b = dsq1; }
}
float vein1 = sqrt(max(m1b, 1e-6)) - sqrt(max(m1a, 1e-6));

// Fine secondary hairline tectonic fissures
float3 mp2 = (p + w * 1.45) * 18.5;
float3 mc2 = floor(mp2);
float3 mf2 = frac(mp2);
float m2a = 8.0, m2b = 8.0;
for (int z2 = -1; z2 <= 1; z2++)
for (int y2 = -1; y2 <= 1; y2++)
for (int x2 = -1; x2 <= 1; x2++)
{
    float3 g2 = float3(x2, y2, z2);
    float3 id2 = mc2 + g2;
    float3 rnd2 = frac(sin(float3(
        dot(id2, float3(173.3, 251.9, 107.1)),
        dot(id2, float3(229.7, 149.3, 293.5)),
        dot(id2, float3(137.9, 211.1, 163.7))
    )) * 43758.5453);
    float3 diff2 = g2 + (0.15 + 0.70 * rnd2) - mf2;
    float dsq2 = dot(diff2, diff2);
    if (dsq2 < m2a) { m2b = m2a; m2a = dsq2; }
    else if (dsq2 < m2b) { m2b = dsq2; }
}
float vein2 = sqrt(max(m2b, 1e-6)) - sqrt(max(m2a, 1e-6));

// 3D rocky cooling basalt grain + crustal depth strata using non-degenerate UV.y
float n1 = 0.5 + 0.5 * sin(p.x * 23.0 + sin(p.y * 19.0 + p.z * 17.0) * 2.1);
float n2 = 0.5 + 0.5 * cos(p.y * 47.0 - sin(p.z * 41.0 + p.x * 37.0) * 1.9);
float n3 = 0.5 + 0.5 * sin(p.z * 83.0 + cos(p.x * 71.0 - p.y * 67.0) * 1.7);
float basaltGrain = n1 * 0.50 + n2 * 0.32 + n3 * 0.18;
float strata = 0.5 + 0.5 * sin(UV.y * 22.0 + basaltGrain * 4.2 + sin(UV.x * 12.56637) * 1.1);
float pulse = 0.88 + 0.20 * sin(Time * 6.8 + basaltGrain * 5.0);

float veinWidth = lerp(0.045, 0.125, depth);
float mainCore = 1.0 - smoothstep(0.0, veinWidth * 0.42, vein1);
float mainGlow = 1.0 - smoothstep(veinWidth * 0.25, veinWidth * 1.85, vein1);
float fineVein = (1.0 - smoothstep(0.0, 0.048, vein2)) * (0.40 + 0.60 * depth);
float magmaMask = saturate(mainGlow + fineVein * 0.70);

float3 basalt = lerp(float3(0.014, 0.011, 0.013), float3(0.064, 0.030, 0.020), basaltGrain * (0.65 + 0.35 * strata))
              + float3(0.16, 0.024, 0.005) * pow(max(depth, 1e-5), 1.50) * (0.35 + 0.65 * basaltGrain);

float3 molten = (mainGlow * float3(3.6, 0.42, 0.032)
              + fineVein * float3(2.3, 0.28, 0.022)
              + mainCore * float3(9.5, 2.85, 0.380)) * pulse;

return Gain * (basalt * (1.0 - magmaMask * 0.58) + molten);
""",
)

core_mat = material(
    "M_PrologueCore",
    [normal, view, gain, time_param, local_pos],
    """
float3 Nw = normalize(N);
float3 Vw = normalize(V);
float facing = saturate(dot(Nw, Vw));
float limb = pow(max(1.0 - facing, 1e-5), 2.2);
float3 p = normalize(LocalPos + float3(0.0, 0.0, 1e-5));

// Boiling 3D magma convection cells animated in Time
float3 flow = float3(
    sin(p.y * 5.2 + Time * 0.85) * 0.18,
    cos(p.z * 4.8 - Time * 0.72) * 0.18,
    sin(p.x * 5.6 + Time * 0.94) * 0.18
);
float3 cp = (p + flow) * 4.6;
float3 cc = floor(cp);
float3 cf = frac(cp);
float c1 = 8.0, c2 = 8.0;
for (int z1 = -1; z1 <= 1; z1++)
for (int y1 = -1; y1 <= 1; y1++)
for (int x1 = -1; x1 <= 1; x1++)
{
    float3 g = float3(x1, y1, z1);
    float3 id = cc + g;
    float3 rnd = frac(sin(float3(
        dot(id, float3(127.1, 311.7, 74.7)),
        dot(id, float3(269.5, 183.3, 246.1)),
        dot(id, float3(113.5, 271.9, 124.6))
    )) * 43758.5453);
    float3 diff = g + (0.16 + 0.68 * rnd) - cf;
    float dsq = dot(diff, diff);
    if (dsq < c1) { c2 = c1; c1 = dsq; }
    else if (dsq < c2) { c2 = dsq; }
}
float cellEdge = sqrt(max(c2, 1e-6)) - sqrt(max(c1, 1e-6));
float turb = 0.5 + 0.5 * sin(p.x * 13.0 + p.y * 11.0 - Time * 2.4 + cos(p.z * 15.0 + Time * 1.9) * 1.6);

float crustMask = smoothstep(0.14, 0.42, cellEdge) * smoothstep(0.32, 0.72, turb);
float hotCore = (1.0 - smoothstep(0.0, 0.22, cellEdge)) + (1.0 - crustMask) * 0.65;
float pulse = 0.90 + 0.18 * sin(Time * 7.5 + turb * 4.0);

float3 cooledSlag = float3(0.09, 0.018, 0.005);
float3 magmaRiver = lerp(float3(4.5, 0.62, 0.05), float3(13.5, 5.40, 1.30), saturate(hotCore * 0.78));
float3 coronaEdge = float3(7.5, 1.85, 0.22) * limb;
return Gain * (lerp(magmaRiver, cooledSlag, crustMask * 0.85) * pulse + coronaEdge);
""",
)

core_corona = material(
    "M_PrologueCoreCorona",
    [normal, view, gain, time_param, local_pos],
    """
float3 Nw = normalize(N);
float3 Vw = normalize(V);
float3 p = normalize(LocalPos + float3(0.0, 0.0, 1e-5));
float rim = pow(max(1.0 - saturate(abs(dot(Nw, Vw))), 1e-5), 2.3);
float wave = 0.72 + 0.28 * sin(p.x * 9.0 + p.y * 7.0 - Time * 4.5) * cos(p.z * 8.0 + Time * 3.7);
float3 glow = lerp(float3(4.2, 0.65, 0.08), float3(11.0, 3.80, 0.75), rim);
return glow * Gain * rim * wave;
""",
    unreal.BlendMode.BLEND_ADDITIVE,
)

starfield = material(
    "M_OrbitalBackdrop",
    [uv],
    """
float2 scaled = UV * float2(520.0, 410.0);
float2 cell = floor(scaled);
float random = frac(sin(dot(cell, float2(127.1, 311.7))) * 43758.5453);
float2 pos = 0.22 + 0.56 * float2(frac(random * 139.17), frac(random * 291.17));
float star = (1.0 - smoothstep(0.07, 0.28, length(frac(scaled) - pos))) * pow(max(random, 1e-5), 16.0) * 1.4;
float haze = pow(max(saturate(1.0 - abs(UV.y - UV.x * 0.35 - 0.27) * 3.2), 1e-5), 5.0);
return float3(0.0016, 0.0027, 0.005) + haze * float3(0.004, 0.006, 0.011) + star * float3(0.70, 0.82, 1.0);
""",
)

material(
    "M_PrologueGlow",
    [
        uv,
        gain,
        tint,
        ("Ring", unreal.MaterialExpressionScalarParameter, {"parameter_name": "Ring", "default_value": 0.0}),
    ],
    """
float2 p = (UV - 0.5) * 2.0;
float r = length(p);
float ring = exp2(-520.0 * (r - 0.72) * (r - 0.72)) + 0.21 * exp2(-49.0 * (r - 0.72) * (r - 0.72));
float glow = pow(max(saturate(1.0 - r), 1e-5), 3.0);
return Tint * Gain * lerp(glow, ring * saturate((1.0 - r) * 8.0), Ring);
""",
    unreal.BlendMode.BLEND_ADDITIVE,
)

material(
    "M_ProloguePlume",
    [
        uv,
        normal,
        view,
        gain,
        time_param,
        (
            "Tint",
            unreal.MaterialExpressionVectorParameter,
            {"parameter_name": "Tint", "default_value": unreal.LinearColor(1.0, 0.45, 0.12, 1.0)},
        ),
    ],
    """
float fresnel = pow(max(saturate(abs(dot(normalize(N), normalize(V)))), 1e-5), 1.45);
float axial = smoothstep(0.02, 0.20, UV.y) * smoothstep(0.98, 0.28, UV.y);
float mach = 0.78 + 0.22 * sin(UV.y * 34.0 - Time * 48.0);
float streak = 0.84 + 0.16 * sin(UV.x * 37.7 + Time * 19.0);
float core = pow(max(saturate(fresnel * axial), 1e-5), 1.15) * mach * streak;
float3 hot = lerp(Tint, float3(1.0, 0.92, 0.72), pow(max(core, 1e-5), 2.2) * 0.75);
return hot * Gain * core;
""",
    unreal.BlendMode.BLEND_ADDITIVE,
)

options = unreal.FbxImportUI()
options.import_as_skeletal = False
options.import_mesh = True
options.import_materials = options.import_textures = False
options.static_mesh_import_data.combine_meshes = True
options.static_mesh_import_data.auto_generate_collision = False
options.static_mesh_import_data.generate_lightmap_u_vs = False

for file in sorted(SOURCE.glob("SM_Prologue_*.fbx")):
    mesh = import_file(file, options)
    stem = file.stem
    if stem == "SM_Prologue_Core":
        for slot in range(len(mesh.static_materials)):
            mesh.set_material(slot, core_mat)
    elif stem.startswith("SM_Prologue_Ejecta_"):
        for slot in range(len(mesh.static_materials)):
            mesh.set_material(slot, mantle)
    else:
        for slot in range(len(mesh.static_materials)):
            mesh.set_material(slot, surface if slot == 0 else mantle)
    LIB.save_loaded_asset(mesh, only_if_is_dirty=False)
    unreal.log(f"PROLOGUE: {mesh.get_name()} {mesh.get_bounds().box_extent}")

for wav in sorted(SOURCE.glob("Prologue_*.wav")):
    import_file(wav)
unreal.log("PROLOGUE: import complete")
