#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-vonr}"
RELEASE="${RELEASE:-vonr}"
CHART_DIR="${CHART_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TIMEOUT="${TIMEOUT:-10m}"

rendered="$(helm template "$RELEASE" "$CHART_DIR" -n "$NAMESPACE")"
while read -r image; do
  leaf="${image##*/}"
  if [[ "$leaf" != *:* || "$image" == *:latest ]]; then
    echo "ERROR: image is untagged or uses latest: $image" >&2
    exit 1
  fi
done < <(awk '$1 == "image:" {gsub(/"/, "", $2); print $2}' <<<"$rendered")

for component in ue1 ue2; do
  deployment="$RELEASE-open5gs-vonr-$component"
  kubectl -n "$NAMESPACE" rollout status "deployment/$deployment" --timeout="$TIMEOUT"
  for attempt in $(seq 1 60); do
    ue_logs="$(kubectl -n "$NAMESPACE" logs "deployment/$deployment" -c ue --tail=250)"
    grep -q 'PDU Session establishment is successful' <<<"$ue_logs" && break
    [[ "$attempt" -eq 60 ]] && { echo "ERROR: $component did not establish a PDU session" >&2; exit 1; }
    sleep 2
  done
done
kubectl -n "$NAMESPACE" rollout status "deployment/$RELEASE-open5gs-vonr-pcscf" --timeout="$TIMEOUT"

ue1="$RELEASE-open5gs-vonr-ue1"
ue2="$RELEASE-open5gs-vonr-ue2"
pcscf="$(helm get values "$RELEASE" -n "$NAMESPACE" -a -o json | sed -n 's/.*"pcscf":"\([^"]*\)".*/\1/p')"
pcscf="${pcscf:-10.54.0.41}"

ue_ip() {
  kubectl -n "$NAMESPACE" exec "deployment/$1" -c sipp -- sh -c \
    "ip -4 -o addr show uesimtun0 | awk '{print \$4}' | cut -d/ -f1"
}

ue1_ip="$(ue_ip "$ue1")"
ue2_ip="$(ue_ip "$ue2")"
echo "UE 1001 tunnel: $ue1_ip; UE 1002 tunnel: $ue2_ip; P-CSCF: $pcscf"

register() {
  local deployment="$1" user="$2" ip="$3"
  kubectl -n "$NAMESPACE" exec "deployment/$deployment" -c sipp -- \
    sipp "$pcscf:5060" -sf /scenarios/register.xml -i "$ip" -p 5060 \
    -s "$user" -m 1 -timeout 20s -trace_err
}
register "$ue1" 1001 "$ue1_ip"
register "$ue2" 1002 "$ue2_ip"

kubectl -n "$NAMESPACE" exec "deployment/$ue2" -c sipp -- \
  sh -c "sipp -sf /scenarios/uas.xml -i '$ue2_ip' -p 5060 -m 1 -timeout 30s -trace_err >/tmp/uas.log 2>&1 &"
sleep 2
kubectl -n "$NAMESPACE" exec "deployment/$ue1" -c sipp -- \
  sipp "$pcscf:5060" -sf /scenarios/uac.xml -i "$ue1_ip" -p 5060 \
  -s 1002 -m 1 -timeout 30s -trace_err

echo 'PASS: 1001 completed the simulated VoNR SIP dialog with 1002 through both 5G PDU sessions.'
