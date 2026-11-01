"""Compare local Armenian->English translation models on the test clips.

Each model translates two versions of every clip:
  REF - your reference text (clean Armenian)          -> shows the translator's own quality
  ASR - the large-v3 int8 transcript (with its errors) -> what it will receive live
Reports time per sentence and GPU memory, and writes results/mt_comparison.md
with a 0-2 score field for each ASR translation.

Usage:
    python scripts/compare_mt.py
    python scripts/compare_mt.py --models nllb-600M --beams 1
"""
import argparse
import os
import re
import time

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

MODELS = {
    "opus-mt": "Helsinki-NLP/opus-mt-hy-en",
    "nllb-600M": "facebook/nllb-200-distilled-600M",
    "nllb-1.3B": "facebook/nllb-200-distilled-1.3B",
}
ASR_REPORT = "results/asr_large-v3_int8_float16.md"


def load_inputs():
    """Read reference text and large-v3 transcript for each clip from the ASR report."""
    clips, cur = {}, None
    with open(ASR_REPORT, encoding="utf-8") as f:
        for line in f:
            if line.startswith("## "):
                cur = line[3:].strip()
                clips[cur] = {}
            elif line.startswith("**REF:**") and cur:
                ref = re.sub(r"\[[^\]]*\]:?", "", line[8:])        # drop [A]: speaker tags
                clips[cur]["REF"] = re.sub(r"[․.]{2,}", "", ref).strip()
            elif line.startswith("- **large-v3**") and cur:
                clips[cur]["ASR"] = line.split("): ", 1)[1].strip()
    return clips


parser = argparse.ArgumentParser()
parser.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
parser.add_argument("--beams", type=int, default=4)
args = parser.parse_args()

clips = load_inputs()
print(f"{len(clips)} clips, models: {args.models}, beams: {args.beams}\n")
out = {name: {} for name in clips}   # clip -> (model, kind) -> (english, seconds)
summary = {}

for key in args.models:
    repo = MODELS[key]
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    t = time.perf_counter()
    tok = AutoTokenizer.from_pretrained(repo, src_lang="hye_Armn") if "nllb" in key \
        else AutoTokenizer.from_pretrained(repo)
    model = AutoModelForSeq2SeqLM.from_pretrained(repo, torch_dtype=torch.float16).cuda().eval()
    load_s = time.perf_counter() - t
    gen_kwargs = dict(num_beams=args.beams, max_new_tokens=160)
    if "nllb" in key:
        gen_kwargs["forced_bos_token_id"] = tok.convert_tokens_to_ids("eng_Latn")

    def translate(text):
        batch = tok(text, return_tensors="pt").to("cuda")
        with torch.inference_mode():
            ids = model.generate(**batch, **gen_kwargs)
        return tok.decode(ids[0], skip_special_tokens=True)

    translate("Բարև, ինչպե՞ս ես։")             # warm-up, not timed
    times = []
    for name, c in clips.items():
        for kind in ("REF", "ASR"):
            t = time.perf_counter()
            en = translate(c[kind])
            torch.cuda.synchronize()
            secs = time.perf_counter() - t
            times.append(secs)
            out[name][(key, kind)] = (en, secs)
            print(f"[{key}] {name} {kind}: {secs:.2f}s  {en}")
    summary[key] = dict(load_s=load_s, mem=torch.cuda.max_memory_allocated() / 2**20,
                        mean=sum(times) / len(times), worst=max(times))
    print()
    del model, tok
    torch.cuda.empty_cache()

os.makedirs("results", exist_ok=True)
path = f"results/mt_{'+'.join(args.models)}_beam{args.beams}.md"
with open(path, "w", encoding="utf-8") as f:
    f.write(f"# Translation comparison (float16, beams {args.beams})\n\n"
            "| Model | Load (s) | Peak GPU memory (MB) | Mean time / sentence (s) | Worst (s) |\n"
            "|---|---|---|---|---|\n")
    for k, s in summary.items():
        f.write(f"| {k} | {s['load_s']:.1f} | {s['mem']:.0f} | {s['mean']:.2f} | {s['worst']:.2f} |\n")
    f.write("\nScore each ASR translation: 2 = meaning correct, 1 = gist understandable, "
            "0 = wrong or misleading.\n")
    for name, c in clips.items():
        f.write(f"\n## {name}\n\n**HY (REF):** {c['REF']}\n\n")
        for k in args.models:
            f.write(f"- {k}: {out[name][(k, 'REF')][0]}\n")
        f.write(f"\n**HY (ASR, large-v3):** {c['ASR']}\n\n")
        for k in args.models:
            en, secs = out[name][(k, "ASR")]
            f.write(f"- {k} ({secs:.2f}s): {en}  \n  score: \n")

print("Summary:")
for k, s in summary.items():
    print(f"  {k:10} load {s['load_s']:4.1f}s  peak GPU {s['mem']:6.0f} MB  "
          f"time/sentence mean {s['mean']:.2f}s worst {s['worst']:.2f}s")
print(f"\nReport written to {path}")
