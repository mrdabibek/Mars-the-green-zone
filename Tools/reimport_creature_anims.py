# Re-imports ONLY the creature AnimSequences (meshes/skeletons untouched) with import_uniform_scale=100, same options as Tools/import_assets.py.
# Why: the default scale left animated bone spans ~100x smaller than the skeleton (see Assets/Creatures/Independent_QA/REPORT.md, Tools/measure_creature_anim_scale.py).
import unreal, os
ROOT = '/home/dabi/Documents/Mars Last Green/Assets/Creatures/Production'
tools = unreal.AssetToolsHelpers.get_asset_tools(); n = 0
for kind in ['Raider', 'Breaker', 'Gunner']:
    skel = unreal.EditorAssetLibrary.load_asset('/Game/Creatures/%s/SK_Alien_%s_Skeleton' % (kind, kind))
    for fn in sorted(os.listdir(os.path.join(ROOT, kind))):
        stem = os.path.splitext(fn)[0]
        if not (fn.lower().endswith('.fbx') and stem.startswith('AS_%s_' % kind)): continue
        o = unreal.FbxImportUI(); o.import_mesh = False; o.import_as_skeletal = True; o.import_animations = True; o.import_materials = False; o.import_textures = False
        o.automated_import_should_detect_type = False; o.mesh_type_to_import = unreal.FBXImportType.FBXIT_ANIMATION; o.skeleton = skel
        d = o.anim_sequence_import_data; d.convert_scene = True; d.force_front_x_axis = False; d.import_uniform_scale = 100.0
        for p, v in [('import_meshes_in_bone_hierarchy', False), ('animation_length', unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME), ('remove_redundant_keys', False)]:
            try: d.set_editor_property(p, v)
            except Exception: pass
        # replace_existing keeps the old asset's import settings (scale stayed 1), so delete first; a fresh import honours import_uniform_scale.
        unreal.EditorAssetLibrary.delete_asset('/Game/Creatures/%s/%s' % (kind, stem))
        t = unreal.AssetImportTask(); t.filename = os.path.join(ROOT, kind, fn); t.destination_path = '/Game/Creatures/' + kind; t.destination_name = stem
        t.automated = True; t.replace_existing = True; t.replace_existing_settings = True; t.save = True; t.options = o
        tools.import_asset_tasks([t]); n += 1
        unreal.log('MLG_REIMPORT %s ok=%s' % (stem, bool(unreal.EditorAssetLibrary.load_asset('/Game/Creatures/%s/%s' % (kind, stem)))))
unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
unreal.log('MLG_REIMPORT_DONE clips=%d' % n)
