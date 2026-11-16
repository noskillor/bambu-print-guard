#!/usr/bin/env bash
# Install bambu-print-guard natively on Debian 12/13 (e.g. inside a Proxmox LXC).
# Run as root from a checkout of this repository:   bash deploy/lxc/install.sh
#
# Installs: Docker (for the Obico ML container), Python + Pillow, the guard as a
# systemd service under /opt/print-guard. Re-running updates the guard in place.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PREFIX=/opt/print-guard
OBICO_DIR=/opt/obico-server

[ "$(id -u)" -eq 0 ] || { echo "Please run as root"; exit 1; }

echo "== Packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq docker.io git curl ca-certificates python3 python3-pil fonts-dejavu-core >/dev/null

echo "== Obico ML container (built from the official repository)"
if [ -d "$OBICO_DIR/.git" ]; then
  git -C "$OBICO_DIR" pull -q
else
  git clone -q --depth 1 -b release https://github.com/TheSpaghettiDetective/obico-server.git "$OBICO_DIR"
fi
docker build -q -f "$OBICO_DIR/ml_api/Containerfile.cpu" -t print-guard-ml "$OBICO_DIR/ml_api" >/dev/null
docker rm -f print-guard-ml >/dev/null 2>&1 || true
docker run -d --name print-guard-ml --restart unless-stopped --network host print-guard-ml >/dev/null

echo "== Guard"
install -d -m 700 "$PREFIX"
install -m 755 "$REPO_DIR/print_guard/print_guard.py" "$PREFIX/print_guard.py"
if [ ! -f "$PREFIX/config.json" ]; then
  # Native install: ML container and guard share the host network.
  sed -e 's#"token_file": "/config/ha_token"#"token_file": "/opt/print-guard/ha_token"#' \
      -e 's#"ml_api": "http://ml:3333/p/"#"ml_api": "http://127.0.0.1:3333/p/"#' \
      -e 's#"frame_base_url": "http://guard:8098"#"frame_base_url": "http://127.0.0.1:8098"#' \
      -e 's#"data_dir": "/data"#"data_dir": "/opt/print-guard/data"#' \
      "$REPO_DIR/config.example.json" > "$PREFIX/config.json"
  echo "   created $PREFIX/config.json - edit it now"
fi
[ -f "$PREFIX/ha_token" ] || { touch "$PREFIX/ha_token"; chmod 600 "$PREFIX/ha_token"; echo "   put your HA token into $PREFIX/ha_token"; }
install -m 644 "$REPO_DIR/deploy/lxc/print-guard.service" /etc/systemd/system/print-guard.service
systemctl daemon-reload
systemctl enable print-guard >/dev/null
systemctl restart print-guard

echo
echo "Done. Check with:  journalctl -u print-guard -f"
echo "Single test cycle: python3 $PREFIX/print_guard.py --config $PREFIX/config.json --once"
