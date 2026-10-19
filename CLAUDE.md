# Claude Code notes

Read **AGENTS.md** first — it is the single source of truth for this repo (environment limits, workflow, rules).

Claude-specific extras:
- HyperFrames agent skills can be installed with `python vp.py hf skills update` (or `setup.ps1 -Skills`);
  they load in the next session. Use them for motion-graphics compositions under `hyperframes/templates/`.
- Run long renders with background execution and check progress from the log, not by polling in a tight loop.
- Use the Read tool on `work/<name>/contact_sheet.jpg` / preview sheets to actually look at frames.
