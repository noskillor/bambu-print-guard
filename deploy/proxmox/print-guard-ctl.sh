#!/bin/bash
# Optional, runs on the Proxmox host (systemd timer, every 30 s).
# Starts the print-guard LXC as soon as the printer is printing and shuts it
# down again after the printer has been idle for IDLE_LIMIT checks, so the
# guard only uses RAM/CPU while a print is running.
#
# Settings: /etc/print-guard-ctl.conf (see print-guard-ctl.conf.example)
set -u
CONF=/etc/print-guard-ctl.conf
[ -f "$CONF" ] || { echo "missing $CONF"; exit 1; }
# shellcheck source=/dev/null
. "$CONF"
: "${VMID:?} ${HA_URL:?} ${STATUS_SENSOR:?} ${TOKEN_FILE:?}"
ACTIVE_STATES=${ACTIVE_STATES:-"running pause prepare slicing init"}
IDLE_LIMIT=${IDLE_LIMIT:-4}
IDLE_FILE=/run/print-guard-idle-count

TOKEN=$(tr -d '[:space:]' < "$TOKEN_FILE")
STATE=$(curl -s -m 8 -H "Authorization: Bearer $TOKEN" "$HA_URL/api/states/$STATUS_SENSOR" \
        | python3 -c 'import sys,json; print(json.load(sys.stdin)["state"])' 2>/dev/null)
[ -z "$STATE" ] && exit 0          # Home Assistant unreachable -> change nothing

LXC=$(pct status "$VMID" | awk '{print $2}')

if [[ " $ACTIVE_STATES " == *" $STATE "* ]]; then
  echo 0 > "$IDLE_FILE"
  if [ "$LXC" != "running" ]; then
    logger -t print-guard-ctl "printer state=$STATE -> starting CT $VMID"
    pct start "$VMID"
  fi
elif [ "$LXC" = "running" ]; then
  n=$(( $(cat "$IDLE_FILE" 2>/dev/null || echo 0) + 1 ))
  echo $n > "$IDLE_FILE"
  if [ $n -ge "$IDLE_LIMIT" ]; then
    logger -t print-guard-ctl "printer state=$STATE -> shutting down CT $VMID"
    pct shutdown "$VMID" --timeout 60
    echo 0 > "$IDLE_FILE"
  fi
fi
