"""Render a Short in the 'finance_story' style from a talking-head recording.

Usage:
  python render_short.py <plan.py> <output.mp4>                 full render
  python render_short.py <plan.py> <out_dir> --preview 3.0 12.5  still frames at output times

The plan file defines SRC, KEEP, CAPTIONS, STATS, HEADERS, BADGES, CARD, DISCLAIMER (all in SOURCE seconds).
"""
import sys, os, math, runpy, json
import numpy as np, cv2, av
import mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from _env import ROOT, FONTS, require_fonts

W, H, FPS = 1080, 1920, 30
require_fonts()
F_BOLD, F_BLACK, F_SEMI = FONTS["bold"], FONTS["black"], FONTS["semi"]
F_SERIF_IT, F_EMOJI = FONTS["serif_italic"], FONTS["emoji"]

plan = runpy.run_path(sys.argv[1])
OUT = sys.argv[2]
PREVIEW = None
if "--preview" in sys.argv:
    PREVIEW = [float(x) for x in sys.argv[sys.argv.index("--preview") + 1:]]
SRC = plan["SRC"]


# ------------------------------------------------------------------ helpers
def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_back(x):
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def upright(rgb):
    """Phone stores portrait as rotated landscape (rotation -90) and front camera mirrors."""
    return np.ascontiguousarray(np.fliplr(np.rot90(rgb, k=-1)))


_font_cache = {}


def font(path, size):
    k = (path, size)
    if k not in _font_cache:
        _font_cache[k] = ImageFont.truetype(path, size)
    return _font_cache[k]


def text_layer(lines, shadow=True, pad=30):
    """lines: list of (text, font_path, size, color, dx, dy) relative to block centre-top. Returns RGBA image + anchor."""
    measures = []
    for (t, fp, sz, col, dx, dy) in lines:
        f = font(fp, sz)
        bb = f.getbbox(t)
        measures.append((bb, f))
    minx = min(dx - (bb[2] - bb[0]) / 2 for (bb, f), (_, _, _, _, dx, _) in zip(measures, lines))
    maxx = max(dx + (bb[2] - bb[0]) / 2 for (bb, f), (_, _, _, _, dx, _) in zip(measures, lines))
    miny = min(dy + bb[1] for (bb, f), (_, _, _, _, _, dy) in zip(measures, lines))
    maxy = max(dy + bb[3] for (bb, f), (_, _, _, _, _, dy) in zip(measures, lines))
    w, h = int(maxx - minx + 2 * pad), int(maxy - miny + 2 * pad)
    txt = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    for (t, fp, sz, col, dx, dy), (bb, f) in zip(lines, measures):
        x = dx - (bb[2] - bb[0]) / 2 - bb[0] - minx + pad
        y = dy - miny + pad
        d.text((x, y), t, font=f, fill=col)
    if shadow:
        a = txt.split()[3].filter(ImageFilter.GaussianBlur(7))
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sh.putalpha(a.point(lambda v: int(v * 0.70)))
        sh = sh.transform(sh.size, Image.AFFINE, (1, 0, 0, 0, 1, -4))
        out = Image.alpha_composite(sh, txt)
    else:
        out = txt
    # anchor: block centre x, top y of first line in block coords
    return out, (-minx + pad, -miny + pad)


def blit(frame, rgba, cx, top, opacity=1.0, scale=1.0, anchor=None):
    """frame float32 HxWx3 [0,1]; rgba PIL; place so that anchor point lands at (cx, top)."""
    if opacity <= 0.01:
        return
    img = rgba
    ax, ay = anchor if anchor else (img.width / 2, 0)
    if abs(scale - 1) > 1e-3:
        nw, nh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
        img = img.resize((nw, nh), Image.BICUBIC)
        ax, ay = ax * scale, ay * scale
    arr = np.asarray(img, dtype=np.float32) / 255.0
    x0, y0 = int(round(cx - ax)), int(round(top - ay))
    x1, y1 = x0 + arr.shape[1], y0 + arr.shape[0]
    fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if fx0 >= fx1 or fy0 >= fy1:
        return
    sub = arr[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    a = sub[..., 3:4] * opacity
    region = frame[fy0:fy1, fx0:fx1]
    region[:] = region * (1 - a) + sub[..., :3] * a


# ------------------------------------------------------------------ element builders
CAP_Y = int(0.55 * H)
CAP_Y_LOW = int(0.66 * H)
_cache = {}


def cached(key, fn):
    if key not in _cache:
        _cache[key] = fn()
    return _cache[key]


def caption_img(text):
    return cached(("cap", text), lambda: text_layer([(text, F_BOLD, 64, (255, 255, 255, 255), 0, 0)]))


def stat_img(text, sub=None):
    def mk():
        lines = [(text, F_BLACK, 112, (255, 255, 255, 255), 0, 0)]
        if sub:
            lines.append((sub, F_BOLD, 52, (255, 255, 255, 235), 0, 140))
        return text_layer(lines)
    return cached(("stat", text, sub), mk)


def header_img(line1, accent, show_accent):
    def mk():
        lines = [(line1, F_BOLD, 70, (255, 255, 255, 255), 0, 0)]
        if show_accent:
            lines.append((accent, F_SERIF_IT, 104, (255, 255, 255, 255), 70, 78))
        else:  # keep the same block geometry so line1 doesn't jump when accent appears
            lines.append((accent, F_SERIF_IT, 104, (255, 255, 255, 0), 70, 78))
        return text_layer(lines)
    return cached(("hdr", line1, accent, show_accent), mk)


def badge_img(glyph, label, d=176):
    def mk():
        pad = 20
        lab_h = 56 if label else 0
        im = Image.new("RGBA", (d + 2 * pad, d + 2 * pad + lab_h), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.ellipse([pad, pad, pad + d, pad + d], fill=(12, 10, 9, 150), outline=(255, 255, 255, 165), width=3)
        f = font(F_EMOJI, int(d * 0.44))
        bb = f.getbbox(glyph)
        gx = pad + d / 2 - (bb[2] + bb[0]) / 2
        gy = pad + d / 2 - (bb[3] + bb[1]) / 2
        dr.text((gx, gy), glyph, font=f, fill=(255, 255, 255, 255))  # monochrome glyph = white line icon
        if label:
            fl = font(F_SEMI, 38)
            lb = fl.getbbox(label)
            dr.text((pad + d / 2 - (lb[2] + lb[0]) / 2, pad + d + 8), label, font=fl, fill=(255, 255, 255, 240))
        sh = im.split()[3].filter(ImageFilter.GaussianBlur(8)).point(lambda v: int(v * 0.5))
        shadow = Image.new("RGBA", im.size, (0, 0, 0, 0)); shadow.putalpha(sh)
        return Image.alpha_composite(shadow, im)
    return cached(("badge", glyph, label, d), mk)


def card_row_img(label, value, color):
    def mk():
        wdt, hgt = 820, 118
        im = Image.new("RGBA", (wdt, hgt), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle([0, 0, wdt - 1, hgt - 1], radius=26, fill=(14, 11, 9, 175), outline=(255, 255, 255, 60), width=2)
        fl, fv = font(F_SEMI, 46), font(F_BLACK, 60)
        lb = fl.getbbox(label); vb = fv.getbbox(value)
        dr.text((40, hgt / 2 - (lb[3] + lb[1]) / 2), label, font=fl, fill=(255, 255, 255, 225))
        dr.text((wdt - 40 - vb[2], hgt / 2 - (vb[3] + vb[1]) / 2), value, font=fv, fill=color)
        return im
    return cached(("row", label, value, color), mk)


def small_text_img(text):
    return cached(("small", text), lambda: text_layer([(text, F_SEMI, 34, (255, 255, 255, 190), 0, 0)], pad=16))


# ------------------------------------------------------------------ edit decision list
def build_segments():
    """KEEP ranges, minus internal silences > 0.30 s detected from audio energy."""
    c = av.open(SRC)
    ast = c.streams.audio[0]
    rs = av.AudioResampler(format="fltp", layout="stereo", rate=48000)
    chunks = []
    for fr in c.decode(ast):
        for r in rs.resample(fr):
            chunks.append(r.to_ndarray())
    for r in rs.resample(None):
        chunks.append(r.to_ndarray())
    c.close()
    audio = np.concatenate(chunks, axis=1).astype(np.float32)
    mono = audio.mean(0)
    hop = 480  # 10 ms
    e = np.array([np.sqrt(np.mean(mono[i:i + hop] ** 2)) + 1e-9 for i in range(0, len(mono) - hop, hop)])
    db = 20 * np.log10(e)
    noise = np.percentile(db, 8)
    speech = np.percentile(db, 90)
    thr = noise + 0.22 * (speech - noise)  # low threshold: soft word tails count as speech
    voiced = db > thr
    sm = np.convolve(db, np.ones(3) / 3, mode="same")  # 30 ms smoothed energy for finding quiet cut points

    def quietest(lo, hi):
        """Cut at the quietest 30 ms point inside [lo, hi] seconds (Whisper word ends are often early)."""
        i0, i1 = max(0, int(lo * 100)), min(len(sm) - 1, int(hi * 100))
        if i1 <= i0:
            return lo
        return (i0 + int(np.argmin(sm[i0:i1 + 1]))) / 100

    def refine_end(b):
        # let the last word ring out: search up to 0.40 s past the timestamp; stop early once properly silent
        for i in range(int(b * 100), min(len(db), int((b + 0.40) * 100))):
            if np.all(db[i:i + 6] < thr):  # 60 ms of silence = word finished
                return i / 100 + 0.10       # keep a little natural room tone after the word
        return quietest(b, b + 0.40) + 0.02

    def refine_start(a):
        # Whisper word starts can be late too: walk back to the real onset (60 ms of silence before it)
        for i in range(int(a * 100), max(0, int((a - 0.45) * 100)), -1):
            if np.all(db[max(0, i - 6):i] < thr):
                return max(0.0, i / 100 - 0.06)
        return max(0.0, quietest(a - 0.45, a + 0.02) - 0.02)

    segs = []
    for k in plan["KEEP"]:
        a, b = k[0], k[1]
        opts = k[2] if len(k) > 2 else {}
        a = a if opts.get("hard_start") else refine_start(a)  # hard start: speech is continuous with the cut word
        b = b if opts.get("hard_end") else refine_end(b)
        i0, i1 = int(a * 100), int(b * 100)
        cur = a
        run_start = None
        for i in range(i0, min(i1, len(voiced))):
            if not voiced[i]:
                if run_start is None:
                    run_start = i
            else:
                # only remove clear pauses (> 0.5 s); leave 0.18 s each side so speech breathes
                if run_start is not None and (i - run_start) >= 50:
                    s_end = run_start / 100 + 0.18
                    s_next = i / 100 - 0.15
                    if s_end - cur > 0.12:
                        segs.append((cur, s_end))
                    cur = s_next
                run_start = None
        segs.append((cur, b))
    # ranges may now touch/overlap after refinement -> merge
    segs.sort()
    merged = []
    for a, b in segs:
        if merged and a <= merged[-1][1] + 0.02:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    segs = merged
    segs = [(round(a, 3), round(b, 3)) for a, b in segs if b - a > 0.25]  # drop tiny fragments
    out, t = [], 0.0
    for a, b in segs:
        out.append({"src0": a, "src1": b, "out0": t, "out1": t + (b - a)})
        t += b - a
    return out, audio, (noise, speech)


SEGS, SRC_AUDIO, LEVELS = build_segments()
DUR = SEGS[-1]["out1"]


def s2o(s):
    """Source time -> output time (times inside cut gaps snap to next kept segment)."""
    for sg in SEGS:
        if s < sg["src0"]:
            return sg["out0"]
        if s <= sg["src1"]:
            return sg["out0"] + (s - sg["src0"])
    return DUR


def o2s(t):
    for sg in SEGS:
        if t < sg["out1"]:
            return sg["src0"] + (t - sg["out0"]), sg
    sg = SEGS[-1]
    return sg["src1"], sg


# ------------------------------------------------------------------ shots (alternating framing)
def build_shots():
    cuts = [sg["out0"] for sg in SEGS]
    shots, last, angle = [], 0.0, 0
    for c in cuts[1:]:
        if c - last >= 1.2:
            shots.append((last, c, angle)); angle ^= 1; last = c
    shots.append((last, DUR, angle))
    final = []
    for (a, b, ang) in shots:  # split long shots
        n = max(1, int(round((b - a) / 3.2)))
        step = (b - a) / n
        for k in range(n):
            final.append((a + k * step, a + (k + 1) * step, ang if k % 2 == 0 else ang ^ 1))
    return final


SHOTS = build_shots()
HEADER_TIMES = [s2o(h["t"]) for h in plan["HEADERS"]]
ANGLES = [dict(zoom=1.12, fx=0.50, fy=0.30), dict(zoom=1.26, fx=0.44, fy=0.30)]


def shot_at(t):
    for (a, b, ang) in SHOTS:
        if a <= t < b:
            return a, b, ang
    return SHOTS[-1]


# ------------------------------------------------------------------ face track pass
def face_track():
    cache_p = os.path.join(ROOT, "work", os.path.basename(SRC) + ".face2.json")
    if os.path.exists(cache_p):
        d = json.load(open(cache_p))
        return np.array(d["t"]), np.array(d["x"]), np.array(d["y"]), np.array(d["w"])
    det = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
        base_options=mpt.BaseOptions(model_asset_path=os.path.join(ROOT, "models/mediapipe/blaze_face_short_range.tflite")),
        running_mode=vision.RunningMode.IMAGE, min_detection_confidence=0.5))
    c = av.open(SRC); v = c.streams.video[0]
    ts, xs, ys, ws = [], [], [], []
    k = 0
    for f in c.decode(v):
        k += 1
        if k % 2:
            continue
        t = float(f.pts * v.time_base)
        img = upright(f.to_ndarray(format="rgb24"))
        small = cv2.resize(img, (img.shape[1] // 2, img.shape[0] // 2), interpolation=cv2.INTER_AREA)
        r = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=small))
        if r.detections:
            bb = max(r.detections, key=lambda d: d.bounding_box.width).bounding_box
            ts.append(t)
            xs.append((bb.origin_x + bb.width / 2) * 2 / img.shape[1])
            ys.append((bb.origin_y + bb.height / 2) * 2 / img.shape[0])
            ws.append(bb.width * 2 / img.shape[1])
    c.close()
    json.dump({"t": ts, "x": xs, "y": ys, "w": ws}, open(cache_p, "w"))
    return np.array(ts), np.array(xs), np.array(ys), np.array(ws)


FT, FX, FY, FW = face_track()


def smooth_face(s):
    """Robust 1.2 s window median then mean -> stabilised framing. Returns (x, y, width) normalised."""
    m = np.abs(FT - s) < 0.6
    if m.sum() == 0:
        i = np.argmin(np.abs(FT - s))
        return FX[i], FY[i], FW[i]
    return float(np.mean(np.clip(FX[m], np.median(FX[m]) - 0.03, np.median(FX[m]) + 0.03))), \
        float(np.mean(np.clip(FY[m], np.median(FY[m]) - 0.03, np.median(FY[m]) + 0.03))), \
        float(np.median(FW[m]))


def head_prior(h, w, fx, fy, fw):
    """Above the shoulders only the head region can be 'person' -> stops wall/curtain leaking into the cutout."""
    px, py, pw = fx * w, fy * h, fw * w
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    shoulders = py + 0.95 * pw
    head_zone = (np.abs(xx - px) < 0.95 * pw).astype(np.float32)
    below = (yy > shoulders).astype(np.float32)
    prior = np.maximum(head_zone, below)
    return cv2.GaussianBlur(prior, (0, 0), 0.08 * pw)


# ------------------------------------------------------------------ look: background + grade
SEG_MODEL = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
    base_options=mpt.BaseOptions(model_asset_path=os.path.join(ROOT, "models/mediapipe/selfie_multiclass_256x256.tflite")),
    running_mode=vision.RunningMode.IMAGE, output_confidence_masks=True))


def make_background(h, w):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    base = np.array([0.15, 0.105, 0.075], np.float32) * (1 - 0.5 * yy[..., None] / h)
    lamp = np.exp(-(((xx - w * 0.84) / (w * 0.10)) ** 2 + ((yy - h * 0.20) / (h * 0.055)) ** 2))[..., None]
    glow = np.exp(-(((xx - w * 0.82) / (w * 0.42)) ** 2 + ((yy - h * 0.24) / (h * 0.26)) ** 2))[..., None]
    side = np.exp(-(((xx - w * 0.08) / (w * 0.25)) ** 2 + ((yy - h * 0.35) / (h * 0.35)) ** 2))[..., None]
    bg = base + lamp * np.array([1.0, 0.86, 0.62]) * 0.80 + glow * np.array([0.36, 0.22, 0.11]) * 0.55 \
        + side * np.array([0.10, 0.07, 0.05])
    # faint picture-frame shapes on the wall for depth (very soft)
    for (cx, cy, fw, fh) in [(0.20, 0.22, 0.16, 0.10), (0.62, 0.15, 0.12, 0.08)]:
        m = ((np.abs(xx - w * cx) < w * fw / 2) & (np.abs(yy - h * cy) < h * fh / 2)).astype(np.float32)
        bg -= cv2.GaussianBlur(m, (0, 0), 6)[..., None] * 0.035
    return cv2.GaussianBlur(np.clip(bg, 0, 1).astype(np.float32), (0, 0), 3)


BG = None
KEYLIGHT = None


def person_alpha(img, prev, prior):
    r = SEG_MODEL.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=img))
    bgc = r.confidence_masks[0].numpy_view()
    a = 1.0 - bgc
    a = np.clip((a - 0.30) / 0.40, 0, 1)  # smoothstep-ish hard edge, kills faint bleed-through
    a = a * a * (3 - 2 * a)
    a = cv2.GaussianBlur(a.astype(np.float32), (0, 0), 1.6) * prior
    if prev is not None:
        a = 0.55 * a + 0.45 * prev  # temporal smoothing against flicker
    return a


def grade_subject(f):
    f = f - 0.35 * np.maximum(f - 0.62, 0)  # roll off highlights (white T-shirt)
    f = f * 0.90
    f = (f - 0.5) * 1.10 + 0.5
    lum = f.mean(axis=2, keepdims=True)
    f = lum + (f - lum) * 0.90
    f = f * np.array([1.04, 0.98, 0.88], np.float32)
    return f


PAD_TOP_FRAC = 0.20  # synthetic headroom above the source frame (background is generated, so we can extend it)


def compose_source(img, alpha):
    """Returns canvas (source + generated headroom on top) with subject over the studio background."""
    global BG, KEYLIGHT
    h, w = img.shape[:2]
    pt = int(PAD_TOP_FRAC * h)
    if BG is None:
        BG = make_background(h + pt, w)
        xx = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
        KEYLIGHT = 1.04 - 0.20 * xx  # light from frame-left, falls off to the right
    f = img.astype(np.float32) / 255.0
    subj = np.clip(grade_subject(f) * KEYLIGHT, 0, 1)
    a = alpha[..., None]
    bg = BG[pt:]
    # light wrap: let a little background glow bleed onto subject edges
    edge = np.clip(cv2.GaussianBlur(alpha, (0, 0), 6)[..., None] - a, 0, 1)
    canvas = BG.copy()
    canvas[pt:] = subj * a + bg * (1 - a) + edge * bg * 0.6
    return canvas, pt


def finishing_layers():
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    xx = np.linspace(-1, 1, W, dtype=np.float32)[None, :, None]
    grad = 1 - 0.72 * np.clip((yy - 0.70) / 0.30, 0, 1) ** 1.3
    vig = 1 - 0.28 * np.clip((xx ** 2 + ((yy - 0.45) * 1.6) ** 2) - 0.35, 0, 1)
    rng = np.random.default_rng(7)
    grains = [rng.normal(0, 0.012, (H // 2, W // 2, 1)).astype(np.float32) for _ in range(4)]
    grains = [cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR)[..., None] for g in grains]
    return (grad * vig).astype(np.float32), grains


MULT, GRAINS = finishing_layers()


def frame_transform(t, sh, src_shape, pad_top, face):
    a, b, ang = sh
    A = ANGLES[ang]
    zoom = A["zoom"] * (1 + 0.035 * (t - a) / max(b - a, 0.5))
    for ht in HEADER_TIMES:  # punch-in on section headers
        dt = t - ht
        if 0 <= dt < 0.9:
            zoom *= 1 + 0.07 * (ease_out(dt / 0.10) if dt < 0.10 else math.exp(-(dt - 0.10) / 0.35))
    fx, fy, _ = face
    h, w = src_shape
    cw, ch = w / zoom, h / zoom
    cx = fx * w + (0.5 - A["fx"]) * cw
    cy = pad_top + fy * h + (0.5 - A["fy"]) * ch
    cx = min(max(cx, cw / 2), w - cw / 2)            # never show past the real left/right edges
    cy = min(max(cy, ch / 2), pad_top + h - ch / 2)  # top may use generated headroom, bottom stays real
    s = W / cw
    return np.float32([[s, 0, -(cx - cw / 2) * s], [0, s, -(cy - ch / 2) * s]])


# ------------------------------------------------------------------ overlays
CAPS = sorted([(s2o(a), s2o(b), txt) for (a, b, txt) in plan["CAPTIONS"]])
STATS = [dict(o0=s2o(x["s"]), o1=s2o(x["e"]), **x) for x in plan["STATS"]]
HEADERS = [dict(o0=s2o(x["t"]), o1=s2o(x["e"]), oa=s2o(x["accent_t"]), **x) for x in plan["HEADERS"]]
BADGE_GROUPS = [dict(o0=s2o(g["s"]), o1=s2o(g["e"]), items=[dict(oa=s2o(it["t"]), **it) for it in g["items"]], layout=g["layout"])
                for g in plan["BADGES"]]
CARD = plan.get("CARD")
if CARD:
    CARD = dict(o0=s2o(CARD["s"]), o1=s2o(CARD["e"]), rows=[dict(oa=s2o(r["t"]), **r) for r in CARD["rows"]])
DISC = [(s2o(a), s2o(b), txt) for (a, b, txt) in plan.get("DISCLAIMER", [])]


def badge_positions(layout, n):
    if layout == "ring3":
        cx, cy, r = W / 2, 1440, 190
        angs = [-90, 150, 30]
        return [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in angs[:n]], (cx, cy, r)
    if layout == "pair":
        return [(W / 2 - 190, 1330), (W / 2 + 190, 1330)][:n], None
    raise ValueError(layout)


def draw_overlays(frame, t):
    active_stat = next((s for s in STATS if s["o0"] <= t < s["o1"]), None)
    active_hdr = next((h for h in HEADERS if h["o0"] <= t < h["o1"]), None)
    card_on = CARD and CARD["o0"] <= t < CARD["o1"]

    # badges (behind text)
    for g in BADGE_GROUPS:
        if not (g["o0"] <= t < g["o1"]):
            continue
        fade_out = min(1.0, (g["o1"] - t) / 0.2)
        pos, ring = badge_positions(g["layout"], len(g["items"]))
        if ring:
            first = g["items"][0]["oa"]
            ra = ease_out((t - first) / 0.35) * 0.45 * fade_out
            if ra > 0:
                cx, cy, r = ring
                ov = cached(("ring", r), lambda: _ring_img(r))
                blit(frame, ov, cx, cy - ov.height / 2, opacity=ra)
        if g["layout"] == "pair" and t >= g["items"][-1]["oa"]:
            ar = cached(("arrow",), _arrow_img)
            k = ease_out((t - g["items"][-1]["oa"]) / 0.25)
            blit(frame, ar, W / 2, pos[0][1] - ar.height / 2 + 0, opacity=k * fade_out)
        for it, (bx, by) in zip(g["items"], pos):
            dt = t - it["oa"]
            if dt < 0:
                continue
            img = badge_img(it["glyph"], it.get("label"))
            sc = 0.6 + 0.4 * ease_back(dt / 0.24)
            blit(frame, img, bx, by - (img.height - 56 * (1 if it.get("label") else 0)) / 2 * sc,
                 opacity=min(1, dt / 0.12) * fade_out, scale=sc)

    # final card
    if card_on:
        fade_out = min(1.0, (CARD["o1"] - t) / 0.25)
        for i, row in enumerate(CARD["rows"]):
            dt = t - row["oa"]
            if dt < 0:
                continue
            img = card_row_img(row["label"], row["value"], tuple(row["color"]))
            k = ease_out(dt / 0.28)
            blit(frame, img, W / 2, 1130 + i * 142 + (1 - k) * 36, opacity=k * fade_out)

    # stat / header replace the caption at caption position
    if active_stat:
        dt = t - active_stat["o0"]
        img, anc = stat_img(active_stat["text"], active_stat.get("sub"))
        k = ease_out(dt / 0.16)
        blit(frame, img, W / 2, CAP_Y - 40, opacity=k, scale=0.94 + 0.06 * k, anchor=anc)
    if active_hdr:
        show_acc = t >= active_hdr["oa"]
        img, anc = header_img(active_hdr["line1"], active_hdr["accent"], show_acc)
        k = ease_out((t - active_hdr["o0"]) / 0.12)
        blit(frame, img, W / 2, CAP_Y - 30, opacity=k, anchor=anc)

    if not active_stat:
        cap = None
        for (a, b, txt) in CAPS:
            if a <= t < b:
                cap = txt
        if cap and not (active_hdr and active_hdr.get("hide_captions")):
            if card_on:
                y = 1600
            elif active_hdr:
                y = CAP_Y_LOW + 40
            else:
                y = CAP_Y
            img, anc = caption_img(cap)
            blit(frame, img, W / 2, y, anchor=anc)

    for (a, b, txt) in DISC:
        if a <= t < b:
            img, anc = small_text_img(txt)
            blit(frame, img, W / 2, 1795, opacity=min(1, (t - a) / 0.3, (b - t) / 0.3), anchor=anc)


def _ring_img(r):
    im = Image.new("RGBA", (int(2 * r + 20), int(2 * r + 20)), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([10, 10, 10 + 2 * r, 10 + 2 * r], outline=(255, 255, 255, 255), width=3)
    return im


def _arrow_img():
    im = Image.new("RGBA", (190, 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line([(20, 20), (160, 20)], fill=(255, 255, 255, 220), width=4)
    d.polygon([(170, 20), (150, 8), (150, 32)], fill=(255, 255, 255, 220))
    return im


# ------------------------------------------------------------------ sound effects (synthesised, royalty-free)
SR = 48000
_rng = np.random.default_rng(11)


def _env(n, attack, release):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / release)


def _bandpass_noise(n, f_lo, f_hi):
    X = np.fft.rfft(_rng.normal(0, 1, n))
    fr = np.fft.rfftfreq(n, 1 / SR)
    X *= ((fr > f_lo) & (fr < f_hi))
    y = np.fft.irfft(X, n=n)
    return y / (np.abs(y).max() + 1e-9)


def sfx_whoosh(dur=0.45):
    """Filtered-noise sweep: low -> high -> low, used on section headers."""
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    out = np.zeros(n)
    bands = [(200, 600), (500, 1500), (1200, 3500), (2500, 6000)]
    for k, (lo, hi) in enumerate(bands):
        centre = (k + 0.5) / len(bands) * 0.7 + 0.15
        out += _bandpass_noise(n, lo, hi) * np.exp(-((t - centre) / 0.18) ** 2)
    out *= np.sin(np.pi * t) ** 1.5
    return out / (np.abs(out).max() + 1e-9)


def sfx_pop():
    """Soft bubble pop for icon badges: short sine with fast downward pitch."""
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    f = 900 * np.exp(-t * 18) + 380
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.035)
    return y / np.abs(y).max()


def sfx_ding():
    """Two-note 'cash' chime for ₹ numbers (bell-like partials)."""
    out = np.zeros(int(0.9 * SR))
    for start, f0 in [(0.0, 1318.5), (0.07, 1760.0)]:
        n = len(out) - int(start * SR)
        t = np.arange(n) / SR
        tone = sum(a * np.sin(2 * np.pi * f0 * m * t) for m, a in [(1, 1.0), (2.76, 0.35), (5.4, 0.12)])
        out[int(start * SR):] += tone * _env(n, 0.002, 0.28)
    return out / np.abs(out).max()


def sfx_tick():
    n = int(0.05 * SR)
    y = _bandpass_noise(n, 2000, 7000) * _env(n, 0.0005, 0.008)
    return y / np.abs(y).max()


def sfx_impact():
    """Low cinematic hit for the payoff number: sub drop + noise burst."""
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    f = 110 * np.exp(-t * 3) + 38
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.004, 0.45)
    burst = _bandpass_noise(n, 80, 2500) * _env(n, 0.001, 0.06) * 0.5
    y = sub + burst
    return y / np.abs(y).max()


def sfx_events():
    """(output_time, sound, gain_dB relative to full scale)."""
    ev = []
    for h in HEADERS:
        ev.append((max(0.0, h["o0"] - 0.18), sfx_whoosh(), -20))
    for s in STATS:
        ev.append((s["o0"], sfx_ding(), -22))
    for g in BADGE_GROUPS:
        for it in g["items"]:
            ev.append((it["oa"], sfx_pop(), -18))
    if CARD:
        for i, r in enumerate(CARD["rows"]):
            last = i == len(CARD["rows"]) - 1
            ev.append((r["oa"], sfx_impact() if last else sfx_tick(), -16 if last else -22))
            if last:
                ev.append((r["oa"], sfx_ding(), -23))
    return ev


def mix_sfx(y):
    n = y.shape[1]
    bus = np.zeros(n, np.float32)
    for (t0, snd, gdb) in sfx_events():
        i = int(t0 * SR)
        if i >= n:
            continue
        seg = snd[:n - i] * 10 ** (gdb / 20)
        bus[i:i + len(seg)] += seg.astype(np.float32)
    # very light stereo spread so effects sit around the voice, not on top of it
    return y + np.stack([bus * 0.95, bus * 1.0])


# ------------------------------------------------------------------ audio
def build_audio():
    sr = 48000
    parts = []
    fade = int(0.025 * sr)  # 25 ms fades: no clicks, no chopped consonants
    for sg in SEGS:
        a = SRC_AUDIO[:, int(sg["src0"] * sr):int(sg["src1"] * sr)].copy()
        if a.shape[1] > 2 * fade:
            ramp = np.linspace(0, 1, fade, dtype=np.float32)
            a[:, :fade] *= ramp; a[:, -fade:] *= ramp[::-1]
        parts.append(a)
    y = np.concatenate(parts, axis=1)
    y -= y.mean(axis=1, keepdims=True)
    # gentle 80 Hz high-pass via FFT
    n = y.shape[1]
    Y = np.fft.rfft(y, axis=1)
    fr = np.fft.rfftfreq(n, 1 / sr)
    Y *= (1 / np.sqrt(1 + (80 / np.maximum(fr, 1e-3)) ** 4))[None, :]
    y = np.fft.irfft(Y, n=n, axis=1).astype(np.float32)
    # loudness: bring voiced RMS to about -17 dBFS (~ -14 LUFS for speech), soft-limit peaks
    mono = y.mean(0)
    hop = 480
    rms = np.array([np.sqrt(np.mean(mono[i:i + hop] ** 2)) for i in range(0, n - hop, hop)]) + 1e-9
    voiced = rms[20 * np.log10(rms) > np.percentile(20 * np.log10(rms), 40)]
    cur = 20 * np.log10(np.sqrt(np.mean(voiced ** 2)))
    y *= 10 ** ((-17 - cur) / 20)
    # light compression: smooth gain riding (2:1 above -20 dBFS)
    env = np.sqrt(cv2.GaussianBlur((y.mean(0) ** 2).reshape(1, -1).astype(np.float32), (0, 0), sigmaX=sr * 0.01).reshape(-1)) + 1e-6
    env_db = 20 * np.log10(env)
    gain_db = np.where(env_db > -20, -(env_db + 20) * 0.5, 0.0)
    y *= (10 ** (gain_db / 20)).astype(np.float32)[None, :]
    y *= 10 ** (3 / 20)  # make-up
    if plan.get("SFX", True):
        y = mix_sfx(y)
    y = np.tanh(y / 0.89) * 0.89  # soft limiter, peaks < -1 dBFS
    end = int(0.12 * sr)
    y[:, -end:] *= np.linspace(1, 0, end, dtype=np.float32)
    return y


# ------------------------------------------------------------------ main render loop
def render():
    want_out = PREVIEW if PREVIEW else [i / FPS for i in range(int(DUR * FPS))]
    want = sorted(want_out)
    c = av.open(SRC); v = c.streams.video[0]
    frames_iter = c.decode(v)
    cur_frame, cur_t, nxt = None, -1.0, None

    if not PREVIEW:
        outc = av.open(OUT, "w")
        vs = outc.add_stream("libx264", rate=FPS)
        vs.width, vs.height, vs.pix_fmt = W, H, "yuv420p"
        vs.options = {"crf": "18", "preset": "medium", "profile": "high", "movflags": "+faststart"}
        as_ = outc.add_stream("aac", rate=48000)
        as_.layout = "stereo"
        as_.bit_rate = 192000
    else:
        os.makedirs(OUT, exist_ok=True)

    prev_alpha, prev_seg = None, None
    for idx, t in enumerate(want):
        s, sg = o2s(t)
        # advance decoder to the source frame at time s
        while cur_t < s - 0.5 / 30:
            try:
                f = next(frames_iter)
            except StopIteration:
                break
            cur_frame, cur_t = f, float(f.pts * v.time_base)
        img = upright(cur_frame.to_ndarray(format="rgb24"))
        if sg is not prev_seg:
            prev_alpha = None
        face = smooth_face(s)
        prior = head_prior(img.shape[0], img.shape[1], *face)
        alpha = person_alpha(img, prev_alpha, prior)
        prev_alpha, prev_seg = alpha, sg
        comp, pad_top = compose_source(img, alpha)
        M = frame_transform(t, shot_at(t), img.shape[:2], pad_top, face)
        fr = cv2.warpAffine(comp, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        blur = cv2.GaussianBlur(fr, (0, 0), 1.2)
        fr = np.clip(fr + (fr - blur) * 0.6, 0, 1)  # sharpen (source is 720p)
        fr = fr * MULT + GRAINS[idx % 4]
        fr = np.clip(fr, 0, 1).astype(np.float32)
        draw_overlays(fr, t)
        out8 = (np.clip(fr, 0, 1) * 255 + 0.5).astype(np.uint8)
        if PREVIEW:
            Image.fromarray(out8).save(os.path.join(OUT, f"preview_{t:06.2f}.jpg"), quality=90)
        else:
            vf = av.VideoFrame.from_ndarray(out8, format="rgb24")
            for p in vs.encode(vf):
                outc.mux(p)
            if idx % 150 == 0:
                print(f"frame {idx}/{len(want)}  t={t:.1f}s", flush=True)
    c.close()

    if not PREVIEW:
        for p in vs.encode():
            outc.mux(p)
        y = build_audio()
        n = int(DUR * 48000)
        y = y[:, :n] if y.shape[1] >= n else np.pad(y, ((0, 0), (0, n - y.shape[1])))
        pts = 0
        for i in range(0, n, 1024):
            blk = np.ascontiguousarray(y[:, i:i + 1024])
            af = av.AudioFrame.from_ndarray(blk, format="fltp", layout="stereo")
            af.sample_rate = 48000
            af.pts = pts
            pts += blk.shape[1]
            for p in as_.encode(af):
                outc.mux(p)
        for p in as_.encode():
            outc.mux(p)
        outc.close()
        print("DONE", OUT, f"{DUR:.1f}s")


def write_wav(path, y):
    import wave
    pcm = (np.clip(y.T, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
        w.writeframes(pcm.tobytes())


print(f"segments={len(SEGS)} shots={len(SHOTS)} duration={DUR:.1f}s levels(noise,speech)={LEVELS}")
if "--audio-only" in sys.argv:
    # QA pass: final mix + voice-only mix, plus the cut list (fast, no video)
    os.makedirs(OUT, exist_ok=True)
    write_wav(os.path.join(OUT, "mix.wav"), build_audio())
    plan["SFX"] = False
    write_wav(os.path.join(OUT, "voice_only.wav"), build_audio())
    json.dump(SEGS, open(os.path.join(OUT, "segments.json"), "w"), indent=1)
    print("AUDIO QA written to", OUT)
else:
    render()
