"""Check that the workspace is ready. Prints OK / MISSING per component and what it affects."""
import os, sys, json, shutil, subprocess, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import ROOT, MODELS, NODE, CHROME, FONTS  # noqa: E402

ok = True


def line(good, name, detail="", needed_for=""):
    global ok
    ok &= good or not needed_for.startswith("REQUIRED")
    print(f"  {'OK     ' if good else 'MISSING'}  {name:28s} {detail}" + ("" if good else f"   -> {needed_for}"))


print("Video-Pipeline doctor\n")
print(f"  python {sys.version.split()[0]}  ({sys.executable})")
for mod, req in [("av", "REQUIRED: all video IO"), ("numpy", "REQUIRED"), ("cv2", "REQUIRED"), ("PIL", "REQUIRED"),
                 ("mediapipe", "REQUIRED: background removal + face tracking"), ("faster_whisper", "REQUIRED: transcripts/captions"),
                 ("huggingface_hub", "optional: cloud generation"), ("gradio_client", "optional: HF Spaces"),
                 ("paramiko", "optional: Vultr GPU"), ("truststore", "optional: corporate TLS")]:
    try:
        m = importlib.import_module(mod); line(True, mod, getattr(m, "__version__", ""))
    except Exception as e:
        line(False, mod, str(e)[:60], req)

try:
    import av
    line("libx264" in av.codecs_available and "aac" in av.codecs_available, "H.264/AAC encoders (PyAV)", "", "REQUIRED: export")
except Exception:
    pass

for n in ["selfie_multiclass_256x256.tflite", "blaze_face_short_range.tflite"]:
    line(os.path.exists(os.path.join(MODELS, "mediapipe", n)), f"model {n[:24]}", "", "REQUIRED: run setup")
for k, v in FONTS.items():
    line(bool(v), f"font {k}", v or "", "REQUIRED: put a TTF in assets/fonts (see docs/SETUP.md)")

line(bool(NODE), "node", NODE or "", "optional: HyperFrames")
hf = os.path.join(ROOT, "hyperframes", "node_modules", "hyperframes")
line(os.path.exists(hf), "hyperframes (npm)", "", "optional: HyperFrames motion graphics")
line(bool(CHROME), "chrome/edge", CHROME or "", "optional: HyperFrames rendering")
line(bool(shutil.which("ffmpeg")), "ffmpeg on PATH", "(not needed by this pipeline)", "optional: only for `hyperframes render`")

print("\nSecrets (.env / env vars):")
for k, use in [("HF_TOKEN", "Hugging Face inference/Spaces"), ("VULTR_API_KEY", "Vultr GPU server")]:
    has = bool(os.environ.get(k)) or (k == "VULTR_API_KEY" and os.path.exists(os.path.join(ROOT, "tools", "vultr_api_key.txt"))) \
        or (k == "HF_TOKEN" and os.path.exists(os.path.expanduser("~/.cache/huggingface/token")))
    print(f"  {'set    ' if has else 'not set'}  {k:14s} ({use})")

print("\nREADY" if ok else "\nSome REQUIRED items are missing - re-run setup.")
sys.exit(0 if ok else 1)
