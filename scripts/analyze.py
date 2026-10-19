"""Break a video into readable pieces: metadata, 1-per-second frames, contact sheet, word-timed transcript.
Usage: python analyze.py <video> <output_dir>
"""
import os, sys, json, av
import _env  # noqa: F401  (loads .env, repo model cache, OS cert store)
from PIL import Image

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

# Metadata
c = av.open(src)
v = c.streams.video[0]
meta = {
    "duration_s": c.duration / 1e6,
    "width": v.codec_context.width,
    "height": v.codec_context.height,
    "fps": float(v.average_rate),
    "has_audio": bool(c.streams.audio),
}
json.dump(meta, open(os.path.join(out, "metadata.json"), "w"), indent=1)

# Frames every 1s, downscaled for viewing
next_t = 0.0
for f in c.decode(v):
    t = float(f.pts * v.time_base)
    if t >= next_t:
        img = f.to_image()
        img.thumbnail((540, 1200))
        img.save(os.path.join(out, f"frame_{t:05.1f}.jpg"), quality=85)
        next_t += 1.0
c.close()

# Contact sheet
files = sorted(x for x in os.listdir(out) if x.startswith("frame_"))
ims = [Image.open(os.path.join(out, x)) for x in files]
w, h = ims[0].size
cols = 5
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (w * cols, h * rows), "black")
for i, im in enumerate(ims):
    sheet.paste(im, ((i % cols) * w, (i // cols) * h))
sheet.thumbnail((2000, 2000))
sheet.save(os.path.join(out, "contact_sheet.jpg"), quality=85)

# Transcript with word timestamps
if meta["has_audio"]:
    import numpy as np
    from faster_whisper import WhisperModel
    # Decode to 16 kHz mono float32 ourselves (faster-whisper's decoder doesn't match this PyAV version)
    ac = av.open(src)
    rs = av.AudioResampler(format="s16", layout="mono", rate=16000)
    chunks = []
    for fr in ac.decode(ac.streams.audio[0]):
        for r in rs.resample(fr):
            chunks.append(r.to_ndarray().reshape(-1))
    for r in rs.resample(None):
        chunks.append(r.to_ndarray().reshape(-1))
    ac.close()
    audio = np.concatenate(chunks).astype(np.float32) / 32768.0
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segs, info = model.transcribe(audio, word_timestamps=True, vad_filter=True)
    words = []
    for s in segs:
        for wd in s.words:
            words.append({"w": wd.word.strip(), "s": round(wd.start, 2), "e": round(wd.end, 2)})
    json.dump({"language": info.language, "words": words},
              open(os.path.join(out, "transcript.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("LANG:", info.language)
    print("TEXT:", " ".join(x["w"] for x in words))
print("META:", meta)
