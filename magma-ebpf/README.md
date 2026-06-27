# magma-ebpf

This chart packages the workflow from the TOSSI Magma eBPF deployment guide:

- orc8r is expected to be deployed with the TOSSI `magma-ocr8r` Ansible/RKE+Helm tooling.
- the Access Gateway is an Ubuntu host running the Magma Docker AGW stack.
- the eBPF GTP-U datapath is installed on the AGW host under `lte/gateway/ebpf`.

The chart is intentionally guarded. By default it only renders Kubernetes
configuration and a Helm test Pod. Host mutation is disabled unless you opt in
to the privileged host-agent DaemonSet and then enable specific actions.

## What the chart manages

- `ConfigMap` with orc8r/AGW/eBPF runtime settings.
- optional `Secret` for `rootCA.pem`, or reference to an existing Secret.
- optional privileged AGW host-agent DaemonSet for staging config and running
  the documented AGW/eBPF host installers.
- optional verification Job.
- Helm test hook that validates the rendered config in-cluster.

## Images

All images are pinned to non-`latest` tags:

- `ubuntu:24.04` for the disabled-by-default host agent.
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

## Host install mode

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

## Reference

- TOSSI guide: <https://tossi.org/docs/core/magma-ebpf/>
- eBPF branch: <https://github.com/TOSSI-Foundation/magma/tree/ebpf>
- orc8r deployer: <https://github.com/TOSSI-Foundation/magma-ocr8r>
