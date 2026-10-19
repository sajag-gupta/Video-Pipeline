# Workflow: recording → upload-ready Short

## 0. Record (see RECORDING_GUIDE.md)
Rear camera or mirroring off, phone propped at eye level, face a window, mic 20–30 cm, 1080p30.
Drop the file into `input/`.

## 1. Inspect
```
vp.py audio-check input/take.mp4 work/take      # level, noise floor, clipping, pauses, transcript + word timings
vp.py analyze     input/take.mp4 work/take      # metadata, 1 fps frames, contact_sheet.jpg
```
Look at `contact_sheet.jpg`: is it rotated / mirrored? Where is the face? What's behind you?
Optional: `vp.py bg-test input/take.mp4 12 work/take/bg.jpg` to preview background replacement.

## 2. Plan (`plans/take.py`)
Copy `plans/example_plan.py`. Read `work/take/audio_report.json` → `words` (each has `w`, `s`, `e` in seconds).
- **KEEP**: ranges of whole sentences. Drop false starts, repeated words, off-script tangents.
- **CAPTIONS**: 1–4 words per chunk; correct misheard words; punctuation helps reading.
- **STATS**: every spoken money figure / % → big number (replaces the caption while shown).
- **HEADERS**: "First…/Second…/Third…" and the key takeaway → sans line + serif accent word.
- **BADGES**: lists of 2–3 concrete things → icons (`ring3` or `pair`).
- **CARD**: the payoff summary at the end.
- **DISCLAIMER**: for any investing talk ("Personal experience · Not financial advice").

## 3. Preview stills
```
vp.py preview plans/take.py work/take_prev --preview 1 8 15 30 45 60
```
Check: captions don't cover the mouth, badges don't collide with captions, card doesn't cover the face,
background cut-out has no wall leaks. Tweak constants in render_short.py (CAP_Y, ring position, ANGLES) if needed.

## 4. Audio QA (fast; no video)
```
vp.py audio-qa plans/take.py work/take_qa
vp.py qa-cuts  work/take_qa
```
Every cut line should end with a complete sentence and have no `<-- loud at cut` flag.
`work/take_qa/mix.wav` (with SFX) and `voice_only.wav` are there to listen to.

## 5. Render + verify
```
vp.py render plans/take.py output/take_short.mp4
```
~0.8 s per output frame on an 8-core laptop CPU (90 s ≈ 35 min). Verify duration, audio peak, and a frame sheet.

## 6. Upload
- YouTube Shorts ≤ 3 min; title = the hook; add the "Not financial advice" line in the description for money topics.
- Instagram: upload natively (no other-app watermarks); consider Trial Reels for tests.
- Tick "altered or synthetic content" / "AI info" only if AI-generated realistic people or voices are used.

## Motion graphics / faceless videos
See HYPERFRAMES.md. Render compositions with `vp.py hf-frames` + `vp.py encode`.

## AI generation (B-roll, voice clone, talking video)
See GPU_CLOUD.md. Generated clips go into `assets/broll/` and can be cut in as overlays.
