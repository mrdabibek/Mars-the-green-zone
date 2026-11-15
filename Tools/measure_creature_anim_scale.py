# Read-only: for every /Game/Creatures/*/AS_* clip, compare animated bone span (mid-clip, world space) to the skeleton's reference span.
# A healthy clip has ratio ~1 (rest-like poses are within ~2x). A 100x import-scale bug shows as ratio ~0.01. Prints MLG_ANIM lines.
import unreal
bad = 0; total = 0
for name in ['Raider', 'Breaker', 'Gunner']:
    for ad in unreal.EditorAssetLibrary.list_assets('/Game/Creatures/' + name, recursive=False, include_folder=False):
        a = unreal.EditorAssetLibrary.load_asset(ad)
        if not isinstance(a, unreal.AnimSequence): continue
        pose = a.get_anim_pose_at_time(a.get_play_length() * 0.5, unreal.AnimPoseEvaluationOptions())
        bones = unreal.AnimPoseExtensions.get_bone_names(pose)
        def span(fn):
            pts = [fn(pose, b, unreal.AnimPoseSpaces.WORLD).translation for b in bones]
            return [max(getattr(p, k) for p in pts) - min(getattr(p, k) for p in pts) for k in 'xyz']
        an = span(unreal.AnimPoseExtensions.get_bone_pose); rf = span(unreal.AnimPoseExtensions.get_ref_bone_pose)
        ratio = max(an) / max(max(rf), 1e-6); total += 1; ok = 0.2 < ratio < 5.0; bad += (not ok)
        unreal.log("MLG_ANIM %s %s animated=%.1fcm reference=%.1fcm ratio=%.3f %s" % (name, a.get_name(), max(an), max(rf), ratio, "OK" if ok else "BAD_SCALE"))
unreal.log("MLG_ANIM_DONE clips=%d bad=%d" % (total, bad))
