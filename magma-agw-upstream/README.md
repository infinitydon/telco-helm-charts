# Magma AGW Upstream

This chart starts from the upstream Magma `v1.9.0` experimental
`lte/gateway/deploy/agwc-helm-charts` chart and keeps it as a clean Kubernetes
baseline before adding any eBPF datapath work.

It intentionally remains close to upstream:

- one Deployment per AGW component
- one replica per AGW component
- `Recreate` deployment strategy
- `hostNetwork: true`
- shared `/etc/magma`, `/var/opt/magma`, `/tmp`, and `/var/run` assumptions
- privileged datapath-related components such as `oai-mme`, `pipelined`, `sctpd`,
  and `sessiond`

Changes from upstream:

- chart name/version are repo-local: `magma-agw-upstream` `0.1.0`
- image tags default to `1.9.0-upstream`, not `latest`
- Helm rendering fails if any chart image uses `latest`
- adds missing Docker Compose services `envoy_controller` and `liagentd`
- adds `nodeSelector` and `tolerations`
- adds an idempotent optional `agw-node-prep` DaemonSet for AGW host prerequisites
- enables Magma 5G SA mconfig defaults
- adds an optional UERANSIM 5G gNB/UE simulator with Multus NADs and an
  idempotent subscriber/APN provisioning Job
- adds a basic Helm test hook

`liagentd` is present but disabled by default because the packaged upstream
`liagentd.yml` sets `enable: false`; deploying it in that state causes the
process to exit cleanly and Kubernetes to report a restart loop.

## AGW scale model

Magma AGW is containerized in the upstream `v1.9.0` release, but the upstream
AGWC Helm chart still models an Access Gateway as a single gateway instance, not
as a horizontally scaled replica set.

In this chart, every AGW service inherits the upstream deployment template with:

- `replicas: 1`
- `strategy.type: Recreate`
- `hostNetwork: true`
- required pod anti-affinity against AGW pods from other Helm releases
- shared host/PVC state such as `/etc/snowflake`, `/var/opt/magma`, OVS, and
  `gtp_br0`

Do not run multiple replicas of the same AGW instance on one node. To deploy
multiple gateways in one Kubernetes cluster, use separate gateway identities,
node selectors, interface/IP assignments, secrets/certificates, and persistent
state. The supported operational model for this chart is:

```text
one AGW gateway identity == one AGW instance == one selected Kubernetes node
```

Nodes that are allowed to host AGW must be labelled:

```sh
kubectl label node ebpf-bng-node-02 magma.io/agw-node=true --overwrite
```

The default `nodeSelector` requires both the participation label and the tested
node hostname:

```yaml
nodeSelector:
  magma.io/agw-node: "true"
  kubernetes.io/hostname: ebpf-bng-node-02
```

For multiple AGWs, install one Helm release per gateway and set each release's
`nodeSelector.kubernetes.io/hostname` to a different labelled AGW node. The
chart also adds anti-affinity so AGW pods from another Helm release cannot land
on the same node.

Running more than one distinct AGW on the same node is not covered by the
upstream chart and would require explicit isolation of host networking, OVS
bridges, interface names, IPs, gateway IDs, certificates, host paths, and
persistent volumes. Treat that as custom engineering rather than a supported
replica mode.

## Images

Default image values:

```yaml
image:
  repository: ghcr.io/infinitydon/telco-helm-charts
  tag: "1.9.0-upstream"
  gatewayGoRepository: ghcr.io/infinitydon/telco-helm-charts
  gatewayGoTag: "1.9.0-upstream"
  test: alpine:3.20.3
```

## Node Prep DaemonSet

`nodePrep.enabled` deploys a privileged DaemonSet on the selected AGW node. It is
idempotent: it checks for Open vSwitch, kernel modules, `gtp_br0`, internal
ports, interface addresses, and sysctls before changing host state.

For production, review these values and map them to the real AGW N2/N3/uplink
interfaces before installing. The defaults use node-02 for Magma AGW and create
host-side macvlan interfaces for N2/N3. The N2 subnet intentionally avoids
`192.88.99.0/24` because Linux SCTP treats that old 6to4 anycast range poorly.

```yaml
nodeSelector:
  kubernetes.io/hostname: ebpf-bng-node-02

nodePrep:
  enabled: true
  runMagmaOvsKmodUpgrade: true
  requireMagmaOvsKmod: false
  magmaOvsKmodUpgradePath: /usr/local/bin/ovs-kmod-upgrade.sh
  bridge:
    name: gtp_br0
    address: 192.168.128.1/24
    datapathType: system
  gtpu:
    enabled: false
    cleanupPorts:
      - gtpu0
    ofport: 32768
  interfaces:
    createMissing: true
    cleanupLegacy:
      - eth1
      - eth2
    s1:
      name: magma-n2
      type: macvlan
      parent: enp8s19
      address: 10.88.99.142/24
      replaceAddresses: true
    nat:
      name: magma-n3
      type: macvlan
      parent: enp8s20
      address: 192.168.60.142/24
```

## 5G Simulator

`simulator.enabled` deploys UERANSIM. It defaults to `false` so a full
Orc8r/NMS-backed deployment can register and configure the AGW before the UE
attempts registration. When enabled, the tested default uses Multus `macvlan`
for the simulator gNB and schedules it on node-01 so NGAP/SCTP is a real
inter-node association. Magma AGW remains on node-02.

UERANSIM must run on a completely separate worker node from the AGW. Do not
schedule the simulator onto the AGW worker node; the chart defaults enforce this
with a separate simulator node label, hostname selector, and pod anti-affinity
against AGW pods.

UERANSIM is a simulator workload, not an NMS-managed eNodeB/CBSD inventory
object. Its gNB establishes NGAP/SCTP toward the AGW and the UE/session should
be visible through gateway/session state and logs, but it should not be expected
to appear as a persistent "radio node" in the Magma NMS equipment views.

Label the simulator worker:

```sh
kubectl label node ebpf-bng-node-01 magma.io/ueransim-node=true --overwrite
```

```yaml
simulator:
  enabled: true
  nodeSelector:
    magma.io/ueransim-node: "true"
    kubernetes.io/hostname: ebpf-bng-node-01
  antiAffinity:
    separateFromAgw: true
  multus:
    type: macvlan
    n2:
      master: enp8s19
      ip: 10.88.99.150/24
    n3:
      master: enp8s20
      ip: 192.168.60.150/24
  subscriber:
    provision: false
```

`simulator.gnb.startDelaySeconds` defaults to `30` and
`simulator.ue.startDelaySeconds` defaults to `60` so the AGW SCTP listener and
gNB are up before the UE attempts registration. If the AGW node is slow to
initialize OVS or services, increase the gNB and UE delays together.

For a full Magma deployment, create the subscriber and APN in NMS/Orc8r. The
local subscriber provisioning Job is disabled by default and is intended only
for standalone AGW datapath testing. In cluster testing, UERANSIM completed NG
setup, initial registration, PDU session establishment, and brought up
`uesimtun0` after the subscriber was present.

Recommended full-stack order:

1. Deploy Orc8r/NMS and confirm the GUI/API are reachable.
2. Create the network, gateway, APN/DNN, and UE subscriber in NMS/Orc8r.
3. Deploy AGW and confirm it is registered/synced with Orc8r.
4. Enable UERANSIM by setting `simulator.enabled=true`, keeping
   `simulator.subscriber.provision=false`.

## Installation

This chart deploys the Access Gateway only. Magma NMS GUI and Orc8r REST API
access are provided by the Orchestrator side, not by the AGW pods. In this repo,
see the `magma-ebpf` chart for the TOSSI Orc8r/NMS deployer wrapper and its
NodePort access notes.

### Prerequisites

Before installing, confirm the target cluster has:

- Multus installed and the `NetworkAttachmentDefinition` CRD present.
- A Linux node labelled for AGW, default `ebpf-bng-node-02` with
  `magma.io/agw-node=true`.
- A separate Linux node labelled for UERANSIM, default `ebpf-bng-node-01` with
  `magma.io/ueransim-node=true`.
- Usable host interfaces for AGW N2/N3 and simulator N2/N3. The tested defaults
  are `enp8s19` and `enp8s20` on both nodes.
- SCTP and GTP kernel support. `nodePrep` attempts to load `gtp`,
  `openvswitch`, and `nf_conntrack`, but it does not build kernel modules.
- Open vSwitch. If it is missing and `nodePrep.installOpenvSwitch=true`, the
  node prep DaemonSet installs it with `apt-get`.
- Magma-compatible OVS/GTP kernel support. Upstream Magma troubleshooting
  expects AGW hosts with the Magma OVS kernel module path available through
  `/usr/local/bin/ovs-kmod-upgrade.sh` when OVS reports GTP-related datapath
  errors. The node prep DaemonSet can run this script when it exists. Set
  `nodePrep.requireMagmaOvsKmod=true` to fail fast when the script is missing.
  The default keeps `gtp_br0` on the kernel `system` datapath and removes stale
  static workaround ports such as `gtpu0`.

The tested Ubuntu 24.04 node had only stock Ubuntu Open vSwitch packages and no
`/usr/local/bin/ovs-kmod-upgrade.sh`. With that host state, UERANSIM control
plane reached NG setup, UE registration, and PDU establishment, but UE user-plane
traffic failed because `pipelined` hit OpenFlow `BAD_FIELD` errors. Resolve the
host Magma OVS/GTP prerequisite before treating the datapath test as complete.

Quick checks:

```sh
kubectl get crd network-attachment-definitions.k8s.cni.cncf.io
kubectl get pods -n kube-system -l app=multus -o wide
kubectl get nodes -o wide
kubectl get nodes -l magma.io/agw-node=true
kubectl get nodes -l magma.io/ueransim-node=true
```

On each selected node, verify the interface names before using the defaults:

```sh
kubectl debug node/<node-name> -it --image=ubuntu:22.04 -- chroot /host ip -br addr
```

### Bring-Up

```sh
kubectl create namespace magma
```

For lab use, the chart can create a self-signed cert Secret when
`secret.create=true`. For a real orc8r-backed deployment, disable that and create
the root CA Secret needed to communicate with orc8r:

```sh
kubectl create secret generic agwc-secret-certs \
  --from-file=rootCA.pem=rootCA.pem \
  --from-file=gateway.crt=gateway.crt \
  --from-file=gateway.key=gateway.key \
  --from-file=controller.crt=controller.crt \
  --from-file=controller.key=controller.key \
  --namespace magma
```

Deploy after reviewing `values.yaml`:

```sh
helm upgrade --install agwc ./magma-agw-upstream \
  --namespace magma \
  --values values.yaml \
  --wait \
  --timeout 20m
```

For the tested lab defaults:

```sh
helm upgrade --install agwc ./magma-agw-upstream \
  --namespace magma-agw-test \
  --set namespace=magma-agw-test \
  --set simulator.enabled=true \
  --wait \
  --timeout 20m
```

### Verification

Check the release and pods:

```sh
helm status agwc -n magma-agw-test
kubectl get pods -n magma-agw-test -o wide
kubectl logs -n magma-agw-test deploy/agwc-ueransim-gnb --tail=100
kubectl logs -n magma-agw-test deploy/agwc-ueransim-ue --tail=120
```

Expected successful simulator messages:

```text
NG Setup procedure is successful
Initial Registration is successful
PDU Session establishment is successful PSI[1]
TUN interface[uesimtun0, 192.168.128.x] is up.
```

Check AGW N2 SCTP listener:

```sh
kubectl exec -n magma-agw-test deploy/oai-mme -- \
  sh -c 'cat /proc/net/sctp/eps | grep 38412'
```

The tested default binds `10.88.99.142:38412`. Avoid `192.88.99.0/24` for N2;
it caused SCTP client failures even though ICMP worked.

## Provisioning

For the full deployment path, provisioning should be done through NMS/Orc8r:

- create the LTE/5G network
- register the gateway
- configure APNs/DNNs
- add subscribers/SIM credentials
- keep UERANSIM SIM values aligned with the NMS subscriber

When `simulator.subscriber.provision=true`, the chart creates a revision-scoped
Job named like `agwc-subscriber-provision-<revision>`. This is a standalone lab
shortcut and should stay disabled when Orc8r/NMS is managing the gateway.

The Job is idempotent:

- waits for local `subscriberdb`
- checks whether the subscriber exists
- adds the subscriber if missing
- updates the APN/DNN profile on every run

Standalone lab subscriber override:

```yaml
simulator:
  ue:
    supi: imsi-001010000000001
    key: 465B5CE8B199B49FAA5F0A2EE238A6BC
    opc: E8ED289DEBA952E4283B54E88E6183CA
    apn: magma.ipv4
  subscriber:
    provision: true
    nextSeq: "000000000000"
    apnConfig: "magma.ipv4,9,1,0,0,300000000,300000000,0,,,,"
```

Manual verification:

```sh
kubectl logs -n magma-agw-test job/agwc-subscriber-provision-<revision>
kubectl exec -n magma-agw-test deploy/subscriberdb -- \
  /usr/local/bin/subscriber_cli.py get IMSI001010000000001
```

To use your own UE/SIM values, update `simulator.ue.*` and
`simulator.subscriber.apnConfig` together. If using an external orchestrator for
subscribers, set `simulator.subscriber.provision=false`.

## Certificates

The chart supports two certificate modes.

Lab mode:

```yaml
secret:
  create: true
  certs: agwc-secret-certs
```

Helm generates a self-signed CA plus gateway/controller certificates and stores
them in `agwc-secret-certs`. This is suitable for local chart testing and for
the standalone AGW workflow in this repo. Because Helm `genCA`/`genSignedCert`
generates new material on render, do not treat lab certificates as stable
identity for production.

Production/orc8r mode:

```yaml
secret:
  create: false
  certs: agwc-secret-certs
```

Create `agwc-secret-certs` yourself with the certificate material issued for the
gateway and controller trust chain:

- `rootCA.pem`
- `gateway.crt`
- `gateway.key`
- `controller.crt`
- `controller.key`

Update or rotate certificates when:

- certificates are expired or near expiry
- the gateway is re-enrolled or its identity changes
- the orc8r/controller CA changes
- a private key is suspected to be exposed
- moving from lab mode to real orc8r mode

After updating the Secret, rerun Helm so the revision-scoped config Job copies
the files into the AGW PVC, then restart the affected control-plane pods:

```sh
helm upgrade --install agwc ./magma-agw-upstream \
  --namespace magma \
  --values values.yaml \
  --wait \
  --timeout 20m

kubectl rollout restart -n magma \
  deployment/control-proxy deployment/oai-mme deployment/sctpd
```

If switching from `secret.create=true` to externally managed certificates,
delete and recreate the Secret before the Helm upgrade:

```sh
kubectl delete secret agwc-secret-certs -n magma
kubectl create secret generic agwc-secret-certs \
  --from-file=rootCA.pem=rootCA.pem \
  --from-file=gateway.crt=gateway.crt \
  --from-file=gateway.key=gateway.key \
  --from-file=controller.crt=controller.crt \
  --from-file=controller.key=controller.key \
  --namespace magma
```

Delete:

```sh
helm uninstall agwc --namespace magma
kubectl delete -n magma secret agwc-secret-certs
kubectl delete namespace magma
```
