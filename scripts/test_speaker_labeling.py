"""Simulate a conversation from the test clips and run the real SpeakerLabeler on it.

The single-speaker video clips (A: 01, 03 / B: 02, 06 / C: 04) are cut into short pieces
and interleaved round-robin as if people were taking turns.

Metrics (truth: 3 people):
  speakers   - labels created (ideal 3; more = one person split into several labels)
  mixed      - labels that contain more than one real person (ideal 0; worst failure)
  consistent - pieces carrying their person's main label (penalises splitting)

Also prints how similar 2-second pieces of the same / different people are, which is
where a threshold for short phrases has to sit.

Usage: python scripts/test_speaker_labeling.py
"""
import os
import sys
import wave
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from live_translate.speakers import SpeakerLabeler, load_encoder   # noqa: E402

SR = 16000
CLIPS = {"video_01": "A", "video_03": "A", "video_02": "B", "video_06": "B", "video_04": "C"}


def load(name):
    with wave.open(f"recordings/clips/{name}.wav") as f:
        return np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768


def conversation(piece_s):
    n = int(piece_s * SR)
    queues = {c: [load(c)[i:i + n] for i in range(0, 10 * SR - n + 1, n)] for c in CLIPS}
    turns = []
    while any(queues.values()):
        for c in ["video_01", "video_02", "video_04", "video_03", "video_06"]:
            if queues[c]:
                turns.append((CLIPS[c], queues[c].pop(0)))
    return turns


encoder = load_encoder()

# 1) How similar are 2 s pieces of the same / different people?
probe = SpeakerLabeler(encoder=encoder)
turns = conversation(2.0)
embs = np.array([probe.embed(a) for _, a in turns])
who = [t for t, _ in turns]
sim = embs @ embs.T
same = [sim[i, j] for i in range(len(who)) for j in range(i + 1, len(who)) if who[i] == who[j]]
diff = [sim[i, j] for i in range(len(who)) for j in range(i + 1, len(who)) if who[i] != who[j]]
print("2 s pieces, pairwise similarity:")
print(f"  same person:      min {min(same):.2f}  10% {np.percentile(same, 10):.2f}  median {np.median(same):.2f}")
print(f"  different people: median {np.median(diff):.2f}  90% {np.percentile(diff, 90):.2f}  max {max(diff):.2f}\n")

# 2) Run the labeler on simulated conversations
print(f"{'piece':>5} {'thr':>5} {'merge':>5} {'speakers':>8} {'mixed':>5} {'consistent':>10}   truth+label sequence")
for piece in (1.5, 2.0, 3.0):
    turns = conversation(piece)
    truth = [t for t, _ in turns]
    for th in (0.25, 0.30, 0.35, 0.40):
        for merge in (None, 0.55):
            lab = SpeakerLabeler(threshold=th, merge_threshold=merge, encoder=encoder)
            pred = [lab.assign(a) for _, a in turns]
            mixed = sum(len({t for t, q in zip(truth, pred) if q == p}) > 1 for p in set(pred))
            main = {s: Counter(q for t, q in zip(truth, pred) if t == s).most_common(1)[0][0]
                    for s in set(truth)}
            consistent = sum(main[t] == q for t, q in zip(truth, pred))
            seq = " ".join(f"{t}{q}" for t, q in zip(truth, pred))
            print(f"{piece:4.1f}s {th:5.2f} {str(merge):>5} {len(set(pred)):8d} {mixed:5d} "
                  f"{consistent:5d}/{len(turns):<4}   {seq}")
    print()
print("'A1 B2 C3 A1' = true speaker A shown as Speaker 1, B as Speaker 2, ...")
