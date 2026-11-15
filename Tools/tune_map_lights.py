# Multiplies PointLights in /Game/Maps/Base by RELATIVE factors: env MLG_LIGHT_FACTOR_INT for interior lamps (label starts with
# PointLight_Habitat / Corridor / Greenhouse / GrowLamp) and MLG_LIGHT_FACTOR_EXT for everything else (beacons, relay, ice field).
# Interiors need far less than exteriors: indoor surfaces are lit only by these lamps, outdoors the sun/sky carry the scene (see rendered tests).
# Keep LIGHT_SCALE_INTERIOR / LIGHT_SCALE_EXTERIOR in Tools/build_base_map.py equal to the resulting absolute scales.
# Backups: Saved/backups/Base.umap.before_light_scale (original), .at_0.03 (all x0.03)
import os, unreal
fi = float(os.environ.get('MLG_LIGHT_FACTOR_INT', '1.0')); fe = float(os.environ.get('MLG_LIGHT_FACTOR_EXT', '1.0'))
fs = float(os.environ.get('MLG_SUN_FACTOR', '1.0')); fk = float(os.environ.get('MLG_SKY_FACTOR', '1.0'))   # relative: DirectionalLight / SkyLight
INT = ('PointLight_Habitat', 'PointLight_Corridor', 'PointLight_Greenhouse', 'PointLight_GrowLamp')
unreal.EditorLoadingAndSavingUtils.load_map('/Game/Maps/Base')
ni = ne = 0
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_class().get_name() == 'PointLight':
        c = a.get_component_by_class(unreal.LightComponent)
        interior = a.get_actor_label().startswith(INT)
        c.set_editor_property('intensity', c.get_editor_property('intensity') * (fi if interior else fe))
        ni += interior; ne += (not interior)
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    cn = a.get_class().get_name()
    if cn in ('DirectionalLight', 'SkyLight'):
        c = a.get_component_by_class(unreal.SkyLightComponent if cn == 'SkyLight' else unreal.LightComponent); f = fs if cn == 'DirectionalLight' else fk
        c.set_editor_property('intensity', c.get_editor_property('intensity') * f); unreal.log('MLG_TUNE %s -> %s' % (cn, c.get_editor_property('intensity')))
unreal.log('MLG_TUNE interior=%d x%s exterior=%d x%s' % (ni, fi, ne, fe))
unreal.EditorLoadingAndSavingUtils.save_current_level()
