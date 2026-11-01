"""Live Armenian speech -> English translation in the terminal.

Pipeline (one thread per audio source, one GPU worker):

    AudioSource (mic)    -> Segmenter (Silero VAD) --+
                                                     +--> queue --> Worker:
    AudioSource (system) -> Segmenter (Silero VAD) --+               Transcriber (faster-whisper, Armenian)
                                                                     SpeakerLabeler (Me / Speaker N)
                                                                     Translator (NLLB-200, hy -> en)
                                                                     print_segment()
"""
