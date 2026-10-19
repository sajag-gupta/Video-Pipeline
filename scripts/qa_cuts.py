"""QA the edit: transcribe the edited voice track and show what is heard on both sides of every cut.
Usage: python qa_cuts.py <qa_dir>   (expects voice_only.wav + segments.json from render_short.py --audio-only)
"""
import sys, os, json, wave
import _env  # noqa: F401  (loads .env, repo model cache, OS cert store)
import numpy as np
from faster_whisper import WhisperModel

d = sys.argv[1]
segs = json.load(open(os.path.join(d, "segments.json")))
with wave.open(os.path.join(d, "voice_only.wav")) as w:
    pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, 2).mean(1)
a48 = pcm.astype(np.float32) / 32768
a16 = a48[::3].copy()  # 48k -> 16k (speech band is well below 8 kHz)

model = WhisperModel("small", device="cpu", compute_type="int8")
ss, _ = model.transcribe(a16, word_timestamps=True, vad_filter=False, condition_on_previous_text=True)
words = [w for s in ss for w in s.words]
print("FULL:", " ".join(w.word.strip() for w in words))
print()
for sg in segs[1:]:
    t = sg["out0"]
    before = [w for w in words if t - 1.6 < w.end <= t + 0.05]
    after = [w for w in words if t - 0.05 <= w.start < t + 1.2]
    # energy right at the cut: if it's loud, we're cutting through a sound
    i = int(t * 48000)
    e = 20 * np.log10(np.sqrt(np.mean(a48[max(0, i - 1200):i + 1200] ** 2)) + 1e-9)
    tail = before[-1] if before else None
    flag = ""
    if tail and tail.probability < 0.5:
        flag += "  <-- last word unclear"
    if e > -30:
        flag += f"  <-- loud at cut ({e:.0f} dB)"
    print(f"cut @{t:6.2f}s | ...{' '.join(w.word.strip() for w in before[-4:]):45s} || {' '.join(w.word.strip() for w in after[:3]):30s} {flag}")
