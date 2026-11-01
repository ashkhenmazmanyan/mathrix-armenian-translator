"""Command line: python -m live_translate [options]"""
import argparse
import os
import sys


def parse_args():
    p = argparse.ArgumentParser(
        prog="python -m live_translate",
        description="Live Armenian speech -> English translation in the terminal.")
    p.add_argument("--list-devices", action="store_true", help="list audio sources and exit")
    p.add_argument("--mic", help="microphone: number from --list-devices or part of its name "
                                 "(default: the system default microphone)")
    p.add_argument("--system", help="system-audio (monitor) source: number or part of its name "
                                    "(default: monitor of the default output device)")
    p.add_argument("--no-mic", action="store_true", help="don't capture the microphone")
    p.add_argument("--no-system", action="store_true", help="don't capture system audio")
    p.add_argument("--asr-model", default="large-v3",
                   help="faster-whisper model (default large-v3; large-v3-turbo is ~3x faster, less accurate)")
    p.add_argument("--asr-compute-type", default="int8_float16")
    p.add_argument("--mt-model", default="nllb-600M", choices=["nllb-600M", "nllb-1.3B"])
    p.add_argument("--min-silence", type=float, default=0.6,
                   help="seconds of silence that end a phrase (default 0.6)")
    p.add_argument("--max-segment", type=float, default=8.0,
                   help="longest phrase in seconds before it is cut (default 8; ASR time grows "
                        "with length, 10 s phrases reached 4.0 s latency on one source)")
    p.add_argument("--speaker-threshold", type=float, default=0.30,
                   help="voice similarity needed to count as a known speaker (default 0.30; "
                        "higher = more new speakers, lower = risk of merging people)")
    p.add_argument("--no-speaker-split", action="store_true",
                   help="don't split system-audio phrases where the voice changes")
    p.add_argument("--latency", action="store_true", help="show a latency breakdown under each line")
    p.add_argument("--debug-dir", help="save the raw audio streams and every phrase (WAV + log) "
                                       "here, to check afterwards what was missed")
    p.add_argument("--download-models", action="store_true",
                   help="download the selected models (needs internet) and exit")
    return p.parse_args()


def main():
    args = parse_args()
    # Let PyTorch grow/shrink its GPU memory blocks instead of fragmenting them;
    # GPU memory is tight (6 GB shared with the desktop and the browser running the call).
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    if not args.download_models:
        # Run fully offline: models must already be in the local cache.
        os.environ.setdefault("HF_HUB_OFFLINE", "1")

    if args.list_devices:
        from .devices import print_sources
        print_sources()
        return
    if args.download_models:
        from faster_whisper import download_model
        from huggingface_hub import snapshot_download
        from .translate import MT_MODELS
        print("ASR:", download_model(args.asr_model))
        print("MT: ", snapshot_download(MT_MODELS[args.mt_model]))
        from .speakers import load_encoder, ECAPA_SAVEDIR
        load_encoder("cpu")
        print("Speaker:", ECAPA_SAVEDIR)
        return

    from .pipeline import run
    run(args)
    # Exit immediately: letting the interpreter tear down the native GPU/audio libraries
    # (CTranslate2, PulseAudio) while their threads exist aborted with
    # "terminate called without an active exception" and hung the terminal.
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
