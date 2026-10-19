#!/usr/bin/env bash
# Generate B-roll clips with Wan2.2 TI2V-5B from a prompt list (one prompt per line).
#   python vp.py vultr put prompts.txt /root/gen/prompts.txt
#   python vp.py vultr run "bash /root/gen/broll_batch.sh /root/gen/prompts.txt"
#   python vp.py vultr get /root/gen/broll.tar.gz output/broll.tar.gz
# Size 704*1280 = vertical 9:16-ish for Shorts. ~5 s clips. STATUS: untested end-to-end.
set -euo pipefail
PROMPTS=${1:-/root/gen/prompts.txt}
cd /root/gen && source venv/bin/activate
mkdir -p broll
i=0
while IFS= read -r prompt; do
  [ -z "$prompt" ] && continue
  i=$((i+1))
  echo "== [$i] $prompt"
  python Wan2.2/generate.py --task ti2v-5B --size 704*1280 --ckpt_dir ./Wan2.2-TI2V-5B \
    --offload_model True --convert_model_dtype --t5_cpu \
    --prompt "$prompt" --save_file "broll/clip_$(printf %02d $i).mp4"
done < "$PROMPTS"
tar czf broll.tar.gz broll
echo "BATCH DONE: $i clips -> /root/gen/broll.tar.gz"
