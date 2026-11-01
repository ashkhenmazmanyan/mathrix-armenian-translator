"""Wiring: audio threads -> segment queue -> one GPU worker -> terminal."""
import queue
import threading
import time

import numpy as np
import torch

from . import devices
from .asr import Transcriber, has_armenian
from .audio import AudioSource
from .output import print_segment
from .speakers import SpeakerLabeler
from .translate import Translator
from .vad import Segmenter


class Worker(threading.Thread):
    """Processes segments one at a time (the GPU is shared), oldest first."""

    def __init__(self, segments, asr, mt, speakers, session_start, stop, show_latency):
        super().__init__(name="worker", daemon=True)
        self.segments, self.asr, self.mt, self.speakers = segments, asr, mt, speakers
        self.session_start, self.stop, self.show_latency = session_start, stop, show_latency
        self.latencies, self.dropped = [], 0

    def run(self):
        while not self.stop.is_set():
            try:
                seg = self.segments.get(timeout=0.2)
            except queue.Empty:
                continue
            t0 = time.monotonic()
            hy = self.asr.transcribe(seg.audio)
            t1 = time.monotonic()
            if not hy or not has_armenian(hy):
                self.dropped += 1
                if self.show_latency:
                    print(f"    (dropped {seg.source} segment: {hy!r})\n", flush=True)
                continue
            speaker = self.speakers.label(seg)
            en = self.mt.translate(hy)
            t2 = time.monotonic()
            latency = t2 - seg.end
            self.latencies.append(latency)
            detail = None
            if self.show_latency:
                detail = (f"latency {latency:.1f}s = silence wait {seg.detected - seg.end:.1f}"
                          f" + queue {t0 - seg.detected:.1f} + asr {t1 - t0:.1f}"
                          f" + speaker/mt {t2 - t1:.1f}; audio {len(seg.audio) / 16000:.1f}s"
                          + ("; cut at max length" if seg.forced else ""))
            print_segment(seg.start - self.session_start, speaker, hy, en, detail)


def run(args):
    torch.set_num_threads(2)   # VAD runs on CPU; keep it from competing with audio threads
    sources = []
    if not args.no_mic:
        sources.append(("mic", devices.resolve(args.mic, loopback=False)))
    if not args.no_system:
        sources.append(("system", devices.resolve(args.system, loopback=True)))
    if not sources:
        raise SystemExit("Nothing to listen to (both --no-mic and --no-system given).")

    print(f"Loading models: ASR {args.asr_model} ({args.asr_compute_type}), MT {args.mt_model} ...",
          flush=True)
    asr = Transcriber(args.asr_model, args.asr_compute_type)
    mt = Translator(args.mt_model)
    asr.warmup()
    mt.warmup()

    stop = threading.Event()
    segments = queue.Queue()
    session_start = time.monotonic()
    worker = Worker(segments, asr, mt, SpeakerLabeler(), session_start, stop, args.latency)
    worker.start()

    threads = []
    for name, device in sources:
        seg = Segmenter(name, segments.put, min_silence=args.min_silence, max_len=args.max_segment)
        t = AudioSource(name, device, seg.process, stop)
        t.start()
        threads.append(t)
        print(f"Listening: {'Me' if name == 'mic' else 'call side'} <- {device.name}")
    print("Speak Armenian. Press Ctrl+C to stop.\n", flush=True)

    try:
        while not stop.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    stop.set()
    print("\nStopping...", flush=True)
    # Let the audio threads close their streams and the worker finish its current phrase.
    for t in threads:
        t.join(timeout=2.0)
    worker.join(timeout=10.0)
    for t in threads:
        if t.error:
            print(f"Audio error in {t.name}: {t.error}")
    lat = np.array(worker.latencies)
    if len(lat):
        print(f"\nSession: {len(lat)} lines, latency mean {lat.mean():.1f}s, "
              f"max {lat.max():.1f}s, over 5 s: {(lat > 5).sum()}; dropped segments: {worker.dropped}")
