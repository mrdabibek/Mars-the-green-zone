# Mars: Last Green — experimental creature animations

These are work-in-progress assets, not approved game animations. The supplied downloads are unchanged.

## Blender projects

- `Raider_walk.blend` and `Breacher_walk.blend`: original Tripo quadruped walk (frames 1–62, 30 fps) plus a newly made procedural `Idle_DRAFT` (frames 1–61). Walk is active on open.
- `Scavenger_DRAFT.blend`: an experimental 18-bone humanoid rig with `Walk_DRAFT` (frames 1–31) and `Idle_DRAFT` (frames 1–61). Scavenger source GLB has 995,038 vertices and 1,922,500 triangles. The work copy is reduced to 90,791 vertices and 134,575 triangles. Bone fitting and spatial weights are automatic approximations, not artist-approved.

Select an action in Blender's Action Editor to review it. The first visible Scavenger walk test had severe spikes near the feet; weights were adjusted and those spikes were not visible in the sampled render frames. Foot sliding, anatomy, all other frames and angles, and mesh detail still require visual review. The source walking clips' first/last bone translations differ; their looping needs refinement.

## Exports

`Export_DRAFT/` holds one FBX per creature and clip. Each was imported back into Blender and checked for one armature, a weighted mesh, animation data and movement at a sampled frame; `roundtrip_results.json` contains the measurements. The FBX import reports the animation range one frame later than the source; timing and playback need further investigation. The assets have not been imported into Unreal or validated for engine scale, material appearance, bone mapping, performance or gameplay.

`import_walk.py` and `export_drafts.py` include a process-local workaround for this installed Blender's FBX operator registration problem. No system Blender files were changed. `scavenger_draft.py` generates the experimental rig, and `verify_exports.py` performs round-trip checks.
