"""Terminal output."""


def clock(seconds):
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def print_segment(t, speaker, hy, en, detail=None):
    lines = [f"[{clock(t)}] {speaker}", f"HY: {hy}", f"EN: {en}"]
    if detail:
        lines.append(f"    ({detail})")
    print("\n".join(lines) + "\n", flush=True)
