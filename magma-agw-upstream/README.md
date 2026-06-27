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
- image tags default to `1.9.0`, not `latest`
- Helm rendering fails if any chart image uses `latest`
- adds missing Docker Compose services `envoy_controller` and `liagentd`
- adds `nodeSelector` and `tolerations`
- adds a basic Helm test hook

## Images

Default image values:

```yaml
image:
  repository: public.ecr.aws/z2g3r6f7
  tag: "1.9.0"
  gatewayGoRepository: public.ecr.aws/z2g3r6f7
  gatewayGoTag: "1.9.0"
  test: alpine:3.20.3
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
