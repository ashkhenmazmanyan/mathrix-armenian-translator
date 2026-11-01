"""Speaker labels.

Microphone audio is always "Me". On the system-audio side, different voices must get
"Speaker 1", "Speaker 2", ... consistently for the whole session (Stage 6).
For now every system-audio segment is "Speaker 1".
"""


class SpeakerLabeler:
    def label(self, segment):
        return "Me" if segment.source == "mic" else "Speaker 1"
