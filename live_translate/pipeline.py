"""Wiring: audio threads -> segment queue -> one GPU worker -> terminal."""
import os
import queue
import threading
import time
import warnings
import wave

import numpy as np
import torch

from . import devices
from .asr import Transcriber, has_armenian, looks_like_noise
from .audio import AudioSource
from .output import print_segment
from .speakers import SpeakerLabeler
from .translate import Translator
from .vad import Segmenter


class Worker(threading.Thread):
    """Processes segments one at a time (the GPU is shared), oldest first."""

    def __init__(self, segments, asr, mt, speakers, session_start, stop, show_latency,
                 split_speakers=True, debug_dir=None):
        super().__init__(name="worker", daemon=True)
        self.debug_dir, self.count = debug_dir, 0
        self.split_speakers = split_speakers
        self.segments, self.asr, self.mt, self.speakers = segments, asr, mt, speakers
        self.session_start, self.stop, self.show_latency = session_start, stop, show_latency
        self.latencies, self.dropped = [], 0

    def run(self):
        while not self.stop.is_set():
            try:
                seg = self.segments.get(timeout=0.2)
            except queue.Empty:
                continue
            if seg.source == "system" and self.split_speakers:
                parts = self.speakers.split_on_speaker_change(seg.audio)
            else:
                parts = [(0, seg.audio)]
            for offset, audio in parts:
                self.handle_safely(seg, offset, audio, split=len(parts) > 1)

    def handle_safely(self, seg, offset, audio, split):
        """One failing phrase must never stop the session (a CUDA out-of-memory error
        while a Google Meet call was using the GPU killed the worker in a test)."""
        for attempt in (1, 2):
            try:
                self.handle(seg, offset, audio, split)
                break
            except Exception as e:                      # noqa: BLE001
                oom = "out of memory" in str(e).lower()
                torch.cuda.empty_cache()
                if oom and attempt == 1:
                    continue                            # retry once after freeing cached memory
                self.dropped += 1
                print(f"    (skipped a {seg.source} phrase: {type(e).__name__}: {e})\n", flush=True)
                break
        # Return memory cached by PyTorch (translation, speaker model) so the Whisper
        # engine, which has its own allocator, can use it.
        torch.cuda.empty_cache()

    def handle(self, seg, offset, audio, split):
        t0 = time.monotonic()
        hy = self.asr.transcribe(audio)
        t1 = time.monotonic()
        self.count += 1
        t_rel = seg.start + offset / 16000 - self.session_start
        if self.debug_dir:
            write_wav(os.path.join(self.debug_dir, f"{self.count:03d}_{seg.source}_{int(t_rel):04d}s.wav"), audio)
            with open(os.path.join(self.debug_dir, "log.txt"), "a", encoding="utf-8") as f:
                f.write(f"{self.count:03d} {seg.source} t={t_rel:.1f}s audio={len(audio)/16000:.1f}s "
                        f"HY={hy!r} removed_by_filter={self.asr.last_removed!r}\n")
        if not hy or not has_armenian(hy) or looks_like_noise(hy):
            self.dropped += 1
            if self.show_latency:
                print(f"    (dropped {seg.source} segment: {hy!r})\n", flush=True)
            return
        if seg.source == "mic":
            speaker, sim = "Me", None
        else:
            speaker = f"Speaker {self.speakers.assign(audio)}"
            sim = self.speakers.last_similarity
        en = self.mt.translate(hy)
        t2 = time.monotonic()
        latency = t2 - seg.end
        self.latencies.append(latency)
        detail = None
        if self.show_latency:
            detail = (f"latency {latency:.1f}s = silence wait {seg.detected - seg.end:.1f}"
                      f" + queue {t0 - seg.detected:.1f} + asr {t1 - t0:.1f}"
                      f" + speaker/mt {t2 - t1:.1f}; audio {len(audio) / 16000:.1f}s"
                      + ("; cut at max length" if seg.forced else "")
                      + ("; split on voice change" if split else "")
                      + (f"; voice match {sim:.2f}" if sim is not None else "")
                      + (f"; filter removed: {self.asr.last_removed!r}" if self.asr.last_removed else ""))
        print_segment(t_rel, speaker, hy, en, detail)


def write_wav(path, audio):
    with wave.open(path, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
        f.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())


def run(args):
    torch.set_num_threads(2)   # VAD runs on CPU; keep it from competing with audio threads
    warnings.filterwarnings("ignore", message=".*list_audio_backends.*")   # SpeechBrain/torchaudio notice
    sources = []
    if not args.no_mic:
        sources.append(("mic", devices.resolve(args.mic, loopback=False)))
    if not args.no_system:
        sources.append(("system", devices.resolve(args.system, loopback=True)))
    if not sources:
        raise SystemExit("Nothing to listen to (both --no-mic and --no-system given).")

    print(f"Loading models: ASR {args.asr_model} ({args.asr_compute_type}), MT {args.mt_model}, "
          f"speaker ECAPA (threshold {args.speaker_threshold}) ...",
          flush=True)
    asr = Transcriber(args.asr_model, args.asr_compute_type)
    mt = Translator(args.mt_model)
    speakers = SpeakerLabeler(threshold=args.speaker_threshold)
    asr.warmup()
    mt.warmup()
    speakers.warmup()
    torch.cuda.empty_cache()
    free, total = torch.cuda.mem_get_info()
    print(f"GPU memory free after loading: {free / 2**30:.1f} of {total / 2**30:.1f} GB", flush=True)
    if free < 1.0 * 2**30:
        print("Warning: little GPU memory left. Close GPU-heavy apps or disable hardware "
              "acceleration in the browser used for the call.", flush=True)

    stop = threading.Event()
    segments = queue.Queue()
    session_start = time.monotonic()
    if args.debug_dir:
        os.makedirs(args.debug_dir, exist_ok=True)
    worker = Worker(segments, asr, mt, speakers, session_start, stop, args.latency,
                    split_speakers=not args.no_speaker_split, debug_dir=args.debug_dir)
    worker.start()

    threads, raw_files = [], []
    for name, device in sources:
        seg = Segmenter(name, segments.put, min_silence=args.min_silence, max_len=args.max_segment)
        on_block = seg.process
        if args.debug_dir:      # also keep the whole stream, to compare with what was printed
            raw = wave.open(os.path.join(args.debug_dir, f"stream_{name}.wav"), "wb")
            raw.setnchannels(1); raw.setsampwidth(2); raw.setframerate(16000)
            raw_files.append(raw)

            def on_block(block, t, seg=seg, raw=raw):
                raw.writeframes((np.clip(block, -1, 1) * 32767).astype(np.int16).tobytes())
                seg.process(block, t)
        t = AudioSource(name, device, on_block, stop)
        t.start()
        threads.append(t)
        print(f"Listening: {'Me' if name == 'mic' else 'call side'} <- {device.name}")
    print("Speak Armenian. Press Ctrl+C to stop.\n", flush=True)

    try:
        while not stop.is_set():
            time.sleep(0.5)
            if not worker.is_alive():
                print("Error: the processing thread stopped unexpectedly.", flush=True)
                break
    except KeyboardInterrupt:
        pass
    stop.set()
    print("\nStopping...", flush=True)
    # Let the audio threads close their streams and the worker finish its current phrase.
    for t in threads:
        t.join(timeout=2.0)
    worker.join(timeout=10.0)
    for raw in raw_files:
        raw.close()
    for t in threads:
        if t.error:
            print(f"Audio error in {t.name}: {t.error}")
    lat = np.array(worker.latencies)
    if len(lat):
        print(f"\nSession: {len(lat)} lines, latency mean {lat.mean():.1f}s, "
              f"max {lat.max():.1f}s, over 5 s: {(lat > 5).sum()}; dropped segments: {worker.dropped}")
