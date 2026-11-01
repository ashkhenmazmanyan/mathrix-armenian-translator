"""Check speaker-change splitting on the test clips.

video_05 holds A then B (should be split once, at the turn); the single-speaker clips
should ideally not be split (a split there is harmless but unnecessary).
Also builds two artificial turn-takings by joining clips with no pause.

Usage: python scripts/test_speaker_change.py
"""
import os
import sys
import wave
import warnings

import numpy as np

warnings.filterwarnings("ignore", message=".*list_audio_backends.*")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from live_translate.speakers import SpeakerLabeler   # noqa: E402

SR = 16000


def load(name):
    with wave.open(f"recordings/clips/{name}.wav") as f:
        return np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768


lab = SpeakerLabeler()
tests = [(n, load(n), "no split") for n in ("video_01", "video_02", "video_03", "video_04", "video_06")]
tests.append(("video_05 (A then B)", load("video_05"), "1 split at the A->B turn"))
tests.append(("A 5s + B 5s joined", np.r_[load("video_01")[:5 * SR], load("video_02")[:5 * SR]],
              "1 split near 5.0s"))
tests.append(("C 4s + A 6s joined", np.r_[load("video_04")[:4 * SR], load("video_03")[:6 * SR]],
              "1 split near 4.0s"))
for name, audio, expect in tests:
    parts = lab.split_on_speaker_change(audio)
    cuts = [f"{off / SR:.2f}s" for off, _ in parts[1:]]
    print(f"{name:22} cuts at: {', '.join(cuts) or '-':18} (expected: {expect})")
