"""Do speaker embeddings tell the test-clip speakers apart?

Computes an ECAPA voiceprint (SpeechBrain, 192 numbers) for each clip and prints the
cosine-similarity matrix. Same speaker should score clearly higher than different
speakers; the gap tells us where to put the "same person" threshold.

Speakers (from references.txt): video_01/03 = A, video_02/06 = B, video_04 = C,
video_05 = A+B mixed, me_* = Me.
"""
import glob
import os
import time
import wave

import numpy as np
import torch
from speechbrain.inference.speaker import EncoderClassifier

LABELS = {"video_01": "A", "video_02": "B", "video_03": "A", "video_04": "C",
          "video_05": "A+B", "video_06": "B"}
SAVEDIR = os.path.expanduser("~/.cache/live_translate/spkrec-ecapa-voxceleb")


def load(path):
    with wave.open(path) as f:
        return np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768


model = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",
                                       savedir=SAVEDIR, run_opts={"device": "cuda"})
paths = sorted(glob.glob("recordings/clips/video_*.wav")) + \
        sorted(glob.glob("recordings/clips/me_*.wav"))[:2]
names, embs, times = [], [], []
for p in paths:
    audio = torch.from_numpy(load(p)).unsqueeze(0).cuda()
    t = time.perf_counter()
    with torch.inference_mode():
        e = model.encode_batch(audio).squeeze().cpu().numpy()
    times.append(time.perf_counter() - t)
    names.append(os.path.basename(p)[:-4])
    embs.append(e / np.linalg.norm(e))
sim = np.array(embs) @ np.array(embs).T

lab = [LABELS.get(n, "Me") for n in names]
print(f"embedding time per clip: mean {np.mean(times[1:]):.3f}s (first call {times[0]:.2f}s)\n")
print(" " * 14 + "".join(f"{n[-2:]:>3}{l:<4}" for n, l in zip(names, lab)))
for i, n in enumerate(names):
    print(f"{n:9}{lab[i]:>4} " + "".join(f"{sim[i, j]:7.2f}" for j in range(len(names))))

same, diff = [], []
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        if "+" in lab[i] or "+" in lab[j]:
            continue                      # mixed clip: neither "same" nor "different"
        (same if lab[i] == lab[j] else diff).append((sim[i, j], names[i], names[j]))
print("\nSame speaker pairs:      " + ", ".join(f"{a[-2:]}-{b[-2:]} {s:.2f}" for s, a, b in same))
print(f"Different speaker pairs: min {min(diff)[0]:.2f}  max {max(diff)[0]:.2f}"
      f"  (highest: {max(diff)[1]} vs {max(diff)[2]})")
lo, hi = max(diff)[0], min(same)[0]
print(f"\nLowest same-speaker {hi:.2f} vs highest different-speaker {lo:.2f} -> "
      + (f"separable; a threshold around {(lo + hi) / 2:.2f} splits them" if hi > lo
         else "NOT separable with one threshold"))
