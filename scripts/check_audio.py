"""Voice recording quality check: level, noise floor, clipping, pauses, pace, transcript.
Usage: python check_audio.py <audio_file> <output_dir>
"""
import os, sys, json, av
import _env  # noqa: F401  (loads .env, repo model cache, OS cert store)
import numpy as np

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

c = av.open(src)
st = c.streams.audio[0]
info = {"codec": st.codec_context.name, "rate": st.rate, "channels": st.codec_context.channels,
        "bitrate_kbps": round((st.bit_rate or c.bit_rate or 0) / 1000)}
rs = av.AudioResampler(format="flt", layout="mono", rate=16000)
chunks = []
bad_packets = 0
for pk in c.demux(st):
    try:
        frames = pk.decode()
    except av.error.InvalidDataError:
        bad_packets += 1  # skip a corrupt packet instead of failing the whole file
        continue
    for fr in frames:
        for r in rs.resample(fr):
            chunks.append(r.to_ndarray().reshape(-1))
info["bad_packets"] = bad_packets
for r in rs.resample(None):
    chunks.append(r.to_ndarray().reshape(-1))
c.close()
a = np.concatenate(chunks).astype(np.float32)
dur = len(a) / 16000

win = 800  # 50 ms
rms = np.array([np.sqrt(np.mean(a[i:i + win] ** 2)) + 1e-9 for i in range(0, len(a) - win, win)])
db = 20 * np.log10(rms)
speech_db = np.percentile(db, 90)
noise_db = np.percentile(db, 10)
peak = float(np.max(np.abs(a)))
clip_pct = float(np.mean(np.abs(a) > 0.99) * 100)

# Pauses: runs below noise+6 dB longer than 0.6 s
thr = noise_db + 6
pauses, run = [], 0
for i, x in enumerate(db):
    if x < thr:
        run += 1
    else:
        if run * 0.05 >= 0.6:
            pauses.append((round((i - run) * 0.05, 2), round(run * 0.05, 2)))
        run = 0

from faster_whisper import WhisperModel
model = WhisperModel("small", device="cpu", compute_type="int8")
segs, tinfo = model.transcribe(a, word_timestamps=True, vad_filter=True)
words, lines = [], []
for s in segs:
    lines.append({"s": round(s.start, 2), "e": round(s.end, 2), "text": s.text.strip(),
                  "avg_logprob": round(s.avg_logprob, 2)})
    for w in s.words:
        words.append({"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2), "p": round(w.probability, 2)})
speech_time = sum(w["e"] - w["s"] for w in words)
low_conf = [w for w in words if w["p"] < 0.5]

report = {"file": info, "duration_s": round(dur, 1), "speech_level_db": round(float(speech_db), 1),
          "noise_floor_db": round(float(noise_db), 1), "snr_db": round(float(speech_db - noise_db), 1),
          "peak": round(peak, 3), "clipping_pct": round(clip_pct, 3),
          "wpm": round(len(words) / (dur / 60)), "pauses_over_0.6s": pauses,
          "low_confidence_words": low_conf, "segments": lines, "words": words}
json.dump(report, open(os.path.join(out, "audio_report.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

for k in ["file", "duration_s", "speech_level_db", "noise_floor_db", "snr_db", "peak", "clipping_pct", "wpm"]:
    print(k, report[k])
print("pauses", len(pauses), pauses)
print("low_conf", [(w["w"], w["s"], w["p"]) for w in low_conf])
for l in lines:
    print(f"[{l['s']:5.1f}-{l['e']:5.1f}] ({l['avg_logprob']}) {l['text']}")
