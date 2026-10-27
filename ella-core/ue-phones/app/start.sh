#!/bin/sh
set -eu
if [ -n "${N2N3_ADDRESS:-}" ]; then
  ip address replace "$N2N3_ADDRESS" dev "${N2N3_INTERFACE:-net1}"
  ip link set "${N2N3_INTERFACE:-net1}" up
  export N2N3_ADDRESS="${N2N3_ADDRESS%/*}"
fi
export N3_ADDRESS="$(ip -4 -o addr show "${N3_INTERFACE:-net1}" | awk '{print $4}' | cut -d/ -f1)"
test -n "$N3_ADDRESS"
select_core_n2() {
  [ -n "${CORE_MEMBER_HOSTS:-}" ] || { printf '%s' "${CORE_N2%%:*}"; return; }
  active=$(curl -fsS --connect-timeout 2 --max-time 4 "http://${CORE_ACTIVE_HOST}:5002/api/v1/status" 2>/dev/null | jq -r '.result.cluster.nodeId // empty' || true)
  [ -n "$active" ] || return 1
  i=1
  while :; do
    host=$(printf '%s' "$CORE_MEMBER_HOSTS" | cut -d, -f"$i")
    address=$(printf '%s' "$CORE_N2_ADDRESSES" | cut -d, -f"$i")
    [ -n "$host" ] && [ -n "$address" ] || break
    member=$(curl -fsS --connect-timeout 2 --max-time 4 "http://${host}:5002/api/v1/status" 2>/dev/null | jq -r '.result.cluster.nodeId // empty' || true)
    if [ "$active" = "$member" ]; then printf '%s' "$address"; return 0; fi
    i=$((i + 1))
  done
  return 1
}
app_pid=
stop_app() { if [ -n "$app_pid" ]; then kill -TERM "$app_pid" 2>/dev/null || true; wait "$app_pid" 2>/dev/null || true; fi; }
trap 'stop_app; exit 0' TERM INT
while :; do
  selected=$(select_core_n2 || true)
  if [ -z "$selected" ]; then sleep 2; continue; fi
  export CORE_N2="${selected}:38412"
  printf '%s UE phone gNB starting on N2 %s\n' "$(date -u +%FT%TZ)" "$CORE_N2"
  /usr/local/bin/ue-phones &
  app_pid=$!
  while kill -0 "$app_pid" 2>/dev/null; do
    sleep 3
    next=$(select_core_n2 || true)
    if [ -n "$next" ] && [ "$next" != "$selected" ]; then
      printf '%s Active Core changed; reattaching phone gNB to %s:38412\n' "$(date -u +%FT%TZ)" "$next"
      stop_app
      app_pid=
      break
    fi
  done
  wait "$app_pid" 2>/dev/null || true
  app_pid=
  sleep 2
done
