"""Audio capture: one thread per source, delivering 16 kHz mono blocks."""
import threading
import time

import numpy as np

SAMPLE_RATE = 16000
BLOCK = 512            # 32 ms; the block size Silero VAD expects at 16 kHz
WARMUP_SECONDS = 0.5   # discarded at start: the mic produces a "pop" when it wakes up


class AudioSource(threading.Thread):
    """Records from one soundcard device and calls on_block(samples, t_end) for every block.

    t_end is time.monotonic() when the block arrived, i.e. (approximately) when its last
    sample was spoken.
    """

    def __init__(self, name, device, on_block, stop_event):
        super().__init__(name=f"audio-{name}", daemon=True)
        self.device, self.on_block, self.stop_event = device, on_block, stop_event
        self.error = None

    def run(self):
        try:
            with self.device.recorder(samplerate=SAMPLE_RATE, channels=1, blocksize=BLOCK) as rec:
                rec.record(numframes=int(SAMPLE_RATE * WARMUP_SECONDS))
                while not self.stop_event.is_set():
                    block = rec.record(numframes=BLOCK)[:, 0].astype(np.float32)
                    self.on_block(block, time.monotonic())
        except Exception as e:          # report instead of dying silently
            self.error = e
            self.stop_event.set()
