"""Shared environment helpers: repo paths, .env secrets, Node/Chrome discovery, fonts, corporate TLS.

Import from any script:  from _env import ROOT, NODE, CHROME, FONTS
"""
import os, sys, glob, shutil, platform

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
MODELS = os.path.join(ROOT, "models")
IS_WIN = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"


def load_dotenv(path=os.path.join(ROOT, ".env")):
    """Minimal .env loader (KEY=VALUE lines). Real environment variables win."""
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if v and k.strip() not in os.environ:
            os.environ[k.strip()] = v


load_dotenv()
os.environ.setdefault("HF_HOME", os.path.join(MODELS, "hf"))  # model cache lives inside the repo (gitignored)
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# Corporate networks often re-sign TLS with their own root CA: trust the OS certificate store.
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass


def find_node():
    """Portable Node in tools/ first (installed by setup), else system node."""
    pats = ["node-v*-win-x64/node.exe"] if IS_WIN else ["node-v*-*/bin/node"]
    for p in pats:
        hits = sorted(glob.glob(os.path.join(TOOLS, p)))
        if hits:
            return hits[-1]
    return shutil.which("node")


def find_npm_cli(node):
    if not node:
        return None
    d = os.path.dirname(node)
    for c in [os.path.join(d, "node_modules", "npm", "bin", "npm-cli.js"),
              os.path.join(os.path.dirname(d), "lib", "node_modules", "npm", "bin", "npm-cli.js")]:
        if os.path.exists(c):
            return c
    return None


def find_chrome():
    env = os.environ.get("HYPERFRAMES_BROWSER_PATH") or os.environ.get("CHROME_PATH")
    if env and os.path.exists(env):
        return env
    cands = []
    if IS_WIN:
        for base in [os.environ.get("PROGRAMFILES", r"C:\Program Files"), os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                     os.environ.get("LOCALAPPDATA", "")]:
            cands += [os.path.join(base, r"Google\Chrome\Application\chrome.exe"), os.path.join(base, r"Microsoft\Edge\Application\msedge.exe")]
    elif IS_MAC:
        cands = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    else:
        cands = [shutil.which(x) for x in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]]
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


NODE = find_node()
CHROME = find_chrome()


def _font(*names):
    dirs = []
    if IS_WIN:
        dirs = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")]
    elif IS_MAC:
        dirs = ["/System/Library/Fonts", "/System/Library/Fonts/Supplemental", "/Library/Fonts", os.path.expanduser("~/Library/Fonts")]
    else:
        dirs = ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts")]
    dirs.insert(0, os.path.join(ROOT, "assets", "fonts"))  # drop custom fonts here to override
    for n in names:
        for d in dirs:
            hits = glob.glob(os.path.join(d, "**", n), recursive=True)
            if hits:
                return hits[0]
    return None


# Windows names first, then macOS / Linux equivalents
FONTS = {
    "bold": _font("segoeuib.ttf", "Inter-Bold.ttf", "HelveticaNeue.ttc", "DejaVuSans-Bold.ttf"),
    "black": _font("seguibl.ttf", "Inter-Black.ttf", "Arial Black.ttf", "DejaVuSans-Bold.ttf"),
    "semi": _font("seguisb.ttf", "Inter-SemiBold.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"),
    "serif_italic": _font("georgiaz.ttf", "Georgia Bold Italic.ttf", "PlayfairDisplay-BoldItalic.ttf", "DejaVuSerif-BoldItalic.ttf"),
    "emoji": _font("seguiemj.ttf", "NotoEmoji-Regular.ttf", "Apple Color Emoji.ttc", "NotoColorEmoji.ttf"),
}


def require_fonts():
    missing = [k for k, v in FONTS.items() if not v]
    if missing:
        sys.exit(f"Missing fonts {missing}. Put TTFs in assets/fonts/ (see docs/SETUP.md).")
