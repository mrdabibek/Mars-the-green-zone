# Creates the empty /Game/Maps/Base level. Gameplay content is built by AMLGGameMode until real level assets exist.
import unreal
w = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
nav = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.NavMeshBoundsVolume, unreal.Vector(-500, 0, 0))
nav.set_actor_scale3d(unreal.Vector(35, 20, 5))  # default brush is 200 uu: 7000 x 4000 x 1000 covers base + approach
ok = unreal.EditorLoadingAndSavingUtils.save_map(w, '/Game/Maps/Base')
unreal.log("MLG_MAP_SAVED=%s" % ok)
