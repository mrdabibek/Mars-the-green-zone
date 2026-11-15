#!/usr/bin/env python3
"""Synthesize 48kHz 16-bit PCM WAV SFX (23 SFX + stereo Mars wind loop) for Mars: Last Green.

All sounds are procedurally synthesized with deterministic seeding, multi-layered
sub-bass + filtered resonant transients + subtle room tail, DC removal, peak
normalization to -1.5 dBFS (0.8414), and click-free envelopes.

Usage:
    python3 Tools/gen_audio.py
"""
import math
import os
import random
import struct
import wave

SAMPLE_RATE = 48000
MAX_INT16 = 32767
TARGET_PEAK_DBFS = 10.0 ** (-1.5 / 20.0)  # -1.5 dBFS (~0.8414)
SEED = 20261114


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
    """Voss-McCartney / Paul Kellet 7-pole pink noise approximation."""
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


def add_room_tail(samples: list[float], wet: float = 0.14) -> list[float]:
    """Add a subtle, warm multi-tap early reflection / room tail to eliminate dry harshness."""
    if wet <= 0.0 or not samples:
        return samples
    n = len(samples)
    out = list(samples)
    taps = [
        (int(0.011 * SAMPLE_RATE), 0.48),
        (int(0.019 * SAMPLE_RATE), 0.32),
        (int(0.031 * SAMPLE_RATE), 0.21),
        (int(0.047 * SAMPLE_RATE), 0.12),
    ]
    damped = biquad_filter(samples, "lowpass", 2400.0, 0.707)
    for delay, gain in taps:
        g = wet * gain
        for i in range(delay, n):
            out[i] += damped[i - delay] * g
    return out


def apply_fade(samples: list[float], fade_in_s: float = 0.003, fade_out_s: float = 0.008) -> list[float]:
    n = len(samples)
    fi = min(n // 2, max(1, int(fade_in_s * SAMPLE_RATE)))
    fo = min(n // 2, max(1, int(fade_out_s * SAMPLE_RATE)))
    out = list(samples)
    for i in range(fi):
        out[i] *= 0.5 * (1.0 - math.cos(math.pi * i / float(fi)))
    for i in range(fo):
        idx = n - 1 - i
        out[idx] *= 0.5 * (1.0 - math.cos(math.pi * i / float(fo)))
    out[0] = 0.0
    out[-1] = 0.0
    return out


def normalize_channel(samples: list[float], target_peak: float = TARGET_PEAK_DBFS, is_loop: bool = False) -> list[int]:
    if not samples:
        return []
    mean = sum(samples) / len(samples)
    centered = [s - mean for s in samples]
    if not is_loop:
        centered = apply_fade(centered, 0.002, 0.008)
        # Re-center interior while keeping exact zero endpoints
        mean2 = sum(centered) / len(centered)
        centered = [s - mean2 for s in centered]
        centered = apply_fade(centered, 0.002, 0.008)
    else:
        # Smoothly bridge the last 64 samples to match sample[0] so loop seam jump is 0
        seam_n = min(64, len(centered) // 8)
        end_delta = centered[0] - centered[-1]
        for k in range(seam_n):
            w = (k + 1) / float(seam_n)
            centered[len(centered) - seam_n + k] += end_delta * (0.5 * (1.0 - math.cos(math.pi * w)))
        mean2 = sum(centered) / len(centered)
        centered = [s - mean2 for s in centered]

    peak = max(abs(s) for s in centered)
    gain = (target_peak / peak) if peak > 1e-9 else 0.0
    return [max(-MAX_INT16, min(MAX_INT16, int(round(s * gain * MAX_INT16)))) for s in centered]


def write_wav(path: str, audio_data, target_peak: float = TARGET_PEAK_DBFS, is_loop: bool = False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(audio_data, tuple) and len(audio_data) == 2:
        left_q = normalize_channel(audio_data[0], target_peak=target_peak, is_loop=is_loop)
        right_q = normalize_channel(audio_data[1], target_peak=target_peak, is_loop=is_loop)
        interleaved = [0] * (len(left_q) * 2)
        interleaved[0::2] = left_q
        interleaved[1::2] = right_q
        with wave.open(path, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(struct.pack(f"<{len(interleaved)}h", *interleaved))
    else:
        pcm = normalize_channel(audio_data, target_peak=target_peak, is_loop=is_loop)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(struct.pack(f"<{len(pcm)}h", *pcm))


def mix_into(dst: list[float], src: list[float], offset_s: float, gain: float = 1.0):
    start = int(round(offset_s * SAMPLE_RATE))
    for i, s in enumerate(src):
        idx = start + i
        if 0 <= idx < len(dst):
            dst[idx] += s * gain


def gen_rifle_fire() -> list[float]:
    """Punchy multi-layered kinetic/plasma carbine shot (~0.20s: sub thump + transient crack + warm tail)."""
    rng = make_rng(1)
    dur = 0.20
    n = int(SAMPLE_RATE * dur)
    pnoise = pink_noise(n, rng)
    crack = biquad_filter([rng.uniform(-1.0, 1.0) for _ in range(n)], "bandpass", 1950.0, 1.0)
    body_noise = biquad_filter(pnoise, "bandpass", 420.0, 0.85)
    low_boom = biquad_filter(pnoise, "lowpass", 180.0, 0.7)

    out = [0.0] * n
    ph_sub = ph_mid = ph_chirp = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        f_sub = 46.0 + 175.0 * math.exp(-t / 0.020)
        ph_sub += 2.0 * math.pi * f_sub / SAMPLE_RATE
        sub = math.sin(ph_sub) * math.exp(-t / 0.045)

        f_mid = 110.0 + 320.0 * math.exp(-t / 0.014)
        ph_mid += 2.0 * math.pi * f_mid / SAMPLE_RATE
        mid_punch = math.sin(ph_mid) * math.exp(-t / 0.028)

        f_chirp = 190.0 + 980.0 * math.exp(-t / 0.015)
        ph_chirp += 2.0 * math.pi * f_chirp / SAMPLE_RATE
        chirp = math.sin(ph_chirp + 0.45 * math.sin(ph_chirp * 2.0)) * math.exp(-t / 0.022)

        s = (
            0.85 * sub
            + 0.55 * mid_punch
            + 0.35 * chirp
            + 0.70 * crack[i] * math.exp(-t / 0.014)
            + 0.65 * body_noise[i] * math.exp(-t / 0.042)
            + 0.45 * low_boom[i] * math.exp(-t / 0.085)
        )
        out[i] = math.tanh(s * 1.35)
    return apply_fade(add_room_tail(out, 0.16), 0.001, 0.018)


def gen_mech_click(rng: random.Random, dur: float, f0: float, f1: float, band: float) -> list[float]:
    n = int(SAMPLE_RATE * dur)
    raw = biquad_filter(pink_noise(n, rng), "bandpass", band, 1.8)
    out = [0.0] * n
    ph = ph_sub = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        u = t / dur
        f = f0 + (f1 - f0) * u
        ph += 2.0 * math.pi * f / SAMPLE_RATE
        ph_sub += 2.0 * math.pi * (95.0 + 90.0 * math.exp(-t / 0.012)) / SAMPLE_RATE
        env = (1.0 - math.exp(-t / 0.0025)) * math.exp(-t / (dur * 0.30))
        out[i] = (0.48 * math.sin(ph) + 0.42 * math.sin(ph_sub) + 0.80 * raw[i]) * env
    return apply_fade(out, 0.001, 0.006)


def gen_rifle_reload() -> list[float]:
    """3-stage tactile mechanical + capacitor carbine reload sequence (1.75s)."""
    rng = make_rng(2)
    dur = 1.75
    n = int(SAMPLE_RATE * dur)
    out = [0.0] * n

    mix_into(out, gen_mech_click(rng, 0.09, 980.0, 480.0, 1650.0), 0.04, 0.85)
    slide_n = int(0.22 * SAMPLE_RATE)
    slide = biquad_filter(pink_noise(slide_n, rng), "bandpass", 1150.0, 1.4)
    for i in range(slide_n):
        t = i / SAMPLE_RATE
        slide[i] *= math.sin(math.pi * t / 0.22) * 0.45
    mix_into(out, slide, 0.12, 1.0)

    mix_into(out, gen_mech_click(rng, 0.10, 320.0, 140.0, 720.0), 0.76, 0.95)
    mix_into(out, gen_mech_click(rng, 0.08, 1250.0, 780.0, 2100.0), 0.86, 0.95)

    mix_into(out, gen_mech_click(rng, 0.08, 860.0, 1450.0, 1850.0), 1.28, 0.85)
    mix_into(out, gen_mech_click(rng, 0.10, 1450.0, 520.0, 1600.0), 1.40, 1.00)

    hum_n = int(0.26 * SAMPLE_RATE)
    hum = []
    ph = 0.0
    for i in range(hum_n):
        t = i / SAMPLE_RATE
        f = 280.0 + 380.0 * (t / 0.26)
        ph += 2.0 * math.pi * f / SAMPLE_RATE
        hum.append((0.7 * math.sin(ph) + 0.3 * math.sin(ph * 1.5)) * math.sin(math.pi * t / 0.26) * 0.28)
    mix_into(out, hum, 1.44, 1.0)
    return apply_fade(add_room_tail(out, 0.12), 0.003, 0.020)


def gen_hit_marker() -> list[float]:
    """Crisp, warm dual-transient tactical hit confirmation tick (0.075s)."""
    rng = make_rng(20)
    dur = 0.075
    n = int(SAMPLE_RATE * dur)
    tick_noise = biquad_filter([rng.uniform(-1.0, 1.0) for _ in range(n)], "bandpass", 2200.0, 1.8)
    out = [0.0] * n
    for i in range(n):
        t = i / SAMPLE_RATE
        env1 = (1.0 - math.exp(-t / 0.0012)) * math.exp(-t / 0.010)
        env2 = math.exp(-max(0.0, t - 0.015) / 0.014) if t >= 0.015 else 0.0
        thump = math.sin(2.0 * math.pi * 195.0 * t) * math.exp(-t / 0.012)
        s1 = (0.65 * math.sin(2.0 * math.pi * 1850.0 * t) + 0.35 * math.sin(2.0 * math.pi * 2950.0 * t) + 0.4 * tick_noise[i]) * env1
        s2 = math.sin(2.0 * math.pi * 1420.0 * t) * env2 * 0.60
        out[i] = 0.45 * thump + s1 + s2
    return apply_fade(out, 0.001, 0.008)


def gen_raider_telegraph() -> list[float]:
    """Feral chitinous coil-and-hiss lunge telegraph (0.70s)."""
    rng = make_rng(3)
    dur = 0.70
    n = int(SAMPLE_RATE * dur)
    pnoise = pink_noise(n, rng)
    hiss = biquad_filter(pnoise, "bandpass", 1450.0, 1.3)
    chest = biquad_filter(pnoise, "lowpass", 260.0, 0.8)
    out = [0.0] * n
    ph_car = ph_mod = ph_sub = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        u = t / dur
        if u < 0.65:
            f = 115.0 + 210.0 * (u / 0.65) ** 1.35
            amp = 0.40 + 0.60 * (u / 0.65)
        else:
            v = (u - 0.65) / 0.35
            f = 325.0 + 150.0 * math.sin(v * math.pi * 0.5) - 130.0 * v
            amp = 1.0 - 0.40 * v
        ph_car += 2.0 * math.pi * f / SAMPLE_RATE
        ph_mod += 2.0 * math.pi * (f * 0.5) / SAMPLE_RATE
        ph_sub += 2.0 * math.pi * (f * 0.5) / SAMPLE_RATE
        growl = math.tanh(1.6 * math.sin(ph_car + 1.2 * math.sin(ph_mod)))
        sub_growl = math.sin(ph_sub) * 0.55
        breath = (0.65 * hiss[i] + 0.55 * chest[i]) * (0.4 + 0.85 * (u if u < 0.75 else 1.0 - (u - 0.75) * 3.0))
        out[i] = (0.55 * growl + 0.45 * sub_growl + 0.55 * breath) * amp
    return apply_fade(add_room_tail(out, 0.15), 0.010, 0.025)


def gen_breaker_slam() -> list[float]:
    """Massive seismic Breaker shockwave ground slam impact (0.62s)."""
    rng = make_rng(4)
    dur = 0.62
    n = int(SAMPLE_RATE * dur)
    pnoise = pink_noise(n, rng)
    crunch = biquad_filter(pnoise, "bandpass", 420.0, 0.85)
    rumble = biquad_filter(pnoise, "lowpass", 135.0, 0.8)
    debris = biquad_filter(pnoise, "bandpass", 1250.0, 1.2)

    out = [0.0] * n
    ph = ph2 = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        f_sub = 28.0 + 92.0 * math.exp(-t / 0.055)
        ph += 2.0 * math.pi * f_sub / SAMPLE_RATE
        ph2 += 2.0 * math.pi * (f_sub * 1.5) / SAMPLE_RATE
        sub = (0.85 * math.sin(ph) + 0.35 * math.sin(ph2)) * math.exp(-t / 0.18)
        imp = crunch[i] * math.exp(-t / 0.075)
        tail = rumble[i] * math.exp(-t / 0.28)
        grit = debris[i] * math.exp(-t / 0.09)
        out[i] = math.tanh(1.45 * (0.95 * sub + 0.75 * imp + 0.65 * tail + 0.35 * grit))
    return apply_fade(add_room_tail(out, 0.18), 0.002, 0.035)


def gen_gunner_charge() -> list[float]:
    """Plasma rifle turbine & capacitor charge crescendo + lock pulse (0.90s)."""
    rng = make_rng(5)
    dur = 0.90
    n = int(SAMPLE_RATE * dur)
    pnoise = pink_noise(n, rng)
    crackle = biquad_filter(pnoise, "bandpass", 1850.0, 1.6)
    low_hum = biquad_filter(pnoise, "lowpass", 240.0, 0.8)

    out = [0.0] * n
    ph1 = ph2 = ph_sub = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        u = t / dur
        f1 = 155.0 * (5.2 ** (u ** 1.3))
        f2 = f1 * 1.498
        f_sub = 65.0 + 95.0 * u
        ph1 += 2.0 * math.pi * f1 / SAMPLE_RATE
        ph2 += 2.0 * math.pi * f2 / SAMPLE_RATE
        ph_sub += 2.0 * math.pi * f_sub / SAMPLE_RATE

        pulse = 0.76 + 0.24 * math.sin(2.0 * math.pi * (6.0 + 16.0 * u) * t)
        ramp = (u ** 1.1) * (1.0 if u < 0.92 else max(0.0, (1.0 - u) / 0.08))
        tone_val = (0.55 * math.sin(ph1) + 0.30 * math.sin(ph2) + 0.45 * math.sin(ph_sub)) * pulse
        spark = (0.6 * crackle[i] + 0.4 * low_hum[i]) * (0.3 + 0.6 * u)
        chirp = math.sin(2.0 * math.pi * 1480.0 * t) * math.exp(-((t - 0.82) ** 2) / (2 * 0.016 ** 2))
        out[i] = (0.65 * tone_val + 0.35 * spark) * ramp + 0.42 * chirp
    return apply_fade(add_room_tail(out, 0.14), 0.012, 0.015)


def gen_alien_hit() -> list[float]:
    """Heavy chitin/carapace ballistic impact thud + crack (0.16s)."""
    rng = make_rng(6)
    dur = 0.16
    n = int(SAMPLE_RATE * dur)
    pnoise = pink_noise(n, rng)
    snap = biquad_filter(pnoise, "bandpass", 1350.0, 1.3)
    body = biquad_filter(pnoise, "lowpass", 320.0, 0.8)
    out = [0.0] * n
    ph = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        f = 62.0 + 210.0 * math.exp(-t / 0.018)
        ph += 2.0 * math.pi * f / SAMPLE_RATE
        thud = math.sin(ph) * math.exp(-t / 0.042)
        out[i] = math.tanh(1.35 * (0.82 * thud + 0.65 * snap[i] * math.exp(-t / 0.024) + 0.45 * body[i] * math.exp(-t / 0.05)))
    return apply_fade(add_room_tail(out, 0.12), 0.001, 0.014)


def gen_alien_death() -> list[float]:
    """Deep alien vocalization powerdown + heavy grounded body collapse thud (0.85s)."""
    rng = make_rng(7)
    dur = 0.85
    n = int(SAMPLE_RATE * dur)
    pnoise = pink_noise(n, rng)
    exhale = biquad_filter(pnoise, "bandpass", 520.0, 1.0)
    dust = biquad_filter(pnoise, "lowpass", 190.0, 0.8)
    out = [0.0] * n
    ph = ph_sub = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        u = t / dur
        f = 340.0 * math.exp(-t / 0.25) + 46.0
        ph += 2.0 * math.pi * f / SAMPLE_RATE
        wail = math.tanh(1.35 * (0.7 * math.sin(ph + 0.5 * math.sin(ph * 0.5)) + 0.3 * math.sin(ph * 0.5))) * math.exp(-t / 0.32)

        dt = max(0.0, t - 0.40)
        f_thud = 38.0 + 82.0 * math.exp(-dt / 0.042)
        ph_sub += 2.0 * math.pi * f_thud / SAMPLE_RATE
        thud = ((0.85 * math.sin(ph_sub) + 0.45 * dust[i]) * math.exp(-dt / 0.11)) if t >= 0.40 else 0.0

        out[i] = 0.62 * wail + 0.55 * exhale[i] * (1.0 - u) ** 1.2 + 0.80 * thud
    return apply_fade(add_room_tail(out, 0.16), 0.005, 0.030)


def gen_repair_tick() -> list[float]:
    """Warm pneumatic ratchet + plasma micro-weld pulse (0.095s)."""
    rng = make_rng(8)
    dur = 0.095
    n = int(SAMPLE_RATE * dur)
    spark = biquad_filter(pink_noise(n, rng), "bandpass", 1750.0, 1.4)
    out = [0.0] * n
    ph = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        f = 160.0 + 420.0 * math.exp(-t / 0.012)
        ph += 2.0 * math.pi * f / SAMPLE_RATE
        env = (1.0 - math.exp(-t / 0.0015)) * math.exp(-t / 0.022)
        tone = 0.55 * math.sin(ph) + 0.35 * math.sin(2.0 * math.pi * 1180.0 * t)
        out[i] = (tone + 0.55 * spark[i]) * env
    return apply_fade(add_room_tail(out, 0.10), 0.001, 0.008)


def gen_repair_done() -> list[float]:
    """Heavy airlock/device pneumatic seal + warm 3-note harmonic triad (0.46s)."""
    rng = make_rng(9)
    dur = 0.46
    n = int(SAMPLE_RATE * dur)
    out = [0.0] * n
    mix_into(out, gen_mech_click(rng, 0.09, 240.0, 95.0, 620.0), 0.0, 0.65)
    notes = [(0.04, 392.00, 0.18), (0.13, 493.88, 0.20), (0.22, 587.33, 0.24)]
    for start_s, freq, ndur in notes:
        nn = int(ndur * SAMPLE_RATE)
        buf = []
        for i in range(nn):
            t = i / SAMPLE_RATE
            env = (1.0 - math.exp(-t / 0.006)) * math.exp(-t / (ndur * 0.48))
            s = (
                0.68 * math.sin(2.0 * math.pi * freq * t)
                + 0.22 * math.sin(2.0 * math.pi * (freq * 1.5) * t)
                + 0.15 * math.sin(2.0 * math.pi * (freq * 0.5) * t)
            )
            buf.append(s * env)
        mix_into(out, buf, start_s, 0.65)
    return apply_fade(add_room_tail(out, 0.18), 0.003, 0.022)


def gen_alert_low() -> list[float]:
    """Warm, rounded two-tone NASA telemetry caution pulse (0.42s, non-piercing)."""
    dur = 0.42
    n = int(SAMPLE_RATE * dur)
    out = [0.0] * n
    for start_s, freq in [(0.00, 520.0), (0.19, 390.0)]:
        plen = int(0.17 * SAMPLE_RATE)
        buf = []
        for i in range(plen):
            t = i / SAMPLE_RATE
            env = math.sin(math.pi * t / 0.17) ** 0.85
            s = (
                0.72 * math.sin(2.0 * math.pi * freq * t)
                + 0.20 * math.sin(2.0 * math.pi * (freq * 2.0) * t) * math.exp(-t / 0.07)
                + 0.18 * math.sin(2.0 * math.pi * (freq * 0.5) * t)
            )
            buf.append(s * env)
        mix_into(out, buf, start_s, 0.85)
    return apply_fade(add_room_tail(out, 0.15), 0.004, 0.018)


def gen_transmit() -> list[float]:
    """Deep-space telemetry handshake + warm harmonic uplink chord (0.68s)."""
    dur = 0.68
    n = int(SAMPLE_RATE * dur)
    out = [0.0] * n
    ph = ph_sub = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        if t < 0.20:
            u = t / 0.20
            f = 440.0 + 440.0 * u
            amp = math.sin(math.pi * u) ** 0.6
        elif t < 0.46:
            bit = int((t - 0.20) / 0.032)
            f = 1174.66 if (bit % 3 != 0) else 880.0
            amp = 0.58
        else:
            f = 880.0
            amp = 0.78 * math.exp(-(t - 0.46) / 0.12)
        ph += 2.0 * math.pi * f / SAMPLE_RATE
        ph_sub += 2.0 * math.pi * 220.0 / SAMPLE_RATE
        out[i] = (0.72 * math.sin(ph) + 0.28 * math.sin(ph_sub)) * amp
    return apply_fade(add_room_tail(out, 0.18), 0.004, 0.020)


def gen_footstep_indoor() -> list[float]:
    """Heavy pressurized boot step on metallic habitat deck grating (~0.24s)."""
    rng = make_rng(11)
    dur = 0.24
    n = int(SAMPLE_RATE * dur)
    pnoise = pink_noise(n, rng)
    clank = biquad_filter(pnoise, "bandpass", 920.0, 1.5)
    scuff = biquad_filter(pnoise, "bandpass", 2100.0, 1.2)
    out = [0.0] * n
    ph_heel = ph_plate = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        f_heel = 54.0 + 110.0 * math.exp(-t / 0.016)
        ph_heel += 2.0 * math.pi * f_heel / SAMPLE_RATE
        heel = math.sin(ph_heel) * math.exp(-t / 0.042)

        f_plate = 240.0 + 90.0 * math.exp(-t / 0.012)
        ph_plate += 2.0 * math.pi * f_plate / SAMPLE_RATE
        plate = (math.sin(ph_plate) + 0.4 * math.sin(ph_plate * 2.38)) * math.exp(-t / 0.032)

        toe_t = max(0.0, t - 0.042)
        toe_env = math.exp(-toe_t / 0.028) if t >= 0.042 else 0.0
        out[i] = math.tanh(1.25 * (0.85 * heel + 0.42 * plate + 0.55 * clank[i] * math.exp(-t / 0.028) + 0.35 * scuff[i] * toe_env))
    return apply_fade(add_room_tail(out, 0.14), 0.002, 0.018)


def gen_footstep_mars() -> list[float]:
    """Crunchy Martian regolith/gravel boot step (~0.28s)."""
    rng = make_rng(12)
    dur = 0.28
    n = int(SAMPLE_RATE * dur)
    pnoise = pink_noise(n, rng)
    gravel = biquad_filter(pnoise, "bandpass", 1350.0, 1.1)
    grit = biquad_filter(pnoise, "bandpass", 2650.0, 1.4)
    soil = biquad_filter(pnoise, "lowpass", 220.0, 0.8)
    out = [0.0] * n
    ph = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        f = 48.0 + 78.0 * math.exp(-t / 0.020)
        ph += 2.0 * math.pi * f / SAMPLE_RATE
        thump = math.sin(ph) * math.exp(-t / 0.050)
        # Two-stage heel-to-toe regolith crunch envelope
        crunch_env = math.exp(-t / 0.045) + 0.65 * (math.exp(-max(0.0, t - 0.055) / 0.055) if t >= 0.055 else 0.0)
        grain_mod = 0.70 + 0.30 * math.sin(2.0 * math.pi * 68.0 * t + 1.5 * math.sin(2.0 * math.pi * 23.0 * t))
        out[i] = math.tanh(1.3 * (0.78 * thump + 0.55 * soil[i] * math.exp(-t / 0.065) + (0.75 * gravel[i] + 0.45 * grit[i]) * crunch_env * grain_mod))
    return apply_fade(out, 0.002, 0.022)


def gen_jump() -> list[float]:
    """Suit pneumatic servo boost + boot push-off (~0.30s)."""
    rng = make_rng(13)
    dur = 0.30
    n = int(SAMPLE_RATE * dur)
    pnoise = pink_noise(n, rng)
    air = biquad_filter(pnoise, "bandpass", 950.0, 1.2)
    scuff = biquad_filter(pnoise, "lowpass", 340.0, 0.8)
    out = [0.0] * n
    ph_kick = ph_servo = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        u = t / dur
        f_kick = 52.0 + 95.0 * math.exp(-t / 0.024)
        ph_kick += 2.0 * math.pi * f_kick / SAMPLE_RATE
        kick = math.sin(ph_kick) * math.exp(-t / 0.055)

        f_servo = 140.0 + 220.0 * (u ** 0.85)
        ph_servo += 2.0 * math.pi * f_servo / SAMPLE_RATE
        servo = math.sin(ph_servo) * math.sin(math.pi * u) * 0.38

        out[i] = 0.80 * kick + servo + 0.55 * air[i] * math.sin(math.pi * u) + 0.45 * scuff[i] * math.exp(-t / 0.06)
    return apply_fade(add_room_tail(out, 0.10), 0.002, 0.022)


def gen_land() -> list[float]:
    """Heavy suit landing impact + pneumatic shock absorber compression (~0.36s)."""
    rng = make_rng(14)
    dur = 0.36
    n = int(SAMPLE_RATE * dur)
    pnoise = pink_noise(n, rng)
    thud_noise = biquad_filter(pnoise, "lowpass", 240.0, 0.8)
    crunch = biquad_filter(pnoise, "bandpass", 1100.0, 1.1)
    valve_hiss = biquad_filter(pnoise, "bandpass", 1900.0, 1.6)
    out = [0.0] * n
    ph = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        f = 38.0 + 115.0 * math.exp(-t / 0.028)
        ph += 2.0 * math.pi * f / SAMPLE_RATE
        sub = math.sin(ph) * math.exp(-t / 0.085)
        hiss_t = max(0.0, t - 0.05)
        hiss_env = math.sin(math.pi * min(1.0, hiss_t / 0.22)) * 0.42 if 0.05 <= t <= 0.27 else 0.0
        out[i] = math.tanh(1.35 * (0.92 * sub + 0.65 * thud_noise[i] * math.exp(-t / 0.075) + 0.55 * crunch[i] * math.exp(-t / 0.045) + valve_hiss[i] * hiss_env))
    return apply_fade(add_room_tail(out, 0.14), 0.002, 0.025)


def gen_player_hurt() -> list[float]:
    """Visor/suit kinetic impact thud + muffled pressure jolt + brief telemetry warning (~0.38s)."""
    rng = make_rng(15)
    dur = 0.38
    n = int(SAMPLE_RATE * dur)
    pnoise = pink_noise(n, rng)
    impact_n = biquad_filter(pnoise, "lowpass", 310.0, 0.85)
    crack_n = biquad_filter(pnoise, "bandpass", 1250.0, 1.3)
    out = [0.0] * n
    ph_sub = ph_warn = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        f_sub = 44.0 + 145.0 * math.exp(-t / 0.024)
        ph_sub += 2.0 * math.pi * f_sub / SAMPLE_RATE
        sub = math.sin(ph_sub) * math.exp(-t / 0.080)

        warn_env = math.sin(math.pi * (t - 0.06) / 0.18) if 0.06 <= t <= 0.24 else 0.0
        f_warn = 620.0 if t < 0.15 else 465.0
        ph_warn += 2.0 * math.pi * f_warn / SAMPLE_RATE
        warn_tone = math.sin(ph_warn) * warn_env * 0.32

        out[i] = math.tanh(1.4 * (0.95 * sub + 0.70 * impact_n[i] * math.exp(-t / 0.07) + 0.50 * crack_n[i] * math.exp(-t / 0.03) + warn_tone))
    return apply_fade(add_room_tail(out, 0.12), 0.002, 0.025)


def gen_low_o2_heartbeat() -> list[float]:
    """Deep physiological double-thump ('lub-dub') + subtle O2 regulator click (~0.68s)."""
    rng = make_rng(16)
    dur = 0.68
    n = int(SAMPLE_RATE * dur)
    valve = biquad_filter(pink_noise(n, rng), "bandpass", 850.0, 1.5)
    out = [0.0] * n

    for beat_start, f0, f1, b_amp in [(0.02, 68.0, 36.0, 0.95), (0.25, 58.0, 32.0, 0.72)]:
        bn = int(0.18 * SAMPLE_RATE)
        buf = [0.0] * bn
        ph = 0.0
        for k in range(bn):
            t = k / SAMPLE_RATE
            f = f1 + (f0 - f1) * math.exp(-t / 0.032)
            ph += 2.0 * math.pi * f / SAMPLE_RATE
            env = (1.0 - math.exp(-t / 0.008)) * math.exp(-t / 0.052)
            buf[k] = (0.85 * math.sin(ph) + 0.25 * math.sin(2.0 * ph)) * env * b_amp
        mix_into(out, buf, beat_start, 1.0)

    for i in range(n):
        t = i / SAMPLE_RATE
        if 0.44 <= t <= 0.62:
            u = (t - 0.44) / 0.18
            out[i] += valve[i] * math.sin(math.pi * u) * 0.18
    return apply_fade( out, 0.004, 0.025)


def gen_turret_fire() -> list[float]:
    """Twin-barrel automated sentry cannon burst (~0.22s: dual staggered electromagnetic/kinetic pulses)."""
    rng = make_rng(17)
    dur = 0.22
    n = int(SAMPLE_RATE * dur)
    out = [0.0] * n

    for burst_offset, gain in [(0.00, 1.0), (0.052, 0.88)]:
        bn = int(0.14 * SAMPLE_RATE)
        pnoise = pink_noise(bn, rng)
        crack = biquad_filter(pnoise, "bandpass", 1650.0, 1.2)
        thump_n = biquad_filter(pnoise, "lowpass", 260.0, 0.8)
        buf = [0.0] * bn
        ph_sub = ph_pulse = 0.0
        for k in range(bn):
            t = k / SAMPLE_RATE
            f_sub = 58.0 + 160.0 * math.exp(-t / 0.016)
            ph_sub += 2.0 * math.pi * f_sub / SAMPLE_RATE
            f_p = 280.0 + 720.0 * math.exp(-t / 0.014)
            ph_pulse += 2.0 * math.pi * f_p / SAMPLE_RATE
            s = (
                0.80 * math.sin(ph_sub) * math.exp(-t / 0.035)
                + 0.45 * math.sin(ph_pulse) * math.exp(-t / 0.022)
                + 0.65 * crack[k] * math.exp(-t / 0.018)
                + 0.45 * thump_n[k] * math.exp(-t / 0.040)
            )
            buf[k] = math.tanh(1.3 * s)
        mix_into(out, buf, burst_offset, gain)
    return apply_fade(add_room_tail(out, 0.16), 0.001, 0.018)


def gen_pickup() -> list[float]:
    """Tactile magnetic cargo latch + warm rising sci-fi confirmation chord (~0.34s)."""
    rng = make_rng(18)
    dur = 0.34
    n = int(SAMPLE_RATE * dur)
    out = [0.0] * n
    mix_into(out, gen_mech_click(rng, 0.065, 340.0, 160.0, 950.0), 0.0, 0.75)

    notes = [(0.03, 523.25, 0.16, 0.55), (0.09, 659.25, 0.18, 0.50), (0.15, 783.99, 0.18, 0.55)]
    for start_s, freq, ndur, amp in notes:
        nn = int(ndur * SAMPLE_RATE)
        buf = [0.0] * nn
        for k in range(nn):
            t = k / SAMPLE_RATE
            env = (1.0 - math.exp(-t / 0.005)) * math.exp(-t / (ndur * 0.45))
            buf[k] = (0.75 * math.sin(2.0 * math.pi * freq * t) + 0.25 * math.sin(2.0 * math.pi * (freq * 0.5) * t)) * env * amp
        mix_into(out, buf, start_s, 1.0)
    return apply_fade(add_room_tail(out, 0.15), 0.002, 0.020)


def gen_wave_start() -> list[float]:
    """Deep cinematic Martian perimeter horn swell + radar threat pulse (~1.35s)."""
    rng = make_rng(19)
    dur = 1.35
    n = int(SAMPLE_RATE * dur)
    pnoise = pink_noise(n, rng)
    rumble = biquad_filter(pnoise, "lowpass", 150.0, 0.8)
    air = biquad_filter(pnoise, "bandpass", 620.0, 1.4)
    out = [0.0] * n

    freqs = [73.416, 110.0, 146.832, 155.563]  # D2, A2, D3, Eb3 Phrygian tension horn
    weights = [0.50, 0.32, 0.28, 0.22]
    for i in range(n):
        t = i / SAMPLE_RATE
        u = t / dur
        swell = (math.sin(math.pi * u) ** 0.75) * (1.0 - 0.25 * u)
        horn = 0.0
        for f, w in zip(freqs, weights):
            ph = 2.0 * math.pi * f * t
            horn += w * math.tanh(1.4 * (math.sin(ph) + 0.35 * math.sin(2.0 * ph) + 0.15 * math.sin(3.0 * ph)))
        radar_ping = 0.0
        for p_start in (0.18, 0.68):
            if p_start <= t <= p_start + 0.16:
                pt = t - p_start
                radar_ping += 0.28 * math.sin(2.0 * math.pi * 587.33 * pt) * math.exp(-pt / 0.045)
        out[i] = math.tanh(1.25 * ((0.75 * horn + 0.40 * rumble[i] + 0.20 * air[i]) * swell + radar_ping))
    return apply_fade(add_room_tail(out, 0.22), 0.015, 0.045)


def gen_ui_click() -> list[float]:
    """Sleek, soft tactile HUD micro-click (~0.045s)."""
    rng = make_rng(21)
    dur = 0.045
    n = int(SAMPLE_RATE * dur)
    tap_noise = biquad_filter(pink_noise(n, rng), "bandpass", 1450.0, 1.6)
    out = [0.0] * n
    ph = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        f = 180.0 + 780.0 * math.exp(-t / 0.004)
        ph += 2.0 * math.pi * f / SAMPLE_RATE
        env = (1.0 - math.exp(-t / 0.0008)) * math.exp(-t / 0.008)
        out[i] = (0.72 * math.sin(ph) + 0.38 * tap_noise[i]) * env
    return apply_fade(out, 0.001, 0.005)


def gen_mars_wind_loop() -> tuple[list[float], list[float]]:
    """10.000s stereo seamless Martian thin-atmosphere wind loop with crossfaded boundaries."""
    rng_l = make_rng(10)
    rng_r = make_rng(110)
    dur = 10.0
    xfade_s = 1.5
    n = int(SAMPLE_RATE * dur)
    xfade_n = int(SAMPLE_RATE * xfade_s)
    total = n + xfade_n

    def build_channel(rng: random.Random, phase_offset: float) -> list[float]:
        p = pink_noise(total, rng)
        sub_bed = biquad_filter(p, "lowpass", 145.0, 0.75)
        low_gust = biquad_filter(p, "bandpass", 310.0, 1.2)
        whistle = biquad_filter(p, "bandpass", 540.0, 2.0)
        dust = biquad_filter(p, "bandpass", 1050.0, 1.1)

        raw = [0.0] * total
        for i in range(total):
            t = (i % n) / SAMPLE_RATE
            g1 = 0.65 + 0.35 * math.sin(2.0 * math.pi * (t / dur) * 2.0 + phase_offset)
            g2 = 0.58 + 0.42 * math.sin(2.0 * math.pi * (t / dur) * 3.0 + 1.1 + phase_offset * 0.7)
            drone = 0.08 * math.sin(2.0 * math.pi * 55.0 * t + phase_offset) * g1
            raw[i] = 0.80 * sub_bed[i] * g1 + 0.55 * low_gust[i] * g2 + 0.38 * whistle[i] * g2 + 0.20 * dust[i] * (g1 * g2) + drone

        out = raw[:n]
        for i in range(xfade_n):
            alpha = i / float(xfade_n)
            w_in = math.sin(alpha * math.pi * 0.5)
            w_out = math.cos(alpha * math.pi * 0.5)
            out[i] = out[i] * w_in + raw[n + i] * w_out
        return out

    return build_channel(rng_l, 0.0), build_channel(rng_r, 0.85)



def gen_intro_burn():
    n = int(4.2 * SAMPLE_RATE)
    def channel(seed):
        noise = biquad_filter(pink_noise(n, make_rng(seed)), "lowpass", 520.0)
        return [noise[i] * min(1.0, i / (0.4 * SAMPLE_RATE), (n-i) / (0.8 * SAMPLE_RATE)) * (0.8 + 0.2 * math.sin(i / SAMPLE_RATE * 9)) for i in range(n)]
    return channel(111), channel(112)

def gen_intro_shatter():
    n = int(3.6 * SAMPLE_RATE)
    def channel(seed):
        noise = pink_noise(n, make_rng(seed))
        return [noise[i] * math.exp(-i / (SAMPLE_RATE * 1.1)) + 0.35 * math.sin(2 * math.pi * 50 * i / SAMPLE_RATE) * math.exp(-i / (SAMPLE_RATE * 0.7)) for i in range(n)]
    return channel(113), channel(114)

SPECS = [
    ("SFX_Intro_LanderBurn.wav", gen_intro_burn),
    ("SFX_Intro_EarthShatter.wav", gen_intro_shatter),
    # Existing 13 SFX + Ambient Loop
    ("SFX_Rifle_Fire.wav", gen_rifle_fire),
    ("SFX_Rifle_Reload.wav", gen_rifle_reload),
    ("SFX_Hit_Marker.wav", gen_hit_marker),
    ("SFX_Alien_Raider_Telegraph.wav", gen_raider_telegraph),
    ("SFX_Alien_Breaker_Slam.wav", gen_breaker_slam),
    ("SFX_Alien_Gunner_Charge.wav", gen_gunner_charge),
    ("SFX_Alien_Hit.wav", gen_alien_hit),
    ("SFX_Alien_Death.wav", gen_alien_death),
    ("SFX_Repair_Tick.wav", gen_repair_tick),
    ("SFX_Repair_Done.wav", gen_repair_done),
    ("SFX_Alert_Low.wav", gen_alert_low),
    ("SFX_Transmit.wav", gen_transmit),
    ("SFX_Mars_Wind_Loop.wav", gen_mars_wind_loop),
    # 10 New Increment 10 Gameplay & UI SFX
    ("SFX_Footstep_Indoor.wav", gen_footstep_indoor),
    ("SFX_Footstep_Mars.wav", gen_footstep_mars),
    ("SFX_Jump.wav", gen_jump),
    ("SFX_Land.wav", gen_land),
    ("SFX_Player_Hurt.wav", gen_player_hurt),
    ("SFX_LowO2_Heartbeat.wav", gen_low_o2_heartbeat),
    ("SFX_Turret_Fire.wav", gen_turret_fire),
    ("SFX_Pickup.wav", gen_pickup),
    ("SFX_Wave_Start.wav", gen_wave_start),
    ("SFX_UI_Click.wav", gen_ui_click),
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
    if ch not in (1, 2) or sw != 2 or sr != SAMPLE_RATE or nf == 0 or peak >= 0.999 or peak < 0.05:
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
        "edge_samples": (samples[0], samples[-1]),
    }


def main():
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Assets", "Audio"))
    os.makedirs(out_dir, exist_ok=True)
    for filename, fn in SPECS:
        path = os.path.join(out_dir, filename)
        samples = fn()
        write_wav(path, samples, target_peak=TARGET_PEAK_DBFS, is_loop=("loop" in filename.lower()))
        info = verify_wav(path)
        print(
            f"{info['file']:32s} {info['sample_rate']}Hz {info['bits']}bit ch={info['channels']} "
            f"dur={info['duration_s']:6.3f}s peak={info['peak']:.4f} rms={info['rms']:.4f} "
            f"dc={info['dc_offset']:+.5f} edges={info['edge_samples']}"
        )


if __name__ == "__main__":
    main()
