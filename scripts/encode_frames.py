"""Encode a PNG frame folder (from hf_frames.js) to H.264 MP4, optionally with an audio file.
Usage: python encode_frames.py <frames_dir> <out.mp4> [fps] [audio_file]
"""
import os, sys, av, numpy as np
import _env  # noqa: F401  (loads .env, repo model cache, OS cert store)
from PIL import Image

src, out = sys.argv[1], sys.argv[2]
fps = int(sys.argv[3]) if len(sys.argv) > 3 else 30
audio = sys.argv[4] if len(sys.argv) > 4 else None
files = sorted(f for f in os.listdir(src) if f.endswith(".png"))
w, h = Image.open(os.path.join(src, files[0])).size

oc = av.open(out, "w")
vs = oc.add_stream("libx264", rate=fps)
vs.width, vs.height, vs.pix_fmt = w, h, "yuv420p"
vs.options = {"crf": "18", "preset": "medium", "movflags": "+faststart"}
as_ = None
if audio:
    as_ = oc.add_stream("aac", rate=48000); as_.layout = "stereo"; as_.bit_rate = 192000

for f in files:
    img = np.asarray(Image.open(os.path.join(src, f)).convert("RGB"))
    for p in vs.encode(av.VideoFrame.from_ndarray(img, format="rgb24")):
        oc.mux(p)
for p in vs.encode():
    oc.mux(p)

if as_:
    dur = len(files) / fps
    ic = av.open(audio)
    rs = av.AudioResampler(format="fltp", layout="stereo", rate=48000)
    done = 0
    for fr in ic.decode(audio=0):
        for r in rs.resample(fr):
            if done >= dur * 48000:
                break
            r.pts = done
            done += r.samples
            for p in as_.encode(r):
                oc.mux(p)
    for p in as_.encode():
        oc.mux(p)
    ic.close()
oc.close()
print("DONE", out, f"{len(files)} frames, {len(files) / fps:.2f}s")
