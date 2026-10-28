# Ella stack

One Helm release deploys the unified Ella Core, its UI/API Service and diagnostics, with optional IMS, SMSC and per-UE phone/browser UIs. This replaces the duplicated HA, FQDN, lab and UI-only Core charts. Core is pinned to upstream source revision c7cf03530e52 (version string v1.20.0), built with its matching frontend and Linux connectivity tools; custom runtime images are public GHCR images with connectivity tools.

## Install two independent lab stacks

Install Helm 3+, kubectl and Python 3 for the optional acceptance tests. The
two sample values files use separate N6/N2N3 address ranges and NodePorts, so
the standalone and HA releases can run at the same time. Check that the sample
subnets are unused and that `eth0` reaches the same Layer 2 network on every
node selected for Core, IMS/SMSC and the radio simulators.

From the repository root, build the vendored chart dependencies once:

```sh
helm dependency build ./ella-core/ella-stack
```

Keep each admin password in a protected file outside the repository. Each
file must contain only the password, without a trailing newline. Then install
the two releases independently:

```sh
helm upgrade --install ella-sa ./ella-core/ella-stack \
  --namespace ella-sa --create-namespace \
  -f ./ella-core/ella-stack/examples/standalone-n2n3-test.yaml \
  --set-file core.admin.password="$HOME/.secrets/ella-sa-password" \
  --wait --wait-for-jobs --timeout 10m

helm upgrade --install ella-ha ./ella-core/ella-stack \
  --namespace ella-ha --create-namespace \
  -f ./ella-core/ella-stack/examples/ha-n2n3-test.yaml \
  --set-file core.admin.password="$HOME/.secrets/ella-ha-password" \
  --wait --wait-for-jobs --timeout 15m
```

Use `core.admin.existingSecret` instead when a same-namespace Secret already
contains `email` and `password`. The UI login email defaults to
`lab@example.com`; set `core.admin.email` to change it. The password is the
value from the protected file/Secret. No host setup script, local image import
or registry credentials are required for the public images. Helm 4 users can
use `--wait=legacy` if the Helm client does not accept `--wait`.

The supplied sample addresses are examples, not automatically reserved IPs.
Choose unused addresses on the network attached to `global.network.master`;
keep every static address unique across both releases and other hosts.

| Preset under examples/ | Core instances | Services |
| --- | --- | --- |
| standalone-internet.yaml | One | Internet only |
| standalone-internet-ims-sms.yaml | One | Internet, IMS and NAS SMS |
| ha-internet.yaml | Three on separate hosts | Internet only |
| ha-internet-ims-sms.yaml | Three on separate hosts | Internet, IMS and NAS SMS |
| standalone-n2n3-test.yaml | One | Internet, IMS/SMS, phones, UERANSIM and PacketRusher; unique lab subnet/NodePorts |
| ha-n2n3-test.yaml | Three | Same components with HA; separate lab subnet/NodePorts |

Both service modes are controlled by `global.mode`; Core topology is
`core.topology`. The internet/IMS/SMS sample presets provision public test
subscribers, enable the two fixed-identity phone UEs and deploy the optional
N6 lab gateway. The `*-n2n3-test.yaml` samples also enable UERANSIM and
PacketRusher. These are isolated lab fixtures; use a dedicated namespace and
never reuse their test subscriber identities in another active UE simulator.
Default chart values leave provisioning and the phone/native simulators
disabled. For an existing provisioned network, disable the bootstrap
provisioning fixture and configure subscribers through Core instead.

## Network requirements

Core nodes require Linux 6.6+ with TCX support, SCTP, Multus, an available
RWO StorageClass and privileges to attach the datapath. HA requires three
compatible nodes and spreads Core members with anti-affinity. The phone
simulator needs `/dev/net/tun` and XFRM. PacketRusher's eBPF backend requires a
compatible Linux 6.6+ node with BTF; use `packetrusher.nodeSelector` or
`packetrusher.affinity` to keep it off older-kernel nodes. UERANSIM can run on
a wider set of Linux kernels.

Raft uses the Kubernetes pod network and stable per-member FQDNs. N6 is a
Multus macvlan interface (`net1`); N2/N3 use a separate Multus attachment
(`net2`) by default in `ella-stack`. `global.network.n6.coreAddresses` contains
the Core N6/net1 addresses, while
`global.network.n2n3.coreInterfaceAddresses` contains its shared N2/N3/net2
addresses. Both lists are ordered by StatefulSet ordinal: standalone has one
Core Pod and needs exactly one address in each list; HA needs one address per
Core replica (three by default). The standalone example uses `.2` on each
interface; the HA example maps `.2`, `.3` and `.4` to `core-0`, `core-1` and
`core-2`, respectively. N2 SCTP and N3 GTP-U share `net2`. Core, phone UEs,
UERANSIM and PacketRusher must share the N2/N3 Layer 2 network. Each radio has
its own static address. The phone and simulator
supervisors inspect the active Core API and reattach their gNB after
leadership changes. These are static addresses, not Whereabouts allocations.

N6 macvlan must also share Layer 2 across the Core hosts, IMS and gateway. The
default HA example uses gateway `10.6.0.1`, Core `10.6.0.2/.3/.4`, IMS
`10.6.0.5`, N2/N3 Core `10.211.0.2/.3/.4`, radio devices `.20/.21/.30/.31`,
internet pool `10.45.0.0/16`, and IMS pool `10.60.0.0/16`. The dedicated
`*-n2n3-test.yaml` files use distinct subnets and ports for simultaneous SA
and HA installs. A macvlan parent host cannot directly reach its child; use
the pod-network Services for management and the documented NodePorts for UIs.

A node-local bridge is available for standalone deployments through global.network.type=bridge and global.network.bridge. HA with bridge is rejected because separate host bridges do not provide shared L2 connectivity. The optional lab N6 gateway is a dedicated `core-n6-gateway` Deployment (`core.n6Gateway.enabled`), separate from the Core HA/IMS reconciliation controller. It supplies the sample isolated N6 network's next hop and cluster egress; disable it when N6 is directly connected to a suitable upstream router. When the lab gateway is enabled, the Core bootstrap Job disables Ella Core NAT and the gateway applies one SNAT for internet-pool traffic as it enters Kubernetes egress. The separate IMS UE pool is not SNATed by the gateway: IMS shares the N6 L2 network and its return route sends IMS-pool traffic through the gateway to the elected Core member. The old `core.controller.gatewayEnabled` value remains as a compatibility alias; new values should use `core.n6Gateway.enabled`.

## UI and components

The Core UI/API and each phone UI support `ClusterIP`, `NodePort` or
`LoadBalancer` Services. Configure `core.service.type` and
`phones.service.type`; use `core.service.nodePort` and each entry in
`phones.phones[].nodePort` for fixed NodePorts. The defaults are Core
`30502`, Phone A `30880`, and Phone B `30881`. For simultaneous installs,
choose different free NodePorts for every release; the test examples use
`30504/30505` for Core and `30960–30963` for phones. Provider-specific
LoadBalancer options belong in the relevant Service `annotations`. No port
forward is needed with reachable NodePorts/LoadBalancers. Lab UIs have no
user authentication and should stay on a trusted network.

IMS and SMSC remain separately installable charts, but the umbrella automatically renders neither when global.mode=internet. Combined mode requires both dependencies enabled. phones.enabled toggles the phone simulator; phones.browser.enabled toggles Chromium/noVNC, with the lighter reader still available.

Optional native simulators are included through ueransim.enabled and packetrusher.enabled (both default false). They use upstream UERANSIM v3.3.0 and PacketRusher v2.0.0, respectively, checked as latest stable releases on October 26, 2026. PacketRusher explicitly uses its eBPF backend and requires a compatible Linux 6.6+ node. Both work with the standalone/HA Core presets and use the internet DNN. They complement the phone UI; they do not replace its IMS/SMS implementation. See the [UERANSIM guide](../ueransim-5g-chart/README.md), [PacketRusher guide](../packetrusher/README.md) and [native validation](../tests/simulators/README.md).

## Bootstrap and persistence

The provisioning Job is an ordinary Kubernetes Job, not a post-install hook. It initializes the first Core, joins followers through the v1.20 cluster API, waits for membership, assigns HA member display names from each StatefulSet pod name and namespace, then optionally provisions the selected services and lab subscribers. This avoids a Helm readiness/join deadlock. Always use --wait-for-jobs. Phone init containers wait for provisioning success and Core rollout readiness; their short-lived API token can list namespace Jobs and read the release's Core StatefulSet, and is not mounted in the runtime containers. Keep the current completed bootstrap Job: replacement phone Pods use it to verify provisioning.

The default HA names are `<statefulset-pod-name>.<namespace>`, such as `ella-ha-core-0.ella-ha-test`. Set `core.memberDisplayName.template` using `{pod}` and `{namespace}` placeholders, or set `core.memberDisplayName.enabled=false` to leave Core's generated short IDs in the Cluster page. Names over 63 bytes are rejected by bootstrap.

On a fresh Core, provisioning applies the requested data-network pools, including replacing Core's seeded default. Existing data networks are preserved on upgrades so UI changes are retained. Set core.provisioning.reconcileDataNetworks=true to explicitly reconcile their pools/DNS/MTU; pool changes with attached sessions are rejected. Existing IPv6 pools are preserved.

Core uses StatefulSets and persistent per-node databases. IMS/SMSC use their own PVCs. Helm uninstall leaves Core StatefulSet PVCs in place; back up before any explicit PVC deletion. Local-path storage ties a member's volume to its host; the tested Pod replacement does not certify recovery from permanent host/storage loss. Do not reuse a standalone database as an HA database or vice versa without a supported migration procedure. The chart rejects in-place topology changes: back up, uninstall and explicitly migrate/reset data first.

Service-mode changes preserve Core subscriber/configuration data and recreate UE pods and their ephemeral browser profiles/history. Switching back to internet-only stops IMS/SMSC and prunes their chart-owned PVCs; use external claims through ims.persistence.existingClaim and smsc.persistence.existingClaim, or take backups, if their databases must survive that switch. The Core's earlier IMS/SMS configuration remains stored even when the phone/service mode is internet-only.

The HA controller watches Core status and patches the Core UI/API and active NGAP/Diameter Services. In combined lab mode, it also reconciles IMS Diameter peers after Pod IP changes. When enabled, the separate N6 gateway watches leadership and updates lab return routes; it disables ICMP redirects so IMS cannot cache a route that bypasses the gateway and keeps pointing at an old leader. A Raft election is not a guarantee that ongoing calls or RAN sessions survive a process failure; clients may need to reattach. See VALIDATION.md for exactly what was tested.

Network values are grouped by interface: `global.network.n6.coreAddresses`, `gatewayAddress`, `imsAddress` and `smscAddress` configure N6; `global.network.n2n3.coreInterfaceAddresses` configure the Core's shared N2/N3 interface; `coreN2Addresses` are the Core SCTP N2 destinations advertised to radios. UE DNN address pools are separately under `global.network.dnnPools.internet` and `global.network.dnnPools.ims`. In combined mode, IMS and SMSC attach to the Core N6 Multus network. SMSC's stable address defaults to `global.network.n6.smscAddress: 10.6.0.6`; the chart assigns it to `net1` and provisions Core's Diameter peer with it directly, avoiding the SMSC Pod's changeable Kubernetes `eth0` IP.

For upgrades, legacy unscoped keys (`global.network.coreAddresses`, `gateway`, `imsAddress`, `smscAddress`, `internetPool`, `imsPool`, and `n2n3.coreAddresses`) are mapped to the scoped keys. New values files should use the scoped layout above.

## Tests

Run topology checks and the essential phone/Helm acceptance suite against
either independent test release. The phone ports are parameters so the two
examples can be tested side-by-side:

```sh
python3 ella-core/ella-stack/tests/check-topology.py \
  --release ella-sa --namespace ella-sa --topology standalone \
  --output ella-sa-topology.json
python3 ella-core/ella-stack/tests/smoke.py \
  --release ella-sa --namespace ella-sa --host NODE_IP \
  --mode internet-ims-sms --phone-a-port 30960 --phone-b-port 30961 \
  --output ella-sa-smoke.json

python3 ella-core/ella-stack/tests/check-topology.py \
  --release ella-ha --namespace ella-ha --topology ha \
  --output ella-ha-topology.json
python3 ella-core/ella-stack/tests/smoke.py \
  --release ella-ha --namespace ella-ha --host NODE_IP \
  --mode internet-ims-sms --phone-a-port 30962 --phone-b-port 30963 \
  --output ella-ha-smoke.json
```

The smoke runner detects the service mode, runs Helm health checks, then runs
the matching phone checks. In combined mode these cover both UE attachments,
IMS registration, SMS in both directions, calls/answer/media/release, and
HTTPS through each UE. Internet-only mode checks internet attachment, DNS,
ICMP and HTTPS with IMS/SMS disabled. Tests do not need the Core admin
password or subscriber changes. Provide `--kubeconfig` when the active
kubectl/Helm context is not the intended cluster. See [VALIDATION.md](VALIDATION.md)
for the latest live results and known limitations.

To verify native simulator readiness and their internet DNN sessions, run:

```sh
python3 ella-core/tests/simulators/smoke.py --release ella-sa \
  --namespace ella-sa --ue-pool 10.242.0.0/16
python3 ella-core/tests/simulators/smoke.py --release ella-ha \
  --namespace ella-ha --ue-pool 10.246.0.0/16
```

For a controlled HA recovery test in a disposable namespace, save a topology
snapshot, delete the currently elected Core leader Pod, wait for a replacement
member to lead, then run the topology check again. Run the phone acceptance
suite after the UEs reattach. A leader election does not preserve active RAN
sessions or calls; supervisors create fresh UE sessions.

Optional extended checks remain available:

```sh
# Additional registration/security checks plus tunnel-failure recovery: 22 checks.
python3 ella-core/ue-phones/tests/smoke.py --release ella --network \
  --phone-a http://NODE_IP:30880 --phone-b http://NODE_IP:30881
# Separate protocol runner: four essential 4G/5G SMS/call scenarios by default.
# See the service test guide for credentials and pausing/restoring the phones.
python3 ella-core/tests/services/run-scenarios.py --core-api http://NODE_IP:30502
# All 24 protocol edge cases, including the three known HA SMS failures:
python3 ella-core/tests/services/run-scenarios.py --suite extended --core-api http://NODE_IP:30502
```

The essential four protocol scenarios passed in both recorded topology runs. The extended suite is diagnostic and is not the default acceptance gate; its known HA failures remain recorded in VALIDATION.md. All commands are Linux shell/Helm or standard-library Python commands.

## Remove a lab

Uninstall the two releases independently:

```sh
helm uninstall ella-sa --namespace ella-sa
helm uninstall ella-ha --namespace ella-ha
```

Uninstall leaves Core and IMS/SMSC PVCs behind so data is not silently lost.
For a fully disposable lab, remove only its dedicated namespaces after
checking they contain no unrelated workloads:

```sh
kubectl delete namespace ella-sa ella-ha
```

Deleting those namespaces also deletes their chart PVCs and test data. Back up
anything needed first. Do not delete a shared namespace to remove a release.

## Core image provenance

The released v1.20.0 image (revision34f32e9) does not refresh other cluster members' cached API addresses after Pod IP changes. HA protocol tests exposed stale 0.0.0.0/old-Pod addresses after replacement. The default is therefore an unmodified upstream source build at c7cf03530e52a2d353d9d1cd6159943319075bf0, which includes the member-address reconciliation fix and matches the UE/tester libraries. This is a pinned post-release snapshot, not a new official Ella release.

Public image: ghcr.io/infinitydon/ellacore:c7cf03530e52-tools2, pinned by manifest digest in core values. The reproducible Linux Dockerfile is in ../ella-core/images/Dockerfile; upstream LICENSE/NOTICE files are included in the image. All supplied custom images and the validated presets target Linux/amd64, with architecture selectors to avoid scheduling incompatible binaries. Users may override core.image to an appropriately tested upstream release when that fix is published.

N6 macvlan can retain parent checksum offload despite ethtool. Core and IMS initialization configure pod-local tc checksum actions for IPv4 TCP/UDP, including same-host delivery and packets entering the simulated UE TUN. They do not modify the host NIC. Kernel act_csum support is required on Core and IMS nodes.

In combined lab mode, bootstrap configures one IMS Diameter peer per Core ordinal. The controller reconciles those peers in creation-ID order after Pod IP changes. These entries are chart-managed: do not insert/reorder unrelated IMS peers in a provisioned lab. Keeping all Core identities reachable lets IMS use the HSS remembered by an existing registration after Raft leadership changes.
