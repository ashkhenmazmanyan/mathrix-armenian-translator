"""Speaker labels: "Me" for the microphone, "Speaker N" for voices on the system-audio side.

Each system-audio phrase is turned into a voiceprint (SpeechBrain ECAPA embedding, 192
numbers). It is compared (cosine similarity) with the average voiceprint of every speaker
heard so far in this session:
  * similarity >= threshold  -> same speaker; their average is updated
  * otherwise                -> a new speaker, unless the phrase is too short to trust
                                (then it goes to the closest known speaker)
  * if two speakers' averages become very similar (>= merge_threshold), they were the
    same person split early on; they are merged and keep the older number.
Labels therefore stay stable for the session; nothing is remembered afterwards.

Tuning (see scripts/test_speaker_labeling.py and the README):
  * Short phrases give noisy voiceprints (2 s pieces of one person: median 0.52, min 0.22;
    different people up to 0.30), long ones are reliable (10 s: same person 0.69-0.87,
    different <= 0.41). So the threshold grows with phrase length: 0.30 at <= 2 s up to
    0.50 at >= 8 s. A single 0.30 threshold merged two people in a live test: a 10 s
    phrase scoring 0.32 was accepted, which shifted that speaker's average toward the new
    voice and made later phrases match even better.
  * Hence also: a phrase only updates a speaker's average if it matches confidently
    (>= update_min_sim), so one borderline decision cannot drag the average.
  * Phrases under 2 s never create a new speaker.
"""
import os

import numpy as np
import torch

SAMPLE_RATE = 16000
ECAPA_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"
ECAPA_SAVEDIR = os.path.expanduser("~/.cache/live_translate/spkrec-ecapa-voxceleb")


def load_encoder(device="cuda:0"):
    from speechbrain.inference.speaker import EncoderClassifier
    return EncoderClassifier.from_hparams(source=ECAPA_SOURCE, savedir=ECAPA_SAVEDIR,
                                          run_opts={"device": device})


class SpeakerLabeler:
    def __init__(self, threshold=0.30, long_threshold=0.50, long_s=8.0, update_min_sim=0.45,
                 min_new_speaker_s=2.0, merge_threshold=0.55, encoder=None):
        self.threshold = threshold              # for phrases <= 2 s
        self.long_threshold = long_threshold    # for phrases >= long_s
        self.long_s = long_s
        self.update_min_sim = update_min_sim
        self.min_new_speaker_s = min_new_speaker_s
        self.merge_threshold = merge_threshold
        self.encoder = encoder or load_encoder()
        self.sums = []            # per speaker: sum of unit-length voiceprints
        self.ids = []             # per speaker: the number shown ("Speaker <id>")
        self.next_id = 1
        self.last_similarity = None

    def embed(self, audio):
        x = torch.from_numpy(np.ascontiguousarray(audio, dtype=np.float32)).unsqueeze(0)
        with torch.inference_mode():
            e = self.encoder.encode_batch(x.to(self.encoder.device)).squeeze().cpu().numpy()
        return e / (np.linalg.norm(e) + 1e-9)

    def _centroids(self):
        return np.array([s / np.linalg.norm(s) for s in self.sums])

    def _new_speaker(self, e):
        self.sums.append(e.copy())
        self.ids.append(self.next_id)
        self.next_id += 1
        return len(self.sums) - 1

    def _merge_into(self, k):
        """Merge any speaker whose average is now very close to speaker k's."""
        c = self._centroids()
        for j in sorted(range(len(self.sums)), reverse=True):
            if j != k and c[k] @ c[j] >= self.merge_threshold:
                keep, drop = (k, j) if self.ids[k] < self.ids[j] else (j, k)
                self.sums[keep] += self.sums[drop]
                del self.sums[drop], self.ids[drop]
                return self._merge_into(keep - (1 if drop < keep else 0))
        return k

    def threshold_for(self, seconds):
        """Similarity needed to count as a known speaker, rising with phrase length."""
        frac = min(max((seconds - 2.0) / (self.long_s - 2.0), 0.0), 1.0)
        return self.threshold + frac * (self.long_threshold - self.threshold)

    def assign(self, audio):
        """Return the speaker number for a system-audio phrase."""
        seconds = len(audio) / SAMPLE_RATE
        e = self.embed(audio)
        if not self.sums:
            self.last_similarity = None
            return self.ids[self._new_speaker(e)]
        sims = self._centroids() @ e
        best = int(np.argmax(sims))
        self.last_similarity = float(sims[best])
        if sims[best] < self.threshold_for(seconds) and seconds >= self.min_new_speaker_s:
            return self.ids[self._new_speaker(e)]
        # Same speaker (or too short to trust as a new one). Only confident matches
        # update the speaker's average voiceprint.
        if sims[best] >= self.update_min_sim:
            self.sums[best] += e
            if self.merge_threshold is not None:
                best = self._merge_into(best)
        return self.ids[best]

    def split_on_speaker_change(self, audio, win_s=2.0, hop_s=0.25, max_sim=0.15, depth=1):
        """Split a phrase where the voice changes; returns a list of (offset_samples, audio).

        On TV/calls people often take turns without a pause, so one VAD phrase can hold two
        voices. We slide 2 s windows over the phrase and compare the window just before
        each candidate point with the window just after it (so both parts are >= 2 s).
        If the least similar pair is below `max_sim`, the phrase is cut there (at most once
        by default). Tuned conservatively with scripts/test_speaker_change.py: 1.5 s windows
        and max_sim 0.25 cut single-speaker clips and fragmented live TV speech; a missed
        change only costs one mixed line, a false cut costs a broken sentence.
        """
        w, h = int(win_s * SAMPLE_RATE), int(hop_s * SAMPLE_RATE)
        step = w // h                       # windows are a whole number of hops long
        if depth == 0 or len(audio) < 2 * w + h:
            return [(0, audio)]
        starts = list(range(0, len(audio) - w + 1, h))
        windows = np.stack([audio[i:i + w] for i in starts]).astype(np.float32)
        x = torch.from_numpy(windows).to(self.encoder.device)
        with torch.inference_mode():
            e = self.encoder.encode_batch(x).squeeze(1).cpu().numpy()
        e /= np.linalg.norm(e, axis=1, keepdims=True) + 1e-9
        sims = [(float(e[k] @ e[k + step]), starts[k] + w) for k in range(len(starts) - step)]
        sim, cut = min(sims)
        if sim >= max_sim:
            return [(0, audio)]
        left = self.split_on_speaker_change(audio[:cut], win_s, hop_s, max_sim, depth - 1)
        right = self.split_on_speaker_change(audio[cut:], win_s, hop_s, max_sim, depth - 1)
        return left + [(cut + off, a) for off, a in right]

    def label(self, segment):
        if segment.source == "mic":
            return "Me"
        return f"Speaker {self.assign(segment.audio)}"

    def warmup(self):
        self.embed(np.zeros(SAMPLE_RATE, dtype=np.float32))
