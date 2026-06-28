# magma-ebpf

This chart packages the workflow from the TOSSI Magma eBPF deployment guide:

- orc8r is expected to be deployed with the TOSSI `magma-ocr8r` Ansible/RKE+Helm tooling.
- the Access Gateway is an Ubuntu host running the Magma Docker AGW stack.
- the eBPF GTP-U datapath is installed on the AGW host under `lte/gateway/ebpf`.

The chart is intentionally guarded. By default it renders Kubernetes
configuration, stores NMS admin credentials in a Secret, and provides a Helm
test Pod. orc8r deployment and AGW host mutation are disabled unless you opt in
to the deployer Job, optional cluster-admin binding, privileged host-agent
DaemonSet, and specific action flags.

## What the chart manages

- `ConfigMap` with orc8r/AGW/eBPF runtime settings.
- `Secret` for NMS admin credentials, or reference to an existing Secret.
- optional `Secret` for `rootCA.pem`, or reference to an existing Secret.
- optional orc8r deployer Job that runs the TOSSI `magma-ocr8r` Ansible workflow.
- optional privileged AGW host-agent DaemonSet for staging config and running
  the documented AGW/eBPF host installers.
- optional verification Job.
- Helm test hook that validates the rendered config in-cluster.

## Images

All images are pinned to non-`latest` tags:

- `ubuntu:24.04` for the disabled-by-default orc8r deployer and host agent.
- `alpine:3.20.3` for chart verification and Helm tests.

The chart fails rendering if any image value uses the `latest` tag.

## Safe validation

```powershell
helm lint .\magma-ebpf
helm template magma-ebpf .\magma-ebpf
```

Live API validation without host mutation:

```powershell
$env:KUBECONFIG='C:\Users\Chris\.kube\ebng-cp--kubeconfig'
kubectl create ns magma-ebpf-test --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install magma-ebpf .\magma-ebpf -n magma-ebpf-test --wait
helm test magma-ebpf -n magma-ebpf-test --logs
helm uninstall magma-ebpf -n magma-ebpf-test
kubectl delete ns magma-ebpf-test
```

You can also run:

```powershell
.\magma-ebpf\scripts\test.ps1 -Kubeconfig C:\Users\Chris\.kube\ebng-cp--kubeconfig
```

## Full stack mode

The complete workflow has two sides:

1. orc8r/NMS deployment through the TOSSI `magma-ocr8r` deployer.
2. AGW Docker plus eBPF datapath deployment on the Ubuntu AGW host.

The orc8r deployer performs host and cluster-wide operations through SSH and
Ansible. Enable the cluster-admin binding only for a controlled deployer run, or
provide an existing ServiceAccount with equivalent permissions.

Create an SSH Secret for the clean Ubuntu orc8r host:

```powershell
kubectl -n magma create secret generic orc8r-ssh `
  --from-file=id_rsa=C:\path\to\orc8r_id_rsa `
  --from-file=known_hosts=C:\path\to\known_hosts
```

```yaml
rbac:
  clusterAdmin:
    create: true
orc8r:
  domain: magma.local
  nmsOrg: magma-test
  nmsUrl: https://magma-test.magma.local
  nmsAdmin:
    email: admin
    password: admin
  deployer:
    enabled: true
    targetHost: orc8r-host.example.local
    ansibleUser: ubuntu
    ssh:
      existingSecret: orc8r-ssh
    actions:
      deployOrc8r: true
      configureNms: true
      exportRootCA: true
```

If the deployer must use an out-of-cluster kubeconfig, create a Secret and point
the chart at it:

```powershell
kubectl -n magma create secret generic orc8r-kubeconfig `
  --from-file=kubeconfig=C:\Users\Chris\.kube\ebng-cp--kubeconfig
```

```yaml
orc8r:
  deployer:
    kubeconfig:
      existingSecret: orc8r-kubeconfig
      secretKey: kubeconfig
```

## AGW host install mode

Do not enable host install mode until the AGW node has the correct Ubuntu host,
two NICs, and the orc8r root CA.

Minimal staging only:

```yaml
orc8r:
  rootCA:
    existingSecret: magma-rootca
agw:
  hostAgent:
    enabled: true
    nodeSelector:
      kubernetes.io/hostname: agw-node-01
    actions:
      stageConfig: true
      installAgw: false
      installEbpf: false
      startDockerCompose: false
```

Full host mutation:

```yaml
orc8r:
  domain: magma.local
  nmsOrg: magma-test
  nmsUrl: https://magma-test.magma.local
  rootCA:
    existingSecret: magma-rootca
agw:
  gitUrl: https://github.com/TOSSI-Foundation/magma.git
  magmaVersion: ebpf
  ebpfDatapath: true
  interfaces:
    management: eth0
    n3: eth1
  hostAgent:
    enabled: true
    nodeSelector:
      kubernetes.io/hostname: agw-node-01
    actions:
      stageConfig: true
      installAgw: true
      installEbpf: true
      startDockerCompose: true
```

The host-agent mounts `/` from the node at `/host` and runs privileged. Treat it
as a controlled installer, not as a normal application workload.

## End-to-end sequence

```powershell
helm upgrade --install magma-ebpf .\magma-ebpf `
  -n magma --create-namespace `
  -f .\magma-ebpf\values-fullstack-example.yaml
```

Recommended progression:

1. Run the chart with all action flags false and `helm test`.
2. Enable `orc8r.deployer.enabled=true` with only `deployOrc8r=true`.
3. Enable `configureNms=true` once orc8r pods are Ready.
4. Enable `exportRootCA=true` and confirm the root CA Secret exists.
5. Enable AGW host-agent staging on one selected AGW node.
6. Enable `installAgw`, reboot the AGW host if the installer requests it, then enable `installEbpf`.

## Reference

- TOSSI guide: <https://tossi.org/docs/core/magma-ebpf/>
- eBPF branch: <https://github.com/TOSSI-Foundation/magma/tree/ebpf>
- orc8r deployer: <https://github.com/TOSSI-Foundation/magma-ocr8r>
