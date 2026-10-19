# Example edit plan for scripts/render_short.py.  Copy to plans/<video_name>.py and edit.
# ALL TIMES ARE SOURCE SECONDS, taken from the word timestamps that `vp.py audio-check` / `vp.py analyze`
# writes (work/<name>/audio_report.json -> "words"). Personal plans are gitignored; only this example is shared.
#
# How the renderer uses this file:
#   KEEP      -> which parts of the recording survive. Cuts are snapped to REAL silences in the audio
#                (Whisper word edges are often early/late), and pauses > 0.5 s inside a range are shortened.
#   CAPTIONS  -> 1-4 word chunks shown at 55% height (correct Whisper's misspellings here).
#   STATS     -> big numbers that REPLACE the caption while shown (+ "ding" SFX).
#   HEADERS   -> section headers: sans line + serif-italic accent word that appears when spoken (+ whoosh, punch-in zoom).
#   BADGES    -> icon badges (Segoe UI Emoji glyphs rendered white) popping in when each item is said (+ pop SFX).
#   CARD      -> closing summary rows (tick SFX, impact on the last row).
#   DISCLAIMER-> small footer text for a time range.

SRC = r"input/my_recording.mp4"   # path to your talking-head recording (relative to repo root or absolute)

KEEP = [
    # (start, end[, options])   options: {"hard_start": True} / {"hard_end": True} skip silence-snapping on that edge
    (0.75, 7.12, {"hard_start": True}),   # e.g. skip a filler word that runs straight into the first word
    (7.40, 21.70),
    (22.98, 37.53),
]

CAPTIONS = [
    # (start, end, text)
    (0.75, 1.65, "Bangalore."),
    (1.65, 2.57, "Software engineer."),
    (2.57, 4.05, "First job."),
    (5.45, 6.21, "Sounds like"),
    (6.21, 7.12, "a lot, right?"),
]

STATS = [
    dict(s=4.05, e=5.45, text="₹1,00,000/month"),
    dict(s=17.25, e=19.85, text="₹9,500/month", sub="PG rent"),
]

HEADERS = [
    dict(t=14.51, e=16.57, accent_t=15.09, line1="First, my", accent="Stay"),
    # hide_captions=True when the header itself is the spoken sentence
    dict(t=29.01, e=30.85, accent_t=29.83, line1="Second, my", accent="Health"),
]

BADGES = [
    # layout "ring3" (3 items on a ring) or "pair" (2 items with an arrow)
    dict(s=23.01, e=27.08, layout="ring3", items=[
        dict(t=23.01, glyph="\U0001F37D", label="Food"),
        dict(t=23.65, glyph="\U0001F6CF", label="Bed"),
        dict(t=24.27, glyph="\U0001F4F6", label="Wi-Fi"),
    ]),
]

CARD = dict(s=30.0, e=36.0, rows=[
    dict(t=30.0, label="Salary", value="₹1,00,000", color=(255, 255, 255, 255)),
    dict(t=31.5, label="Spent", value="₹40,000", color=(255, 120, 110, 255)),
    dict(t=33.0, label="Saved", value="₹60,000", color=(90, 225, 130, 255)),
])

DISCLAIMER = [(20.0, 30.0, "Personal experience · Not financial advice")]

# SFX = False   # uncomment to render without synthesized sound effects
