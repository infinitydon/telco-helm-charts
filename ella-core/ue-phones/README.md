# UE phones

Two phone-like panels control persistent simulated 5G UEs on the Ella Core integration lab. The backend reuses the pinned upstream Core RAN/UE and IMS libraries; it does not replay test logs or fake network outcomes.

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

The simulator pod is privileged for TUN, IPsec/XFRM and network configuration. It shares the existing `ella-ran` bridge attachment and must run on the same node as the lab Core/IMS. The chart defaults to a NodePort Service on port 30880. It has no user authentication; use it on a trusted lab network.

## Build and deploy

From this directory on the selected Linux node:

```sh
sudo buildah bud --layers -t localhost/ella-ue-phones:0.2.3 .
sudo buildah push localhost/ella-ue-phones:0.2.3 docker-archive:/tmp/ella-ue-phones.tar:localhost/ella-ue-phones:0.2.3
sudo microk8s ctr images import /tmp/ella-ue-phones.tar
```

The Dockerfile checks out Core revision `c7cf03530e52a2d353d9d1cd6159943319075bf0`, installs the application adapters and enables NAS SMS capability in the upstream voice UE constructor. The standalone application is compiled inside that upstream module because its RAN helpers are internal Go packages. Only the application/adapters are stored here; upstream source and licensing remain in their own repository.

From the repository's ella-core directory:

```sh
helm upgrade --install ue ./ue-phones -n ella-services-test --set coreN2=<core-pod-ip>:38412
kubectl -n ella-services-test rollout status deployment/ue-phones
```

Open **http://<node-ip>:30880**; the current lab is **http://192.168.88.165:30880**. No port forwarding is required. Click **Register both phones**, then call the other phone and answer in its panel. The Messages tab works once NAS SMS is ready, without an IMS registration. The default recipient is the other phone.

### Select the Service type

```yaml
service:
  type: NodePort # ClusterIP, NodePort or LoadBalancer
  port: 8080
  nodePort: 30880 # 0 requests automatic allocation; ignored for ClusterIP
  annotations: {}
```

Use Helm overrides such as `--set service.type=ClusterIP` for internal-only access, or `--set service.type=LoadBalancer --set service.nodePort=0` with a cluster load-balancer implementation. Supply provider settings through service.annotations. For NodePort, choose a free port in the cluster's configured range (normally 30000–32767).

Set image.repository/tag/pullPolicy for a registry-hosted image, nodeSelector for the selected node, networkAttachment for the existing Multus NAD and n3Interface for its interface name. The current chart is a two-UE lab fixture with fixed subscriber identities and 5G access, not a generic subscriber management application.

The backend starts its HTTP server before attaching UEs. `/healthz` reports HTTP process health; `/api/state` reports actual UE readiness and startup failures. A green process probe does not imply a successful network attach. After changing Core's pod IP, update coreN2 and restart this release.

## Browsing through the UE data connection

Each phone's **Browser** tab fetches public HTTP/HTTPS pages through that subscriber's separate internet PDU session. DNS and TCP sockets bind to its assigned internet UE IP, a source policy route sends them into its internet TUN, and traffic traverses N3/GTP-U, Ella Core and the N6 internet gateway. The UI displays that UE IP, HTTP status, response size and request duration. Links load through the same UE path. There is no fallback to fetching pages through the dashboard pod's ordinary default route.

This is a **reader view**: formatted page text and links, not a full JavaScript browser. Scripts, logins, forms, images and downloads are not loaded. IPv4 HTTP/HTTPS on ports 80/443 is supported, with verified TLS, bounded redirects, a 25-second request timeout and a 1 MiB page limit. Private/special-use destinations and embedded URL credentials are rejected. Mobile requests use a mobile User-Agent. The phone preserves headings, paragraphs, lists, tables, emphasis and inline links in a responsive reader layout. Remote scripts, styles, resource URLs and event handlers are stripped; link navigation always fetches through the same UE.

The chart deploys an optional N6 gateway using the same image and routing tools. Defaults are bridge ella-test-n6, gateway 10.6.0.1/24, Core N6 address 10.6.0.2 and UE pool 10.45.0.0/16. It NATs both original UE sources and Core's already-translated N6 source onto its pod-network egress. Configure internetGateway values for a different topology, or disable it when using your own gateway. It must share the node-local bridge with Core/IMS. Gateway replacement can briefly interrupt browsing while neighbor entries refresh.

The current core-lab.yaml fixture includes a source-route helper: only packets from the internet UE pool use table 200's default route through 10.6.0.1. Core's API/Diameter routes remain on the pod network, and IMS traffic remains separate. To enable that route in an existing lab without restarting Core or losing its ephemeral database:

```powershell
./ue-phones/tests/enable-internet.ps1
```

That script adds a privileged debug network helper to the existing Core pod when necessary. Its route lasts for that pod's lifetime; newly deployed Core lab pods obtain the equivalent persistent sidecar from the fixture manifest.

## Validate

With the NodePort Service reachable:

```powershell
./ue-phones/tests/smoke.ps1 -BaseUrl http://192.168.88.165:30880 -ResultsFile ./phone-results.json
./ue-phones/tests/web-smoke.ps1 -BaseUrl http://192.168.88.165:30880 -ResultsFile ./web-results.json
```

This checks both NAS attachments and IMS registrations, bidirectional SMS including accented text and actual UE receipt, calls in both directions with manual-answer API controls, bidirectional voice-QFI packet counters, hang-up and deregistration/reregistration. It leaves both phones registered and ready for use.

The API accepts same-origin browser mutations only, validates action names and recipient numbers, limits request/message sizes, and serializes actions per phone. The sender label `accepted by SMSC` is not a delivery claim; it changes to `delivered to UE` only when the other persistent simulated UE receives the matching NAS SMS.

## Remove

```sh
helm uninstall ue -n ella-services-test
```

The IMS/SMSC releases and their databases remain separate.

Available Call/Answer buttons are solid green; End/Decline is solid red. Unavailable actions are gray and carry explicit availability labels.
