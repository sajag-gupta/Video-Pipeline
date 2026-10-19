# Setup details & troubleshooting

## One command
- Windows: `powershell -ExecutionPolicy Bypass -File setup.ps1` (flags: `-NoNode`, `-NoWhisper`, `-Skills`)
- macOS/Linux: `./setup.sh` (flags: `--no-node`, `--no-whisper`, `--skills`)

Then `vp.py doctor` must end with `READY`.

## What gets installed where (all inside the repo, all gitignored)
| Folder | Contents |
|---|---|
| `venv/` | Python packages from requirements.txt |
| `models/mediapipe/` | selfie segmentation + face detector (.tflite, from Google's MediaPipe model storage) |
| `models/hf/` | Whisper `small` (faster-whisper) and any Hugging Face downloads (`HF_HOME`) |
| `tools/node-v22*/` | portable Node.js (checksum-verified from nodejs.org), only if no Node 22+ on the machine |
| `tools/npm-cache/` | npm cache |
| `hyperframes/node_modules/` | HyperFrames CLI, GSAP, puppeteer-core |

## Fonts
The renderer uses Segoe UI (bold/black/semibold), Georgia Bold Italic and Segoe UI Emoji (Windows).
On macOS/Linux it falls back to Inter/DejaVu/Noto if present. To force specific fonts, drop TTFs into
`assets/fonts/` with the Windows file names (`segoeuib.ttf`, `seguibl.ttf`, `seguisb.ttf`, `georgiaz.ttf`,
`seguiemj.ttf`) or any of the fallback names listed in `scripts/_env.py`.

## Common problems
| Symptom | Fix |
|---|---|
| `Permission denied` running an .exe | Machine blocks unsigned binaries. Use the Python/PyAV path (default here). |
| SSL `CERTIFICATE_VERIFY_FAILED` | Corporate TLS inspection: `truststore` must be installed (it is in requirements). |
| npm `spawnSync ... esbuild.exe UNKNOWN` | Install with `--ignore-scripts` (setup does). |
| HyperFrames `FFmpeg not found` | Expected without FFmpeg — render with `vp.py hf-frames` + `vp.py encode`. |
| Headless page never ready | GSAP must load from `vendor/gsap.min.js`, not a CDN; re-run setup to copy it. |
| faster-whisper `metadata_errors` TypeError | Pass decoded numpy audio (scripts already do) — PyAV/faster-whisper version mismatch. |
| Phone video sideways / text mirrored | `upright()` in render_short.py rotates -90 and flips; adjust for your phone. |
