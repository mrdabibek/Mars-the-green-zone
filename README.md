# Mars: Last Green (`Mars-the-green-zone`)

Unreal Engine 5.2 (C++) single-player Mars survival FPS built for the **NASA Space Apps Challenge**.  
Earth has fractured cleanly from seismic/tectonic collapse; stranded solo astronaut **Aster One** descends onto **Jezero Crater** to establish pressurized habitats, synthesize water via Sabatier chemistry, adapt cryo-seeds to Martian soil, and defend humanity's last flora against tri-class alien predators.

## Highlights & Hackathon Deliverables
- **Promotional Game Trailer:** [Docs/Mars_Last_Green_Trailer.mp4](Docs/Mars_Last_Green_Trailer.mp4) (`42.4s`, 720p H.264 + AAC mixed from in-engine audio & Vulkan SM5 captures)
- **Interactive HTML Pitch Deck:** [Docs/NASA_Hackathon_Presentation.html](Docs/NASA_Hackathon_Presentation.html)
- **Hackathon Slide Deck & Summary:** [Presentation/](Presentation/) (`Mars Last Green - NASA Space Apps 2026.pptx`, `Mars Last Green - Project Summary.md`)
- **Final Vulkan SM5 Captures:** [Docs/Final_Screenshots/](Docs/Final_Screenshots/) (`21` rendered frames covering Blue Marble Earth, Core Rupture, Heavy Dropship, Greenhouse & Combat)
- **Engineering Log & Asset Contract:** [Docs/PROGRESS.md](Docs/PROGRESS.md), [Docs/ASSET_CONTRACT.md](Docs/ASSET_CONTRACT.md)

## Key Systems (C++ & UE 5.2)
- **Extended Cinematic Prologue (`MLGPrologue.cpp`):** Orbital Earth Blue Marble telemetry -> glowing tectonic plate fracture -> core exposure & asteroid ejecta -> retro-burn descent onto Jezero pad -> seamless FPS handoff.
- **Authentic Martian Physics:** `0.38G` EVA gravity, `6.1 mbar` thin CO₂ atmosphere, `-55 °C` (`-22 °C .. -78 °C`) ambient thermal bands, and dynamic dust-storm solar array derating.
- **Botanical Gene Splicing & Sabatier H₂O:** Synthesize `CO₂ -> 2H₂O` (`2.2x` water yield) and splice cryo/perchlorate/photosynthetic genes to sustain hydroponic seed bays.
- **Heavy NASA Cargo Dropship (`SM_Tripo_HeavyDropship`):** `12.6 m` Tripo Pro ceramic dropship with carved enterable cargo cabin (`(-1850, -900, 0)`) and octagonal landing pad.
- **Tri-Class Alien Ecology (`MLGAlien.cpp`):** Agile **Raider** (interruptible lunge), cover-seeking **Gunner** (`AimBeam` LOS break counterplay), and armored **Breaker** (jump-counterable `3.5 m` shockwave fling in `0.38G`).

## Build & Verified Test Suites (Linux, UE 5.2.0)
- **Build Editor Module:**
  `~/Applications/UnrealEngine_5.2/Engine/Build/BatchFiles/Linux/Build.sh MarsLastGreenEditor Linux Development -project="$PWD/MarsLastGreen.uproject"`
- **Unit Tests (13/13):**
  `UnrealEditor-Cmd MarsLastGreen.uproject -ExecCmds="Automation RunTests MarsLastGreen; Quit" -nullrhi -unattended -nop4 -nosplash -nosound`
- **Level & Invariant Validation (`anomalies=0`):**
  `UnrealEditor-Cmd MarsLastGreen.uproject /Game/Maps/Base -game -nullrhi -nomenu -ExecCmds="mlg.validate" -benchmark -seconds=4`
- **UI & Input Suite (`31/31`, `failures=0`):**
  `UnrealEditor-Cmd MarsLastGreen.uproject /Game/Maps/Base -game -nullrhi -nomenu -ExecCmds="mlg.uitest" -benchmark -seconds=6`
- **Enemy AI & Counterplay (`15/15`, `failures=0`):**
  `UnrealEditor-Cmd MarsLastGreen.uproject /Game/Maps/Base -game -nullrhi -nomenu -ExecCmds="mlg.enemytest" -benchmark -seconds=120`
- **Full 11-Phase Mission Regression (`21/21`, `failures=0`):**
  `UnrealEditor-Cmd MarsLastGreen.uproject /Game/Maps/Base -game -nullrhi -nomenu -ExecCmds="mlg.missiontest" -benchmark -seconds=400`
- **Combat & Pipe Leak Self-Test:**
  `UnrealEditor-Cmd MarsLastGreen.uproject /Game/Maps/Base -game -nullrhi -nomenu -ExecCmds="mlg.selftest" -benchmark -seconds=60`
- **Creature Anim Scale Guard (`bad=0` across 19 clips):**
  `UnrealEditor-Cmd MarsLastGreen.uproject -ExecutePythonScript="$PWD/Tools/measure_creature_anim_scale.py" -nullrhi -unattended`

## Controls
`WASD` move · `Mouse` aim · `Shift` sprint · `Ctrl` crouch · `Space` jump · `E` interact (repair/plant/transmit) · `LMB` fire · `RMB` ADS · `R` reload · `1-6` + `Enter` planning kit · `Esc` pause / settings / codex · `F5` save / `F9` load checkpoint
