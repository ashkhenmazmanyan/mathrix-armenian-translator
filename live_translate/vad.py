"""Cutting a continuous audio stream into phrases with Silero VAD."""
from collections import deque
from dataclasses import dataclass

import numpy as np
import torch

from .audio import BLOCK, SAMPLE_RATE

BLOCK_SECONDS = BLOCK / SAMPLE_RATE


@dataclass
class Segment:
    source: str          # "mic" or "system"
    audio: np.ndarray    # float32, 16 kHz mono
    start: float         # monotonic time the phrase started
    end: float           # monotonic time the last speech was heard (= end of phrase)
    detected: float      # monotonic time the segmenter decided the phrase was over
    forced: bool         # True if cut because it reached max length


class Segmenter:
    """Feeds blocks through VAD and emits a Segment when a phrase ends.

    A phrase starts when speech probability >= threshold and ends after `min_silence`
    seconds below (threshold - 0.15) -- the gap avoids flickering on/off mid-word.
    Phrases longer than `max_len` are cut so latency stays bounded.
    """

    def __init__(self, source, on_segment, threshold=0.5, min_silence=0.6,
                 max_len=10.0, min_speech=0.4, preroll=0.3, vad=None):
        self.source, self.on_segment = source, on_segment
        self.threshold, self.min_silence = threshold, min_silence
        self.max_len, self.min_speech = max_len, min_speech
        if vad is None:
            from silero_vad import load_silero_vad
            model = load_silero_vad()     # one instance per source: the model keeps state
            vad = lambda block: model(torch.from_numpy(block), SAMPLE_RATE).item()
        self.vad = vad
        self.preroll = deque(maxlen=max(1, int(preroll / BLOCK_SECONDS)))
        self.active = False
        self.blocks, self.start, self.speech_start, self.last_speech = [], 0.0, 0.0, 0.0

    def process(self, block, t_end):
        prob = self.vad(block)
        if not self.active:
            self.preroll.append(block)
            if prob >= self.threshold:
                self.active = True
                self.blocks = list(self.preroll)
                self.start = t_end - BLOCK_SECONDS * len(self.blocks)
                self.speech_start = t_end - BLOCK_SECONDS   # excludes the pre-roll
                self.last_speech = t_end
            return
        self.blocks.append(block)
        if prob >= self.threshold - 0.15:
            self.last_speech = t_end
        too_long = t_end - self.start >= self.max_len
        if t_end - self.last_speech >= self.min_silence or too_long:
            self._emit(t_end, forced=too_long)

    def _emit(self, now, forced):
        if self.last_speech - self.speech_start >= self.min_speech:   # skip clicks/coughs
            end = now if forced else self.last_speech
            self.on_segment(Segment(self.source, np.concatenate(self.blocks),
                                    self.start, end, now, forced))
        self.active = False
        self.blocks = []
        self.preroll.clear()
