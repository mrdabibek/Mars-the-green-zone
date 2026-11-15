"""Render radio and score WAVs for the prologue. Python needs NumPy, ONNX Runtime, and eSpeak NG."""
import argparse
import ctypes
import json
from pathlib import Path
import wave

import numpy as np
import onnxruntime as ort

ROOT = Path(__file__).resolve().parents[1] / "Assets" / "Intro"
RATE = 48000
DURATION = 28.5
RUPTURE = 17.6
LINES = [
    (.65, 3.5, "computer", "Descent engines green. Twelve metres to the pad."),
    (5.1, 7.9, "aster", "Earth Control, we're down. Do you copy?"),
    (8.6, 11.8, "earth", "We copy. Aster, put the relay feed on screen."),
    (12.6, 15.6, "earth", "There are no more launch windows. Keep the seeds cold."),
    (15.8, 17.48, "earth", "Make something grow."),
    (22.95, 24.5, "aster", "Earth? Earth, come in."),
]


def pcm(name, data):
    with wave.open(str(ROOT / (name + ".wav")), "wb") as out:
        out.setparams((2, 2, RATE, 0, "NONE", ""))
        out.writeframes((32767 * np.clip(data, -1, 1)).astype("<i2").tobytes())


def band(data, low, high):
    freq = np.fft.rfftfreq(len(data), 1/RATE)
    transfer = np.minimum(1, (freq/low)**3) * np.minimum(1, (high/np.maximum(freq, 1))**4)
    return np.fft.irfft(np.fft.rfft(data) * transfer, len(data))


def voice_synth(model):
    cfg = json.loads(Path(str(model)+".json").read_text())
    espeak = ctypes.CDLL("libespeak-ng.so.1")
    espeak.espeak_Initialize(2, 0, None, 0)
    espeak.espeak_SetVoiceByName(cfg["espeak"]["voice"].encode())
    espeak.espeak_TextToPhonemes.argtypes = (ctypes.POINTER(ctypes.c_char_p), ctypes.c_int, ctypes.c_int)
    espeak.espeak_TextToPhonemes.restype = ctypes.c_char_p
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 2
    session = ort.InferenceSession(str(model), sess_options=opts, providers=["CPUExecutionProvider"])
    ids = cfg["phoneme_id_map"]

    def synth(text, speaker):
        remaining = ctypes.c_char_p(text.encode("utf-8"))
        phonemes = []
        while remaining.value is not None:
            result = espeak.espeak_TextToPhonemes(ctypes.byref(remaining), 1, 2)
            if result:
                phonemes.append(result.decode("utf-8").strip())
        sequence = ids["^"] + ids["_"]
        for c in ", ".join(phonemes):
            if c in ids:
                sequence += ids[c] + ids["_"]
        sequence += ids["$"]
        samples = session.run(None, {
            "input": np.array([sequence], dtype=np.int64),
            "input_lengths": np.array([len(sequence)], dtype=np.int64),
            "scales": np.array([.53, .94, .62], dtype=np.float32),
        })[0].flatten()
        active = np.flatnonzero(np.abs(samples) > .004)
        if active.size:
            samples = samples[max(0, active[0]-240):active[-1]+480]
        speed = {"earth": 1., "aster": .91, "computer": 1.07}[speaker]
        new_samples = int(len(samples)*RATE/(cfg["audio"]["sample_rate"]*speed))
        return np.interp(np.linspace(0, len(samples)-1, new_samples), np.arange(len(samples)), samples)

    return synth


def make_radio(model, rng):
    speak = voice_synth(model)
    track = np.zeros(int(DURATION*RATE))
    for start, end, speaker, line in LINES:
        samples = speak(line, speaker)
        budget = int((end-start-.12)*RATE)
        if len(samples) > budget:
            samples = np.interp(np.linspace(0, len(samples)-1, budget), np.arange(len(samples)), samples)
        samples = band(samples, 310, 3350)
        samples = .32*np.tanh(samples*(2.5/max(np.max(np.abs(samples)), .01)))
        if speaker == "computer":
            samples *= .86 + .14*np.sin(2*np.pi*54*np.arange(len(samples))/RATE)
        samples += .013*band(rng.normal(size=len(samples)), 1050, 4700)
        ramp = min(RATE//60, len(samples)//2)
        samples[:ramp] *= np.linspace(0,1,ramp)
        samples[-ramp:] *= np.linspace(1,0,ramp)
        offset = int(start*RATE)
        track[offset:offset+len(samples)] += samples
        print(f"{speaker}: {len(samples)/RATE:.2f}s at {start:.2f}")
    t = np.arange(RATE//5)/RATE
    burst = .12*band(rng.normal(size=t.size), 500, 6300)*np.exp(-t*21)
    offset = int(RUPTURE*RATE)
    track[offset:offset+t.size] += burst
    pcm("Prologue_Radio", np.column_stack((track,track)))


def make_score(rng):
    t = np.arange(int(DURATION*RATE))/RATE
    tone = lambda hz, phase=0: np.sin(2*np.pi*hz*t+phase)
    ease = lambda start, end: np.clip((t-start)/(end-start),0,1)**2
    age = np.maximum(0,t-RUPTURE)
    tension = ease(8.4,17.5) * (t<RUPTURE)
    tail = (t>=RUPTURE)*np.exp(-age*1.37)
    drift = .025*tone(43.65)+.018*tone(65.406,.4)+.016*tone(130.8,-.6)+.011*tone(155.56,1)
    drone = drift*ease(0,3.5)*(1-.95*ease(17.58,17.72))
    pressure = .09*tension*tone(39,.76*tone(.38))+.045*tension*tone(46,.6*tone(.76))
    coda = (.046*tone(58.27)+.025*tone(116.54,.9)+.018*tone(174.61,.36))*ease(23,26)*(1-ease(27,28.5))
    lowpass = band(rng.normal(size=t.size),17,170)
    crackle = band(rng.normal(size=t.size),250,1600)
    landing = .57*lowpass*(1-ease(2.95,4.75))*(.7+.3*tone(13))
    landing += .45*lowpass*(t>=4.66)*np.exp(-np.maximum(0,t-4.66)*5.1)
    blast = tail*(.46*tone(33)+.82*lowpass+.42*crackle)
    wind = .09*band(rng.normal(size=t.size),150,1300)*ease(22.6,23.6)*(1-ease(27.5,28.5))
    mid = drone+pressure+coda+landing+blast+wind
    wide = .020*tone(197.1,.85*tone(.33))*tension
    pcm("Prologue_Score", np.tanh(np.column_stack((mid+wide,mid-wide))*.9))


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("model", type=Path, help="Piper Lessac medium .onnx next to its .onnx.json")
    rng = np.random.default_rng(40512)
    make_radio(cli.parse_args().model, rng)
    make_score(rng)
