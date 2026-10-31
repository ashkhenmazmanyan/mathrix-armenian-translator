"""Compare Whisper models on the Armenian test clips.

For every clip and model, prints and saves: the transcript, how long the
transcription took, and what share of the letters are Armenian script
(a quick flag for the "switched to English / hallucinated" failure).
Also reports model load time and GPU memory used per model.

Usage:
    python scripts/compare_asr.py
    python scripts/compare_asr.py --models large-v3-turbo --compute-type int8_float16

Results are written to results/asr_<models>_<compute-type>.md
"""
import argparse
import gc
import glob
import os
import subprocess
import time
import wave

import numpy as np
from faster_whisper import WhisperModel

CLIPS_DIR = "recordings/clips"
SR = 16000


def load_wav(path):
    with wave.open(path) as f:
        assert f.getframerate() == SR and f.getnchannels() == 1, path
        raw = f.readframes(f.getnframes())
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def gpu_mem_mb():
    out = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"])
    return int(out.decode().split()[0])


def armenian_share(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum("԰" <= c <= "֏" for c in letters) / len(letters)


def read_references():
    refs = {}
    path = os.path.join(CLIPS_DIR, "references.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or ":" not in line:
                    continue
                name, text = line.split(":", 1)
                refs[name.strip()] = text.strip()
    return refs


parser = argparse.ArgumentParser()
parser.add_argument("--models", nargs="+", default=["large-v3-turbo", "large-v3"])
parser.add_argument("--compute-type", default="float16")
parser.add_argument("--beam-size", type=int, default=5)
args = parser.parse_args()

clips = {os.path.basename(p)[:-4]: load_wav(p)
         for p in sorted(glob.glob(os.path.join(CLIPS_DIR, "*.wav")))}
refs = read_references()
print(f"{len(clips)} clips, models: {args.models}, compute type: {args.compute_type}, "
      f"beam size: {args.beam_size}\n")

texts = {name: {} for name in clips}       # clip -> model -> (text, seconds, hy share)
summary = {}                               # model -> stats

for model_name in args.models:
    base_mem = gpu_mem_mb()
    t = time.perf_counter()
    model = WhisperModel(model_name, device="cuda", compute_type=args.compute_type)
    load_s = time.perf_counter() - t

    # Warm-up run (not timed): the first call is slower while the GPU initialises.
    list(model.transcribe(next(iter(clips.values())), language="hy")[0])

    peak_mem, times = gpu_mem_mb(), []
    for name, audio in clips.items():
        t = time.perf_counter()
        segments, _ = model.transcribe(audio, language="hy", beam_size=args.beam_size,
                                       condition_on_previous_text=False)
        text = " ".join(s.text.strip() for s in segments)   # runs the model
        secs = time.perf_counter() - t
        times.append(secs / (len(audio) / SR))
        peak_mem = max(peak_mem, gpu_mem_mb())
        texts[name][model_name] = (text, secs, armenian_share(text))
        print(f"[{model_name}] {name}: {secs:.2f}s  hy={armenian_share(text):.0%}  {text}")

    summary[model_name] = dict(load_s=load_s, vram=peak_mem - base_mem,
                               rtf_mean=np.mean(times), rtf_max=np.max(times),
                               hy_min=min(v[model_name][2] for v in texts.values()))
    print()
    del model
    gc.collect()

# ---- write a Markdown report ---------------------------------------------
os.makedirs("results", exist_ok=True)
out = f"results/asr_{'+'.join(args.models)}_{args.compute_type}.md"
with open(out, "w", encoding="utf-8") as f:
    f.write(f"# ASR comparison ({args.compute_type}, beam {args.beam_size})\n\n")
    f.write("| Model | Load (s) | GPU memory (MB) | Mean time / audio s | "
            "Worst time / audio s | Min Armenian share |\n|---|---|---|---|---|---|\n")
    for m, s in summary.items():
        f.write(f"| {m} | {s['load_s']:.1f} | {s['vram']} | {s['rtf_mean']:.3f} | "
                f"{s['rtf_max']:.3f} | {s['hy_min']:.0%} |\n")
    f.write("\n'Time / audio s' = processing seconds per second of audio "
            "(0.2 means a 5 s phrase takes 1 s).\n")
    for name, by_model in texts.items():
        f.write(f"\n## {name}\n\n**REF:** {refs.get(name, '(none)')}\n\n")
        for m, (text, secs, hy) in by_model.items():
            f.write(f"- **{m}** ({secs:.2f}s, Armenian {hy:.0%}): {text}\n")

print("Summary:")
for m, s in summary.items():
    print(f"  {m:16} load {s['load_s']:5.1f}s  GPU mem {s['vram']:5d} MB  "
          f"time/audio-s mean {s['rtf_mean']:.3f} worst {s['rtf_max']:.3f}  "
          f"min Armenian share {s['hy_min']:.0%}")
print(f"\nReport written to {out}")
