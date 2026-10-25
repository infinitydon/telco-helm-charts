#!/bin/bash
set -euo pipefail
umask 077
pids=(); names=()
cleanup(){
 trap - EXIT TERM INT
 for pid in "${pids[@]}"; do kill -TERM "$pid" 2>/dev/null || true; done
 sleep 2
 for pid in "${pids[@]}"; do kill -KILL "$pid" 2>/dev/null || true; done
 wait || true
}
trap cleanup EXIT
trap 'exit 0' TERM INT
remember(){ printf '%s\n' "$!" >"/tmp/browser-$1.pid"; pids+=("$!"); names+=("$1"); }
Xvfb :99 -screen 0 500x900x24 -nolisten tcp & remember Xvfb
for ((i=0;i<30;i++)); do xdpyinfo -display :99 >/dev/null 2>&1 && break; sleep 1; done
xdpyinfo -display :99 >/dev/null
openbox --sm-disable >/tmp/window-manager.log 2>&1 & remember openbox
for ((i=0;i<30;i++)); do xprop -root _NET_SUPPORTING_WM_CHECK 2>/dev/null | grep -q 'window id' && break; sleep 1; done
x11vnc -display :99 -localhost -rfbport 5900 -nopw -forever -shared -noxdamage >/tmp/vnc.log 2>&1 & remember x11vnc
websockify --heartbeat=15 --web=/usr/share/novnc 127.0.0.1:6080 127.0.0.1:5900 >/tmp/websockify.log 2>&1 & remember websockify
for ((i=0;i<180;i++)); do curl -fsS --max-time 2 http://127.0.0.1:8080/api/state 2>/dev/null | grep -q '"ready":true' && break; sleep 1; done
curl -fsS --max-time 2 http://127.0.0.1:8080/api/state | grep -q '"ready":true'
mkdir -p "$HOME/profile"
# A restarted container is the sole owner of this pod-local profile.
rm -f -- "$HOME/profile/SingletonLock" "$HOME/profile/SingletonSocket" "$HOME/profile/SingletonCookie"
start_url=$(/usr/local/bin/browser-state read)
limit=${BROWSER_RENDERER_LIMIT:-4}
[[ "$limit" =~ ^[1-9][0-9]*$ ]] || { echo 'Invalid renderer limit' >&2; exit 1; }
chromium --user-agent="Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36" --user-data-dir="$HOME/profile" --no-first-run --no-default-browser-check --hide-crash-restore-bubble --disable-dev-shm-usage --disable-quic --disable-background-networking --disable-component-update --disable-sync --disable-features=MediaRouter --renderer-process-limit="$limit" --proxy-server=socks5://127.0.0.1:1080 --proxy-bypass-list='<-loopback>' --host-resolver-rules='MAP * ~NOTFOUND, EXCLUDE 127.0.0.1' --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 --remote-allow-origins=http://localhost --kiosk --window-size=500,900 "$start_url" & remember Chromium
while sleep 2; do
 for i in "${!pids[@]}"; do
  if ! kill -0 "${pids[$i]}" 2>/dev/null; then echo "Browser component exited: ${names[$i]}; restarting stack" >&2; exit 1; fi
 done
 /usr/local/bin/browser-state remember
done
