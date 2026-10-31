"""Print all audio input sources, including system-audio monitors."""
import soundcard as sc

print("ALL INPUT SOURCES (incl. monitors):")
for m in sc.all_microphones(include_loopback=True):
    kind = "loopback" if m.isloopback else "mic"
    print(f"   {m.name} | {kind}")
print("DEFAULT MIC:    ", sc.default_microphone().name)
print("DEFAULT SPEAKER:", sc.default_speaker().name)
