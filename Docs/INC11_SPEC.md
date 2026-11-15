# Increment 11 Specification: Animated Opening Story, Early Creature Ambush & Logic/Bug Guard

## Goals
1. **Animated Opening Story Sequence (Mars Landing -> Earth Shatters):**
   - Triggered cleanly when starting a New Game interactively (skipped automatically when `-nomenu`, `mlg.*` automated tests, or loading a checkpoint is active so all existing headless/UI/enemy/mission tests pass 100%).
   - Skippable any time after 0.3s via `Space` / `Enter` / `Left Mouse Button` / `Confirm`.
   - 3D Animated Intro Scene inside `/Game/Maps/Base` (spawned cleanly by Intro Director / `Tools/build_base_map.py`):
     - `SM_Intro_DropLander` (`/Game/Intro/SM_Intro_DropLander`): NASA Mars descent lander with landing struts, heat shield, retro thrusters, emissive cockpit windows, descending cleanly onto west crater landing pad `(-1850, -900, 0)` with thruster glow & dust pulse during Beat 1 (`0.0s - 4.2s`). Remains grounded in world as a visual landmark!
     - `SM_Intro_EarthWhole` & `SM_Intro_EarthShard` (`/Game/Intro/SM_Intro_Earth*`): Visible in the eastern Martian sky (`(18000, 1200, 7500)`), rotating subtly during Beat 2 (`4.2s - 7.5s`), then flaring molten orange-white and bursting radially into `8` tumbling glowing fragments + expanding shockwave ring during Beat 3 (`7.5s - 11.2s`)!
     - Beat 4 (`11.2s - 14.0s`): Camera sweeps to the Habitat / Greenhouse (`SM_Tripo_BotanicalPod`) and reveals a howling Scout Raider silhouette on the crater ridge (`AS_Raider_Telegraph`), transitioning seamlessly into Planning!
   - Cinematic letterbox bars, animated beat subtitles, telemetry ticker, camera shake at Earth shatter, plus synthesized stereo intro WAVs (`SFX_Intro_LanderBurn.wav`, `SFX_Intro_EarthShatter.wav`) added to `Tools/gen_audio.py`, `Tools/import_props_and_music.py`, and `MLGAssets::Audio::*`.

2. **First Creatures Attack Player Early + Smarter Logical Combat:**
   - Shortly after confirming kit (`EMLGPhase::Repair`, ~8s delay when not inside `mlg.missiontest`/`mlg.selftest`), trigger a logical **First Contact Ambush**: 2 Recon Raiders drawn by landing seismic signature spawn at safe rim perimeter and prioritize hunting the **Player** directly (`PlayerAggroUntil` boosted, `RAIDER LUNGE` warning + telegraph/stagger counterplay).
   - During subsequent combat waves, firing the player weapon emits a tactical gunshot alert radius so nearby Raiders/Gunners flank/re-target the player naturally while Breakers assault infrastructure.
   - Ensure `FirstWaveDelay` and deterministic wave tests (`mlg.missiontest`, `mlg.enemytest`, `mlg.selftest`) keep passing with 0 regressions.

3. **Game Logic Analyzer & Anti-Bug Prevention System (`MLGLogicValidator`):**
   - New module files `Source/MarsLastGreen/MLGLogicValidator.h` and `.cpp`:
     - Inspects live game invariants: Phase/wave sanity, non-negative/finite resources (`Health`, `SuitOxygen`, `Sim.Power`, `Sim.Water`, `Sim.Oxygen`, `Seeds`), NaN/Inf transform guards, floor-penetration recovery (if alien or player falls `Z < -60`, snap cleanly back onto NavMesh/floor), AI stuck-recovery (nudge idle/stuck living alien back onto nearest NavMesh point), softlock guard (if combat stalls with `0` ammo + `0` reserve + aliens alive for >10s, emergency fabricator drops 1 magazine with HUD prompt), and UI bounds verification.
     - Exposes `mlg.validate` console command printing `MLG-VALIDATE DONE anomalies=<N>` + detailed diagnostics.
     - Add `MarsLastGreen.Logic.InvariantAudit` Automation test in `Source/MarsLastGreen/Tests/MLGModelTests.cpp` testing all invariant checks, softlock detection, NaN/floor recovery, and Intro skip flags!
     - Also extend `mlg.shots` (or save `inc11` shots) to verify the Landing Pad / Earth Sky / Intro state renders cleanly!
