#!/usr/bin/env bash
# Run ON the rented GPU server (Ubuntu 22.04, NVIDIA GPU). Installs Wan2.2 + Chatterbox voice cloning.
#   python vp.py vultr put remote/setup_gpu.sh /root/setup_gpu.sh
#   python vp.py vultr run "bash /root/setup_gpu.sh"
# STATUS: written from the upstream READMEs, not yet run end-to-end on a server. Check output carefully.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
WORK=/root/gen
mkdir -p $WORK && cd $WORK

echo "== GPU check"
if ! command -v nvidia-smi >/dev/null || ! nvidia-smi >/dev/null 2>&1; then
  echo "No working NVIDIA driver - installing (server will need a reboot, then re-run this script)"
  apt-get update -y && apt-get install -y ubuntu-drivers-common && ubuntu-drivers autoinstall
  echo "REBOOT NEEDED: run 'reboot', wait ~2 min, then re-run setup_gpu.sh"; exit 2
fi
nvidia-smi --query-gpu=name,memory.total --format=csv

echo "== system packages"
apt-get update -y
apt-get install -y python3-venv python3-pip git ffmpeg

echo "== Wan2.2"
[ -d Wan2.2 ] || git clone --depth 1 https://github.com/Wan-Video/Wan2.2.git
python3 -m venv venv && source venv/bin/activate
pip install --upgrade pip wheel
pip install "torch>=2.4" torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
# flash_attn is optional and slow to build; skip it if it fails
grep -v -i flash_attn Wan2.2/requirements.txt > /tmp/wan_req.txt
pip install -r /tmp/wan_req.txt
pip install "huggingface_hub[cli]"
[ -f Wan2.2/requirements_s2v.txt ] && pip install -r Wan2.2/requirements_s2v.txt || true

echo "== model weights (TI2V-5B for B-roll ~30 GB; S2V-14B for talking video, large)"
huggingface-cli download Wan-AI/Wan2.2-TI2V-5B --local-dir $WORK/Wan2.2-TI2V-5B
if [ "${WITH_S2V:-1}" = "1" ]; then
  huggingface-cli download Wan-AI/Wan2.2-S2V-14B --local-dir $WORK/Wan2.2-S2V-14B
fi

echo "== Chatterbox (voice cloning, MIT licence)"
python3 -m venv $WORK/tts && $WORK/tts/bin/pip install --upgrade pip chatterbox-tts

echo "SETUP DONE"
