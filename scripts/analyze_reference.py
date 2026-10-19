"""Deep breakdown of a reference Short: frames, cut detection, motion, transcript, loudness.
Usage: python analyze_reference.py <video> <audio_or_same_video> <output_dir> [frame_step_s]
"""
import os, sys, json, av
import _env  # noqa: F401  (loads .env, repo model cache, OS cert store)
import numpy as np
from PIL import Image, ImageDraw

vsrc, asrc, out = sys.argv[1], sys.argv[2], sys.argv[3]
step = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
os.makedirs(out, exist_ok=True)
fdir = os.path.join(out, "frames")
os.makedirs(fdir, exist_ok=True)

# ---- Video pass: sampled frames + per-frame difference for cut/motion detection
c = av.open(vsrc)
v = c.streams.video[0]
meta = {"duration_s": c.duration / 1e6, "width": v.codec_context.width,
        "height": v.codec_context.height, "fps": float(v.average_rate)}
prev, diffs, saved, next_t = None, [], [], 0.0
for f in c.decode(v):
    t = float(f.pts * v.time_base)
    small = np.asarray(f.to_image().convert("L").resize((72, 128)), dtype=np.float32)
    if prev is not None:
        diffs.append((round(t, 3), float(np.abs(small - prev).mean())))
    prev = small
    if t >= next_t:
        img = f.to_image()
        img.thumbnail((360, 640))
        name = f"f_{t:06.2f}.jpg"
        img.save(os.path.join(fdir, name), quality=82)
        saved.append((t, name))
        next_t += step
c.close()

# Cuts = big spikes relative to local median
d = np.array([x[1] for x in diffs])
med = np.median(d) if len(d) else 0
cuts = [diffs[i][0] for i in range(len(d)) if d[i] > max(25, med * 6)]
motion = [{"t": diffs[i][0], "diff": round(diffs[i][1], 2)} for i in range(0, len(diffs), 5)]

# Contact sheets: 6 cols x 3 rows, timestamp labelled
per = 18
for si in range(0, len(saved), per):
    chunk = saved[si:si + per]
    ims = [Image.open(os.path.join(fdir, n)) for _, n in chunk]
    w, h = ims[0].size
    sheet = Image.new("RGB", (w * 6, h * 3), "black")
    dr = ImageDraw.Draw(sheet)
    for i, ((t, _), im) in enumerate(zip(chunk, ims)):
        x, y = (i % 6) * w, (i // 6) * h
        sheet.paste(im, (x, y))
        dr.rectangle([x, y, x + 70, y + 22], fill="red")
        dr.text((x + 4, y + 4), f"{t:.1f}s", fill="white")
    sheet.save(os.path.join(out, f"sheet_{si // per:02d}.jpg"), quality=85)

# ---- Audio pass: 16k mono for whisper + loudness envelope
ac = av.open(asrc)
rs = av.AudioResampler(format="s16", layout="mono", rate=16000)
chunks = []
for fr in ac.decode(ac.streams.audio[0]):
    for r in rs.resample(fr):
        chunks.append(r.to_ndarray().reshape(-1))
for r in rs.resample(None):
    chunks.append(r.to_ndarray().reshape(-1))
ac.close()
audio = np.concatenate(chunks).astype(np.float32) / 32768.0
win = 1600  # 0.1 s
rms = [float(np.sqrt(np.mean(audio[i:i + win] ** 2)) + 1e-9) for i in range(0, len(audio) - win, win)]
loud = [{"t": round(i * 0.1, 1), "db": round(20 * np.log10(x), 1)} for i, x in enumerate(rms)]

from faster_whisper import WhisperModel
model = WhisperModel("small", device="cpu", compute_type="int8")
segs, info = model.transcribe(audio, word_timestamps=True, vad_filter=True)
words, lines = [], []
for s in segs:
    lines.append({"s": round(s.start, 2), "e": round(s.end, 2), "text": s.text.strip()})
    for wd in s.words:
        words.append({"w": wd.word.strip(), "s": round(wd.start, 2), "e": round(wd.end, 2)})

json.dump({"meta": meta, "cuts": cuts, "language": info.language, "segments": lines,
           "words": words, "loudness_0.1s": loud, "motion_every5f": motion},
          open(os.path.join(out, "reference_data.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

print("META", meta)
print("CUTS", len(cuts), cuts)
print("WPM", round(len(words) / (meta["duration_s"] / 60)))
for l in lines:
    print(f"[{l['s']:5.1f}-{l['e']:5.1f}] {l['text']}")
db = np.array([x["db"] for x in loud])
print("AUDIO dB median", np.median(db), "min", db.min(), "silences>0.4s:",
      sum(1 for i in range(len(db) - 4) if all(db[i:i + 4] < -45)))
