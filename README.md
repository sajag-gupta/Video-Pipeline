# Video-Pipeline

Turn a phone recording of yourself into a polished YouTube Short / Instagram Reel — cuts, captions,
big ₹ numbers, section headers, icon badges, background replacement, colour grade and sound effects —
with one plan file and one command. Plus HyperFrames motion graphics and optional rented-GPU AI generation.

Runs on a locked-down Windows work laptop: **no ffmpeg.exe, no admin rights, no GPU needed.**
(PyAV bundles FFmpeg's libraries; Node is installed portably; corporate TLS inspection is handled.)

## Quick start

```powershell
git clone https://github.com/sajag-gupta/Video-Pipeline.git
cd Video-Pipeline
powershell -ExecutionPolicy Bypass -File setup.ps1
venv\Scripts\python.exe vp.py doctor
```

macOS / Linux: `./setup.sh` then `venv/bin/python vp.py doctor`.

Setup creates `venv/`, installs Python packages, downloads the MediaPipe + Whisper models into `models/`,
installs a portable Node 22 into `tools/` (only if you don't have Node 22+), installs HyperFrames into
`hyperframes/node_modules`, copies `.env.example` to `.env`, and runs the doctor. Re-running is safe.

Requirements: Python 3.11–3.13, Chrome or Edge (for HyperFrames), ~3 GB disk.

## Make a Short (the 6-step loop)

```powershell
# 1. Put the recording in input/ and inspect it (quality, transcript with word timings)
venv\Scripts\python.exe vp.py audio-check input\take1.mp4 work\take1
venv\Scripts\python.exe vp.py analyze     input\take1.mp4 work\take1

# 2. Write the edit plan from the word timings (copy the example)
copy plans\example_plan.py plans\take1.py      # then edit SRC, KEEP, CAPTIONS, STATS, ...

# 3. Check the look on a few frames
venv\Scripts\python.exe vp.py preview plans\take1.py work\take1_preview --preview 1 10 25 40

# 4. Check the cuts by ear-proxy (fast, no video): every sentence must end cleanly
venv\Scripts\python.exe vp.py audio-qa plans\take1.py work\take1_qa
venv\Scripts\python.exe vp.py qa-cuts  work\take1_qa

# 5. Render (slow on CPU: ~25-40 min for 90 s)
venv\Scripts\python.exe vp.py render plans\take1.py output\take1_short.mp4
```

Full details: [docs/WORKFLOW.md](docs/WORKFLOW.md). All commands: `vp.py help`.

## What's in here

| Path | What |
|---|---|
| `vp.py` | single CLI for every step |
| `scripts/render_short.py` | the editor: cuts at real silences, face-tracked reframing, background replacement, grade, captions/stats/headers/badges/card, synthesized SFX, loudness |
| `scripts/analyze*.py`, `check_audio.py`, `qa_cuts.py` | analysis + QA tools |
| `scripts/hf.py`, `hf_frames.js`, `encode_frames.py` | HyperFrames CLI wrapper + an FFmpeg-free renderer |
| `scripts/vultr_ctl.py`, `remote/*.sh` | rent a GPU, run Wan2.2 (B-roll, talking video) + Chatterbox (voice clone), auto-destroy |
| `styles/finance_story_style.json` | the learned reference style (pacing, captions, grade, graphics) |
| `plans/example_plan.py` | documented edit-plan template |
| `docs/` | workflow, setup, HyperFrames, GPU cloud, content strategy, recording guide |
| `AGENTS.md` | instructions for any AI coding agent (Claude, GPT, Gemini, …) |

## Privacy

`.gitignore` keeps **keys (.env), your recordings, renders, transcripts and personal plans** out of git.
Only code, docs, the style template and the example plan are shared.

## Licence notes

Code here: MIT (see LICENSE). Third-party: HyperFrames (Apache-2.0), GSAP (GSAP standard licence, installed
via npm, not redistributed), MediaPipe models (Apache-2.0), Whisper/faster-whisper (MIT), Wan2.2 (Apache-2.0),
Chatterbox (MIT). Avoid XTTS-v2 / stock F5-TTS weights for monetized content (non-commercial licences).
