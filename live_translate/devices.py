"""Finding the microphone and the system-audio monitor source."""
import soundcard as sc


def all_sources():
    """All capture sources, including monitors of output devices (loopback)."""
    return list(sc.all_microphones(include_loopback=True))


def print_sources():
    print("Audio sources (use the number or part of the name with --mic / --system):")
    for i, m in enumerate(all_sources()):
        kind = "system audio (monitor)" if m.isloopback else "microphone"
        print(f"  [{i}] {m.name}   <- {kind}")
    print(f"\nDefault microphone:     {sc.default_microphone().name}")
    print(f"Default output device:  {sc.default_speaker().name}"
          "   (its monitor is the default system-audio source)")


def _monitor_of_default_output():
    # The mic and the speakers can have the same name ("Built-in Audio Analog Stereo"),
    # so match the monitor by its id / "Monitor of ..." name, never by plain name.
    speaker = sc.default_speaker()
    for m in all_sources():
        if m.isloopback and (m.id == f"{speaker.id}.monitor" or m.name == f"Monitor of {speaker.name}"):
            return m
    raise SystemExit(f"No monitor source found for output '{speaker.name}'. Run --list-devices.")


def _is_bluetooth(device):
    return "bluez" in device.id.lower()


def _default_microphone():
    # Recording from a Bluetooth headset's microphone switches the headset into its
    # low-quality "call" profile: in a test the mic stream lost everything above 4 kHz
    # (telephone quality), which wrecked recognition. Prefer a wired/built-in mic.
    mic = sc.default_microphone()
    if _is_bluetooth(mic):
        others = [m for m in sc.all_microphones() if not _is_bluetooth(m)]
        if others:
            print(f"Note: default mic '{mic.name}' is a Bluetooth headset; using '{others[0].name}' "
                  "instead to keep the headset in high-quality mode (choose with --mic).")
            return others[0]
    return mic


def resolve(spec, loopback):
    """spec is None (use the default), an index from --list-devices, or part of a source name."""
    if spec is None:
        return _monitor_of_default_output() if loopback else _default_microphone()
    sources = all_sources()
    if spec.isdigit():
        return sources[int(spec)]
    matches = [m for m in sources if spec.lower() in m.name.lower()]
    preferred = [m for m in matches if m.isloopback == loopback]
    if not (preferred or matches):
        raise SystemExit(f"No audio source matches '{spec}'. Run with --list-devices.")
    return (preferred or matches)[0]
