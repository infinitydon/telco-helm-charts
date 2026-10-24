# UE phones

Two phone-like panels control persistent simulated 5G UEs on the Ella Core integration lab. The backend reuses the pinned upstream Core RAN/UE and IMS libraries; it does not replay test logs or fake network outcomes.

Each phone supports IMS register/unregister, dial, incoming-call indication, answer, reject/cancel/hang-up, synthetic RTP counters, and a NAS SMS composer/inbox. Sent messages distinguish SMSC acceptance from actual receipt by the other simulated UE. Accented text is supported. The event feed shows registration, SMS and call events.

Calls exchange synthetic test packets on the dedicated voice QFI. Browser microphone/speaker audio is not connected. The UI is intended for protocol testing, not as a browser softphone. History is bounded to 100 messages per phone and 100 events, held in memory and cleared on simulator restart.

## Prerequisites

Deploy and provision the [IMS/SMSC integration lab](../tests/services/README.md) first. This application uses its two voice subscribers:

| Phone | IMSI | Number |
| --- | --- | --- |
| A | 001018400000003 | +15558400003 |
| B | 001018400000004 | +15558400004 |

Both need the public lab test key/OPc and internet/ims policies configured by bootstrap.ps1. They remain NAS-attached when IMS is unregistered, so SMS continues to work independently of IMS. Do not run the original test scenarios concurrently against these same IMSIs; each UE must have one owner.

The simulator pod is privileged for TUN, IPsec/XFRM and network configuration. It shares the existing `ella-ran` bridge attachment and must run on the same node as the lab Core/IMS. The chart exposes a ClusterIP Service for local port forwarding. It has no user authentication; do not expose it to untrusted networks.

## Build and deploy

From this directory on the selected Linux node:

```sh
sudo buildah bud --layers -t localhost/ella-ue-phones:0.1.0 .
sudo buildah push localhost/ella-ue-phones:0.1.0 docker-archive:/tmp/ella-ue-phones.tar:localhost/ella-ue-phones:0.1.0
sudo microk8s ctr images import /tmp/ella-ue-phones.tar
```

The Dockerfile checks out Core revision `c7cf03530e52a2d353d9d1cd6159943319075bf0`, installs the application adapters and enables NAS SMS capability in the upstream voice UE constructor. The standalone application is compiled inside that upstream module because its RAN helpers are internal Go packages. Only the application/adapters are stored here; upstream source and licensing remain in their own repository.

From the repository's ella-core directory:

```sh
helm upgrade --install ue ./ue-phones -n ella-services-test --set coreN2=<core-pod-ip>:38412
kubectl -n ella-services-test rollout status deployment/ue-phones
kubectl -n ella-services-test port-forward service/ue-phones 18080:8080
```

Open **http://127.0.0.1:18080**. Click **Register both phones**, then call the other phone and answer in its panel. The Messages tab works once NAS SMS is ready, without an IMS registration. The default recipient is the other phone.

Set image.repository/tag/pullPolicy for a registry-hosted image, nodeSelector for the selected node, networkAttachment for the existing Multus NAD and n3Interface for its interface name. The current chart is a two-UE lab fixture with fixed subscriber identities and 5G access, not a generic subscriber management application.

The backend starts its HTTP server before attaching UEs. `/healthz` reports HTTP process health; `/api/state` reports actual UE readiness and startup failures. A green process probe does not imply a successful network attach. After changing Core's pod IP, update coreN2 and restart this release.

## Validate

With the UI port forward running:

```powershell
./ue-phones/tests/smoke.ps1 -ResultsFile ./phone-results.json
```

This checks both NAS attachments and IMS registrations, bidirectional SMS including accented text and actual UE receipt, calls in both directions with manual-answer API controls, bidirectional voice-QFI packet counters, hang-up and deregistration/reregistration. It leaves both phones registered and ready for use.

The API accepts same-origin browser mutations only, validates action names and recipient numbers, limits request/message sizes, and serializes actions per phone. The sender label `accepted by SMSC` is not a delivery claim; it changes to `delivered to UE` only when the other persistent simulated UE receives the matching NAS SMS.

## Remove

```sh
helm uninstall ue -n ella-services-test
```

The IMS/SMSC releases and their databases remain separate.
