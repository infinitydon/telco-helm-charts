# Ella stack

One Helm release deploys the unified Ella Core, its UI/API Service and diagnostics, with optional IMS, SMSC and per-UE phone/browser UIs. This replaces the duplicated HA, FQDN, lab and UI-only Core charts. Core is pinned to upstream source revision c7cf03530e52 (version string v1.20.0), built with its matching frontend and Linux connectivity tools; custom runtime images are public GHCR images with connectivity tools.

## Linux installation

Install Helm 3+, kubectl and Python 3 only for optional tests. From the repository root:

```sh
helm dependency build ./ella-core/ella-stack
helm upgrade --install ella ./ella-core/ella-stack \
  --namespace ella-services-test --create-namespace \
  -f ./ella-core/ella-stack/examples/standalone-internet-ims-sms.yaml \
  --set-file core.admin.password=/secure/ella-admin-password \
  --wait --wait-for-jobs --timeout 10m
```

The protected password file is a plain text file outside Git containing only the password, without a trailing newline. Alternatively set core.admin.existingSecret to an existing same-namespace Secret containing email and password. No host setup/provisioning script, local image import or registry credentials are required.

The Linux tests use Helm 3.20.2. With Helm 4, use --wait=legacy in place of --wait; both clients were exercised against this cluster.

| Preset under examples/ | Core instances | Services |
| --- | --- | --- |
| standalone-internet.yaml | One | Internet only |
| standalone-internet-ims-sms.yaml | One | Internet, IMS and NAS SMS |
| ha-internet.yaml | Three on separate hosts | Internet only |
| ha-internet-ims-sms.yaml | Three on separate hosts | Internet, IMS and NAS SMS |

Both service modes are controlled by global.mode. Core topology is core.topology. The presets enable public test subscribers, two simulated UEs and the lab N6 gateway; use them only in a dedicated test namespace. Default values leave lab provisioning and phones disabled. For an existing provisioned network, set core.provisioning.enabled=false and configure subscribers through Core instead.

## Network requirements

All Core nodes require Linux 6.6+ (TCX), SCTP, Multus, a default RWO StorageClass and privileges to attach the datapath. The phone simulator also needs TUN and XFRM. HA requires three compatible nodes and enforces anti-affinity unless explicitly overridden.

Core N2, N3 and Raft use the routable Kubernetes pod network. Raft advertises stable pod FQDNs; it never guesses addresses from Whereabouts allocation order. The configurable clusterDomain defaults to cluster.local. N6 uses a Multus macvlan on global.network.master (default eth0), with a shared L2 network across the Core nodes, IMS and gateway. Configure addresses/pools before installation if the defaults overlap your network. The sample uses N6 gateway10.6.0.1, Core10.6.0.2/.3/.4 and IMS10.6.0.5, internet UE pool10.45/16 and IMS UE pool10.60/16. The host's own macvlan parent cannot directly reach its child; management uses pod-network Services instead.

A node-local bridge is available for standalone deployments through global.network.type=bridge and global.network.bridge. HA with bridge is rejected because separate host bridges do not provide shared L2 connectivity. The lab gateway is core.controller.gatewayEnabled; disable it and provide external routing/NAT in real networks.

## UI and components

The default Core UI/API Service is NodePort30502. Configure core.service.type as ClusterIP, NodePort or LoadBalancer, with nodePort and annotations as required. Phone A/B use ports30880/30881 and independently support the same Service types through phones.service.type. No port forwarding is needed. Lab UIs are intended for a trusted network.

IMS and SMSC remain separately installable charts, but the umbrella automatically renders neither when global.mode=internet. Combined mode requires both dependencies enabled. phones.enabled toggles the simulator; phones.browser.enabled toggles Chromium/noVNC, with the lighter reader still available. UERANSIM remains a separate alternative simulator chart; it is not used by these validated UE phone presets.

## Bootstrap and persistence

The provisioning Job is an ordinary Kubernetes Job, not a post-install hook. It initializes the first Core, joins followers through the v1.20 cluster API, waits for membership, then optionally provisions the selected services and lab subscribers. This avoids a Helm readiness/join deadlock. Always use --wait-for-jobs. Phone init containers wait for provisioning success and Core rollout readiness; their short-lived API token can list namespace Jobs and read the release's Core StatefulSet, and is not mounted in the runtime containers. Keep the current completed bootstrap Job: replacement phone Pods use it to verify provisioning.

Core uses StatefulSets and persistent per-node databases. IMS/SMSC use their own PVCs. Helm uninstall leaves Core StatefulSet PVCs in place; back up before any explicit PVC deletion. Local-path storage ties a member's volume to its host; the tested Pod replacement does not certify recovery from permanent host/storage loss. Do not reuse a standalone database as an HA database or vice versa without a supported migration procedure. The chart rejects in-place topology changes: back up, uninstall and explicitly migrate/reset data first.

Service-mode changes preserve Core subscriber/configuration data and recreate UE pods and their ephemeral browser profiles/history. Switching back to internet-only stops IMS/SMSC and prunes their chart-owned PVCs; use external claims through ims.persistence.existingClaim and smsc.persistence.existingClaim, or take backups, if their databases must survive that switch. The Core's earlier IMS/SMS configuration remains stored even when the phone/service mode is internet-only.

The controller watches public Core status, patches only the Core UI/API and active NGAP/Diameter Services, and updates the lab return routes on leader changes. Its gateway disables ICMP redirects so IMS cannot cache a route that bypasses the gateway and keeps pointing at an old leader. A Raft election is not a guarantee that ongoing calls or RAN sessions survive a process failure; clients may need to reattach. See VALIDATION.md for exactly what was tested.

## Tests

```sh
helm test ella -n ella-services-test --timeout 90s
python3 ella-core/ue-phones/tests/internet-smoke.py --release ella --host NODE_IP
python3 ella-core/ue-phones/tests/smoke.py --release ella --network \
  --phone-a http://NODE_IP:30880 --phone-b http://NODE_IP:30881
```

Use the internet-only test in internet mode and the full smoke test in combined mode. The scenario runner uses the same IMSIs as persistent phones: pause those deployments before running it. Test runners need kubectl access to the namespace. All commands are Linux shell/Helm commands; no Windows scripts are shipped.

## Core image provenance

The released v1.20.0 image (revision34f32e9) does not refresh other cluster members' cached API addresses after Pod IP changes. HA protocol tests exposed stale 0.0.0.0/old-Pod addresses after replacement. The default is therefore an unmodified upstream source build at c7cf03530e52a2d353d9d1cd6159943319075bf0, which includes the member-address reconciliation fix and matches the UE/tester libraries. This is a pinned post-release snapshot, not a new official Ella release.

Public image: ghcr.io/infinitydon/ellacore:c7cf03530e52-tools2, pinned by manifest digest in core values. The reproducible Linux Dockerfile is in ../ella-core/images/Dockerfile; upstream LICENSE/NOTICE files are included in the image. All supplied custom images and the validated presets target Linux/amd64, with architecture selectors to avoid scheduling incompatible binaries. Users may override core.image to an appropriately tested upstream release when that fix is published.

N6 macvlan can retain parent checksum offload despite ethtool. Core and IMS initialization configure pod-local tc checksum actions for IPv4 TCP/UDP, including same-host delivery and packets entering the simulated UE TUN. They do not modify the host NIC. Kernel act_csum support is required on Core and IMS nodes.

In combined lab mode, bootstrap configures one IMS Diameter peer per Core ordinal. The controller reconciles those peers in creation-ID order after Pod IP changes. These entries are chart-managed: do not insert/reorder unrelated IMS peers in a provisioned lab. Keeping all Core identities reachable lets IMS use the HSS remembered by an existing registration after Raft leadership changes.
