"""Control a Vultr GPU server for generation jobs.

The API key is read from VULTR_API_KEY (.env or environment) or tools/vultr_api_key.txt. Never commit it.
New accounts have a monthly-fee limit; GPU plans need a limit increase via a Vultr support ticket first.
Billing note: Vultr bills STOPPED servers too. Only `destroy` stops charges.

Usage:
  python vultr_ctl.py account                      balance + running servers (read-only)
  python vultr_ctl.py plans                        GPU plans with stock, price, regions (read-only)
  python vultr_ctl.py create [plan] [region] [max_hours]   create GPU server (COSTS MONEY), with self-destruct timer
  python vultr_ctl.py status                       state + IP of our server
  python vultr_ctl.py run "<shell command>"        run a command over SSH, stream output
  python vultr_ctl.py put <local> <remote>         upload a file
  python vultr_ctl.py get <remote> <local>         download a file
  python vultr_ctl.py destroy                      destroy our server (stops billing)
"""
import os, sys, json, time, base64, urllib.request, urllib.error
from _env import ROOT, TOOLS  # also loads .env and the OS certificate store
STATE = os.path.join(TOOLS, "vultr_state.json")
KEY_DIR = os.path.join(TOOLS, "ssh")
LABEL = "video-pipeline-gpu"
DEFAULT_PLAN, DEFAULT_REGION, UBUNTU_2204 = "vcg-a40-24c-120g-48vram", "sgp", 1743


def api_key():
    k = os.environ.get("VULTR_API_KEY")
    if not k:
        p = os.path.join(TOOLS, "vultr_api_key.txt")
        if not os.path.exists(p):
            sys.exit("No Vultr API key: set VULTR_API_KEY or create tools/vultr_api_key.txt")
        k = open(p).read().strip()
    return k


def call(method, path, body=None):
    req = urllib.request.Request("https://api.vultr.com/v2" + path, method=method,
                                 headers={"Authorization": "Bearer " + api_key(), "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = r.read().decode()
            return json.loads(txt) if txt else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"Vultr API {method} {path} -> {e.code}: {e.read().decode()[:500]}")


def load_state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {}


def save_state(s):
    json.dump(s, open(STATE, "w"), indent=1)


def ensure_ssh_key():
    """ed25519 key pair kept in tools/ssh (gitignored); registered once with Vultr."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization as ser
    os.makedirs(KEY_DIR, exist_ok=True)
    priv_p, pub_p = os.path.join(KEY_DIR, "id_ed25519"), os.path.join(KEY_DIR, "id_ed25519.pub")
    if not os.path.exists(priv_p):
        k = Ed25519PrivateKey.generate()
        open(priv_p, "wb").write(k.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.OpenSSH, ser.NoEncryption()))
        open(pub_p, "wb").write(k.public_key().public_bytes(ser.Encoding.OpenSSH, ser.PublicFormat.OpenSSH) + b" video-pipeline")
    pub = open(pub_p).read().strip()
    st = load_state()
    keys = call("GET", "/ssh-keys?per_page=500").get("ssh_keys", [])
    match = [k for k in keys if k["ssh_key"].strip().split()[:2] == pub.split()[:2]]
    if match:
        kid = match[0]["id"]
    else:
        kid = call("POST", "/ssh-keys", {"name": "video-pipeline", "ssh_key": pub})["ssh_key"]["id"]
    st["ssh_key_id"] = kid
    save_state(st)
    return kid, priv_p


def self_destruct_userdata(max_hours):
    """cloud-init script: after max_hours the server destroys itself through the API (billing safety net)."""
    script = f"""#!/bin/bash
cat > /root/self_destruct.sh <<'EOF'
#!/bin/bash
ID=$(curl -s http://169.254.169.254/v1.json | python3 -c 'import sys,json;print(json.load(sys.stdin)["instanceid"])')
curl -s -X DELETE "https://api.vultr.com/v2/instances/$ID" -H "Authorization: Bearer {api_key()}"
EOF
chmod 700 /root/self_destruct.sh
nohup bash -c 'sleep {int(max_hours * 3600)}; /root/self_destruct.sh' >/root/self_destruct.log 2>&1 &
"""
    return base64.b64encode(script.encode()).decode()


def cmd_account():
    a = call("GET", "/account")["account"]
    inst = call("GET", "/instances?per_page=500")["instances"]
    print(f"credit: ${-float(a['balance']):.2f}  pending charges: ${float(a['pending_charges']):.2f}")
    for i in inst:
        print(f"  server {i['id']} {i['label']} {i['plan']} {i['region']} {i['status']}/{i['power_status']} {i['main_ip']}")
    if not inst:
        print("  no servers running (nothing is billing)")


def cmd_plans():
    ps = call("GET", "/plans?type=all&per_page=500")["plans"]
    for p in sorted([p for p in ps if p.get("gpu_brand", "none") != "none"], key=lambda p: p["hourly_cost"]):
        print(f"{p['id']:34s} ${p['hourly_cost']:>6}/hr  regions: {', '.join(p['locations']) or 'SOLD OUT'}")


def cmd_create(plan=DEFAULT_PLAN, region=DEFAULT_REGION, max_hours=4.0):
    st = load_state()
    if st.get("instance_id"):
        sys.exit(f"Server {st['instance_id']} already recorded; run status/destroy first.")
    p = [x for x in call("GET", "/plans?type=all&per_page=500")["plans"] if x["id"] == plan]
    if not p or region not in p[0]["locations"]:
        sys.exit(f"{plan} not in stock in {region}. Run: python vultr_ctl.py plans")
    hourly = p[0]["hourly_cost"]
    print(f"Creating {plan} in {region} at ${hourly}/hr; self-destructs after {max_hours} h (max ~${hourly * max_hours:.2f})")
    kid, _ = ensure_ssh_key()
    inst = call("POST", "/instances", {
        "region": region, "plan": plan, "os_id": UBUNTU_2204, "label": LABEL, "hostname": LABEL,
        "sshkey_id": [kid], "user_data": self_destruct_userdata(max_hours), "backups": "disabled",
    })["instance"]
    st.update(instance_id=inst["id"], plan=plan, region=region, hourly=hourly, created=time.time(), max_hours=max_hours)
    save_state(st)
    print("instance id:", inst["id"], "- waiting for it to boot...")
    for _ in range(90):
        i = call("GET", f"/instances/{inst['id']}")["instance"]
        if i["status"] == "active" and i["power_status"] == "running" and i["main_ip"] not in ("", "0.0.0.0"):
            st["ip"] = i["main_ip"]; save_state(st)
            print("READY ip:", i["main_ip"])
            return
        time.sleep(10)
    print("Still provisioning; check with: python vultr_ctl.py status")


def cmd_status():
    st = load_state()
    if not st.get("instance_id"):
        print("no server recorded"); return
    i = call("GET", f"/instances/{st['instance_id']}")["instance"]
    st["ip"] = i["main_ip"]; save_state(st)
    hrs = (time.time() - st["created"]) / 3600
    print(f"{i['status']}/{i['power_status']}/{i['server_status']} ip={i['main_ip']}  running {hrs:.2f} h  ~${hrs * st['hourly']:.2f} so far")


def ssh():
    import paramiko
    st = load_state()
    k = paramiko.Ed25519Key.from_private_key_file(os.path.join(KEY_DIR, "id_ed25519"))
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # fresh disposable server every session
    c.connect(st["ip"], username="root", pkey=k, timeout=30, banner_timeout=60, auth_timeout=60)
    return c


def cmd_run(command):
    c = ssh()
    tr = c.get_transport(); tr.set_keepalive(30)
    ch = tr.open_session(); ch.get_pty(); ch.exec_command(command)
    while True:
        if ch.recv_ready():
            sys.stdout.write(ch.recv(65536).decode("utf-8", "replace")); sys.stdout.flush()
        elif ch.exit_status_ready() and not ch.recv_ready():
            break
        else:
            time.sleep(0.2)
    code = ch.recv_exit_status(); c.close()
    print(f"\n[exit {code}]"); sys.exit(code)


def cmd_put(local, remote):
    c = ssh(); s = c.open_sftp(); s.put(local, remote); s.close(); c.close(); print("uploaded", local, "->", remote)


def cmd_get(remote, local):
    c = ssh(); s = c.open_sftp(); s.get(remote, local); s.close(); c.close(); print("downloaded", remote, "->", local)


def cmd_destroy():
    st = load_state()
    if not st.get("instance_id"):
        print("no server recorded"); cmd_account(); return
    call("DELETE", f"/instances/{st['instance_id']}")
    hrs = (time.time() - st["created"]) / 3600
    print(f"destroyed {st['instance_id']} after {hrs:.2f} h (~${hrs * st['hourly']:.2f})")
    for k in ("instance_id", "ip", "created"):
        st.pop(k, None)
    save_state(st)
    time.sleep(5); cmd_account()


if __name__ == "__main__":
    a = sys.argv[1:] or ["account"]
    fn = {"account": cmd_account, "plans": cmd_plans, "create": cmd_create, "status": cmd_status, "run": cmd_run,
          "put": cmd_put, "get": cmd_get, "destroy": cmd_destroy}[a[0]]
    args = a[1:]
    if a[0] == "create" and len(args) > 2:
        args[2] = float(args[2])
    fn(*args)
