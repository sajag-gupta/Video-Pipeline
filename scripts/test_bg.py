"""Try person segmentation + background treatments on one frame. Writes side-by-side preview.
Usage: python test_bg.py <video> <time_s> <out.jpg>
"""
import os, sys, av, numpy as np, cv2
import mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision
from PIL import Image
from _env import MODELS

src, t_want, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
c = av.open(src); v = c.streams.video[0]
for f in c.decode(v):
    if float(f.pts * v.time_base) >= t_want:
        img = f.to_ndarray(format="rgb24"); break
c.close()
img = np.ascontiguousarray(np.fliplr(np.rot90(img, k=-1)))  # upright + un-mirror

seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
    base_options=mpt.BaseOptions(model_asset_path=os.path.join(MODELS, "mediapipe", "selfie_multiclass_256x256.tflite")),
    running_mode=vision.RunningMode.IMAGE, output_confidence_masks=True))
res = seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=img))
bgconf = res.confidence_masks[0].numpy_view()          # class 0 = background
alpha = np.clip(1.0 - bgconf, 0, 1).astype(np.float32)
alpha = cv2.GaussianBlur(alpha, (0, 0), 2.0)[..., None]

h, w = img.shape[:2]
f32 = img.astype(np.float32) / 255

# A: real background, blurred + darkened + warm
bgA = cv2.GaussianBlur(f32, (0, 0), 18)
bgA = bgA * 0.38
bgA = bgA * np.array([1.05, 0.88, 0.70], np.float32)

# B: synthetic warm studio: dark brown gradient + lamp bokeh
yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
base = np.array([0.16, 0.11, 0.08], np.float32) * (1 - 0.45 * yy[..., None] / h)
lamp = np.exp(-(((xx - w * 0.82) / (w * 0.13)) ** 2 + ((yy - h * 0.22) / (h * 0.07)) ** 2))[..., None]
glow = np.exp(-(((xx - w * 0.80) / (w * 0.45)) ** 2 + ((yy - h * 0.25) / (h * 0.30)) ** 2))[..., None]
bgB = base + lamp * np.array([1.0, 0.85, 0.6]) * 0.75 + glow * np.array([0.35, 0.22, 0.12]) * 0.5

def comp(bg):
    o = f32 * alpha + bg * (1 - alpha)
    return (np.clip(o, 0, 1) * 255).astype(np.uint8)

panel = np.concatenate([img, comp(bgA), comp(bgB)], axis=1)
Image.fromarray(panel).resize((w * 3 // 2, h // 2)).save(out, quality=88)
print("ok", img.shape)
