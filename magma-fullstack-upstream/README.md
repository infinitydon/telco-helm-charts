# Magma Fullstack Upstream

This chart wraps the upstream Magma `v1.9.0` Orc8r/NMS and LTE-Orc8r Helm
charts for a lab deployment that can manage `magma-agw-upstream` gateways.

It deploys:

- Postgres for Orc8r and NMS state.
- upstream `orc8r` chart with NMS enabled.
- upstream `lte-orc8r` chart for LTE subscriber, policy, and mconfig APIs.
- lab certificate/config Secrets.
- NMS admin bootstrap Job. The Job first registers the `admin_operator`
  certificate with Orc8r `accessd`, then creates the NMS admin user.
- NodePort NMS and Orc8r nginx services.

Provisioning belongs in NMS/Orc8r. The AGW chart's standalone subscriber Job is
only a lab shortcut and should be disabled for this full-stack path.

## Install

```powershell
helm upgrade --install magma-fullstack .\magma-fullstack-upstream `
  -n magma --create-namespace `
  --wait --timeout 60m
```

Do not run `helm dependency build` unless you intend to re-apply the local
compatibility patches to the vendored `charts/*.tgz` files. The upstream Magma
1.9.0 chart archives are vendored here and patched for newer Kubernetes API
versions and NMS container startup requirements.

Check NMS and Orc8r:

```powershell
helm status magma-fullstack -n magma
kubectl -n magma get pods
kubectl -n magma get svc nginx-proxy magma-fullstack-nginx-proxy magma-fullstack-clientcert-nginx bootstrapper-orc8r-nginx
```

Open NMS with the `nginx-proxy` NodePort:

```text
https://<node-ip>:<nginx-proxy-nodeport>
```

Default login:

```text
organization: magma-test
username: admin
password: admin
```

For DNS/SNI based access, map these names to the node IP or external load
balancer:

- `*.nms.magma.local`
- `api.magma.local`
- `controller.magma.local`
- `bootstrapper-controller.magma.local`

## AGW

Install `magma-agw-upstream` separately after Orc8r/NMS is up. Disable local
subscriber provisioning:

```powershell
helm upgrade --install agwc .\magma-agw-upstream `
  -n magma-agw-test `
  --set namespace=magma-agw-test `
  --set simulator.subscriber.provision=false `
  --wait --timeout 20m
```

Create the network, gateway, APN, and subscriber in NMS. UERANSIM must use SIM
values that match the NMS subscriber record.

## Upstream Chart Notes

This chart intentionally wraps the upstream `orc8r` and `lte-orc8r` Magma
1.9.0 Helm charts instead of reimplementing Orc8r. The vendored chart archives
include small compatibility patches:

- `policy/v1beta1` PodDisruptionBudgets are updated for current Kubernetes.
- NMS nginx gets the environment and certificate mounts required by the
  upstream `linuxfoundation.jfrog.io/magma-docker/nginx:1.9.0` image.
- The dependency service names are aligned with the parent release name.
- The old upstream TCP probes are removed because they do not match the
  listening behavior observed in this lab cluster.

## Certificates

The default chart-generated certificates are for lab use. They are regenerated
when Helm renders the chart unless the existing Secret is kept in place by the
cluster lifecycle. For production, replace `orc8r-secrets-certs` with externally
managed material and keep AGW `rootCA.pem` aligned with Orc8r.
