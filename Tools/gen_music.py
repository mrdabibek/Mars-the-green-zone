#!/usr/bin/env python3
"""Synthesize 48kHz 16-bit stereo adaptive Mars music loops using Python stdlib only.

Outputs into Assets/Audio/:
  - SFX_Music_Calm_Loop.wav   (16.000s stereo, warm atmospheric Martian synth pad + sub-bass + crystalline stereo echoes)
  - SFX_Music_Combat_Loop.wav (12.000s stereo, 120 BPM driving sci-fi pulse bass + sub kick + stereo staccato synth)

Both tracks are 48000 Hz, 16-bit PCM stereo, zero DC offset, normalized to -1.5 dBFS (0.8414),
and use equal-power crossfades + boundary alignment for click-free seamless looping.

Usage:
    python3 Tools/gen_music.py
"""
import math
import os
import random
import struct
import wave

SAMPLE_RATE = 48000
MAX_INT16 = 32767
TARGET_PEAK_DBFS = 10.0 ** (-1.5 / 20.0)  # -1.5 dBFS (~0.8414)
SEED = 20261115


def make_rng(salt: int = 0) -> random.Random:
    return random.Random(SEED + salt)


def biquad_filter(samples: list[float], kind: str, freq: float, q: float = 0.707) -> list[float]:
    """Apply a constant-frequency biquad filter ('lowpass', 'highpass', or 'bandpass')."""
    w0 = 2.0 * math.pi * max(20.0, min(freq, SAMPLE_RATE * 0.45)) / SAMPLE_RATE
    cos_w0 = math.cos(w0)
    sin_w0 = math.sin(w0)
    alpha = sin_w0 / (2.0 * max(0.1, q))

    if kind == "lowpass":
        b0 = (1.0 - cos_w0) * 0.5
        b1 = 1.0 - cos_w0
        b2 = (1.0 - cos_w0) * 0.5
    elif kind == "highpass":
        b0 = (1.0 + cos_w0) * 0.5
        b1 = -(1.0 + cos_w0)
        b2 = (1.0 + cos_w0) * 0.5
    elif kind == "bandpass":
        b0 = alpha
        b1 = 0.0
        b2 = -alpha
    else:
        raise ValueError(f"Unsupported filter kind: {kind}")

    a0 = 1.0 + alpha
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha

    b0 /= a0
    b1 /= a0
    b2 /= a0
    a1 /= a0
    a2 /= a0

    x1 = x2 = y1 = y2 = 0.0
    out = [0.0] * len(samples)
    for i, x0 in enumerate(samples):
        y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        out[i] = y0
        x2, x1 = x1, x0
        y2, y1 = y1, y0
    return out


def pink_noise(n: int, rng: random.Random) -> list[float]:
    b0 = b1 = b2 = b3 = b4 = b5 = b6 = 0.0
    out = [0.0] * n
    for i in range(n):
        white = rng.uniform(-1.0, 1.0)
        b0 = 0.99886 * b0 + white * 0.0555179
        b1 = 0.99332 * b1 + white * 0.0750759
        b2 = 0.96900 * b2 + white * 0.1538520
        b3 = 0.86650 * b3 + white * 0.3104856
        b4 = 0.55000 * b4 + white * 0.5329522
        b5 = -0.7616 * b5 - white * 0.0168980
        pink = b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362
        b6 = white * 0.115926
        out[i] = pink * 0.15
    return out


def soft_clip(x: float, drive: float = 1.0) -> float:
    return math.tanh(x * drive)


def equal_power_loop_crossfade(raw: list[float], loop_samples: int, xfade_samples: int) -> list[float]:
    """Fold tail [loop_samples .. loop_samples + xfade_samples) into head [0 .. xfade_samples) and match boundary."""
    out = list(raw[:loop_samples])
    for i in range(xfade_samples):
        alpha = i / float(xfade_samples)
        w_in = math.sin(alpha * math.pi * 0.5)
        w_out = math.cos(alpha * math.pi * 0.5)
        out[i] = out[i] * w_in + raw[loop_samples + i] * w_out
    seam_n = min(64, len(out) // 8)
    end_delta = out[0] - out[-1]
    for k in range(seam_n):
        w = (k + 1) / float(seam_n)
        out[len(out) - seam_n + k] += end_delta * (0.5 * (1.0 - math.cos(math.pi * w)))
    return out


def normalize_and_quantize_loop_stereo(left: list[float], right: list[float], target_peak: float = TARGET_PEAK_DBFS) -> list[int]:
    mean_l = sum(left) / max(1, len(left))
    mean_r = sum(right) / max(1, len(right))
    cl = [s - mean_l for s in left]
    cr = [s - mean_r for s in right]
    peak = max(max(abs(s) for s in cl), max(abs(s) for s in cr))
    gain = (target_peak / peak) if peak > 1e-9 else 0.0
    interleaved = [0] * (len(cl) * 2)
    for i in range(len(cl)):
        interleaved[2 * i] = max(-MAX_INT16, min(MAX_INT16, int(round(cl[i] * gain * MAX_INT16))))
        interleaved[2 * i + 1] = max(-MAX_INT16, min(MAX_INT16, int(round(cr[i] * gain * MAX_INT16))))
    return interleaved


def write_wav_loop(path: str, stereo_samples: tuple[list[float], list[float]], target_peak: float = TARGET_PEAK_DBFS):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pcm = normalize_and_quantize_loop_stereo(stereo_samples[0], stereo_samples[1], target_peak=target_peak)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(struct.pack(f"<{len(pcm)}h", *pcm))


def midi_to_hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def add_bell_note(buf_l: list[float], buf_r: list[float], start_s: float, freq: float, dur_s: float, amp: float, pan: float = 0.0):
    """Add a warm FM harmonic chime panned in stereo [-1.0 .. +1.0]."""
    start_i = int(start_s * SAMPLE_RATE)
    n = int(dur_s * SAMPLE_RATE)
    total = len(buf_l)
    if start_i >= total:
        return
    angle = (pan + 1.0) * math.pi * 0.25
    gain_l = math.cos(angle)
    gain_r = math.sin(angle)
    for k in range(n):
        idx = start_i + k
        if idx >= total:
            break
        t = k / SAMPLE_RATE
        env = (1.0 - math.exp(-t / 0.022)) * math.exp(-t / (dur_s * 0.36))
        mod_idx = 1.2 * math.exp(-t / 0.40)
        mod = math.sin(2.0 * math.pi * (freq * 2.0) * t)
        s = 0.78 * math.sin(2.0 * math.pi * freq * t + mod_idx * mod)
        s += 0.22 * math.sin(2.0 * math.pi * (freq * 0.5) * t) * math.exp(-t / 0.5)
        val = s * env * amp
        buf_l[idx] += val * gain_l
        buf_r[idx] += val * gain_r


def gen_calm_loop() -> tuple[list[float], list[float]]:
    """16.000s stereo atmospheric Martian synth pad + deep warm sub + ping-pong crystalline pulses."""
    rng_l = make_rng(1)
    rng_r = make_rng(101)
    dur = 16.0
    xfade_s = 2.0
    n = int(SAMPLE_RATE * dur)
    xfade_n = int(SAMPLE_RATE * xfade_s)
    total = n + xfade_n

    chords = [
        [38, 45, 53, 64],
        [38, 46, 53, 57, 62],
        [38, 43, 50, 58, 65],
        [38, 45, 52, 55, 60],
    ]
    bar_s = 4.0

    pad_l = [0.0] * total
    pad_r = [0.0] * total
    for bar_idx, chord in enumerate(chords):
        center_start = bar_idx * bar_s
        for rep in (0.0, dur):
            b_start = center_start + rep
            if b_start >= total / SAMPLE_RATE:
                continue
            fade_dur = bar_s + 1.4
            i0 = max(0, int((b_start - 0.7) * SAMPLE_RATE))
            i1 = min(total, int((b_start + fade_dur) * SAMPLE_RATE))
            for idx in range(i0, i1):
                t_abs = idx / SAMPLE_RATE
                u = (t_abs - (b_start - 0.7)) / (fade_dur + 0.7)
                if u <= 0.0 or u >= 1.0:
                    continue
                env = math.sin(u * math.pi) ** 1.35
                vl = vr = 0.0
                for v_i, midi in enumerate(chord):
                    f = midi_to_hz(midi)
                    detune = 1.0025 if v_i % 2 == 0 else 0.9975
                    ph1 = 2.0 * math.pi * f * t_abs
                    ph2 = 2.0 * math.pi * (f * detune) * t_abs + 0.4 * v_i
                    osc_l = 0.68 * math.sin(ph1) + 0.35 * math.sin(ph2) + 0.14 * math.sin(2.0 * ph1)
                    osc_r = 0.68 * math.sin(ph2) + 0.35 * math.sin(ph1) + 0.14 * math.sin(2.0 * ph2)
                    w = 0.25 if v_i == 0 else 0.15
                    vl += osc_l * w
                    vr += osc_r * w
                pad_l[idx] += vl * env
                pad_r[idx] += vr * env

    pad_l = biquad_filter(pad_l, "lowpass", 680.0, 0.75)
    pad_r = biquad_filter(pad_r, "lowpass", 680.0, 0.75)

    sub = [0.0] * total
    for idx in range(total):
        t = idx / SAMPLE_RATE
        lfo = 0.74 + 0.26 * math.sin(2.0 * math.pi * (t / dur) * 2.0)
        sub[idx] = (
            0.38 * math.sin(2.0 * math.pi * 73.416 * t)
            + 0.22 * math.sin(2.0 * math.pi * 36.708 * t)
        ) * lfo

    chimes_l = [0.0] * total
    chimes_r = [0.0] * total
    pulse_events = [
        (0.5, 62, 2.8, 0.20, -0.35),
        (2.0, 69, 2.5, 0.16, 0.35),
        (3.5, 64, 2.8, 0.16, -0.25),
        (5.0, 65, 2.8, 0.18, 0.30),
        (6.75, 69, 2.5, 0.15, -0.30),
        (8.5, 62, 2.8, 0.18, 0.35),
        (10.0, 70, 2.5, 0.16, -0.35),
        (11.5, 60, 2.6, 0.16, 0.25),
        (13.0, 64, 2.8, 0.18, -0.30),
        (14.5, 57, 2.4, 0.15, 0.30),
    ]
    for rep in (0.0, dur):
        for t_ev, midi, d_ev, amp_ev, pan in pulse_events:
            t_pos = t_ev + rep
            if t_pos < total / SAMPLE_RATE:
                f = midi_to_hz(midi)
                add_bell_note(chimes_l, chimes_r, t_pos, f, d_ev, amp_ev, pan)
                add_bell_note(chimes_l, chimes_r, t_pos + 0.375, f, d_ev * 0.75, amp_ev * 0.42, -pan)
                add_bell_note(chimes_l, chimes_r, t_pos + 0.75, f, d_ev * 0.55, amp_ev * 0.20, pan * 0.5)

    air_l = biquad_filter(pink_noise(total, rng_l), "bandpass", 440.0, 1.3)
    air_r = biquad_filter(pink_noise(total, rng_r), "bandpass", 460.0, 1.3)

    raw_l = [0.0] * total
    raw_r = [0.0] * total
    for i in range(total):
        t = (i % n) / SAMPLE_RATE
        air_sw = 0.05 * (0.65 + 0.35 * math.sin(2.0 * math.pi * (t / dur) * 1.0 + 0.8))
        raw_l[i] = soft_clip(pad_l[i] * 0.85 + sub[i] * 0.68 + chimes_l[i] * 0.75 + air_l[i] * air_sw, 1.05)
        raw_r[i] = soft_clip(pad_r[i] * 0.85 + sub[i] * 0.68 + chimes_r[i] * 0.75 + air_r[i] * air_sw, 1.05)

    return equal_power_loop_crossfade(raw_l, n, xfade_n), equal_power_loop_crossfade(raw_r, n, xfade_n)


def add_synth_bass_note(buf: list[float], start_s: float, freq: float, dur_s: float, amp: float):
    start_i = int(start_s * SAMPLE_RATE)
    n = int(dur_s * SAMPLE_RATE)
    total = len(buf)
    if start_i >= total:
        return
    for k in range(n):
        idx = start_i + k
        if idx >= total:
            break
        t = k / SAMPLE_RATE
        amp_env = (1.0 - math.exp(-t / 0.004)) * math.exp(-t / (dur_s * 0.58))
        bright = math.exp(-t / 0.085)
        s = 0.55 * math.sin(2.0 * math.pi * (freq * 0.5) * t)
        for h in range(1, 7):
            cutoff_weight = math.exp(-((h - 1) * 0.35) * (1.4 - 0.85 * bright))
            s += (cutoff_weight / h) * math.sin(2.0 * math.pi * (freq * h) * t)
        buf[idx] += soft_clip(s * 1.35, 1.15) * amp_env * amp


def add_staccato_lead(buf_l: list[float], buf_r: list[float], start_s: float, freq: float, dur_s: float, amp: float, pan: float):
    start_i = int(start_s * SAMPLE_RATE)
    n = int(dur_s * SAMPLE_RATE)
    total = len(buf_l)
    if start_i >= total:
        return
    angle = (pan + 1.0) * math.pi * 0.25
    gl = math.cos(angle)
    gr = math.sin(angle)
    for k in range(n):
        idx = start_i + k
        if idx >= total:
            break
        t = k / SAMPLE_RATE
        env = (1.0 - math.exp(-t / 0.003)) * math.exp(-t / (dur_s * 0.45))
        s = (
            0.62 * math.sin(2.0 * math.pi * freq * t)
            + 0.26 * math.sin(2.0 * math.pi * (freq * 2.002) * t)
            + 0.14 * math.sin(2.0 * math.pi * (freq * 1.5) * t)
        ) * env * amp
        buf_l[idx] += s * gl
        buf_r[idx] += s * gr


def add_kick(buf: list[float], start_s: float, amp: float):
    start_i = int(start_s * SAMPLE_RATE)
    n = int(0.18 * SAMPLE_RATE)
    total = len(buf)
    if start_i >= total:
        return
    ph = 0.0
    for k in range(n):
        idx = start_i + k
        if idx >= total:
            break
        t = k / SAMPLE_RATE
        f = 42.0 + 118.0 * math.exp(-t / 0.022)
        ph += 2.0 * math.pi * f / SAMPLE_RATE
        env = (1.0 - math.exp(-t / 0.002)) * math.exp(-t / 0.080)
        click = math.sin(2.0 * math.pi * 1150.0 * t) * math.exp(-t / 0.005) * 0.22
        buf[idx] += (math.sin(ph) * env + click) * amp


def add_perc_tick(buf: list[float], start_s: float, amp: float, rng: random.Random, accent: bool = False):
    start_i = int(start_s * SAMPLE_RATE)
    dur = 0.060 if accent else 0.030
    n = int(dur * SAMPLE_RATE)
    total = len(buf)
    if start_i >= total:
        return
    bp = 2600.0 if accent else 4200.0
    y1 = 0.0
    for k in range(n):
        idx = start_i + k
        if idx >= total:
            break
        t = k / SAMPLE_RATE
        w = rng.uniform(-1.0, 1.0)
        hp = w - 0.82 * y1
        y1 = w
        env = math.exp(-t / (0.020 if accent else 0.009))
        tone = math.sin(2.0 * math.pi * bp * t) * 0.25
        buf[idx] += (hp * 0.70 + tone) * env * amp


def gen_combat_loop() -> tuple[list[float], list[float]]:
    """12.000s stereo (120 BPM, 6 bars) driving tense sci-fi pulse bass + sub kick + stereo staccato synth."""
    rng = make_rng(2)
    dur = 12.0
    xfade_s = 1.5
    n = int(SAMPLE_RATE * dur)
    xfade_n = int(SAMPLE_RATE * xfade_s)
    total = n + xfade_n

    step_s = 0.125
    steps_per_loop = 96
    total_steps = int(round((dur + xfade_s) / step_s)) + 2

    bar_roots = [38, 38, 39, 38, 41, 37]
    bass_buf = [0.0] * total
    lead_l = [0.0] * total
    lead_r = [0.0] * total
    drums_buf = [0.0] * total

    ostinato = [0, 7, 1, 7, 3, 7, 1, 10, 0, 7, 1, 8, 5, 3, 1, -2]

    for step in range(total_steps):
        t_s = step * step_s
        if t_s >= total / SAMPLE_RATE:
            break
        loop_step = step % steps_per_loop
        bar = loop_step // 16
        in_bar = loop_step % 16
        root_midi = bar_roots[bar]

        bass_midi = root_midi + (12 if in_bar in (2, 6, 10, 14) else 0)
        bass_amp = 0.44 if in_bar % 4 == 0 else (0.34 if in_bar % 2 == 0 else 0.24)
        add_synth_bass_note(bass_buf, t_s, midi_to_hz(bass_midi), 0.16, bass_amp)

        if in_bar in (0, 3, 6, 8, 10, 12, 14, 15):
            lead_midi = 50 + ostinato[in_bar] + (1 if bar == 2 else 0)
            lead_amp = 0.22 if in_bar in (0, 8, 12) else 0.15
            pan = 0.35 if (step % 2 == 0) else -0.35
            add_staccato_lead(lead_l, lead_r, t_s, midi_to_hz(lead_midi), 0.15, lead_amp, pan)

        if in_bar % 4 == 0:
            add_kick(drums_buf, t_s, 0.55)
        if in_bar in (4, 12):
            add_perc_tick(drums_buf, t_s, 0.22, rng, accent=True)
        elif in_bar % 2 == 1:
            add_perc_tick(drums_buf, t_s, 0.10, rng, accent=False)

    pad_l = [0.0] * total
    pad_r = [0.0] * total
    for i in range(total):
        t = i / SAMPLE_RATE
        bar_f = ((i % n) / SAMPLE_RATE) / 2.0
        bar = int(bar_f) % 6
        f1 = midi_to_hz(50)  # D3
        f2 = midi_to_hz(53 if bar != 5 else 52)  # F3 -> E3
        f3 = midi_to_hz(57 if bar not in (2, 5) else 58)  # A3 / Bb3
        swell = 0.65 + 0.35 * math.sin(2.0 * math.pi * (t / 2.0) - math.pi * 0.5)
        pad_l[i] = (0.16 * math.sin(2.0 * math.pi * f1 * t) + 0.13 * math.sin(2.0 * math.pi * f2 * t) + 0.10 * math.sin(2.0 * math.pi * f3 * t)) * swell
        pad_r[i] = (0.16 * math.sin(2.0 * math.pi * (f1 * 1.002) * t) + 0.13 * math.sin(2.0 * math.pi * (f2 * 0.998) * t) + 0.10 * math.sin(2.0 * math.pi * (f3 * 1.002) * t)) * swell

    bass_buf = biquad_filter(bass_buf, "lowpass", 1150.0, 0.85)
    lead_l = biquad_filter(lead_l, "lowpass", 1600.0, 0.80)
    lead_r = biquad_filter(lead_r, "lowpass", 1600.0, 0.80)
    pad_l = biquad_filter(pad_l, "lowpass", 1100.0, 0.70)
    pad_r = biquad_filter(pad_r, "lowpass", 1100.0, 0.70)

    raw_l = [0.0] * total
    raw_r = [0.0] * total
    for i in range(total):
        raw_l[i] = soft_clip(bass_buf[i] * 0.90 + lead_l[i] * 0.80 + drums_buf[i] * 0.78 + pad_l[i] * 0.58, 1.15)
        raw_r[i] = soft_clip(bass_buf[i] * 0.90 + lead_r[i] * 0.80 + drums_buf[i] * 0.78 + pad_r[i] * 0.58, 1.15)

    return equal_power_loop_crossfade(raw_l, n, xfade_n), equal_power_loop_crossfade(raw_r, n, xfade_n)


SPECS = [
    ("SFX_Music_Calm_Loop.wav", gen_calm_loop),
    ("SFX_Music_Combat_Loop.wav", gen_combat_loop),
]


def verify_wav(path: str) -> dict:
    with wave.open(path, "rb") as wf:
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        sr = wf.getframerate()
        nf = wf.getnframes()
        raw = wf.readframes(nf)
    samples = struct.unpack(f"<{nf * ch}h", raw)
    mn, mx = min(samples), max(samples)
    peak = max(abs(mn), abs(mx)) / 32768.0
    rms = math.sqrt(sum(s * s for s in samples) / max(1, len(samples))) / 32768.0
    dc = sum(samples) / max(1, len(samples)) / 32768.0
    seam_jump = max(abs(samples[-ch + c] - samples[c]) for c in range(ch)) / 32768.0
    if ch != 2 or sw != 2 or sr != SAMPLE_RATE or nf == 0 or peak >= 0.999 or peak < 0.05:
        raise RuntimeError(f"WAV validation failed for {path}: ch={ch} sw={sw} sr={sr} nf={nf} peak={peak:.3f}")
    return {
        "file": os.path.basename(path),
        "channels": ch,
        "bits": sw * 8,
        "sample_rate": sr,
        "duration_s": round(nf / sr, 3),
        "peak": round(peak, 4),
        "rms": round(rms, 4),
        "dc_offset": round(dc, 5),
        "seam_jump": round(seam_jump, 5),
    }


def main():
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Assets", "Audio"))
    os.makedirs(out_dir, exist_ok=True)
    for filename, fn in SPECS:
        path = os.path.join(out_dir, filename)
        samples = fn()
        write_wav_loop(path, samples, target_peak=TARGET_PEAK_DBFS)
        info = verify_wav(path)
        print(
            f"{info['file']:28s} {info['sample_rate']}Hz {info['bits']}bit ch={info['channels']} "
            f"dur={info['duration_s']:6.3f}s peak={info['peak']:.4f} rms={info['rms']:.4f} "
            f"dc={info['dc_offset']:+.5f} seam_jump={info['seam_jump']:.5f}"
        )


if __name__ == "__main__":
    main()
