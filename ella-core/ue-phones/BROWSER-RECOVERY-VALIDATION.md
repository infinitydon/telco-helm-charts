# Browser recovery validation — 25 October 2026

## Failure observed

Phone A's original browser container was OOMKilled (exit 137) at 2026-10-25 17:38:53 UTC with a 1536 MiB limit. Kubernetes restarted it, while the UE container did not restart and remained NAS/IMS registered. The already-open viewer stayed on its old disconnected screen because it had no reconnection loop. A live rollout also exposed cached old viewer HTML; the final change versions the viewer/module URLs and serves viewer assets with Cache-Control: no-store, stripping conditional cache request headers.

## Deployed change

Chart, simulator image and browser image: 0.3.3. Namespace ella-services-test, release ue revision 3.

- Browser memory request 512 MiB / limit 2 GiB; configurable through browser.resources.
- Advisory Chromium renderer-process target 4, configurable through browser.rendererProcessLimit. Site isolation may require additional processes, so this is not a strict process cap or a promise that arbitrary heavy pages cannot exhaust memory.
- tini plus component supervision restarts the browser stack if Chromium, Xvfb, Openbox, x11vnc or websockify exits. Startup/liveness checks verify the X server, VNC greeting, web viewer and CDP HTTP endpoint. WebSocket heartbeat is enabled.
- Viewer retries with bounded exponential backoff, handshake timeout, offline/online handling and a Reconnect now action. Old connection events cannot override a newer connection.
- The pod-local profile volume and checkpointed last HTTP/HTTPS URL survive a browser-container restart. This does not preserve unsaved form state or survive pod replacement.
- Main UE startup, data routing, IMS and SMS handling remain separate from browser restart handling.

Simulator manifest: sha256:b3476035678a71711396003e3f122b23f902583969ac443ef94910f4d0f78e74.
Browser manifest: sha256:ae4b439851ede8e063f73a411594ba0b4195a3826a21493aac67faf78d64ee61.

## Verification

- Six reconnect-controller tests passed: initial connect/deadline cleanup; reconnect/backoff reset; bounded repeated-failure backoff; handshake timeout; offline/online recovery; stale event rejection and stopped timer cleanup.
- Live cache regression check passed: an If-Modified-Since date in 2031 still returns the current viewer with HTTP 200 and Cache-Control: no-store. The API returns viewer version 0.3.3, and the embedded viewer URL contains that version.
- KILL Chromium: recovered in 10.8 seconds.
- KILL websockify: recovered in 19.1 seconds.
- STOP websockify: the liveness probe detected the hang and recovered it in 32.0 seconds.

For each fault, the same pod UID remained, the browser restart count increased, the UE restart count stayed zero, NAS/IMS registration and data address stayed unchanged, a profile marker survived, and Google reopened. See browser-recovery-results.json. The already-open phone UI reconnected after each fault without a page refresh; only an initial refresh was used to load the updated viewer code.

Phone A's three browser restarts in the final pod are the deliberate tests above. Phone B has the same update and remained healthy. The prior 24-scenario reinstall suite was not rerun for this browser-only change. Existing Go build tests, JavaScript/Python syntax checks, browser reconnection tests and Helm lint passed.
