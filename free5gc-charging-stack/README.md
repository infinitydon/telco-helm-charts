# free5GC Charging Stack

This chart deploys the official `free5gc/free5gc-helm` chart at tag `v4.2.2`
as a vendored subchart, enables Multus for AMF N2, SMF N4, and UPF N3/N4/N6,
and deploys the `free5gc-charging-portal` beside it.

The portal writes to the free5GC MongoDB charging data collection and notifies
CHF through `PUT /nchf-convergedcharging/v3/recharging/{ueId}`.

## Install

UPF requires the `gtp5g` kernel module on the selected worker node. This lab
was tested on `ebpf-bng-node-02` with `gtp5g` `v0.10.2` loaded for kernel
`6.8.0-124-generic`.

```bash
helm upgrade --install free5gc-charging-stack ./free5gc-charging-stack \
  --namespace free5gc \
  --create-namespace
```

If `ghcr.io/infinitydon/free5gc-charging-portal:v0.1.1` is private, create a
pull secret in the target namespace and add:

```bash
--set free5gc-charging-portal.imagePullSecrets[0].name=ghcr-pull
```

## Multus

The default lab values pin the workload to `ebpf-bng-node-02` and use:

| Network | Master | Subnet |
| --- | --- | --- |
| N2 | `enp8s19` | `10.201.10.0/24` |
| N3 | `enp8s20` | `10.201.30.0/24` |
| N4 | `enp8s21` | `10.201.40.0/24` |
| N6 | `enp8s22` | `10.201.60.0/24` |

Override those values for a different lab.

## Test

```bash
helm test free5gc-charging-stack -n free5gc
```

The test job checks the portal `/healthz` endpoint and confirms that the N2,
N3, N4, and N6 Multus `NetworkAttachmentDefinition` objects exist. Avoid
`--logs` with Helm v4.2.1; it can report a log lookup error for completed Job
hooks even when the test phase is `Succeeded`.
