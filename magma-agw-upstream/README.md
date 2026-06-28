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
- shared host/PVC state such as `/etc/snowflake`, `/var/opt/magma`, OVS, and
  `gtp_br0`

Do not run multiple replicas of the same AGW instance on one node. To deploy
multiple gateways in one Kubernetes cluster, use separate gateway identities,
node selectors, interface/IP assignments, secrets/certificates, and persistent
state. The supported operational model for this chart is:

```text
one AGW gateway identity == one AGW instance == one selected Kubernetes node
```

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
  bridge:
    name: gtp_br0
    address: 192.168.128.1/24
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

`simulator.enabled` deploys UERANSIM. The tested default uses Multus `macvlan`
for the simulator gNB and schedules it on node-01 so NGAP/SCTP is a real
inter-node association. Magma AGW remains on node-02.

```yaml
simulator:
  enabled: true
  nodeSelector:
    kubernetes.io/hostname: ebpf-bng-node-01
  multus:
    type: macvlan
    n2:
      master: enp8s19
      ip: 10.88.99.150/24
    n3:
      master: enp8s20
      ip: 192.168.60.150/24
  subscriber:
    provision: true
```

The subscriber provisioning Job adds/updates `IMSI001010000000001` and the
`magma.ipv4` APN profile. In cluster testing, UERANSIM completed NG setup,
initial registration, PDU session establishment, and brought up `uesimtun0`.

## Installation

This chart deploys the Access Gateway only. Magma NMS GUI and Orc8r REST API
access are provided by the Orchestrator side, not by the AGW pods. In this repo,
see the `magma-ebpf` chart for the TOSSI Orc8r/NMS deployer wrapper and its
NodePort access notes.

### Prerequisites

Before installing, confirm the target cluster has:

- Multus installed and the `NetworkAttachmentDefinition` CRD present.
- A Linux node selected for AGW, default `ebpf-bng-node-02`.
- A separate Linux node selected for UERANSIM, default `ebpf-bng-node-01`.
- Usable host interfaces for AGW N2/N3 and simulator N2/N3. The tested defaults
  are `enp8s19` and `enp8s20` on both nodes.
- SCTP and GTP kernel support. `nodePrep` attempts to load `gtp`,
  `openvswitch`, and `nf_conntrack`, but it does not build kernel modules.
- Open vSwitch. If it is missing and `nodePrep.installOpenvSwitch=true`, the
  node prep DaemonSet installs it with `apt-get`.

Quick checks:

```sh
kubectl get crd network-attachment-definitions.k8s.cni.cncf.io
kubectl get pods -n kube-system -l app=multus -o wide
kubectl get nodes -o wide
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

When `simulator.subscriber.provision=true`, the chart creates a revision-scoped
Job named like `agwc-subscriber-provision-<revision>`.

The Job is idempotent:

- waits for local `subscriberdb`
- checks whether the subscriber exists
- adds the subscriber if missing
- updates the APN/DNN profile on every run

Default subscriber values:

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
