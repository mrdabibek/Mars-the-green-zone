#!/usr/bin/env python3
"""Edit the trailer from the 30 fps Unreal movie frames and the Musopen Grieg recording.

Supply the frame folder from the trailer capture and the full 154-second FLAC:
  python Tools/build_trailer.py --frames /path/to/LinuxEditor --music /path/to/musopen.flac
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "Docs" / "Mars_Last_Green_Trailer.mp4"
FPS = 30
WIDTH, HEIGHT = 1600, 900
BOLD = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
REGULAR = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
MUSIC_SOURCE = (
    "https://commons.wikimedia.org/wiki/File:Grieg_-_Peer_Gynt_Suite_No._1,_Op._46_"
    "-_IV._In_the_Hall_of_the_Mountain_King_(Musopen_Symphony).flac"
)


@dataclass(frozen=True)
class Clip:
    name: str
    start: int
    stop: int
    caption: str = ""
    intro: bool = False


CLIPS = (
    Clip("descent", 25, 123, "Aster One descends to Mars", True),
    Clip("relay", 149, 216, "The last signal from Earth", True),
    Clip("fissure", 221, 253, "Make something grow.", True),
    Clip("rupture", 253, 343, "Earth goes silent", True),
    Clip("loadout", 351, 409, "Choose what to carry"),
    Clip("repair", 416, 499, "Restore life support"),
    Clip("greenhouse", 506, 593, "Keep the seed vault alive"),
    Clip("waterline", 601, 679, ""),
    Clip("defense", 684, 854, "Defend the outpost"),
)
END_FRAMES = 120
DURATION = (sum(c.stop - c.start for c in CLIPS) + END_FRAMES) / FPS


def ffmpeg(*args):
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-filter_threads", "2", "-filter_complex_threads", "2", *map(str, args)],
        check=True,
    )


def font(path, size):
    return ImageFont.truetype(path, size)


def overlay(clip, path):
    image = Image.new("RGBA", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)
    dark = (9, 13, 20, 255)
    paper = (248, 245, 237, 255)
    copper = (242, 165, 107, 255)
    if clip.intro:
        # The game supplies its own letterbox and subtitles. Remask just those bands.
        draw.rectangle((0, 0, WIDTH, 81), fill=dark)
        draw.rectangle((0, 781, WIDTH, HEIGHT), fill=dark)
        if clip.caption:
            draw.rectangle((56, 823, 80, 827), fill=copper)
            draw.text((99, 808), clip.caption, font=font(BOLD, 38), fill=paper)
    elif clip.caption:
        # Reserve a safe lower strip so the game's vital signs and ammo stay visible.
        draw.rectangle((0, 819, WIDTH, HEIGHT), fill=dark)
        draw.rectangle((56, 855, 80, 859), fill=copper)
        draw.text((98, 838), clip.caption, font=font(BOLD, 35), fill=paper)
    image.save(path)


def end_card(path):
    image = Image.new("RGB", (WIDTH, HEIGHT), "#0a1119")
    draw = ImageDraw.Draw(image)
    draw.rectangle((108, 277, 179, 282), fill="#e9a376")
    draw.text((105, 313), "MARS", font=font(BOLD, 72), fill="#e9a376")
    draw.text((101, 393), "LAST GREEN", font=font(BOLD, 113), fill="#f7f3e9")
    draw.text((110, 585), "A first-person survival game on Mars", font=font(REGULAR, 38), fill="#c1ceda")
    draw.text((110, 682), "NASA SPACE APPS CHALLENGE 2026  /  GAME PROTOTYPE",
              font=font(MONO, 18), fill="#99afbf")
    draw.text((110, 790), "Music: Edvard Grieg · In the Hall of the Mountain King · Musopen Symphony Orchestra",
              font=font(REGULAR, 19), fill="#b6c5cf")
    draw.text((110, 827), "In-engine footage · AI-assisted game assets and radio dialogue",
              font=font(REGULAR, 18), fill="#99afbf")
    image.save(path)


def encode_clip(frames, clip, target, work):
    graphic = work / f"{clip.name}.png"
    overlay(clip, graphic)
    if clip.intro:
        grade = "eq=contrast=1.045:brightness=-0.022:saturation=0.97"
        crop = "scale=1600:900"
    elif clip.caption:
        # Keep the complete game viewport and allocate space below it for the caption.
        grade = "eq=contrast=1.025:brightness=-0.008:saturation=0.96"
        crop = "scale=1456:818,pad=1600:900:72:0:0x090d14"
    else:
        grade = "eq=contrast=1.025:brightness=-0.008:saturation=0.96"
        crop = "scale=1600:900"
    vf = f"[0:v]{crop},{grade},setsar=1[shot];[shot][1:v]overlay,format=yuv420p[v]"
    ffmpeg("-framerate", FPS, "-start_number", clip.start, "-i", frames / "MovieFrame%05d.png",
           "-i", graphic, "-filter_complex", vf, "-map", "[v]", "-frames:v", clip.stop - clip.start,
           "-an", "-c:v", "libx264", "-threads", 3, "-preset", "fast", "-crf", 17, target)


def soundtrack(music, dest):
    audio = ROOT / "Assets" / "Audio"
    radio = ROOT / "Assets" / "Intro" / "Prologue_Radio.wav"
    sources = [
        music, audio / "SFX_Intro_LanderBurn.wav", audio / "SFX_Intro_EarthShatter.wav",
        radio, audio / "SFX_Mars_Wind_Loop.wav", audio / "SFX_Rifle_Fire.wav",
        audio / "SFX_Transmit.wav",
    ]
    inputs = [part for source in sources for part in ("-i", source)]
    graph = (
        "[0:a]asplit=2[build][final];"
        "[build]atrim=start=86.25:duration=26.63,asetpts=PTS-STARTPTS,volume='1.55-0.77*clip((t-10)/5,0,1)':eval=frame,"
        "afade=t=in:d=0.4[buildcut];"
        "[final]atrim=start=148.62:duration=3.48,asetpts=PTS-STARTPTS,volume=0.72[finalcut];"
        "[buildcut][finalcut]acrossfade=d=0.35:c1=tri:c2=tri[score];"
        "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=start=0.55:duration=3.05,asetpts=PTS-STARTPTS,"
        "highpass=f=45,volume=0.36,afade=t=in:d=0.14,afade=t=out:st=2.55:d=0.5[burn];"
        "[2:a]aformat=sample_rates=48000:channel_layouts=stereo,highpass=f=45,volume=0.32,adelay=6575:all=1[impact];"
        "[3:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=start=15.8:end=16.9,asetpts=PTS-STARTPTS,"
        "volume=1.65,adelay=5510:all=1[radio];"
        "[4:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=duration=7.95,volume=0.34,"
        "afade=t=in:d=0.75,afade=t=out:st=7.15:d=0.8,adelay=17180:all=1[wind];"
        "[5:a]asplit=7[g1][g2][g3][g4][g5][g6][g7];"
    )
    # Cut gunshots to the recorded start of each visible shot burst.
    gun_delays = (20490, 20715, 20940, 21735, 21960, 23235, 23460)
    for i, delay in enumerate(gun_delays, start=1):
        graph += f"[g{i}]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.46,adelay={delay}:all=1[g{i}mix];"
    graph += (
        "[6:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.48,adelay=25435:all=1[tx];"
        "[score][burn][impact][radio][wind][g1mix][g2mix][g3mix][g4mix][g5mix][g6mix][g7mix][tx]"
        f"amix=inputs=13:duration=longest:normalize=0,apad,atrim=duration={DURATION:.6f},"
        f"afade=t=out:st={DURATION-.30:.6f}:d=0.30,alimiter=limit=0.83:level=0:latency=1[a]"
    )
    ffmpeg(*inputs, "-filter_complex", graph, "-map", "[a]", "-c:a", "aac", "-b:a", "256k", dest)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--frames", type=Path, required=True)
    cli.add_argument("--music", type=Path, required=True)
    cli.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = cli.parse_args()

    frames = args.frames.resolve()
    music = args.music.resolve()
    output = args.output.resolve()
    for clip in CLIPS:
        for index in range(clip.start, clip.stop):
            path = frames / f"MovieFrame{index:05d}.png"
            if not path.is_file():
                cli.error(f"Missing frame {path}")
    if not music.is_file():
        cli.error(f"Missing orchestral recording: {music}. Source: {MUSIC_SOURCE}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="mars-edit-", dir=output.parent) as tmp:
        work = Path(tmp)
        parts = []
        for i, clip in enumerate(CLIPS):
            part = work / f"clip-{i:02d}.mp4"
            encode_clip(frames, clip, part, work)
            parts.append(part)
            print(f"Rendered {clip.name}", flush=True)

        card = work / "end.png"
        end = work / "end.mp4"
        end_card(card)
        ffmpeg("-loop", "1", "-framerate", FPS, "-i", card, "-frames:v", END_FRAMES,
               "-vf", "fade=t=in:d=0.27,fade=t=out:st=3.72:d=0.28,format=yuv420p",
               "-an", "-c:v", "libx264", "-threads", 3, "-preset", "fast", "-crf", 17, end)
        parts.append(end)

        playlist = work / "clips.txt"
        playlist.write_text("".join(f"file '{part.name}'\n" for part in parts))
        mixed = work / "soundtrack.m4a"
        soundtrack(music, mixed)
        result = work / "trailer.mp4"
        ffmpeg("-f", "concat", "-safe", "0", "-i", playlist, "-i", mixed,
               "-map", "0:v", "-map", "1:a", "-c", "copy", "-movflags", "+faststart",
               "-metadata", "title=Mars: Last Green | Gameplay Trailer",
               "-metadata", "comment=Edvard Grieg performance by the Musopen Symphony Orchestra (public domain).",
               result)
        shutil.move(result, output)
    print(f"Saved {output} ({DURATION:.2f} seconds)")


if __name__ == "__main__":
    main()
