<h1 align="center">
  <img src="assets/logo.svg" width="80" /><br/>
  haze
</h1>

Spin up pentest wisps on DigitalOcean, fast.

```
    •
          haze v0.1.1 - https://invar.lat
  •   •

  haze> up
  haze> up -p web
  haze> up -p dev
  haze> status
  haze> ssh [id]
  haze> exec <cmd>
  haze> push <local> [remote]
  haze> pull <remote> [local]
  haze> sync <local> <remote>
  haze> forward
  haze> fwd-kill
  haze> down [id]
  haze> !<cmd>
```

## Requirements

- Python 3.10+
- [Terraform](https://developer.hashicorp.com/terraform/downloads)
- `ssh` / `scp` / `rsync`
- DigitalOcean account + API token

## Setup

```bash
git clone https://github.com/INVAR-lab/haze
cd haze
./setup.sh
source .venv/bin/activate
```

Get your API token at [cloud.digitalocean.com/account/api/tokens](https://cloud.digitalocean.com/account/api/tokens), then:

```bash
export DIGITALOCEAN_TOKEN=dop_v1_...
python3 haze.py
```

## Profiles

| flag | installs |
|---|---|
| *(none)* | apt update, base tools (nmap, socat, tcpdump, tmux…) |
| `-p web` | ffuf, sqlmap, ghauri, httpx, subfinder, nuclei |
| `-p dev` | docker, wordpress + mysql on `:8080`, wp-cli |
| `-p chain` | socat, chisel, ligolo-ng, cloudflared, openvpn + `client.ovpn` |

Profile scripts run in background — the wisp is usable immediately after provisioning.  
Monitor progress with `exec tail -f /tmp/haze-profile.log`.

## Images

| flag | base |
|---|---|
| `ubuntu` | Ubuntu 22.04 LTS |
| `debian` | Debian 12 |

## Options

```
haze> up -p web --size=s-2vcpu-4gb --region=fra1
```

| flag | default | options |
|---|---|---|
| `--size` | `s-1vcpu-512mb-10gb` ($4/mo) | [DO sizes](https://slugs.do-api.dev/) |
| `--region` | `nyc3` | `nyc3` `sfo3` `ams3` `sgp1` `lon1` `fra1` |

## State

Wisp state, disposable SSH keys and tunnel PIDs are stored in `~/.haze/`.  
Terraform logs go to `~/.haze/last.log`.

---

An [INVAR](https://invar.lat) project.
