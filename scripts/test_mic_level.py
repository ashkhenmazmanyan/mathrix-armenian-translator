"""Record 5 s from the default mic at 16 kHz mono, print levels, save a WAV."""
import wave
import numpy as np
import soundcard as sc

SR, SECONDS = 16000, 5
mic = sc.default_microphone()
print(f"Recording {SECONDS}s from: {mic.name} -- go...")
with mic.recorder(samplerate=SR, channels=1) as rec:
    audio = rec.record(numframes=SR * SECONDS)[:, 0]

def dbfs(x):
    return 20 * np.log10(max(abs(x), 1e-10))

dc = np.mean(audio)
ac = audio - dc
print(f"Peak:       {dbfs(np.max(np.abs(audio))):6.1f} dBFS")
print(f"RMS:        {dbfs(np.sqrt(np.mean(audio**2))):6.1f} dBFS")
print(f"DC offset:  {dc:+.4f}")
print(f"RMS no-DC:  {dbfs(np.sqrt(np.mean(ac**2))):6.1f} dBFS   <- the actual sound")
print(f"Clipped:    {np.mean(np.abs(audio) >= 1.0) * 100:5.1f}%")

with wave.open("recordings/mic_test.wav", "wb") as f:
    f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
    f.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
print("Saved recordings/mic_test.wav")
