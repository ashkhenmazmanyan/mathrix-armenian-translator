"""Record one test clip from the mic or the system-audio monitor.

Usage:
    python scripts/record_clip.py mic me_01
    python scripts/record_clip.py system video_01 --seconds 10

Saves recordings/clips/<name>.wav (16 kHz mono). Clips are used to compare
speech-recognition models on the same audio.
"""
import argparse
import os
import wave

import numpy as np
import soundcard as sc

SR = 16000
WARMUP = 0.5  # seconds discarded at start (mic wake-up pop)

parser = argparse.ArgumentParser()
parser.add_argument("source", choices=["mic", "system"])
parser.add_argument("name", help="clip name, e.g. me_01 or video_01")
parser.add_argument("--seconds", type=float, default=8)
args = parser.parse_args()

if args.source == "mic":
    device = sc.default_microphone()
else:
    device = sc.get_microphone(sc.default_speaker().name, include_loopback=True)

os.makedirs("recordings/clips", exist_ok=True)
path = f"recordings/clips/{args.name}.wav"

with device.recorder(samplerate=SR, channels=1) as rec:
    rec.record(numframes=int(SR * WARMUP))
    print(f"Recording {args.seconds:.0f}s from {device.name} -> {path} -- go...")
    audio = rec.record(numframes=int(SR * args.seconds))[:, 0]

peak = 20 * np.log10(max(np.max(np.abs(audio)), 1e-10))
clipped = np.mean(np.abs(audio) >= 1.0) * 100
print(f"Done. Peak {peak:.1f} dBFS, clipped {clipped:.1f}%")

with wave.open(path, "wb") as f:
    f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
    f.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
