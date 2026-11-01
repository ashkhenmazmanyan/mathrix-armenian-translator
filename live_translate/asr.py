"""Armenian speech recognition with faster-whisper."""
import numpy as np
from faster_whisper import WhisperModel


class Transcriber:
    def __init__(self, model="large-v3", compute_type="int8_float16", beam_size=5):
        self.model = WhisperModel(model, device="cuda", compute_type=compute_type)
        self.beam_size = beam_size

    def transcribe(self, audio):
        segments, _ = self.model.transcribe(
            audio, language="hy", beam_size=self.beam_size,
            condition_on_previous_text=False,   # don't let one bad phrase poison the next
            without_timestamps=True)
        # Drop parts Whisper itself considers non-speech (a common source of hallucinations).
        kept = [s for s in segments if not (s.no_speech_prob > 0.6 and s.avg_logprob < -1.0)]
        return " ".join(s.text.strip() for s in kept).strip()

    def warmup(self):
        self.transcribe(np.zeros(16000, dtype=np.float32))


def has_armenian(text):
    return any("԰" <= c <= "֏" for c in text)
