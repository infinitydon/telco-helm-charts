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

For production, review these values and map them to the real AGW S1/NAT/uplink
interfaces before installing:

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
    s1:
      name: eth1
      address: 192.88.99.142/24
    nat:
      name: eth2
      address: 192.168.60.142/24
```

## Installation

Create the namespace:

```sh
~ kubectl create namespace magma
```

Create the root CA Secret needed to communicate with orc8r:

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
