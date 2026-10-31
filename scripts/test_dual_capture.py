"""Record the microphone and the system-audio monitor at the same time.

Saves recordings/both_mic.wav and recordings/both_system.wav (16 kHz mono)
and prints levels for each, so we can confirm both sources are captured
in parallel and stay separate.
"""
import threading
import warnings
import wave

import numpy as np
import soundcard as sc

SR = 16000          # sample rate expected by speech models
SECONDS = 15        # length of the test recording
WARMUP = 0.5        # seconds discarded at start (mic wake-up pop)

results = {}
barrier = threading.Barrier(2)  # start both recorders at the same moment


def record(name, device):
    with device.recorder(samplerate=SR, channels=1) as rec:
        rec.record(numframes=int(SR * WARMUP))   # discard start-up pop
        barrier.wait()
        results[name] = rec.record(numframes=SR * SECONDS)[:, 0]


def dbfs(x):
    return 20 * np.log10(max(abs(x), 1e-10))


def save(path, audio):
    with wave.open(path, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
        f.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())


mic = sc.default_microphone()
speaker = sc.default_speaker()
monitor = sc.get_microphone(speaker.name, include_loopback=True)
print(f"Mic:     {mic.name}")
print(f"System:  {monitor.name}")
print(f"Recording {SECONDS}s from both -- play a video AND speak...")

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    threads = [threading.Thread(target=record, args=("mic", mic)),
               threading.Thread(target=record, args=("system", monitor))]
    for t in threads: t.start()
    for t in threads: t.join()

for name in ("mic", "system"):
    a = results[name]
    print(f"[{name:6}] {len(a)/SR:5.2f}s  peak {dbfs(np.max(np.abs(a))):6.1f} dBFS  "
          f"RMS {dbfs(np.sqrt(np.mean(a**2))):6.1f} dBFS  "
          f"clipped {np.mean(np.abs(a) >= 1.0)*100:4.1f}%")
    save(f"recordings/both_{name}.wav", results[name])

print(f"Warnings during recording: {len(caught)}")
for w in caught:
    print("   ", w.message)
print("Saved recordings/both_mic.wav and recordings/both_system.wav")
