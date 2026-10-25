# UE phones

Two dedicated phone UIs control separately deployed persistent simulated 5G UEs on the Ella Core integration lab. The backend reuses the pinned upstream Core RAN/UE and IMS libraries; it does not replay test logs or fake network outcomes.

Each phone supports IMS register/unregister, dial, incoming-call indication, answer, reject/cancel/hang-up, synthetic RTP counters, and a NAS SMS composer/inbox. Sent messages distinguish SMSC acceptance from actual receipt by the other simulated UE. Accented text is supported. The event feed shows registration, SMS and call events.

Incoming calls now show a prominent page-level ringing banner, a pulsing phone border, and large Answer/Decline controls inside the receiving phone. The alert stays visible when a different phone or its Browser tab is on screen. New SMS shows a preview alert, an unread badge and an inbox banner; Open message clears the unread indication. Read/unread tracking is local to the current page session. Click **Enable alert sounds** for a synthesized ringtone and message chime; browser sound requires that user gesture. These are in-page alerts, not OS push notifications when the dashboard is closed.

Calls exchange synthetic test packets on the dedicated voice QFI. Browser microphone/speaker audio is not connected. The UI is intended for protocol testing, not as a browser softphone. History is bounded to 100 messages per phone and 100 events, held in memory and cleared on simulator restart.

## Prerequisites

Deploy and provision the [IMS/SMSC integration lab](../tests/services/README.md) first. This application uses its two voice subscribers:

| Phone | IMSI | Number |
| --- | --- | --- |
| A | 001018400000003 | +15558400003 |
| B | 001018400000004 | +15558400004 |

Both need the public lab test key/OPc and internet/ims policies configured by the ella-core-lab Helm provisioning Job. They remain NAS-attached when IMS is unregistered, so SMS continues to work independently of IMS. Do not run the original test scenarios concurrently against these same IMSIs; each UE must have one owner.

The simulator pod is privileged for TUN, IPsec/XFRM and network configuration. Each shares the existing `ella-ran` bridge attachment and must run on the same node as the lab Core/IMS. The chart defaults to dedicated NodePort Services on ports 30880 and 30881. It has no user authentication; use it on a trusted lab network.

## Build and deploy

The chart pulls the published `ghcr.io/infinitydon/ella-ue-phones:0.3.4` and `ghcr.io/infinitydon/ella-ue-browser:0.3.4` images. No node-local image import or installation script is required. Both images include Linux IP, ICMP, DNS, HTTP, socket and packet-capture tools. Browser tools retain the same unprivileged UE-only network restrictions.

Optional rebuild and publication from this directory on Linux:

```sh
buildah login ghcr.io
buildah bud --layers -t ghcr.io/infinitydon/ella-ue-phones:0.3.4 .
buildah push ghcr.io/infinitydon/ella-ue-phones:0.3.4
buildah bud --layers -t ghcr.io/infinitydon/ella-ue-browser:0.3.4 ./browser
buildah push ghcr.io/infinitydon/ella-ue-browser:0.3.4
```

The Dockerfile checks out Core revision `c7cf03530e52a2d353d9d1cd6159943319075bf0`, installs the application adapters and enables NAS SMS capability in the upstream voice UE constructor. The standalone application is compiled inside that upstream module because its RAN helpers are internal Go packages. Only the application/adapters are stored here; upstream source and licensing remain in their own repository.

From the repository's ella-core directory:

```sh
helm upgrade --install ue ./ue-phones -n ella-services-test --wait
kubectl -n ella-services-test rollout status deployment/ue-ue-a
kubectl -n ella-services-test rollout status deployment/ue-ue-b
```

Open Phone A at **http://<node-ip>:30880** and Phone B at **http://<node-ip>:30881**. The current lab uses node **192.168.88.165**. Each UI shows only its own subscriber. Register each phone for IMS calls and answer from the other UI. NAS SMS works independently of IMS registration. No port forwarding is required.

When upgrading the old shared dashboard, scale deployment ue-phones to zero and delete its Service before upgrading: the new Phone A Service reuses its NodePort. This also prevents two simulator processes from owning the same IMSIs. The previous application should not run alongside the dedicated deployments.

### Select the Service type

```yaml
service:
  type: NodePort # ClusterIP, NodePort or LoadBalancer
  port: 8080
  annotations: {}
phones:
  - {name: ue-a, id: "1", label: Phone A, peer: ue-b, gnbId: "000009", nodePort: 30880}
  - {name: ue-b, id: "2", label: Phone B, peer: ue-a, gnbId: "00000a", nodePort: 30881}
```

Use Helm overrides such as `--set service.type=ClusterIP` for internal-only access, or `--set service.type=LoadBalancer` with a cluster load-balancer implementation. Set each phones[].nodePort to 0 for automatic allocation; these ports are ignored for ClusterIP. Supply provider settings through service.annotations. For NodePort, choose a free port in the cluster's configured range (normally 30000–32767).

Set image.repository/tag/pullPolicy for a registry-hosted image, nodeSelector for the selected node, networkAttachment for the existing Multus NAD and n3Interface for its interface name. The current chart is a two-UE lab fixture with fixed subscriber identities and 5G access, not a generic subscriber management application.

The backend starts its HTTP server before attaching UEs. `/healthz` reports HTTP process health; `/api/state` reports actual UE readiness and startup failures. A green process probe does not imply a successful network attach. After replacing Core, reattach the UEs by restarting their deployments. The lab default resolves Core through its headless Service; explicit external coreN2 IP overrides must be updated if that address changes.

## Browsing through the UE data connection

Each phone has its own non-root Chromium sidecar, ephemeral browser profile, 500×900 mobile viewport, and noVNC display embedded in the Browser tab. Enter a website address and click Go; https:// is added automatically when omitted, and explicit http:// addresses are preserved. The page supports original CSS, images, JavaScript and interactive input. noVNC streams pixels and input, while website requests execute inside the UE pod. Chromium uses mobile emulation, not an Android OS emulator.

Chromium connects to a loopback-only SOCKS5 listener in the simulator. The listener resolves DNS and opens TCP sockets bound to that subscriber's internet PDU address. An unreachable fallback route prevents source-policy lookup from falling through to the pod network if its TUN route disappears. Source routing sends traffic through the UE TUN, N3/GTP-U, Ella Core and N6. IPv4/IPv6 owner firewall rules restrict browser UID 1000 to loopback and responses to established connections; new direct egress is rejected. QUIC is disabled. Public TCP ports 80/443 are supported; private and special-use addresses are rejected. VNC, websockify and Chromium debugging bind only to loopback, and the UI reverse-proxies noVNC on the same Service.

Set browser.enabled=false for the lightweight formatted reader instead. Reader requests retain the 25-second/1-MiB limits; Chromium browsing does not use that reader body limit. Browser profiles and simulator message history reset with pod replacement. Full browser sessions use more RAM than the reader; requests/limits are configurable under browser.resources.

The chart deploys an optional N6 gateway using the same image and routing tools. Defaults are bridge ella-test-n6, gateway 10.6.0.1/24, Core N6 address 10.6.0.2 and UE pool 10.45.0.0/16. It NATs both original UE sources and Core's already-translated N6 source onto its pod-network egress. Configure internetGateway values for a different topology, or disable it when using your own gateway. It must share the node-local bridge with Core/IMS. Gateway replacement can briefly interrupt browsing while neighbor entries refresh.

The ella-core-lab chart installs the Core source route through its permanent troubleshoot sidecar. No debug-container injection or host-side route script is needed on a fresh install. Only internet-pool traffic uses table 200 through the N6 gateway; Core API/Diameter routes remain on the pod network. The default coreN2 uses the headless Core Service DNS name, so reinstalling Core does not require editing a pod IP.

## Validate

With the NodePort Service reachable:

```sh
python3 ue-phones/tests/smoke.py --network --output phone-results.json
```

The --network option verifies per-UE proxy egress, direct-egress rejection, independent tunnel failure and recovery. It briefly interrupts Phone A internet access and restores its tunnel and source route in a finally block.

The cross-platform smoke test checks both NAS attachments and IMS registrations, bidirectional SMS including accented text and actual UE receipt, calls in both directions with manual-answer API controls, bidirectional voice-QFI packet counters, hang-up and deregistration/reregistration. It leaves both phones registered and ready for use.

The API accepts same-origin browser mutations only, validates action names and recipient numbers, limits request/message sizes, and serializes actions per phone. The sender label `accepted by SMSC` is not a delivery claim; it changes to `delivered to UE` only when the other persistent simulated UE receives the matching NAS SMS.

## Remove

```sh
helm uninstall ue -n ella-services-test
```

The IMS/SMSC releases and their databases remain separate.

Available Call/Answer buttons are solid green; End/Decline is solid red. Unavailable actions are gray and carry explicit availability labels.

## Browser recovery

The noVNC viewer reconnects automatically with bounded exponential backoff and a manual Reconnect now action. It pauses retries while offline, retries when connectivity returns, and replaces connections that fail to complete their handshake. Viewer HTML/JavaScript is served without caching and is versioned so an older disconnected viewer is not reused after upgrades.

The browser container supervises Chromium, Xvfb, Openbox, x11vnc and websockify under tini. If a component exits, the stack restarts; Kubernetes startup/liveness checks also verify the X display, VNC handshake, web viewer and Chromium API, allowing hung services to recover. The UE container remains separate from browser restart handling.

The profile and last observed HTTP/HTTPS page are checkpointed in a pod-local emptyDir. Cookies/profile data and that page survive a browser-container restart, including a forced process kill. This is best-effort URL recovery, not restoration of unsaved form contents; pod replacement still clears the profile. The last-page checkpoint updates every few seconds.

Default browser memory is now 2 GiB with a 512 MiB request. browser.resources remains configurable; browser.rendererProcessLimit defaults to 4 as an advisory Chromium process target. Heavy pages can still exceed a configured limit, so recovery handles process/container failures rather than assuming they never happen.

~~~sh
node --test ue-phones/browser/connection.test.js
# Open a webpage and register Phone A before these deliberate failure tests:
python3 ue-phones/tests/browser-recovery.py --component Chromium --output chromium-recovery.json
python3 ue-phones/tests/browser-recovery.py --component websockify --output display-recovery.json
python3 ue-phones/tests/browser-recovery.py --component websockify --freeze --output hung-display-recovery.json
~~~

The failure tests verify restart in the same pod, profile/page recovery, and unchanged UE registration/address/restart count. The freeze case is rescued by the liveness probe. Browser reconnection itself can be observed in the already-open phone UI, without refreshing it.

## Connectivity tools

All three custom images (phones/gateway, Chromium and integration tester) include `ip`, `ss`, `ping`, `arping`, `tracepath`, `traceroute`, `dig`, `nslookup`, `curl`, `wget`, `nc`, `tcpdump`, `iptables`, `ethtool`, `procps`, `jq` and `openssl`.

```sh
kubectl -n ella-services-test exec deployment/ue-ue-a -c phone -- ip address
kubectl -n ella-services-test exec deployment/ue-ue-a -c phone -- ss -lnptu
kubectl -n ella-services-test exec deployment/ue-ue-a -c phone -- tcpdump -ni any -c 10
kubectl -n ella-services-test exec deployment/ue-ue-a -c browser -- curl --socks5-hostname 127.0.0.1:1080 -I https://example.com
kubectl -n ella-services-test exec ella-services-tester -- dig ella-core-lab
```

Use `ping -I <internetIp>` or `dig -b <internetIp> @8.8.8.8 example.com` in the phone container to test its current UE data address shown by `/api/state`. Browser UID 1000 remains restricted to the local SOCKS proxy; raw sockets and direct external traffic are intentionally unavailable there. Packet capture and interface changes belong in the privileged phone/tester containers or the Core diagnostic sidecar.

For a private registry, create a Kubernetes pull Secret separately and set `imagePullSecrets: [{name: your-pull-secret}]` on this chart and `tester.imagePullSecrets` on the Core lab chart. Never store registry credentials in values committed to Git.
