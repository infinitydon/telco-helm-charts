# Magma AGW Upstream

This chart starts from the upstream Magma `v1.9.0` experimental
`lte/gateway/deploy/agwc-helm-charts` chart and keeps it as a clean Kubernetes
baseline before adding any eBPF datapath work.

It intentionally remains close to upstream:

- one Deployment per AGW component
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

`simulator.enabled` deploys UERANSIM. The tested default uses Multus
`host-device` for the simulator gNB and schedules it on node-01 so NGAP/SCTP is
a real inter-node association. Magma AGW remains on node-02.

```yaml
simulator:
  enabled: true
  nodeSelector:
    kubernetes.io/hostname: ebpf-bng-node-01
  multus:
    type: host-device
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

Create the namespace:

```sh
~ kubectl create namespace magma
```

For lab use, the chart can create a self-signed cert Secret when
`secret.create=true`. For a real orc8r-backed deployment, disable that and create
the root CA Secret needed to communicate with orc8r:

```sh
~ kubectl create secret generic agwc-secret-certs --from-file=rootCA.pem=rootCA.pem --namespace magma
```

Deploy after reviewing `values.yaml`:

```sh
~ helm upgrade --install agwc ./magma-agw-upstream --namespace magma --values=values.yaml
```

Delete:

```sh
~ helm uninstall agwc --namespace magma
~ kubectl delete -n magma secret agwc-secret-certs
~ kubectl delete namespace magma
```
