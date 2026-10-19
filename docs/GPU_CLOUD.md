# AI generation on rented GPUs (B-roll, voice clone, talking video)

**Everything here costs money. Confirm the price before creating anything, and destroy servers after use.**

## What runs where
| Job | Model (licence) | GPU needed | Script |
|---|---|---|---|
| Photoreal B-roll, 5 s clips | Wan2.2 TI2V-5B (Apache-2.0) | 24 GB+ (L4, A40, 4090) | `remote/broll_batch.sh` |
| You speaking an audio track (photo + audio → video) | Wan2.2 S2V-14B (Apache-2.0) | 80 GB ideal (A100); 48 GB with offload — untested | `remote/talking_and_voice.sh talk` |
| Your cloned voice saying new text | Chatterbox (MIT) | any NVIDIA GPU; CPU possible but slow | `remote/talking_and_voice.sh voice` |
| Graphic B-roll | HyperFrames | none (local) | docs/HYPERFRAMES.md |

Expect generated voice ≈ 80–90 % like you, and occasional artifacts (teeth, hands, fast head turns) in talking video.
Disclose AI-generated realistic people/voices on YouTube and Instagram.

## Vultr (scripted)
1. API key: console → Account → API → Enable API → put it in `.env` as `VULTR_API_KEY` (or `tools/vultr_api_key.txt`).
2. **New accounts have a monthly-fee limit** that blocks GPU plans ("maximum monthly fee limit"):
   open a Billing ticket asking for a limit increase (e.g. $1,500) for hourly Cloud GPU use.
3. Commands:
   ```
   vp.py vultr account          # credit + running servers
   vp.py vultr plans            # GPU plans, $/hr, regions with stock
   vp.py vultr create vcg-a40-24c-120g-48vram sgp 4    # COSTS MONEY; self-destructs after 4 h
   vp.py vultr put remote/setup_gpu.sh /root/setup_gpu.sh
   vp.py vultr run "bash /root/setup_gpu.sh"
   vp.py vultr put remote/broll_batch.sh /root/gen/broll_batch.sh
   vp.py vultr put prompts.txt /root/gen/prompts.txt
   vp.py vultr run "bash /root/gen/broll_batch.sh /root/gen/prompts.txt"
   vp.py vultr get /root/gen/broll.tar.gz output/broll.tar.gz
   vp.py vultr destroy          # ALWAYS. Stopped Vultr servers still bill.
   ```
   The SSH key pair is generated into `tools/ssh/` (gitignored) and registered with Vultr automatically.
   The self-destruct timer runs on the server via cloud-init using the API key (it is destroyed with the server).

## Google Cloud ($300 trial)
Trial accounts have **0 GPU quota**: Billing → *Activate full account* (credit carries over) → Budgets & alerts →
IAM & Admin → Quotas: request `GPUs (all regions)` = 1 and `NVIDIA L4 GPUs` (us-central1) = 1
(A100 80GB often refused for new accounts). VM: g2-standard-8 + 1× L4, "Deep Learning on Linux" image,
150 GB balanced disk, Spot provisioning. SSH from the browser, then run `remote/setup_gpu.sh`.
**Stop** the VM after each session (GCP doesn't bill stopped VMs except disk).

## Hugging Face
- Token: huggingface.co/settings/tokens → fine-grained → "Inference Providers" + "Read public gated repos".
  Store as `HF_TOKEN` in `.env` or `~/.cache/huggingface/token`.
- Inference Providers (fal/replicate/wavespeed serve Wan2.2 T2V) need prepaid credits or PRO.
- Free Spaces (e.g. official `Wan-AI/Wan2.2-S2V`: image + audio + 480P/720P) via `gradio_client`;
  queues/limits apply and uploads go to the Space operator — get consent before uploading someone's face/voice.

## Prompting B-roll (Wan2.2)
Describe: subject, action, camera move, lens/depth of field, lighting, mood, style. Example:
"Slow dolly past Bangalore traffic at dusk, auto-rickshaws and scooters, warm sodium street lights, light haze,
shallow depth of field, cinematic, realistic". Keep clips 3–5 s and cut them in as 2–3 s cutaways.
