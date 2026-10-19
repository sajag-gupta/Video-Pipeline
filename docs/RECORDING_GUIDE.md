# Recording guide (the edit can't fix what the camera didn't capture)

| Do | Why |
|---|---|
| Rear camera, or turn off "mirror front camera" | Avoids mirrored text (the renderer assumes mirrored + rotated phone files; check) |
| Prop the phone at eye level; don't hand-hold | Stabilisation helps, but crops and can't fix motion blur |
| Face a window or lamp (light on your face) | Less noise, less blur, better background cut-out |
| Wipe the lens; tap your face to lock focus | Real blur is unfixable |
| Mic 20–30 cm away, normal voice | Clipping/distortion is unfixable (keep peaks below max) |
| Fan/AC off, room with soft furnishings | Steady noise is removable; echo and traffic only partly |
| 1080p, 30 fps | Matches the 1080×1920 export |
| Pause ~1 s between sentences; repeat a fluffed line | Clean cut points; the edit keeps the best take |
| Turn head/chair slightly at each new point | Gives the alternating-angle look of the reference |
| Plain background is fine | The renderer replaces it with a warm studio look |

Audio-only recordings (for faceless videos or S2V talking video) follow the same mic rules.
Run `vp.py audio-check <file> work/<name>` right after recording — it reports clipping, noise and pauses in a minute.
