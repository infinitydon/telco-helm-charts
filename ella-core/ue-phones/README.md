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

Both need the public lab test key/OPc and internet/ims policies configured by bootstrap.ps1. They remain NAS-attached when IMS is unregistered, so SMS continues to work independently of IMS. Do not run the original test scenarios concurrently against these same IMSIs; each UE must have one owner.

The simulator pod is privileged for TUN, IPsec/XFRM and network configuration. Each shares the existing `ella-ran` bridge attachment and must run on the same node as the lab Core/IMS. The chart defaults to dedicated NodePort Services on ports 30880 and 30881. It has no user authentication; use it on a trusted lab network.

## Build and deploy

From this directory on the selected Linux node:

```sh
sudo buildah bud --layers -t localhost/ella-ue-phones:0.3.0 .
sudo buildah push localhost/ella-ue-phones:0.3.0 docker-archive:/tmp/ella-ue-phones.tar:localhost/ella-ue-phones:0.3.0
sudo microk8s ctr images import /tmp/ella-ue-phones.tar
sudo buildah bud --layers -t localhost/ella-ue-browser:0.3.0 ./browser
sudo buildah push localhost/ella-ue-browser:0.3.0 docker-archive:/tmp/ella-ue-browser.tar:localhost/ella-ue-browser:0.3.0
sudo microk8s ctr images import /tmp/ella-ue-browser.tar
```

The Dockerfile checks out Core revision `c7cf03530e52a2d353d9d1cd6159943319075bf0`, installs the application adapters and enables NAS SMS capability in the upstream voice UE constructor. The standalone application is compiled inside that upstream module because its RAN helpers are internal Go packages. Only the application/adapters are stored here; upstream source and licensing remain in their own repository.

From the repository's ella-core directory:

```sh
helm upgrade --install ue ./ue-phones -n ella-services-test --set coreN2=<core-pod-ip>:38412
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

The backend starts its HTTP server before attaching UEs. `/healthz` reports HTTP process health; `/api/state` reports actual UE readiness and startup failures. A green process probe does not imply a successful network attach. After changing Core's pod IP, update coreN2 and restart this release.

## Browsing through the UE data connection

Each phone has its own non-root Chromium sidecar, ephemeral browser profile, 500×900 mobile viewport, and noVNC display embedded in the Browser tab. Enter a URL and click Go; the page supports original CSS, images, JavaScript and interactive input. noVNC streams pixels and input, while website requests execute inside the UE pod. Chromium uses mobile emulation, not an Android OS emulator.

Chromium connects to a loopback-only SOCKS5 listener in the simulator. The listener resolves DNS and opens TCP sockets bound to that subscriber's internet PDU address. An unreachable fallback route prevents source-policy lookup from falling through to the pod network if its TUN route disappears. Source routing sends traffic through the UE TUN, N3/GTP-U, Ella Core and N6. IPv4/IPv6 owner firewall rules restrict browser UID 1000 to loopback and responses to established connections; new direct egress is rejected. QUIC is disabled. Public TCP ports 80/443 are supported; private and special-use addresses are rejected. VNC, websockify and Chromium debugging bind only to loopback, and the UI reverse-proxies noVNC on the same Service.

Set browser.enabled=false for the lightweight formatted reader instead. Reader requests retain the 25-second/1-MiB limits; Chromium browsing does not use that reader body limit. Browser profiles and simulator message history reset with pod replacement. Full browser sessions use more RAM than the reader; requests/limits are configurable under browser.resources.

The chart deploys an optional N6 gateway using the same image and routing tools. Defaults are bridge ella-test-n6, gateway 10.6.0.1/24, Core N6 address 10.6.0.2 and UE pool 10.45.0.0/16. It NATs both original UE sources and Core's already-translated N6 source onto its pod-network egress. Configure internetGateway values for a different topology, or disable it when using your own gateway. It must share the node-local bridge with Core/IMS. Gateway replacement can briefly interrupt browsing while neighbor entries refresh.

The current core-lab.yaml fixture includes a source-route helper: only packets from the internet UE pool use table 200's default route through 10.6.0.1. Core's API/Diameter routes remain on the pod network, and IMS traffic remains separate. To enable that route in an existing lab without restarting Core or losing its ephemeral database:

```powershell
./ue-phones/tests/enable-internet.ps1
```

That script adds a privileged debug network helper to the existing Core pod when necessary. Its route lasts for that pod's lifetime; newly deployed Core lab pods obtain the equivalent persistent sidecar from the fixture manifest.

## Validate

With the NodePort Service reachable:

```powershell
./ue-phones/tests/split-smoke.ps1 -BaseUrlA http://192.168.88.165:30880 -BaseUrlB http://192.168.88.165:30881 -ResultsFile ./phone-results.json
./ue-phones/tests/web-smoke.ps1 -BaseUrl http://192.168.88.165:30880 -PeerBaseUrl http://192.168.88.165:30881 -ResultsFile ./web-results.json
```

Run ./ue-phones/tests/browser-network.ps1 to verify per-UE proxy egress, direct-egress rejection, independent tunnel failure and recovery. It briefly interrupts Phone A internet access and restores its tunnel and source route in a finally block.

The split smoke test checks both NAS attachments and IMS registrations, bidirectional SMS including accented text and actual UE receipt, calls in both directions with manual-answer API controls, bidirectional voice-QFI packet counters, hang-up and deregistration/reregistration. It leaves both phones registered and ready for use.

The API accepts same-origin browser mutations only, validates action names and recipient numbers, limits request/message sizes, and serializes actions per phone. The sender label `accepted by SMSC` is not a delivery claim; it changes to `delivered to UE` only when the other persistent simulated UE receives the matching NAS SMS.

## Remove

```sh
helm uninstall ue -n ella-services-test
```

The IMS/SMSC releases and their databases remain separate.

Available Call/Answer buttons are solid green; End/Decline is solid red. Unavailable actions are gray and carry explicit availability labels.
