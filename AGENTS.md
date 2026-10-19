# Instructions for AI agents working in this repo

You are helping a creator turn self-recorded talking-head videos into Shorts/Reels in a documented house style.
Read this whole file before acting. Everything runs through `python vp.py <command>` (use `venv\Scripts\python.exe` on Windows).

## Environment facts (do not re-discover)
- Primary machine: locked-down Windows work laptop. **Unsigned executables are blocked** (ffmpeg.exe, esbuild.exe,
  Git Bash's /usr/bin tools like ls/grep/head). Signed `node.exe`, Chrome, Python and pip packages work.
  → Do video IO with **PyAV** (bundled FFmpeg libs). Never assume an `ffmpeg` binary. Use Python for file ops.
- Corporate TLS inspection: `scripts/_env.py` injects `truststore` so Python trusts the Windows cert store.
  Never disable certificate verification.
- npm installs must use `--ignore-scripts` (postinstall binaries are blocked). GSAP is vendored locally into
  composition folders by setup because the CDN doesn't load in headless Chrome.
- `hyperframes render` requires FFmpeg → use `vp.py hf-frames` + `vp.py encode` instead.
- No local GPU. AI video/voice generation = rented GPU (`vp.py vultr`, costs money) or HF Spaces/Inference (needs credits).
- Phone recordings are often stored rotated (-90) and mirrored (front camera). `render_short.upright()` assumes both;
  check `analyze` frames and adjust if a recording isn't rotated/mirrored.

## The editing workflow (follow in order; never skip QA)
1. `vp.py audio-check <video> work/<name>` → quality + word timestamps (`audio_report.json`).
2. `vp.py analyze <video> work/<name>` → frames + contact sheet. LOOK at the frames (orientation, framing, background).
3. Write `plans/<name>.py` from `plans/example_plan.py`, using the word timestamps:
   - KEEP whole sentences. Cut fillers only where there is a real pause; keep small connecting words ("so", "and",
     "though") whole rather than half-cutting them. Remove off-script tangents.
   - Fix Whisper misspellings in CAPTIONS (e.g. "side piece"→"SIPs"). Captions must match what is said.
   - STATS for spoken numbers, HEADERS for section starts (accent word = the key noun), BADGES for listed items.
4. `vp.py preview plan work/<name>_prev --preview <times>` → check every overlay position against the face.
5. `vp.py audio-qa plan work/<name>_qa` then `vp.py qa-cuts work/<name>_qa` → **every cut must show the full
   sentence ending and no "loud at cut" flags.** Fix KEEP and repeat before rendering.
6. `vp.py render plan output/<name>.mp4` (25–40 min). Then verify: duration, A/V length match, audio peak < 1.0,
   sample frames. Report honestly what you could and couldn't verify (you can't listen).

## Hard-won rules (the user complained when these were violated)
- **Never clip sentence endings.** Whisper word end times are early and start times late; the renderer snaps cuts
  to real silences (`refine_end` / `refine_start` in build_segments). Keep that logic; don't cut on raw timestamps.
- Don't over-compress pacing: pauses > 0.5 s are shortened but keep ~0.15–0.18 s breathing room.
- Sound effects are expected (whoosh on headers, ding on stats, pop on badges, impact on the final number).
- Flag factual inconsistencies in the recording (e.g. a number said two different ways) instead of silently "fixing" audio.
- Long renders: run in background and report progress honestly.

## Style
`styles/finance_story_style.json` holds the learned reference style (cut every ~2.7 s via alternating framing,
warm low-key grade, white bold captions at 55% height, big stat numbers, sans + serif-italic accent headers,
translucent icon badges, closing summary card, no outro). Keep new videos consistent with it.

## Secrets & privacy
- Keys live in `.env` (gitignored) or `tools/*.txt`. Never print, log, or commit them. Never write them into docs.
- The repo is PUBLIC. Never commit recordings, renders, transcripts, personal plans, or anything under input/ work/ output/.
- Creating cloud servers or using paid inference **spends the user's money: get explicit approval with the price first.**
  Always destroy Vultr servers when done (stopped servers still bill). `vultr create` adds a self-destruct timer.
- Uploading the user's face/voice to third-party services needs explicit consent each time.
- AI-generated realistic video/voice of the user must be disclosed on YouTube/Instagram.

## Where things are
See README.md table. Docs: docs/WORKFLOW.md, docs/SETUP.md, docs/HYPERFRAMES.md, docs/GPU_CLOUD.md,
docs/CONTENT_STRATEGY.md, docs/RECORDING_GUIDE.md.
