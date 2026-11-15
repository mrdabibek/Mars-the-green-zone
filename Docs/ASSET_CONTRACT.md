# Asset handoff
Codex owns asset sourcing and visual inspection; Claude owns game code and integration. No binary is final until visually inspected, rights reviewed, imported and tested. Keep original downloads and source attribution. Temporary geometry must be visibly documented. Coordinate changes here; do not replace assets without notice.

| Asset | Status | Intended role |
| --- | --- | --- |
| Z2_Spacesuit_NASA.glb | Exported to `Assets/References/Export_FBX/SM_NASA_Z2_Spacesuit.fbx` & imported to `/Game/Environment/References/SM_NASA_Z2_Spacesuit` | Visual reference / landmark suit prop |
| Habitat Demonstration Unit | Exported to `SM_NASA_Habitat_Part1.fbx` / `Part2.fbx` & imported to `/Game/Environment/References/` | Habitat exterior reference |
| FPS arms and animations | Using UE5.2 FirstPerson template (`SK_Mannequin_Arms`, `FP_Rifle_*`; broken `FirstPerson_AnimBP` removed) | First-person skeletal arms |
| Sci-fi weapon and animations | Using UE5.2 `SK_FPGun` (`Muzzle`, `GripPoint` sockets; `M_FPGun`) + procedural recoil/ADS/tracer | First-person combat |
| Animal alien and intelligent alien | Production FBXs & textures delivered in `Assets/Creatures/Production/` and imported to `/Game/Creatures/{Raider,Breaker,Gunner}/` | Rigged characters and animation |
| Greenhouse, plants, pipes, tank and purifier | PolyHaven `potted_plant_02`/`04` imported as `SM_Plant_Mature_02`/`04`; devices use scaled primitives + status beacons | Repairable and destructible objectives |
| Mars environment and modular habitat | PolyHaven `moon_rock_01`/`02` tinted Mars-red as `SM_MarsRock_01`/`02`; habitat blockout in `Base.umap` + `BuildPrototypeBase()` | Traversable level |

Downloaded two mature potted plant models and two lunar rock models from Poly Haven (CC0), FBX with textures, checksums verified. See [Assets/ASSET_SOURCES.md](../Assets/ASSET_SOURCES.md).

---
## Claude integration spec (what the code expects) - 2026-11-14
Units: cm, UE axes (X forward, Z up). Pivots at the base centre unless noted. Every asset needs source + license in `Assets/ASSET_SOURCES.md`. C++ probes `/Game/` packages safely via `MLGAssets::LoadOptional` (`FPackageName::DoesPackageExist` before `StaticLoadObject`) with primitive fallbacks.

| Asset ID | Replaces (temporary) | Type | Size (cm) | Collision | Notes |
| --- | --- | --- | --- | --- | --- |
| `SM_Dev_PowerUnit`, `SM_Dev_OxygenGen`, `SM_Dev_Purifier`, `SM_Dev_GreenhouseSeal` | cube in `AMLGDevice` (80x80x120) | static | ~80x80x120 | simple box | 3 visual states wanted (ok/damaged/broken) via material param or swapped mesh |
| `SM_PlantPlot` | cube in `AMLGPlantPlot` (200x200x40 tray) | static | 200x200x40 | simple box | |
| `SM_Plant_Mature_02`, `SM_Plant_Mature_04` | cone (mature stage) | static | 70.1x65.7x84.1 / 16.8x18.5x26.7 | none | imported to `/Game/Environment/`; `AMLGPlantPlot` scales bounds to fit |
| `SK_Mannequin_Arms` + `FP_Rifle_*` | none | skeletal | UE5 mannequin arms | none | `/Game/FirstPersonArms/Character/Mesh/SK_Mannequin_Arms`, `FP_Rifle_{Idle,Run,Fire}` |
| `SK_FPGun` | composite primitive carbine | skeletal | UE5 FP rifle | none | `/Game/FPWeapon/Mesh/SK_FPGun`, sockets `Muzzle`, `GripPoint`, material `M_FPGun` |
| `SK_Alien_Raider`, `SK_Alien_Breaker`, `SK_Alien_Gunner` | sphere body in `AMLGAlien` | skeletal | 80 / 200 / 180 tall | capsule | idle, walk, run, telegraph, hit, death (+ cover for Gunner); non-gory |
| `SM_MarsRock_01`, `SM_MarsRock_02` | blockout rock props | static | 21.2x11.2x7.5 / 24.6x25.1x20.2 | simple | `/Game/Environment/SM_MarsRock_{01,02}`, Mars-tinted PBR (`M_MarsRock_{01,02}`) |
| `SFX_*` (13 cues) | none | audio | WAV 48 kHz 16-bit mono | n/a | `/Game/Audio/SFX_*` |

---
## Verified Creature FBX Specs (`Assets/Creatures/Production/` -> `/Game/Creatures/`)
All creature meshes are exported at 30 fps, frame-0 start (`anim_offset=0.0` roundtrip-verified), **+X forward**, **Z up**, grounded base-center pivot (**Z=0**), with co-located basecolor + normal maps and `EmissiveColor` VectorParameter on body materials (driven by `AMLGAlien::Tint()` during `Telegraph`/`Stagger`).

### 1. Raider (`EMLGAlienKind::Raider`)
- **FBX**: `Assets/Creatures/Production/Raider/SK_Alien_Raider.fbx` -> `/Game/Creatures/Raider/SK_Alien_Raider` (`SK_Alien_Raider_Skeleton`)
- **Dimensions / Mesh**: `150.85 x 69.37 x 80.00 cm` (`minZ = 0.0 cm`), 4,674 verts / 9,339 polys, weighted to 32 bones (capsule `r=30, hh=40`, height 80 cm).
- **Skeleton Bones (32)**: `Root`, `Spine_0..4`, `Head_0..3`, `Front_Right_Scapula`, `Front_Right_Limb_0..3`, `Front_Left_Limb_0..3`, `Rear_Right_Limb_0..4`, `Rear_Left_Limb_0..4`, `Tail_0..2` (`tripo::` prefix and leading digits stripped for UE5.2 compatibility).
- **Textures / Material**: `Mars_Last_Green_Raider_Animated_basecolor.jpg`, `Mars_Last_Green_Raider_Animated_normal.jpg` -> `/Game/Creatures/Raider/Materials/M_Alien_Raider` (slot `tripo_mat_52e2c664`).
- **Animations (6)**:
  - `AS_Raider_Idle`: frames `0..60`, `2.000s` (loop, `end_diff=0.0`)
  - `AS_Raider_Walk`: frames `0..60`, `2.000s` (loop, `end_diff=0.0`)
  - `AS_Raider_Run`: frames `0..21`, `0.700s` (loop, `end_diff=0.0`)
  - `AS_Raider_Telegraph`: frames `0..21`, `0.700s` (matches `TelegraphSeconds = 0.7f`)
  - `AS_Raider_Hit`: frames `0..14`, `0.467s` (covers `StaggerSeconds = 0.45f`)
  - `AS_Raider_Death`: frames `0..45`, `1.500s` (grounded collapse, matches `1.5f` death state)

### 2. Breaker (`EMLGAlienKind::Breaker`)
- **FBX**: `Assets/Creatures/Production/Breaker/SK_Alien_Breaker.fbx` -> `/Game/Creatures/Breaker/SK_Alien_Breaker` (`SK_Alien_Breaker_Skeleton`)
- **Dimensions / Mesh**: `420.59 x 196.70 x 200.00 cm` (`minZ = 0.0 cm`), 4,840 verts / 9,676 polys, weighted to 23 bones (capsule `r=60, hh=70`).
- **Skeleton Bones (23)**: `Root`, `Spine_0..3`, `Head_0..1`, `Front_Right_Limb_0..2`, `Front_Left_Limb_0..3`, `Rear_Right_Limb_0..2`, `Rear_Left_Limb_0..2`, `Tail_0..2`.
- **Textures / Material**: `Mars_Last_Green_Breacher_Animated_basecolor.jpg`, `Mars_Last_Green_Breacher_Animated_normal.jpg` -> `/Game/Creatures/Breaker/Materials/M_Alien_Breaker` (slot `tripo_mat_a248d4ea`).
- **Animations (6)**:
  - `AS_Breaker_Idle`: frames `0..75`, `2.500s` (loop, `end_diff=0.0`)
  - `AS_Breaker_Walk`: frames `0..60`, `2.000s` (loop, `end_diff=0.0`)
  - `AS_Breaker_Run`: frames `0..30`, `1.000s` (loop, `end_diff=0.0`)
  - `AS_Breaker_Telegraph`: frames `0..54`, `1.800s` (rear-up exposing belly + slam; matches `TelegraphSeconds = 1.8f`)
  - `AS_Breaker_Hit`: frames `0..36`, `1.200s` (matches `StaggerSeconds = 1.2f`)
  - `AS_Breaker_Death`: frames `0..45`, `1.500s` (grounded collapse, matches `1.5f` death state)

### 3. Gunner (`EMLGAlienKind::Gunner`)
- **FBX**: `Assets/Creatures/Production/Gunner/SK_Alien_Gunner.fbx` -> `/Game/Creatures/Gunner/SK_Alien_Gunner` (`SK_Alien_Gunner_Skeleton`)
- **Dimensions / Mesh**: `78.51 x 94.99 x 180.13 cm` (`minZ = -0.09 cm`), 36,053 verts / 48,122 polys, weighted to 25 UE5-style bones + integrated Energy Carbine.
- **Skeleton Bones (25)**: `root`, `pelvis`, `spine_01..03`, `neck_01`, `head`, `clavicle_l/r`, `upperarm_l/r`, `lowerarm_l/r`, `hand_l/r`, `weapon_r`, `muzzle`, `thigh_l/r`, `calf_l/r`, `foot_l/r`, `ball_l/r`. (`muzzle` bone resolves `GetMesh()->DoesSocketExist(TEXT("Muzzle"))` in `AMLGAlien::GetMuzzleLocation()`).
- **Textures / Materials**: `Mars_Last_Green_Gunner_basecolor.png`, `Mars_Last_Green_Gunner_normal.png` (2048x2048 baked from 1.92M sculpt) -> `/Game/Creatures/Gunner/Materials/M_Alien_Gunner` (slot 0), `/Game/Creatures/Gunner/M_Gunner_Rifle` (slot 1), `/Game/Creatures/Gunner/M_Gunner_RifleCore` (slot 2).
- **Animations (7)**:
  - `AS_Gunner_Idle`: frames `0..60`, `2.000s` (low-ready loop, `end_diff=0.0`)
  - `AS_Gunner_Walk`: frames `0..36`, `1.200s` (loop, `end_diff=0.0`)
  - `AS_Gunner_Run`: frames `0..21`, `0.700s` (loop, `end_diff=0.0`)
  - `AS_Gunner_Telegraph`: frames `0..27`, `0.900s` (raise-aim-fire; matches `TelegraphSeconds = 0.9f`)
  - `AS_Gunner_Cover`: frames `0..60`, `2.000s` (crouch loop; matches `2.0f` cover state)
  - `AS_Gunner_Hit`: frames `0..15`, `0.500s` (matches `StaggerSeconds = 0.5f`)
  - `AS_Gunner_Death`: frames `0..45`, `1.500s` (grounded collapse, matches `1.5f` death state)

- **Preview Contact Sheets**: `Assets/Creatures/Production/Previews/{Raider,Breaker,Gunner}_contact_sheet.png` (1200x1200 3x3 renders, Rest + Walk/Run/Telegraph/Hit/Death/+Cover).

---
## Verified Reference & PolyHaven Specs (`Assets/References/Export_FBX/` & `Assets/PolyHaven/`)
All static props are grounded at **Z=0**, XY-centered, imported with collision & lightmap UVs:

| Asset | Source | Size (cm) | Polys / Verts | UE5 Content Path & Materials |
| --- | --- | --- | --- | --- |
| `SM_NASA_Z2_Spacesuit` | `Assets/References/Z2_Spacesuit_NASA.glb` | `79.21 x 103.81 x 193.00` | 30,904 / 50,864 | `/Game/Environment/References/SM_NASA_Z2_Spacesuit` (`M_NASA_Z2_Spacesuit`) |
| `SM_NASA_Habitat_Part1` | `Assets/References/Habitat Demonstration Unit (part 1).glb` | `559.56 x 244.21 x 320.00` | 2,264 / 1,922 | `/Game/Environment/References/SM_NASA_Habitat_Part1` (`M_NASA_Habitat_Part1`) |
| `SM_NASA_Habitat_Part2` | `Assets/References/Habitat Demonstration Unit (part 2).glb` | `927.72 x 648.04 x 320.00` | 4,320 / 5,099 | `/Game/Environment/References/SM_NASA_Habitat_Part2` (`M_NASA_Habitat_Part2`) |
| `SM_MarsRock_01` | `Assets/PolyHaven/moon_rock_01/moon_rock_01_2k.fbx` (CC0) | `21.2 x 11.2 x 7.5` | 2K PBR | `/Game/Environment/SM_MarsRock_01` (`M_MarsRock_01`, Mars tint + flipped OpenGL normal) |
| `SM_MarsRock_02` | `Assets/PolyHaven/moon_rock_02/moon_rock_02_2k.fbx` (CC0) | `24.6 x 25.1 x 20.2` | 2K PBR | `/Game/Environment/SM_MarsRock_02` (`M_MarsRock_02`, Mars tint + flipped OpenGL normal) |
| `SM_Plant_Mature_02` | `Assets/PolyHaven/potted_plant_02/potted_plant_02_2k.fbx` (CC0) | `70.1 x 65.7 x 84.1` | 2K PBR | `/Game/Environment/SM_Plant_Mature_02` (`M_Plant_02_Pot`, `M_Plant_02_Leaves` masked 2-sided) |
| `SM_Plant_Mature_04` | `Assets/PolyHaven/potted_plant_04/potted_plant_04_2k.fbx` (CC0) | `16.8 x 18.5 x 26.7` | 2K PBR | `/Game/Environment/SM_Plant_Mature_04` (`M_Plant_04` 2-sided) |

---
## Verified Audio Specs (`Tools/gen_audio.py` -> `Assets/Audio/` -> `/Game/Audio/`)
All 13 SFX are deterministically synthesized using Python stdlib (`wave`, `struct`, `math`, `random`) at **48,000 Hz, 16-bit signed PCM, mono**, DC-centered, normalized below `0.90` peak (zero clipping), with zero-edge one-shot fades (`edges=(0, 0)`) and seamless crossfade looping on `SFX_Mars_Wind_Loop`.

| WAV / UE Asset Name | `/Game/Audio/` Path | Duration | Peak | Gameplay Cue / Timing |
| --- | --- | --- | --- | --- |
| `SFX_Rifle_Fire` | `/Game/Audio/SFX_Rifle_Fire` | `0.160s` | `0.860` | `UMLGWeaponComponent::FireOnce` (540 RPM) & turret fire (`MLGDefenseNode`) |
| `SFX_Rifle_Reload` | `/Game/Audio/SFX_Rifle_Reload` | `1.750s` | `0.840` | `UMLGWeaponComponent::Reload` (3-stage Foley within `ReloadSeconds = 2.0f`) |
| `SFX_Hit_Marker` | `/Game/Audio/SFX_Hit_Marker` | `0.070s` | `0.800` | `UMLGWeaponComponent::FireOnce` when hitting `AMLGAlien` |
| `SFX_Alien_Raider_Telegraph` | `/Game/Audio/SFX_Alien_Raider_Telegraph` | `0.700s` | `0.840` | `AMLGAlien` Raider telegraph (`0.70s`), also Breaker telegraph at `0.55x` pitch |
| `SFX_Alien_Breaker_Slam` | `/Game/Audio/SFX_Alien_Breaker_Slam` | `0.550s` | `0.880` | `AMLGAlien::Strike` on Breaker overhead ground slam |
| `SFX_Alien_Gunner_Charge` | `/Game/Audio/SFX_Alien_Gunner_Charge` | `0.900s` | `0.820` | `AMLGAlien` Gunner telegraph charge (`0.90s` aligned to `TelegraphSeconds = 0.9f`) |
| `SFX_Alien_Hit` | `/Game/Audio/SFX_Alien_Hit` | `0.140s` | `0.840` | `AMLGAlien::TakeDamage` & turret hit impact |
| `SFX_Alien_Death` | `/Game/Audio/SFX_Alien_Death` | `0.850s` | `0.840` | `AMLGAlien::Die` non-gory powerdown + collapse thud |
| `SFX_Repair_Tick` | `/Game/Audio/SFX_Repair_Tick` | `0.090s` | `0.780` | `AMLGCharacter`, `AMLGDefenseNode`, `AMLGPlantPlot` hold-interact progress tick |
| `SFX_Repair_Done` | `/Game/Audio/SFX_Repair_Done` | `0.420s` | `0.800` | `AMLGDevice::Interact`, `AMLGDefenseNode`, `AMLGPlantPlot` completion chime |
| `SFX_Alert_Low` | `/Game/Audio/SFX_Alert_Low` | `0.400s` | `0.780` | `AMLGDevice::TakeDamage`, `AMLGPlantPlot`, `AMLGDefenseNode`, `AMLGGameState`, `AMLGGameMode` |
| `SFX_Transmit` | `/Game/Audio/SFX_Transmit` | `0.650s` | `0.800` | `AMLGDevice::Interact` on Transmitter console win signal |
| `SFX_Mars_Wind_Loop` | `/Game/Audio/SFX_Mars_Wind_Loop` | `10.000s` | `0.620` | `AMLGCharacter::BeginPlay` (`looping=True`, 1.0s equal-power crossfade, indoor attenuated) |
