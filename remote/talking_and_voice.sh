#!/usr/bin/env bash
# Two generation jobs on the GPU server. STATUS: untested end-to-end; flags follow the upstream READMEs.
#
# 1) Voice clone (Chatterbox): new sentence in your voice from a 1-3 min clean reference recording
#    bash talking_and_voice.sh voice /root/gen/my_voice_ref.wav "Text to say" /root/gen/out_voice.wav
#
# 2) Talking video (Wan2.2-S2V-14B): your photo + an audio file (your REAL recording or the cloned voice)
#    bash talking_and_voice.sh talk /root/gen/me.jpg /root/gen/line.wav "a young man talking to camera, warm indoor light" /root/gen/talk.mp4
#
# Disclose AI-generated realistic people/voices on YouTube ("altered or synthetic content") and Instagram ("AI info").
set -euo pipefail
cd /root/gen
case "$1" in
  voice)
    REF=$2; TEXT=$3; OUT=$4
    $PWD/tts/bin/python - "$REF" "$TEXT" "$OUT" <<'PY'
import sys, torchaudio
from chatterbox.tts import ChatterboxTTS
ref, text, out = sys.argv[1:4]
m = ChatterboxTTS.from_pretrained(device="cuda")
wav = m.generate(text, audio_prompt_path=ref)
torchaudio.save(out, wav, m.sr)
print("saved", out)
PY
    ;;
  talk)
    IMG=$2; AUD=$3; PROMPT=$4; OUT=$5
    source venv/bin/activate
    python Wan2.2/generate.py --task s2v-14B --size 704*1024 --ckpt_dir ./Wan2.2-S2V-14B \
      --offload_model True --convert_model_dtype \
      --prompt "$PROMPT" --image "$IMG" --audio "$AUD" --save_file "$OUT"
    ;;
  *) echo "usage: $0 voice|talk ..."; exit 1;;
esac
