# Proxmox: run the guard only while printing

The guard needs ~1 GB RAM. On a small Proxmox host you can keep its LXC stopped and let
the host start it when a print begins and shut it down afterwards.

## 1. Create the LXC

Debian 12 or 13 template, unprivileged, **nesting + keyctl** enabled (needed for Docker),
2 cores, 1.5 GB RAM, 10 GB disk, static IP, **Start at boot: off**.

```bash
pct create 200 local:vztmpl/debian-13-standard_13.6-1_amd64.tar.zst \
  --hostname print-guard --cores 2 --memory 1536 --swap 512 --rootfs local-lvm:10 \
  --net0 name=eth0,bridge=vmbr0,ip=192.168.1.60/24,gw=192.168.1.1 \
  --unprivileged 1 --features nesting=1,keyctl=1 --onboot 0
pct start 200 && pct enter 200
apt update && apt install -y git
git clone https://github.com/noskillor/bambu-print-guard.git && cd bambu-print-guard
bash deploy/lxc/install.sh
```

Set `public_url` in `/opt/print-guard/config.json` to `http://<LXC IP>:8098`.

## 2. Controller on the host

```bash
# on the Proxmox host, from a checkout of this repository
install -m 700 deploy/proxmox/print-guard-ctl.sh /usr/local/bin/
install -m 644 deploy/proxmox/print-guard-ctl.service deploy/proxmox/print-guard-ctl.timer /etc/systemd/system/
install -m 600 deploy/proxmox/print-guard-ctl.conf.example /etc/print-guard-ctl.conf
nano /etc/print-guard-ctl.conf          # VMID, HA_URL, STATUS_SENSOR, TOKEN_FILE
nano /root/.print-guard-ha-token && chmod 600 /root/.print-guard-ha-token
systemctl daemon-reload && systemctl enable --now print-guard-ctl.timer
```

Every 30 s the controller reads the printer status from Home Assistant. In
`running/pause/prepare/slicing/init` it starts the container; after ~2 minutes
without a print it shuts it down. Log: `journalctl -t print-guard-ctl`.

If Home Assistant is unreachable, the controller changes nothing.

## Backup

Add the container to a backup job (*Datacenter → Backup*). Stopped containers are backed
up normally.
