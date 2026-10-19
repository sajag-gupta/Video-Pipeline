"""Run the HyperFrames CLI with the Node found by _env (portable tools/node first, else system node).
Usage:
  python hf.py install                 npm install hyperframes/ (local, --ignore-scripts for locked-down PCs)
  python hf.py <args...>               run the hyperframes CLI inside hyperframes/
  python hf.py --cwd <dir> <args...>   run it inside another folder

Note: `hyperframes render` needs FFmpeg on PATH. Where FFmpeg is blocked, render with
scripts/hf_frames.js + scripts/encode_frames.py instead (see docs/HYPERFRAMES.md).
"""
import os, sys, subprocess, json
from _env import ROOT, TOOLS, NODE, CHROME, find_npm_cli

HF_HOME = os.path.join(ROOT, "hyperframes")
if not NODE:
    sys.exit("Node.js not found. Run setup (it installs a portable Node into tools/).")

env = dict(os.environ)
env["PATH"] = os.path.dirname(NODE) + os.pathsep + env.get("PATH", "")
env["npm_config_cache"] = os.path.join(TOOLS, "npm-cache")
env["PUPPETEER_SKIP_DOWNLOAD"] = "1"
if CHROME:
    env.setdefault("PUPPETEER_EXECUTABLE_PATH", CHROME)
    env.setdefault("HYPERFRAMES_BROWSER_PATH", CHROME)


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout[-8000:])
    print(r.stderr[-4000:])
    print("exit", r.returncode)
    return r.returncode


args = sys.argv[1:]
if args and args[0] == "install":
    npm = find_npm_cli(NODE)
    sys.exit(run([NODE, npm, "install", "--ignore-scripts", "--no-fund", "--no-audit"], HF_HOME))

cwd = HF_HOME
if args and args[0] == "--cwd":
    cwd, args = args[1], args[2:]
pkg = json.load(open(os.path.join(HF_HOME, "node_modules", "hyperframes", "package.json")))
bin_rel = pkg["bin"] if isinstance(pkg["bin"], str) else list(pkg["bin"].values())[0]
cli = os.path.join(HF_HOME, "node_modules", "hyperframes", bin_rel)
sys.exit(run([NODE, cli] + args, cwd))
