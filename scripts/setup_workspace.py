"""Workspace installer, called by setup.ps1 / setup.sh after the venv exists. Safe to re-run (idempotent).

Steps: folders -> .env -> MediaPipe models -> Whisper model -> portable Node (if no node) -> HyperFrames + GSAP -> doctor.
Flags: --no-node (skip Node/HyperFrames), --no-whisper (skip whisper pre-download), --skills (install HyperFrames agent skills)
"""
import os, sys, io, re, json, shutil, hashlib, zipfile, tarfile, platform, subprocess, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import ROOT, TOOLS, MODELS, IS_WIN, IS_MAC, find_node, find_npm_cli, find_chrome  # noqa: E402

ARGS = set(sys.argv[1:])
NODE_MAJOR = "22"
MP_MODELS = {
    "selfie_multiclass_256x256.tflite": "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite",
    "selfie_segmenter.tflite": "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite",
    "blaze_face_short_range.tflite": "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite",
}


def step(msg):
    print(f"\n==> {msg}", flush=True)


def fetch(url):
    with urllib.request.urlopen(url, timeout=600) as r:
        return r.read()


def folders():
    step("Folders")
    for d in ["input", "work", "output", "plans", "styles", "models/mediapipe", "models/hf", "tools", "assets/fonts", "assets/broll"]:
        os.makedirs(os.path.join(ROOT, d), exist_ok=True)
    env, ex = os.path.join(ROOT, ".env"), os.path.join(ROOT, ".env.example")
    if not os.path.exists(env) and os.path.exists(ex):
        shutil.copy(ex, env)
        print("created .env from .env.example (fill in keys you want to use)")


def mediapipe_models():
    step("MediaPipe models (segmentation + face detection)")
    for name, url in MP_MODELS.items():
        p = os.path.join(MODELS, "mediapipe", name)
        if os.path.exists(p) and os.path.getsize(p) > 100_000:
            print("ok", name); continue
        data = fetch(url)
        open(p, "wb").write(data)
        print(f"downloaded {name} ({len(data) / 1e6:.1f} MB)")


def whisper_model():
    if "--no-whisper" in ARGS:
        return
    step("Whisper 'small' speech model (~470 MB, first time only)")
    from faster_whisper import WhisperModel
    WhisperModel("small", device="cpu", compute_type="int8")
    print("ok")


def portable_node():
    """Install Node 22 into tools/ when no suitable node exists (verified against nodejs.org SHASUMS)."""
    node = find_node()
    if node:
        v = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
        if v.startswith("v") and int(v[1:].split(".")[0]) >= int(NODE_MAJOR):
            print("ok node", v, node); return node
    step(f"Portable Node.js {NODE_MAJOR} -> tools/")
    base = f"https://nodejs.org/dist/latest-v{NODE_MAJOR}.x/"
    idx = fetch(base).decode()
    arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
    osn = "win" if IS_WIN else ("darwin" if IS_MAC else "linux")
    ext = "zip" if IS_WIN else "tar.gz"
    name = re.search(rf"node-v{NODE_MAJOR}[\d.]+-{osn}-{arch}\.{ext}", idx).group(0)
    data = fetch(base + name)
    if hashlib.sha256(data).hexdigest() not in fetch(base + "SHASUMS256.txt").decode():
        sys.exit("Node download checksum mismatch - aborting")
    if ext == "zip":
        zipfile.ZipFile(io.BytesIO(data)).extractall(TOOLS)
    else:
        tarfile.open(fileobj=io.BytesIO(data), mode="r:gz").extractall(TOOLS)
    node = find_node()
    print("installed", name, "->", node)
    return node


def hyperframes(node):
    step("HyperFrames (npm install --ignore-scripts) + GSAP vendor copy")
    npm = find_npm_cli(node)
    env = dict(os.environ, PATH=os.path.dirname(node) + os.pathsep + os.environ.get("PATH", ""),
               npm_config_cache=os.path.join(TOOLS, "npm-cache"), PUPPETEER_SKIP_DOWNLOAD="1")
    hf = os.path.join(ROOT, "hyperframes")
    r = subprocess.run([node, npm, "install", "--ignore-scripts", "--no-fund", "--no-audit"], cwd=hf, env=env,
                       capture_output=True, text=True)
    print(r.stdout[-800:], r.stderr[-800:])
    if r.returncode:
        print("WARNING: npm install failed - HyperFrames features unavailable"); return
    gsap = os.path.join(hf, "node_modules", "gsap", "dist", "gsap.min.js")
    for tdir in [os.path.join(hf, "templates", d) for d in os.listdir(os.path.join(hf, "templates"))]:
        os.makedirs(os.path.join(tdir, "vendor"), exist_ok=True)
        shutil.copy(gsap, os.path.join(tdir, "vendor", "gsap.min.js"))
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "hf.py"), "telemetry", "disable"], capture_output=True)
    if "--skills" in ARGS:
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "hf.py"), "skills", "update"])


def main():
    folders()
    mediapipe_models()
    whisper_model()
    if "--no-node" not in ARGS:
        try:
            node = portable_node()
            hyperframes(node)
        except Exception as e:
            print("WARNING: Node/HyperFrames step failed:", e)
    step("Doctor")
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "doctor.py")])


if __name__ == "__main__":
    main()
