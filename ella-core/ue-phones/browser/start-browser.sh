#!/bin/sh
set -eu
Xvfb :99 -screen 0 500x900x24 -nolisten tcp &
until xdpyinfo -display :99 >/dev/null 2>&1; do sleep 1; done
openbox --sm-disable >/tmp/window-manager.log 2>&1 &
until xprop -root _NET_SUPPORTING_WM_CHECK 2>/dev/null | grep -q 'window id'; do sleep 1; done
x11vnc -display :99 -localhost -rfbport 5900 -nopw -forever -shared -noxdamage >/tmp/vnc.log 2>&1 &
websockify --web=/usr/share/novnc 127.0.0.1:6080 127.0.0.1:5900 >/tmp/websockify.log 2>&1 &
until curl -fsS http://127.0.0.1:8080/api/state | grep -q '"ready":true'; do sleep 2; done
exec chromium --user-data-dir=/home/browser/profile --no-first-run --no-default-browser-check --disable-dev-shm-usage --disable-quic --disable-background-networking --disable-component-update --disable-sync --disable-features=MediaRouter --proxy-server=socks5://127.0.0.1:1080 --proxy-bypass-list='<-loopback>' --host-resolver-rules='MAP * ~NOTFOUND, EXCLUDE 127.0.0.1' --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 --remote-allow-origins=http://localhost --kiosk --window-size=500,900 about:blank
