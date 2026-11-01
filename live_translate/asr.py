"""Armenian speech recognition with faster-whisper."""
import re

import numpy as np
from faster_whisper import WhisperModel


class Transcriber:
    def __init__(self, model="large-v3", compute_type="int8_float16", beam_size=5):
        self.model = WhisperModel(model, device="cuda", compute_type=compute_type)
        self.beam_size = beam_size
        self.last_removed = ""     # text dropped by the no-speech filter (for --debug-dir)

    def transcribe(self, audio):
        segments, _ = self.model.transcribe(
            audio, language="hy", beam_size=self.beam_size,
            condition_on_previous_text=False,   # don't let one bad phrase poison the next
            without_timestamps=True)
        # Drop parts Whisper itself considers non-speech (a common source of hallucinations).
        segments = list(segments)
        kept = [s for s in segments if not (s.no_speech_prob > 0.6 and s.avg_logprob < -1.0)]
        self.last_removed = " ".join(s.text.strip() for s in segments if s not in kept).strip()
        return remove_repeats(" ".join(s.text.strip() for s in kept).strip())

    def warmup(self):
        self.transcribe(np.zeros(16000, dtype=np.float32))


def has_armenian(text):
    return any("԰" <= c <= "֏" for c in text)


def remove_repeats(text):
    """Drop a sentence that repeats the previous one: Whisper sometimes loops on music or
    noise ("Հատ ուղոխել եմ։ Հատ ուղոխել եմ։ Հատ ուղոխել եմ։")."""
    out = []
    for sentence in re.split(r"(?<=[։:.!?])\s+", text):
        key = re.sub(r"[^\w]", "", sentence.lower())
        if sentence and (not out or key != re.sub(r"[^\w]", "", out[-1].lower())):
            out.append(sentence)
    return " ".join(out)


FILLER = re.compile(r"^(մ+հ?[ու]*մ+|հ?ըմ+)$")   # "մհմ", "մհում", "մմ", "ըմ": listening noises


def looks_like_noise(text):
    """True for text Whisper produces from non-speech or listening noises.

    Seen in a 7-minute call: short phrases (1.2-2.0 s) of laughter/breath came out as
    "Մենք այդ այդ այդ այդ", "Հայսպես այդ այդ այդ այդ այդ", "Հում հում", laughter as
    "Հախախախախախախախ", and "մհմ"/"մհում"
    was translated as "Oh, my God" / "It's a mystery". These lines are dropped (and, because
    this happens before speaker labelling, they can no longer create fake speakers).
    Real short answers like "Այո" or "Հա" are kept.
    """
    words = [re.sub(r"[^\w]", "", w.lower()) for w in text.split()]
    words = [w for w in words if w]
    if not words:
        return True
    if len(words) == 1 and FILLER.match(words[0]):
        return True
    # laughter: one or two "words" made of a repeated syllable ("Հախախախախախախախ")
    if len(words) <= 2 and any(re.search(r"(..)\1\1", w) for w in words):
        return True
    run = longest = 1
    for a, b in zip(words, words[1:]):
        run = run + 1 if a == b else 1
        longest = max(longest, run)
    return len(words) <= 6 and (longest >= 3 or (len(words) <= 3 and longest >= 2))
