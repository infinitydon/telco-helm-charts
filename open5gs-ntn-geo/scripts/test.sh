#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-ntn-geo}"
RELEASE="${RELEASE:-ntn-geo}"
CHART_DIR="${CHART_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TIMEOUT="${TIMEOUT:-15m}"
PREFIX="$RELEASE-open5gs-ntn-geo"

helm lint "$CHART_DIR"
rendered="$(helm template "$RELEASE" "$CHART_DIR" -n "$NAMESPACE")"
while read -r image; do
  leaf="${image##*/}"
  [[ "$leaf" == *:* && "$image" != *:latest ]] || { echo "ERROR: unpinned image: $image" >&2; exit 1; }
done < <(awk '$1 == "image:" {gsub(/"/, "", $2); print $2}' <<<"$rendered")

kubectl -n "$NAMESPACE" rollout status "deployment/$PREFIX-gnb" --timeout="$TIMEOUT"
kubectl -n "$NAMESPACE" rollout status "deployment/$PREFIX-ue" --timeout="$TIMEOUT"

deadline=$((SECONDS + 900))
while (( SECONDS < deadline )); do
  amf_logs="$(kubectl -n "$NAMESPACE" logs "deployment/$PREFIX-amf" --tail=1000 2>/dev/null || true)"
  gnb_logs="$(kubectl -n "$NAMESPACE" logs "deployment/$PREFIX-gnb" -c gnb --tail=300 2>/dev/null || true)"
  grep -qi 'gNB-N2 accepted' <<<"$amf_logs" && ngap=1 || ngap=0
  grep -qi 'Registration complete' <<<"$amf_logs" && grep -qiE 'UE RNTI.*in-sync|RRC_CONNECTED' <<<"$gnb_logs" && attach=1 || attach=0
  kubectl -n "$NAMESPACE" exec "deployment/$PREFIX-ue" -c ue -- ip link show oaitun_ue1 >/dev/null 2>&1 && pdu=1 || pdu=0
  (( ngap && attach && pdu )) && break
  sleep 5
done
(( ngap )) || { echo 'ERROR: gNB did not establish NGAP with AMF' >&2; exit 1; }
(( attach )) || { echo 'ERROR: UE did not complete RACH/RRC/NAS registration' >&2; exit 1; }
(( pdu )) || { echo 'ERROR: UE did not establish a PDU session' >&2; exit 1; }

kubectl -n "$NAMESPACE" exec "deployment/$PREFIX-ue" -c ue -- sh -ec \
  'ip -4 addr show oaitun_ue1'
kubectl -n "$NAMESPACE" logs "deployment/$PREFIX-upf" -c upf --tail=300 | grep -q 'UE F-SEID.*IPv4\[10\.46\.0\.'
echo "PASS: $RELEASE gNB/UE RFsim, RACH, registration, PDU session, UE tunnel, and UPF session succeeded."
