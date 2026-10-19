# HyperFrames (motion graphics, faceless videos, graphic B-roll)

[HyperFrames](https://github.com/heygen-com/hyperframes) turns HTML + GSAP animations into video.
Use it for: number count-ups, charts, kinetic type, app/phone mock-ups, receipts, maps, title cards, faceless explainers.
Not for: photorealistic footage (that's Wan/Veo — see GPU_CLOUD.md) or your talking head (that's render_short.py).

## Render without FFmpeg
```
vp.py hf-frames hyperframes/templates/hf-starter/index.html work/hf_frames 30
vp.py encode    work/hf_frames output/hf_starter.mp4 30 [optional_audio.wav]
```
`hf_frames.js` opens the composition in your Chrome, seeks `window.__timelines["main"]` frame by frame,
toggles `data-start/data-duration` clip visibility, and screenshots each frame.
Limitations vs the official renderer: no embedded `<video>`/`<audio>` playback inside compositions
(add audio at `encode` time), no shader transitions. With FFmpeg available, `vp.py hf render` works normally.

## New composition
1. Copy `hyperframes/templates/hf-starter/` to a new folder (keep `vendor/gsap.min.js`; setup copies it into every template).
2. Edit `index.html`: root `data-composition-id="main"`, `data-width=1080`, `data-height=1920`, `data-duration`;
   register one paused GSAP timeline at `window.__timelines["main"]`. No `Math.random()`/`Date.now()`/network.
3. Lint/docs: `vp.py hf --cwd <folder> lint`, `vp.py hf docs gsap`, `vp.py hf catalog` (≈400 ready blocks).

## Agent skills
`vp.py hf skills update` installs HyperFrames skills for Claude Code / Codex / Cursor / Gemini CLI into
`~/.claude/skills` and `~/.agents/skills` (they run with full agent permissions — review them).
