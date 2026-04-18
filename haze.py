#!/usr/bin/env python3
"""haze v0.1.1 - a project by INVAR"""

import json, os, subprocess, sys, time, socket, shlex, readline, secrets, shutil, platform, errno
from datetime import datetime, timezone
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
except ImportError:
    sys.exit("pip install rich")

console = Console(highlight=False)

ROOT      = Path(__file__).parent
TF_SRC    = ROOT / "terraform"
PROF_DIR  = ROOT / "profiles"
HAZE_DIR  = Path.home() / ".haze"
STATE     = HAZE_DIR / "instances.json"
LOGFILE   = HAZE_DIR / "last.log"
TUNNEL_D  = HAZE_DIR / "tunnels"

VALID_PROFILES = {"default", "web", "chain", "dev"}

IMAGES = {
    "ubuntu": "ubuntu-22-04-x64",
    "debian": "debian-12-x64",
}

def ok(msg):   console.print(f"  [green][[/][bold green]+[/][green]][/] {msg}")
def err(msg):  console.print(f"  [red][[/][bold red]-[/][red]][/] {msg}")
def info(msg): console.print(f"  [dim][[/][dim]*[/][dim]][/] [dim]{msg}[/]")

def load_all() -> list:
    if not STATE.exists():
        return []
    try:
        return json.loads(STATE.read_text())
    except (json.JSONDecodeError, OSError):
        err(f"state file corrupted  →  check {STATE}")
        return []

def save_all(instances: list):
    STATE.write_text(json.dumps(instances, indent=2))

def get_by_id(idx: int):
    instances = load_all()
    if idx < 1 or idx > len(instances):
        err(f"no wisp with id {idx}")
        return None
    return instances[idx - 1]

def node_count() -> int:
    return len(load_all())

def prompt() -> str:
    n = node_count()
    if n:
        return f"\033[1;36m  [{n}]haze>\033[0m "
    return "\033[1;36m  haze>\033[0m "

def _node_name():
    return "hz-" + secrets.token_hex(3)

def _ws(name: str) -> Path:
    d = HAZE_DIR / "ws" / name
    d.mkdir(parents=True, exist_ok=True)
    return d

def _key(name: str) -> Path:
    return _ws(name) / "id_haze"

def _ssh_opts(name: str) -> list:
    return ["-i", str(_key(name)),
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR"]

def _keygen(name: str):
    k = _key(name)
    k.unlink(missing_ok=True)
    Path(str(k) + ".pub").unlink(missing_ok=True)
    subprocess.run(["ssh-keygen", "-t", "ed25519", "-f", str(k), "-N", "", "-q"], check=True)
    k.chmod(0o600)

def _keyclean(name: str):
    k = _key(name)
    k.unlink(missing_ok=True)
    Path(str(k) + ".pub").unlink(missing_ok=True)

def _tf(ws: Path, *args):
    with open(LOGFILE, "a") as f:
        r = subprocess.run(["terraform", *args], cwd=ws, stdout=f, stderr=f)
    if r.returncode != 0:
        err(f"terraform {args[0]} failed  →  cat {LOGFILE}")
        return False
    return True

def _wait_ssh(ip, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        try:
            socket.create_connection((ip, 22), timeout=3).close()
            return True
        except OSError:
            time.sleep(3)
    return False

def _uptime(since_iso):
    delta = datetime.now(timezone.utc) - datetime.fromisoformat(since_iso)
    h, m = divmod(int(delta.total_seconds()) // 60, 60)
    return f"{h}h {m}m" if h else f"{m}m"

def _run_profile(ip: str, name: str, profile: str):
    opts = _ssh_opts(name)
    scripts = ["default", profile] if profile != "default" else ["default"]

    for script in scripts:
        src = PROF_DIR / f"{script}.sh"
        if not src.exists():
            continue
        with open(LOGFILE, "a") as f:
            subprocess.run(["scp", *opts, str(src), f"root@{ip}:/tmp/{script}.sh"], stdout=f, stderr=f)

    remote_cmd = " && ".join(
        f"bash /tmp/{s}.sh" for s in scripts if (PROF_DIR / f"{s}.sh").exists()
    )
    subprocess.run([
        "ssh", *opts, f"root@{ip}",
        f"nohup bash -c '{remote_cmd}' > /tmp/haze-profile.log 2>&1 &"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    info("provisioning in background  [dim](exec tail -f /tmp/haze-profile.log)[/]")

def cmd_up(args):
    profile = "default"
    image   = "ubuntu"
    size    = "s-1vcpu-512mb-10gb"
    region  = "nyc3"

    i = 0
    while i < len(args):
        if args[i] == "-p" and i + 1 < len(args):
            profile = args[i + 1]; i += 2
        elif args[i].startswith("--size="):
            size = args[i].split("=")[1]; i += 1
        elif args[i].startswith("--region="):
            region = args[i].split("=")[1]; i += 1
        else:
            i += 1

    if profile not in VALID_PROFILES:
        err(f"unknown profile.  choices: {', '.join(VALID_PROFILES)}")
        return

    if not os.environ.get("DIGITALOCEAN_TOKEN"):
        err("DIGITALOCEAN_TOKEN is not set.")
        return

    name = _node_name()
    ws   = _ws(name)

    for f in TF_SRC.glob("*.tf"):
        shutil.copy(f, ws / f.name)

    _keygen(name)
    pub = Path(str(_key(name)) + ".pub").read_text().strip()

    (ws / "terraform.tfvars").write_text(
        f'name    = "{name}"\n'
        f'image   = "{IMAGES[image]}"\n'
        f'size    = "{size}"\n'
        f'region  = "{region}"\n'
        f'pub_key = "{pub}"\n'
    )

    info(f"wisp  {name}  profile  {profile}")
    info(f"image {image}  size {size}  region {region}")
    info("initializing provider…")
    if not _tf(ws, "init", "-upgrade", "-input=false", "-no-color"):
        _keyclean(name)
        return

    info("provisioning…")
    if not _tf(ws, "apply", "-auto-approve", "-input=false", "-no-color"):
        _keyclean(name)
        return

    try:
        out = json.loads(subprocess.check_output(["terraform", "output", "-json"], cwd=ws))
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        err(f"failed to read terraform output  →  cat {LOGFILE}")
        _keyclean(name)
        return
    ip  = out["ip"]["value"]

    info("waiting for SSH…")
    if not _wait_ssh(ip):
        err("SSH timeout"); return

    _run_profile(ip, name, profile)

    instances = load_all()
    instances.append({
        "name":    name,
        "ip":      ip,
        "image":   image,
        "profile": profile,
        "size":    size,
        "region":  region,
        "created": datetime.now(timezone.utc).isoformat(),
        "ws":      str(ws),
    })
    save_all(instances)
    ok(f"{ip}  [{profile}]")

def _live_tunnels() -> list:
    if not TUNNEL_D.exists():
        return []
    out = []
    for f in TUNNEL_D.glob("*.json"):
        try:
            d = json.loads(f.read_text())
            os.kill(d["pid"], 0)
            out.append(d)
        except (ProcessLookupError, json.JSONDecodeError):
            f.unlink(missing_ok=True)
        except OSError as e:
            if e.errno == errno.ESRCH:
                f.unlink(missing_ok=True)
    return out

def _node_tunnels(name: str) -> str:
    tunnels = [t for t in _live_tunnels() if t["name"] == name]
    if not tunnels:
        return "—"
    return "  ".join(f":{t['lport']}→:{t['rport']} {t.get('proto','tcp')}" for t in tunnels)

def cmd_down(args):
    instances = load_all()
    if not instances:
        err("no wisps up."); return

    if not args:
        if len(instances) == 1:
            idx = 1
        else:
            cmd_status([])
            try:
                idx = int(input("  wisp id? > ").strip())
            except (ValueError, EOFError, KeyboardInterrupt):
                return
    else:
        try:
            idx = int(args[0])
        except ValueError:
            err("usage: down <id>"); return

    inst = get_by_id(idx)
    if not inst: return

    info(f"dissolving {inst['name']}…")
    ws = Path(inst["ws"])
    if not _tf(ws, "destroy", "-auto-approve", "-input=false", "-no-color"): return

    _keyclean(inst["name"])
    instances.pop(idx - 1)
    save_all(instances)
    ok("done")

def cmd_status(_):
    instances = load_all()
    if not instances:
        info("no wisps up."); return

    t = Table(border_style="dim", header_style="bold cyan", show_edge=False)
    t.add_column("id",      style="bold",  width=4)
    t.add_column("wisp",    style="cyan")
    t.add_column("ip")
    t.add_column("image",   style="dim")
    t.add_column("profile", style="green")
    t.add_column("uptime",  style="dim")
    t.add_column("tunnels", style="yellow")

    for i, inst in enumerate(instances, 1):
        t.add_row(
            str(i),
            inst["name"],
            inst["ip"],
            inst["image"],
            inst["profile"],
            _uptime(inst["created"]),
            _node_tunnels(inst["name"]),
        )

    console.print()
    console.print(t)
    console.print()

def cmd_ssh(args):
    instances = load_all()
    if not instances:
        err("no wisps up."); return

    if not args:
        if len(instances) == 1:
            inst = instances[0]
        else:
            cmd_status([])
            try:
                idx = int(input("  wisp id? > ").strip())
            except (ValueError, EOFError, KeyboardInterrupt):
                return
            inst = get_by_id(idx)
            if not inst: return
    else:
        try:
            inst = get_by_id(int(args[0]))
            if not inst: return
        except ValueError:
            err("usage: ssh [id]"); return

    info(f"connecting to {inst['ip']}…")
    subprocess.run(["ssh", *_ssh_opts(inst["name"]), f"root@{inst['ip']}"])
    info("back in haze")

def cmd_push(args):
    instances = load_all()
    if not instances:
        err("no wisps up."); return

    if not args:
        err("usage: push <local> [remote]"); return

    if len(instances) == 1:
        inst = instances[0]
    else:
        cmd_status([])
        try:
            idx = int(input("  wisp id? > ").strip())
        except (ValueError, EOFError, KeyboardInterrupt):
            return
        inst = get_by_id(idx)
        if not inst: return

    local  = args[0]
    remote = args[1] if len(args) > 1 else "/root/"
    info(f"{local}  →  {inst['ip']}:{remote}")
    subprocess.run(["scp", *_ssh_opts(inst["name"]), local, f"root@{inst['ip']}:{remote}"])
    ok("done")

def cmd_pull(args):
    instances = load_all()
    if not instances:
        err("no wisps up."); return

    if not args:
        err("usage: pull <remote> [local]"); return

    if len(instances) == 1:
        inst = instances[0]
    else:
        cmd_status([])
        try:
            idx = int(input("  wisp id? > ").strip())
        except (ValueError, EOFError, KeyboardInterrupt):
            return
        inst = get_by_id(idx)
        if not inst: return

    remote = args[0]
    local  = args[1] if len(args) > 1 else "."
    info(f"{inst['ip']}:{remote}  →  {local}")
    subprocess.run(["scp", *_ssh_opts(inst["name"]), f"root@{inst['ip']}:{remote}", local])
    ok("done")


def cmd_sync(args):
    if len(args) < 2:
        err("usage: sync <local> <remote>"); return

    instances = load_all()
    if not instances:
        err("no wisps up."); return

    if len(instances) == 1:
        inst = instances[0]
    else:
        cmd_status([])
        try:
            idx = int(input("  wisp id? > ").strip())
        except (ValueError, EOFError, KeyboardInterrupt):
            return
        inst = get_by_id(idx)
        if not inst: return

    local  = args[0]
    remote = args[1]

    Path(local).mkdir(parents=True, exist_ok=True)

    subprocess.run([
        "ssh", *_ssh_opts(inst["name"]), f"root@{inst['ip']}",
        f"mkdir -p {remote}"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ssh_cmd = f"ssh {' '.join(_ssh_opts(inst['name']))}"
    remote_str = f"root@{inst['ip']}:{remote}/"

    info(f"{local}  ⇄  {inst['ip']}:{remote}")
    subprocess.run([
        "rsync", "-avz", "--delete",
        "-e", ssh_cmd,
        f"{local.rstrip('/')}/",
        remote_str,
    ])
    ok("synced")

def cmd_forward(_):
    instances = load_all()
    if not instances:
        err("no wisps up."); return

    if len(instances) == 1:
        inst = instances[0]
    else:
        cmd_status([])
        try:
            idx = int(input("  wisp id? > ").strip())
        except (ValueError, EOFError, KeyboardInterrupt):
            return
        inst = get_by_id(idx)
        if not inst: return

    try:
        rport = int(input("  remote port? > ").strip())
        lport = int(input("  local port?  > ").strip())
        proto = input("  protocol? [tcp/http] > ").strip().lower() or "tcp"
        if proto not in ("tcp", "http"):
            proto = "tcp"
    except (ValueError, EOFError, KeyboardInterrupt):
        err("cancelled"); return

    TUNNEL_D.mkdir(exist_ok=True)
    pid_f = TUNNEL_D / f"{inst['name']}_{lport}.json"

    if pid_f.exists():
        err(f"tunnel :{lport} already open for {inst['name']}")
        return

    proc = subprocess.Popen([
        "ssh", *_ssh_opts(inst["name"]),
        "-N", "-L", f"127.0.0.1:{lport}:127.0.0.1:{rport}",
        "-o", "ServerAliveInterval=30",
        f"root@{inst['ip']}",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    time.sleep(1.2)
    if proc.poll() is not None:
        err("tunnel failed to start"); return

    pid_f.write_text(json.dumps({"pid": proc.pid, "lport": lport, "rport": rport, "name": inst["name"], "proto": proto}))
    ok(f"localhost:{lport}  →  {inst['ip']}:{rport}  {proto}  [dim](pid {proc.pid})[/]")

def cmd_exec(args):
    if not args:
        err("usage: exec <command>"); return

    instances = load_all()
    if not instances:
        err("no wisps up."); return

    if len(instances) == 1:
        inst = instances[0]
    else:
        cmd_status([])
        try:
            idx = int(input("  wisp id? > ").strip())
        except (ValueError, EOFError, KeyboardInterrupt):
            return
        inst = get_by_id(idx)
        if not inst: return

    remote_cmd = " ".join(args)
    try:
        subprocess.run(["ssh", *_ssh_opts(inst["name"]), f"root@{inst['ip']}", remote_cmd])
    except KeyboardInterrupt:
        console.print()

def cmd_fwd_kill(args):
    tunnels = _live_tunnels()
    if not tunnels:
        err("no active tunnels."); return

    if len(tunnels) == 1:
        t = tunnels[0]
    else:
        for i, t in enumerate(tunnels, 1):
            console.print(f"  [dim]{i}[/]  :{t['lport']}→:{t['rport']} {t.get('proto','tcp')}  {t['name']}")
        try:
            idx = int(input("  tunnel id? > ").strip()) - 1
            t = tunnels[idx]
        except (ValueError, IndexError, EOFError, KeyboardInterrupt):
            err("cancelled"); return

    try:
        os.kill(t["pid"], 9)
    except ProcessLookupError:
        pass

    pid_f = TUNNEL_D / f"{t['name']}_{t['lport']}.json"
    pid_f.unlink(missing_ok=True)
    ok(f"tunnel :{t['lport']}→:{t['rport']} closed")

def cmd_help(_):
    console.print("""
  [dim]up [-p profile] [--size=..] [--region=..][/]   spawn a wisp
  [dim]down [id][/]                                    dissolve a wisp
  [dim]status[/]                                       list active wisps
  [dim]ssh [id][/]
  [dim]exec <cmd>                                      run command on wisp[/]
  [dim]push <local> [remote][/]
  [dim]pull <remote> [local][/]
  [dim]sync <local> <remote>                           bidirectional sync[/]
  [dim]forward[/]
  [dim]fwd-kill[/]
  [dim]!<cmd>                                          run local command[/]
  [dim]exit[/]

  [dim]profiles: default  web  chain  dev[/]
""")

COMMANDS = {
    "up":       cmd_up,
    "down":     cmd_down,
    "status":   cmd_status,
    "ssh":      cmd_ssh,
    "exec":     cmd_exec,
    "push":     cmd_push,
    "pull":     cmd_pull,
    "sync":     cmd_sync,
    "forward":  cmd_forward,
    "fwd-kill": cmd_fwd_kill,
    "help":     cmd_help,
    "?":        cmd_help,
}

def repl():
    HAZE_DIR.mkdir(exist_ok=True)
    readline.parse_and_bind(r"control-l: clear-screen")

    if platform.system() == "Darwin":
        readline.parse_and_bind(r'"\e[1;5C": forward-word')
        readline.parse_and_bind(r'"\e[1;5D": backward-word')
        readline.parse_and_bind(r'"\e\e[C": forward-word')
        readline.parse_and_bind(r'"\e\e[D": backward-word')
    else:
        readline.parse_and_bind(r'"\e[1;5C": forward-word')
        readline.parse_and_bind(r'"\e[1;5D": backward-word')
        readline.parse_and_bind(r'"\e[5C": forward-word')
        readline.parse_and_bind(r'"\e[5D": backward-word')

    console.print("\n    [bold cyan]•[/]\n          [bold]haze[/] [dim]v0.1.1 - https://invar.lat[/]\n  [bold cyan]•   •[/]\n")

    while True:
        try:
            line = input(prompt()).strip()
        except KeyboardInterrupt:
            console.print()
            try:
                ans = input("  exit? (y/n) ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                console.print(); break
            if ans == "y": break
            continue
        except EOFError:
            console.print(); break

        if not line:
            continue
        if line in ("exit", "quit", "q"):
            break
        if line.startswith("!"):
            try:
                subprocess.run(shlex.split(line[1:].strip()))
            except ValueError:
                err("invalid input")
            except KeyboardInterrupt:
                console.print()
            continue

        try:
            parts = shlex.split(line)
        except ValueError:
            err("invalid input"); continue
        cmd, args = parts[0], parts[1:]
        if cmd in COMMANDS:
            COMMANDS[cmd](args)
        else:
            err(f"unknown command: {cmd}")

if __name__ == "__main__":
    repl()
