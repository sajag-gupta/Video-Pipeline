"""Video-Pipeline command line. One entry point for every step, so any person or LLM agent can drive it.

  python vp.py help
"""
import os, sys, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(ROOT, "scripts")
sys.path.insert(0, S)

COMMANDS = {
    # name: (script, usage, description)
    "doctor":     ("doctor.py", "", "check the workspace is ready"),
    "analyze":    ("analyze.py", "<video> <out_dir>", "metadata + 1 fps frames + contact sheet + word-timed transcript"),
    "reference":  ("analyze_reference.py", "<video> <audio_or_video> <out_dir> [frame_step]", "deep breakdown of a reference Short (cuts, frames, transcript, loudness)"),
    "audio-check":("check_audio.py", "<audio_or_video> <out_dir>", "recording quality: level, noise, clipping, pauses, transcript"),
    "bg-test":    ("test_bg.py", "<video> <time_s> <out.jpg>", "preview background-replacement looks on one frame"),
    "preview":    ("render_short.py", "<plan.py> <out_dir> --preview t1 t2 ...", "render still frames of the edit at output times"),
    "audio-qa":   ("render_short.py", "<plan.py> <out_dir> --audio-only", "fast pass: final mix + voice-only + cut list (no video)"),
    "qa-cuts":    ("qa_cuts.py", "<qa_dir>", "transcribe the edited voice and show both sides of every cut"),
    "render":     ("render_short.py", "<plan.py> <output.mp4>", "full render of the Short (slow: ~0.8 s per frame on CPU)"),
    "hf":         ("hf.py", "<hyperframes args...>", "run the HyperFrames CLI (init, check, docs, catalog, ...)"),
    "hf-frames":  ("hf_frames.js", "<index.html> <frames_dir> [fps]", "render a HyperFrames composition to PNGs with Chrome"),
    "encode":     ("encode_frames.py", "<frames_dir> <out.mp4> [fps] [audio]", "PNG frames -> H.264 MP4 (+ optional audio)"),
    "vultr":      ("vultr_ctl.py", "account|plans|create|status|run|put|get|destroy", "rented GPU server (COSTS MONEY - see docs/GPU_CLOUD.md)"),
    "setup":      ("setup_workspace.py", "[--no-node] [--no-whisper] [--skills]", "re-run workspace setup"),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("help", "-h", "--help"):
        print(__doc__.strip(), "\n")
        for k, (_, u, d) in COMMANDS.items():
            print(f"  {k:12s} {u:52s} {d}")
        print("\nTypical flow: analyze -> write plans/<name>.py -> preview -> audio-qa -> qa-cuts -> render  (see docs/WORKFLOW.md)")
        return
    name, args = sys.argv[1], sys.argv[2:]
    if name not in COMMANDS:
        sys.exit(f"unknown command {name!r}; try: python vp.py help")
    script = os.path.join(S, COMMANDS[name][0])
    if name == "audio-qa" and "--audio-only" not in args:
        args.append("--audio-only")
    if script.endswith(".js"):
        from _env import NODE, CHROME
        if not NODE:
            sys.exit("Node.js not found - run setup")
        env = dict(os.environ, **({"HYPERFRAMES_BROWSER_PATH": CHROME} if CHROME else {}))
        sys.exit(subprocess.call([NODE, script] + args, env=env))
    sys.exit(subprocess.call([sys.executable, script] + args))


if __name__ == "__main__":
    main()
