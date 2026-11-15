#!/usr/bin/env python3
"""
Build the promotional trailer video Docs/Mars_Last_Green_Trailer.mp4
and archive final Vulkan SM5 screenshots to Docs/Final_Screenshots/.
"""

import glob
import os
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path("/home/dabi/Documents/Mars Last Green")
SHOTS_SRC = ROOT / "Saved" / "Screenshots" / "LinuxEditor"
SHOTS_DST = ROOT / "Docs" / "Final_Screenshots"
PREVIEWS = ROOT / "Assets" / "Tripo" / "Previews"
AUDIO = ROOT / "Assets" / "Audio"
INTRO_AUDIO = ROOT / "Assets" / "Intro"
OUT_VIDEO = ROOT / "Docs" / "Mars_Last_Green_Trailer.mp4"
TMP = Path("/tmp/mlg_trailer_work")
FFMPEG = str(Path.home() / ".local" / "bin" / "ffmpeg")
FFPROBE = str(Path.home() / ".local" / "bin" / "ffprobe")

W, H = 1280, 720
FPS = 30
XFADE = 0.50

FONT_BOLD = "/usr/share/fonts/opentype/urw-base35/URWGothic-Demi.otf"
FONT_SANS = "/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf"
FONT_REG = "/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf"
FONT_MONO = "/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Bold.otf"


def run(cmd):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True)


def sync_final_screenshots():
    SHOTS_DST.mkdir(parents=True, exist_ok=True)
    for old in SHOTS_DST.glob("*.png"):
        old.unlink()
    copied = 0
    for src in sorted(SHOTS_SRC.glob("HighresScreenshot*.png")):
        shutil.copy2(src, SHOTS_DST / src.name)
        copied += 1
    print(f"Synced {copied} screenshots to {SHOTS_DST}")
    return copied


def draw_overlay_png(out_path: Path, tag: str = "", title: str = "", subtitle: str = "", mode: str = "card"):
    """Create a sleek 1280x720 RGBA overlay PNG (no clutter on pre-captioned prologue frames)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    f_tag = ImageFont.truetype(FONT_MONO, 18)
    f_title = ImageFont.truetype(FONT_BOLD, 34)
    f_sub = ImageFont.truetype(FONT_REG, 22)

    if mode == "badge_top":
        if tag:
            tw = draw.textbbox((0, 0), tag, font=f_tag)[2]
            pad_x, pad_y = 18, 10
            bx0, by0 = 36, 76
            bx1, by1 = bx0 + tw + pad_x * 2, by0 + 22 + pad_y * 2
            draw.rounded_rectangle([bx0, by0, bx1, by1], radius=6, fill=(8, 14, 24, 180), outline=(88, 196, 255, 210), width=2)
            draw.rectangle([bx0, by0, bx0 + 5, by1], fill=(235, 95, 52, 240))
            draw.text((bx0 + pad_x, by0 + pad_y - 1), tag, font=f_tag, fill=(210, 242, 255, 255))

    elif mode == "lower_third":
        # Subtle bottom gradient bar (avoid HUD edges, centered crisp feature callout bar)
        grad = Image.new("RGBA", (W, 130), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(grad)
        for y in range(130):
            alpha = int(175 * (y / 130.0) ** 1.3)
            gdraw.line([(0, y), (W, y)], fill=(6, 10, 18, alpha))
        img.alpha_composite(grad, (0, H - 130))

        # Centered pill panel cleanly between bottom-left (x<355) and bottom-right (x>985) HUD cards
        pill_w = 600
        pill_h = 82
        px0 = (W - pill_w) // 2 + 18
        py0 = H - 108
        draw.rounded_rectangle([px0, py0, px0 + pill_w, py0 + pill_h], radius=10, fill=(10, 16, 28, 205), outline=(74, 178, 232, 210), width=2)
        draw.rectangle([px0, py0 + 8, px0 + 6, py0 + pill_h - 8], fill=(242, 108, 62, 255))

        if tag:
            draw.text((px0 + 24, py0 + 10), tag, font=f_tag, fill=(116, 214, 255, 255))
        if title:
            lt_font = ImageFont.truetype(FONT_SANS, 22)
            for sz in (22, 20, 18, 16):
                cand = ImageFont.truetype(FONT_SANS, sz)
                if draw.textbbox((0, 0), title, font=cand)[2] <= pill_w - 40:
                    lt_font = cand
                    break
            draw.text((px0 + 24, py0 + 38), title, font=lt_font, fill=(248, 251, 255, 255))

    elif mode == "hero_plate":
        # Clean semi-transparent dark band at top for 3D Tripo asset sheets
        draw.rectangle([0, 0, W, 86], fill=(8, 12, 20, 220))
        draw.line([(0, 86), (W, 86)], fill=(86, 198, 255, 220), width=2)
        if tag:
            draw.text((40, 16), tag, font=f_tag, fill=(244, 124, 72, 255))
        if title:
            draw.text((40, 42), title, font=ImageFont.truetype(FONT_SANS, 28), fill=(244, 249, 255, 255))

    elif mode == "endcard":
        # Full dark cosmic backdrop overlay over dimmed frame
        draw.rectangle([0, 0, W, H], fill=(7, 10, 18, 195))
        # Subtle accent glow lines
        draw.line([(160, 205), (W - 160, 205)], fill=(238, 98, 56, 200), width=2)
        draw.line([(240, 505), (W - 240, 505)], fill=(86, 194, 255, 180), width=2)

        f_mega = ImageFont.truetype(FONT_BOLD, 74)
        f_sub_lg = ImageFont.truetype(FONT_SANS, 28)
        f_meta = ImageFont.truetype(FONT_MONO, 20)

        t0 = "NASA SPACE APPS HACKATHON // UE 5.2 C++"
        b0 = draw.textbbox((0, 0), t0, font=f_meta)
        draw.text(((W - (b0[2] - b0[0])) // 2, 168), t0, font=f_meta, fill=(116, 214, 255, 255))

        t1 = "MARS: LAST GREEN"
        b1 = draw.textbbox((0, 0), t1, font=f_mega)
        draw.text(((W - (b1[2] - b1[0])) // 2, 250), t1, font=f_mega, fill=(255, 255, 255, 255))

        t2 = "Earth Shattered. Seed the Red Planet. Hold the Colony."
        b2 = draw.textbbox((0, 0), t2, font=f_sub_lg)
        draw.text(((W - (b2[2] - b2[0])) // 2, 355), t2, font=f_sub_lg, fill=(245, 152, 102, 255))

        t3 = "Real Martian Physics (6.1 mb | -55C | 0.38G) · Sabatier H2O · Tripo 3D · 13/13 Tests Pass"
        b3 = draw.textbbox((0, 0), t3, font=f_sub)
        draw.text(((W - (b3[2] - b3[0])) // 2, 422), t3, font=f_sub, fill=(214, 228, 242, 255))

        t4 = "github.com/mrdabibek/Mars-the-green-zone"
        b4 = draw.textbbox((0, 0), t4, font=f_meta)
        draw.text(((W - (b4[2] - b4[0])) // 2, 535), t4, font=f_meta, fill=(138, 240, 190, 255))

    img.save(out_path)


def make_ken_burns_clip(src_img: Path, overlay_png: Path, out_mp4: Path, dur: float, z0: float, z1: float, pan_x0: float, pan_x1: float, pan_y0: float, pan_y1: float):
    """Render a jitter-free 30fps Ken-Burns clip using 3x supersampling."""
    frames = max(int(round(dur * FPS)), 1)
    # Supersampled 3x dimensions for subpixel smooth zoompan
    up_w, up_h = W * 3, H * 3
    denom = max(frames - 1, 1)
    z_expr = f"{z0:.4f}+({z1:.4f}-({z0:.4f}))*on/{denom}"
    x_expr = f"(iw-iw/zoom)*({pan_x0:.4f}+({pan_x1:.4f}-({pan_x0:.4f}))*on/{denom})"
    y_expr = f"(ih-ih/zoom)*({pan_y0:.4f}+({pan_y1:.4f}-({pan_y0:.4f}))*on/{denom})"

    vf = (
        f"[0:v]scale={up_w}:{up_h}:force_original_aspect_ratio=increase,"
        f"crop={up_w}:{up_h},"
        f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={W}x{H}:fps={FPS},"
        f"eq=contrast=1.04:saturation=1.08,"
        f"format=rgba[bg];"
        f"[bg][1:v]overlay=0:0:format=auto,format=yuv420p[v]"
    )
    run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-i", str(src_img),
        "-loop", "1", "-t", f"{dur:.3f}", "-i", str(overlay_png),
        "-filter_complex", vf,
        "-map", "[v]", "-t", f"{dur:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
        str(out_mp4),
    ])


def main():
    sync_final_screenshots()

    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True, exist_ok=True)

    # (src_image, duration_s, mode, tag, title, z0, z1, x0, x1, y0, y1)
    scenes = [
        (SHOTS_DST / "HighresScreenshot00010.png", 3.4, "badge_top", "T-00:18 // EARTH RELAY TELEMETRY", "", 1.00, 1.12, 0.50, 0.50, 0.50, 0.48),
        (SHOTS_DST / "HighresScreenshot00011.png", 3.3, "badge_top", "CRUSTAL SHEAR // PACIFIC BELT FAILURE", "", 1.02, 1.14, 0.48, 0.52, 0.50, 0.50),
        (SHOTS_DST / "HighresScreenshot00012.png", 3.5, "badge_top", "CORE EXPOSURE // LINK SEVERED", "", 1.00, 1.15, 0.50, 0.50, 0.50, 0.46),
        (SHOTS_DST / "HighresScreenshot00009.png", 3.6, "badge_top", "JEZERO CRATER // RETRO-BURN DESCENT", "", 1.08, 1.00, 0.52, 0.48, 0.45, 0.50),
        (SHOTS_DST / "HighresScreenshot00013.png", 3.8, "badge_top", "ASTER OUTPOST // LAST GREEN", "", 1.00, 1.08, 0.48, 0.52, 0.50, 0.50),
        (SHOTS_DST / "HighresScreenshot00014.png", 3.4, "lower_third", "TRIPO PRO 3D // NASA HEAVY DROPSHIP", "12.6m Ceramic Hull · Custom PBR Bake & Landing Pad", 1.00, 1.10, 0.45, 0.55, 0.50, 0.48),
        (SHOTS_DST / "HighresScreenshot00018.png", 3.3, "lower_third", "CARGO BAY INTERIOR", "Carved Walkable Cabin · Telemetry & Bio-Storage Deck", 1.00, 1.12, 0.50, 0.50, 0.50, 0.50),
        (SHOTS_DST / "HighresScreenshot00003.png", 3.2, "lower_third", "LIFE SUPPORT & Z2 SUIT", "Pressurized Airlock · Oxygen Refill & Cryo Vault", 1.02, 1.10, 0.45, 0.55, 0.50, 0.48),
        (SHOTS_DST / "HighresScreenshot00019.png", 3.7, "lower_third", "CRYO-SEED GENOMICS & SABATIER H2O", "Adapt Mars Crops + CO2 -> 2H2O Synthesis at 6.1 mbar", 1.00, 1.11, 0.52, 0.46, 0.52, 0.48),
        (SHOTS_DST / "HighresScreenshot00016.png", 3.2, "lower_third", "MODULAR HABITAT COMPOUND", "Interconnected Sectors · HDU Airlock & Perimeter Floodlights", 1.00, 1.09, 0.48, 0.52, 0.50, 0.50),
        (SHOTS_DST / "HighresScreenshot00006.png", 3.2, "lower_third", "ACTIVE TELEGRAPH COMBAT", "Interrupt Raider Lunges & Hold Outpost Infrastructure", 1.00, 1.13, 0.50, 0.50, 0.52, 0.48),
        (SHOTS_DST / "HighresScreenshot00017.png", 3.8, "lower_third", "TRI-CLASS ALIEN SWARM", "Armored Breakers · Cover-Seeking Gunners · Weakspot Stagger", 1.02, 1.12, 0.46, 0.54, 0.50, 0.50),
        (PREVIEWS / "HeavyDropship_sheet.png", 3.0, "hero_plate", "AI 3D PIPELINE // TRIPO PRO + BLENDER PBR", "7 Normalized Hero Assets · Clean Topology & Specular Tuning", 1.00, 1.06, 0.50, 0.50, 0.50, 0.50),
        (SHOTS_DST / "HighresScreenshot00009.png", 4.5, "endcard", "", "", 1.02, 1.08, 0.50, 0.50, 0.50, 0.50),
    ]

    clips = []
    durs = []
    for idx, (img_p, dur, mode, tag, title, z0, z1, x0, x1, y0, y1) in enumerate(scenes):
        if not img_p.exists():
            raise FileNotFoundError(f"Missing image: {img_p}")
        ov = TMP / f"ov_{idx:02d}.png"
        clip = TMP / f"clip_{idx:02d}.mp4"
        draw_overlay_png(ov, tag=tag, title=title, mode=mode)
        make_ken_burns_clip(img_p, ov, clip, dur, z0, z1, x0, x1, y0, y1)
        clips.append(clip)
        durs.append(dur)

    # Concatenate video clips with smooth 0.5s xfade transitions
    inputs = []
    for c in clips:
        inputs.extend(["-i", str(c)])

    # Compute exact cumulative duration for audio alignment
    xfade_filters = []
    cur_label = "[0:v]"
    cum = durs[0]
    for i in range(1, len(clips)):
        offset = cum - XFADE
        out_label = f"[v{i}]" if i < len(clips) - 1 else "[vfinal]"
        trans = "fadeblack" if i in (3, 13) else "fade"
        xfade_filters.append(f"{cur_label}[{i}:v]xfade=transition={trans}:duration={XFADE:.3f}:offset={offset:.3f}{out_label}")
        cur_label = out_label
        cum = offset + durs[i]

    total_dur = cum
    print(f"Total video duration: {total_dur:.2f}s across {len(clips)} scenes")

    video_only = TMP / "video_only.mp4"
    run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        *inputs,
        "-filter_complex", ";".join(xfade_filters),
        "-map", "[vfinal]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
        str(video_only),
    ])

    # Build rich multi-layered audio track synced to key visual events
    # Audio indices:
    # 0: Prologue_Score.wav (0..18s)
    # 1: Prologue_Radio.wav (0.4..17s)
    # 2: SFX_Intro_EarthShatter.wav (at 3.0s)
    # 3: SFX_Intro_LanderBurn.wav (at 8.7s)
    # 4: SFX_Music_Calm_Loop.wav (at 15.0s..28.5s)
    # 5: SFX_Wave_Start.wav (at 27.5s)
    # 6: SFX_Music_Combat_Loop.wav (at 27.8s..total_dur)
    # 7: SFX_Alien_Raider_Telegraph.wav (at 30.2s)
    # 8: SFX_Rifle_Fire.wav (at 31.3s, 31.55s, 34.4s)
    # 9: SFX_Alien_Breaker_Slam.wav (at 33.6s)
    # 10: SFX_Transmit.wav (at total_dur - 4.3s)
    fade_out_start = max(total_dur - 2.2, 1.0)
    a_inputs = [
        "-i", str(INTRO_AUDIO / "Prologue_Score.wav"),
        "-i", str(INTRO_AUDIO / "Prologue_Radio.wav"),
        "-i", str(AUDIO / "SFX_Intro_EarthShatter.wav"),
        "-i", str(AUDIO / "SFX_Intro_LanderBurn.wav"),
        "-i", str(AUDIO / "SFX_Music_Calm_Loop.wav"),
        "-i", str(AUDIO / "SFX_Wave_Start.wav"),
        "-stream_loop", "2", "-i", str(AUDIO / "SFX_Music_Combat_Loop.wav"),
        "-i", str(AUDIO / "SFX_Alien_Raider_Telegraph.wav"),
        "-i", str(AUDIO / "SFX_Rifle_Fire.wav"),
        "-i", str(AUDIO / "SFX_Alien_Breaker_Slam.wav"),
        "-i", str(AUDIO / "SFX_Transmit.wav"),
    ]
    tx_ms = int((total_dur - 4.3) * 1000)
    afilter = (
        "[0:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:17.5,afade=t=in:st=0:d=0.4,afade=t=out:st=15.0:d=2.5,volume=0.80[a0];"
        "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:16.5,adelay=400|400,afade=t=out:st=15.0:d=1.5,volume=0.62[a1];"
        "[2:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay=3000|3000,volume=0.75[a2];"
        "[3:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay=8700|8700,volume=0.68[a3];"
        "[4:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:14.0,adelay=15200|15200,afade=t=in:st=15.2:d=1.5,afade=t=out:st=27.2:d=2.0,volume=0.72[a4];"
        "[5:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay=27500|27500,volume=0.85[a5];"
        f"[6:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:{total_dur - 27.6:.2f},adelay=27800|27800,afade=t=in:st=27.8:d=0.8,afade=t=out:st={fade_out_start:.2f}:d=2.0,volume=0.78[a6];"
        "[7:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay=30200|30200,volume=0.75[a7];"
        "[8:a]asplit=3[r1][r2][r3];"
        "[r1]aformat=sample_rates=48000:channel_layouts=stereo,adelay=31300|31300,volume=0.65[a8a];"
        "[r2]aformat=sample_rates=48000:channel_layouts=stereo,adelay=31550|31550,volume=0.65[a8b];"
        "[r3]aformat=sample_rates=48000:channel_layouts=stereo,adelay=34400|34400,volume=0.65[a8c];"
        "[9:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay=33600|33600,volume=0.88[a9];"
        f"[10:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay={tx_ms}|{tx_ms},volume=0.82[a10];"
        f"[a0][a1][a2][a3][a4][a5][a6][a7][a8a][a8b][a8c][a9][a10]amix=inputs=13:duration=longest:normalize=0,"
        f"alimiter=limit=0.92,atrim=0:{total_dur:.3f},afade=t=out:st={fade_out_start:.2f}:d=2.1[amix]"
    )

    audio_only = TMP / "audio_mix.m4a"
    run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        *a_inputs,
        "-filter_complex", afilter,
        "-map", "[amix]", "-c:a", "aac", "-b:a", "192k",
        str(audio_only),
    ])

    OUT_VIDEO.parent.mkdir(parents=True, exist_ok=True)
    run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video_only),
        "-i", str(audio_only),
        "-c:v", "copy", "-c:a", "copy",
        "-movflags", "+faststart", "-shortest",
        str(OUT_VIDEO),
    ])

    # Extract 4 sample frames for visual verification
    for sec in (4.5, 17.5, 34.5, max(total_dur - 1.5, 1.0)):
        run([
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{sec:.2f}", "-i", str(OUT_VIDEO), "-frames:v", "1",
            str(TMP / f"check_{int(sec):02d}s.png"),
        ])

    size_mb = OUT_VIDEO.stat().st_size / (1024 * 1024)
    print(f"TRAILER_READY path={OUT_VIDEO} size={size_mb:.2f}MB duration={total_dur:.2f}s")
    run([FFPROBE, "-v", "error", "-show_entries", "format=duration,size,bit_rate:stream=codec_name,width,height,r_frame_rate", "-of", "compact", str(OUT_VIDEO)])


if __name__ == "__main__":
    main()
