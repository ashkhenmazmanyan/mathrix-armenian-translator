# Live Armenian → English translation in the terminal

A Python program that listens to a live conversation — your microphone and the other side of a call — transcribes spoken **Armenian**, translates it to **English**, labels who spoke, and prints each phrase in the terminal, typically **1.5–3 s** after the phrase ends. Everything runs **locally** (no cloud APIs).

```
[00:00:29] Me
HY: Միհատ այս խնդիրները լուծենք, հետո արդեն այս չգիտեմ վիսպրի խնդիրները ընթացքում էլի։
EN: Let's solve these problems one at a time, and then I don't know about the problems of whiskey in the long run.

[00:00:59] Speaker 3
HY: ինչի համար շատ ուրախ եմ, ինձ համարում եմ կայացած տվյալ մասնագիտության մեջ։
EN: And I'm really excited about that, because I think I'm in this profession.
```
(Unedited output from a Google Meet test call — including its recognition errors, see §7.)

## Contents
1. [Setup](#1-setup) · 2. [Audio setup](#2-audio-setup-linux--pipewire) · 3. [Running](#3-running) · 4. [Architecture](#4-architecture) · 5. [Model choices](#5-model-choices-and-why) · 6. [How it was tested](#6-how-it-was-tested) · 7. [Known limitations](#7-known-limitations) · 8. [With more time](#8-what-i-would-improve-with-more-time) · 9. [Repository layout](#9-repository-layout)

---

## 1. Setup

**Tested on:** Ubuntu 24.04 (PipeWire audio), Intel i5-13450HX, 16 GB RAM, **NVIDIA RTX 4050 Laptop GPU (6 GB)**, NVIDIA driver 595, Python 3.12.
An NVIDIA GPU is required for the default models (CPU-only would be far too slow for the 5 s budget).

```bash
# NVIDIA driver (if `nvidia-smi` fails). No separate CUDA toolkit is needed:
sudo apt install nvidia-driver-595-open && sudo reboot

git clone <this repo> && cd mathrix-armenian-translator
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# One-time model download (~6 GB, needs internet). Normal runs are fully offline.
python -m live_translate --download-models
```

Pinned on purpose: `torch==2.8.0` / `torchaudio==2.8.0` (torchaudio 2.9 removes audio back-ends that SpeechBrain still calls — the deprecation warning is visible with 2.8) and `transformers<5`.

## 2. Audio setup (Linux / PipeWire)

The program needs two inputs: **your microphone** ("Me") and **the call audio** (everyone else).

* **Call audio:** PipeWire automatically offers a *"Monitor of &lt;output device&gt;"* source — an exact copy of what the laptop plays. You still hear the call normally. This is the Linux equivalent of BlackHole + Multi-Output Device on macOS; nothing needs installing.
* **Use headphones.** Without them the microphone also picks up the call from the speakers and it gets transcribed twice (once as "Me"). Echo handling is out of scope.
* **Bluetooth headphones:** fine for *listening*, but **don't use the headset's microphone** — neither in the call app nor in this program. Recording from it switches the headset into its "call" profile: in a test the mic stream lost everything above 4 kHz (telephone quality) and recognition collapsed. The program automatically avoids a Bluetooth mic as default and says so; use the laptop's built-in mic.
* **Call app (tested with Google Meet in Chrome):** microphone = built-in mic, speaker = your headphones. **Turn off Chrome's graphics acceleration** (Settings → System) — on a 6 GB GPU the browser's video call and the three models otherwise compete for GPU memory.
* **Mic level:** on the test laptop the built-in mic clipped at 80 % input volume; **30 %** gave clean speech (peak ≈ −8 dBFS). Check with `python scripts/test_mic_level.py`, set with `wpctl set-volume @DEFAULT_AUDIO_SOURCE@ 0.3`.

List and choose devices:
```bash
python -m live_translate --list-devices
python -m live_translate --mic "Built-in" --system "Monitor of P9"   # number or part of the name
```
By default the mic is the system default mic (non-Bluetooth preferred) and the call side is the monitor of the current default output.

## 3. Running

```bash
python -m live_translate              # mic + call audio
python -m live_translate --latency    # also show a latency breakdown under every line
```
Stop with **Ctrl+C**; a summary (lines, mean/max latency) is printed.

| Option | Default | Purpose |
|---|---|---|
| `--mic`, `--system` | defaults (see above) | choose devices |
| `--no-mic`, `--no-system` | | capture only one side |
| `--asr-model` | `large-v3` | `large-v3-turbo` is ~3× faster, less accurate (fallback if latency gets tight) |
| `--mt-model` | `nllb-600M` | `nllb-1.3B`: slightly better, needs ~1.5 GB more GPU memory |
| `--speaker-threshold` | `0.30` | voice match needed for short phrases (rises to 0.50 for long ones) |
| `--no-speaker-split` | | don't split a phrase where the voice changes |
| `--min-silence` | `0.6` s | pause that ends a phrase |
| `--max-segment` | `8` s | longest phrase before it is cut |
| `--debug-dir DIR` | | save both raw streams + every phrase (WAV) and a log, to inspect what was missed |

## 4. Architecture

```
 AudioSource "mic"    ─► Segmenter (Silero VAD) ─┐
 AudioSource "system" ─► Segmenter (Silero VAD) ─┴─► queue ─► Worker (one GPU thread):
   (soundcard, 16 kHz mono,     phrase = speech until                1. [system] split at voice change
    32 ms blocks, 1 thread       0.6 s silence, max 8 s               2. Transcriber  faster-whisper large-v3 int8, language=hy
    per source)                                                       3. SpeakerLabeler  Me / Speaker N (ECAPA voiceprints)
                                                                      4. Translator   NLLB-200 600M, hy→en
                                                                      5. print [time] speaker / HY / EN
```

| Module | Responsibility |
|---|---|
| `devices.py` | list sources, find the monitor of the default output **by id** (mic and speakers can share a name), avoid Bluetooth mics |
| `audio.py` | capture thread per source; discards the first 0.5 s (the mic produced a start-up "pop") |
| `vad.py` | Silero VAD per source → `Segment`s; hysteresis (speech ≥ 0.5, continue ≥ 0.35), 0.3 s pre-roll, drops blips < 0.4 s |
| `asr.py` | Armenian transcription, no-speech filter, removal of Whisper's repetition loops, filter for noise hallucinations / filler sounds |
| `speakers.py` | voiceprints, online clustering, voice-change split |
| `translate.py` | NLLB, sentence-by-sentence, repetition guard |
| `pipeline.py` | threads, queue, error handling (a failing phrase is skipped, never stops the session), latency measurement |

**Design choices:** one GPU worker processes phrases oldest-first (both models share one GPU; parallel runs would only slow each other). Latency is measured from the moment the last speech of a phrase was heard to the moment its line is printed. Runs are offline (`HF_HUB_OFFLINE=1`), which also demonstrates the local-only requirement.

## 5. Model choices and why

All candidates were compared on **the same 11 Armenian test clips** (5 of my own voice via the mic, 6 from an Armenian TV interview via system audio, 195 scored words), with reference transcripts I wrote. Raw results are in `results/`.

### Speech recognition: **Whisper large-v3 (faster-whisper, int8)**

| Model | Word errors (manual count) | Time per audio second | GPU memory |
|---|---|---|---|
| large-v3-turbo, float16 | 78 / 195 = **40.0 %** | 0.09 | 2.2 GB |
| large-v3, float16 | ≈ int8 (near-identical text) | 0.30 | 3.8 GB |
| **large-v3, int8** | 66 / 195 = **33.8 %** | 0.25 (worst 0.33) | **2.0 GB** |

* Decision rule fixed *before* counting: large-v3 only if ≥ 10 fewer errors than turbo. It had 12 fewer → large-v3; turbo stays available via `--asr-model`. The margin is small; the clearest gain is **numbers** (`2026`, `12 500`, `25`), which turbo garbled.
* int8 cost no measurable accuracy and halved memory — essential on a 6 GB GPU.
* `tiny` (sanity check) produced fluent but **entirely invented English** from Armenian speech — an early warning that hallucination must be checked.
* Considered, not tested (time): **Meta MMS** (CTC, no punctuation/casing), **SeamlessM4T v2** (heavy for 6 GB, non-commercial licence), community **Armenian fine-tunes of Whisper** (most promising next step, see §8).
* Whisper runs through **faster-whisper/CTranslate2**: ~4× faster and lighter than the reference implementation.

### Translation: **NLLB-200 distilled 600M**

Each model translated the reference text *and* the large-v3 transcript (with its errors) — the second is what it receives live. Scored 0/1/2 per clip on the ASR input (max 22):

| Model | Score | GPU memory | Time per sentence |
|---|---|---|---|
| Opus-MT hy→en | 7 | 0.2 GB | 0.10 s |
| **NLLB-200 600M** | **10** | **1.2 GB** | 0.24 s |
| NLLB-200 1.3B | 12 | 2.7 GB | 0.42 s |

* Rule: within ~2 points → smaller model. 1.3B would leave almost no GPU memory next to large-v3 and a browser call.
* **Key finding: translation is not the bottleneck — recognition is.** NLLB translates the clean reference text mostly correctly; on the ASR text quality halves, because errors pass straight through (`Երեկ`→`Երեք`: "yesterday" → "three of us"; `օգտվել կանաչ` ("use green") → "get drunk… cannabis").
* **Local LLMs** (e.g. via Ollama) were considered: a 7–8B model needs ~4–5 GB GPU memory even quantised (doesn't fit next to Whisper), generates slower, and small open models are weak in Armenian. Their real advantage — repairing ASR errors from context — is listed in §8. Cloud LLMs/APIs are excluded by the brief.

### Phrase detection: **Silero VAD**
Small neural VAD (~1 ms per 32 ms block on CPU), far more robust to noise than energy-based detection; installed as a pip package, no download.

### Speaker labels: **SpeechBrain ECAPA-TDNN voiceprints + online clustering**
* ECAPA turns a phrase into a 192-number voiceprint trained to identify speakers (not words), so it works for Armenian. ~13 ms per phrase. Openly downloadable (pyannote's models are gated behind a token and its pipeline is built for whole recordings, not live streams).
* "Me" = everything from the mic. On the call side each phrase is compared (cosine similarity) with each known speaker's average voiceprint → same speaker or new "Speaker N".

## 6. How it was tested

Each component was measured before it was built into the program (scripts in `scripts/`, results in `results/`):

| What | How | Result |
|---|---|---|
| Audio capture | `test_mic_level.py`, `test_dual_capture.py` | both sources recorded in parallel, separated with headphones; found mic clipping at 80 % and a start-up pop |
| ASR / MT | `compare_asr.py`, `compare_mt.py` + manual scoring | tables above |
| Speaker voiceprints | `test_speaker_embeddings.py` | 10 s clips: same person 0.69–0.86, different ≤ 0.41 → separable |
| Labelling on short phrases | `test_speaker_labeling.py` (clips cut into 1.5–3 s turns) | 2 s pieces: same person median 0.52 (min 0.22), different max 0.30 → no single threshold is perfect for short phrases |
| Voice-change split | `test_speaker_change.py` | first version (1.5 s windows, 0.25) cut single-speaker clips → made conservative (2 s, 0.15, max 1 cut) |

**Live tests and what they changed:**

| Live test | What happened | Change |
|---|---|---|
| Mic only, read text | latency mean 2.1–3.1 s, max 3.6 s; NLLB silently dropped a 2nd sentence | translate sentence by sentence |
| TV talk show (3 people, cross-talk, music) — stress test | 5 labels for 3 people, phrases over-split | conservative splitting; documented as limitation |
| Podcast (3 people) | **two people merged**: a 10 s phrase matching at 0.32 was accepted, which pulled the average voiceprint toward the new voice | threshold now **rises with phrase length** (0.30 at ≤ 2 s → 0.50 at ≥ 8 s); only confident matches (≥ 0.45) update a voiceprint → rerun: 3 people correct |
| Podcast | NLLB looped ("when you're with them" ×26) | `no_repeat_ngram_size=4` + output length cap |
| Google Meet call, 2 remote people (held-out, settings frozen) | speakers labelled correctly; my own voice missing (run used `--no-mic`) | — |
| Meet call, both sources | my lines garbled: program had picked the **Bluetooth headset mic** → telephone quality (energy > 4 kHz: 0.03 % vs 1.86 % on the built-in mic) | avoid Bluetooth mics by default |
| Meet call, both sources | latency mean 1.7 s, max 2.7 s; after ~2 min **CUDA out of memory** (browser call on the same GPU) killed the worker silently | skip failing phrase instead of dying, free cached GPU memory after each phrase, watchdog, report free GPU memory at start |
| Meet call, both sources, **6 min 51 s** (2 remote people; Chrome acceleration off, 1.7 GB GPU memory free after loading) | 86 lines, **no crash, no skipped phrase**; latency mean 2.2 s, max 4.1 s; the two remote people mostly kept their labels, but short noises (1.2–2.0 s: laughter, breath) came out as "… այդ այդ այդ" and created extra labels (Speaker 3, 4); "մհմ" was translated as "Oh, my God" | filter for noise hallucinations and filler sounds, applied *before* speaker labelling, so they can no longer create speakers |

**Latency (end of phrase → line printed):** in every live run no line exceeded 5 s (over ~200 lines); worst observed 4.1 s, typical 1.5–3 s. Longest phrases (8 s) and a queue behind the other speaker are what push it up.

**Silence:** a deliberate test with **37 s of silence** on both sources produced **no output**; in the 7-minute call the quiet stretches produced none either. Laughter right after it was transcribed as "Հախախախախախախախ" and "translated" — now filtered.

**Overfitting note:** thresholds were tuned on my clips and one podcast; the Meet calls were run with settings frozen. Tested so far with at most 3 call-side speakers, Eastern Armenian only.

## 7. Known limitations

* **Recognition accuracy is the main limitation (~34 % word errors on my test set).** Most errors keep the *sound* of the word but confuse similar consonants (`Քայլեցինք`→`Կայլեցինք`, `Բնակավայր`→`Վնակավայր`), possibly because Whisper's training data mixes Eastern and Western Armenian pronunciation. Errors then propagate into the English.
* **Overlapping speech / turns without a pause:** a phrase gets one label; the voice-change split catches clear changes only, so a few words at a turn may carry the wrong label.
* **Short phrases** (< 2 s, e.g. "Այո", "մհմ") never create a new speaker; they go to the closest known one, which can be wrong.
* **Listening noises and laughter:** "մհմ"/"մհում", laughter ("Հախախախ…") and repeated-word hallucinations ("այդ այդ այդ") are filtered, but other short sounds ("համ", "հայ") can still turn into nonsense ("That's right", "Oh, my God"). The filter is a text heuristic and could in rare cases drop a real repeated word ("չէ չէ չէ").
* **Speaker numbering:** if one person was split early, the two labels are merged later and keep the older number; lines already printed keep the old label, and numbers can have gaps.
* **Idioms and ambiguity:** `փորում թիթեռնիկներ` (butterflies in the stomach) → "butterflies digging" with every model.
* **GPU memory:** 6 GB is tight with a browser video call; a phrase may be skipped (shown) under memory pressure.
* **Requires headphones and a non-Bluetooth mic** (see §2). Tested on one Linux laptop only.
* Not tested: > 3 call-side speakers, noisy environments, Western Armenian, very long sessions.

## 8. What I would improve with more time

1. **Better Armenian ASR:** evaluate Armenian fine-tuned Whisper models and fine-tune on Common Voice / FLEURS Armenian; build a proper WER test set instead of 11 clips.
2. **ASR error correction from context** with a small LLM on a machine with more GPU memory (would fix "three of us" → "yesterday").
3. **Show partial text while someone is still speaking** (streaming), then finalise.
4. **Overlap-aware diarization** (e.g. pyannote) and label correction once more speech has been heard.
5. Filter pure backchannel sounds; convert NLLB to CTranslate2 int8 to free GPU memory; automated tests for the segmenter and labeller.

## 9. Repository layout

```
live_translate/   the program (python -m live_translate)
scripts/          measurement scripts used for every decision above
results/          comparison reports and manual scoring (text only)
chats/            complete AI chat transcripts (one .md per session)
requirements.txt
```
No model weights, audio recordings or keys are committed (`.gitignore`). Recordings used for testing stay local in `recordings/`.

## AI assistance

Built with Claude (Cowork) as required; the full, unedited conversations are in `chats/`.
