# free5GC Charging Stack

This chart deploys the official `free5gc/free5gc-helm` chart at tag `v4.2.2`
as a vendored subchart, enables Multus for AMF N2, SMF N4, and UPF N3/N4/N6,
and deploys separate operator and user charging portals beside it. It also
vendors the free5GC UERANSIM chart for gNB/UE simulation over Multus N2/N3.

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

If `ghcr.io/infinitydon/free5gc-charging-portal:v0.2.0` is private, create a
pull secret in the target namespace and add:

```bash
--set free5gc-charging-portal.imagePullSecrets[0].name=ghcr-pull
```

The user portal inherits that pull secret by default. You can also set:

```bash
--set userPortal.imagePullSecrets[0].name=ghcr-pull
```

## Portals

| Portal | URL | Purpose |
| --- | --- | --- |
| Operator | `http://<node-ip>:31380/` | Operator PIN-protected top-up for any subscriber charging record. |
| User | `http://<node-ip>:31381/` | Fictitious self top-up bound to the detected subscriber. |

The user portal does not trust a browser-supplied `ueId`. It resolves the
subscriber from a trusted header (`x-subscriber-supi`) or the configured UE
source-IP/CIDR binding.

The chart also provisions the default UERANSIM subscriber
`imsi-208930000000001` through the free5GC WebConsole API during install and
upgrade.

## Multus

The default lab values pin the workload to `ebpf-bng-node-02` and use:

| Network | Master | Subnet |
| --- | --- | --- |
| N2 | `enp8s19` | `10.201.10.0/24` |
| N3 | `enp8s20` | `10.201.30.0/24` |
| N4 | `enp8s21` | `10.201.40.0/24` |
| N6 | `enp8s22` | `10.201.60.0/24` |

Override those values for a different lab.

UERANSIM uses the same Multus N2/N3 networks by default:

| Component | Interface | IP |
| --- | --- | --- |
| gNB | N2 | `10.201.10.20` |
| gNB | N3 | `10.201.30.20` |
| UE | SUPI | `imsi-208930000000001` |

## Test

```bash
helm test free5gc-charging-stack -n free5gc
```

By default, the Helm test runs the UERANSIM hook and verifies that the UE has a
`uesimtun0` interface with an address from the `10.60.0.0/16` UE subnet.

An optional stack smoke test can also check both portal `/healthz` endpoints,
the user portal identity endpoint with
`x-subscriber-supi: imsi-208930000000001`, and the N2, N3, N4, and N6 Multus
`NetworkAttachmentDefinition` objects:

```bash
helm upgrade --install free5gc-charging-stack ./free5gc-charging-stack \
  --namespace free5gc \
  --set stackSmokeTest.enabled=true
helm test free5gc-charging-stack -n free5gc
```
