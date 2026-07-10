# free5GC Charging Stack

This chart deploys the official `free5gc/free5gc-helm` chart at tag `v4.2.2`
as a vendored subchart, enables Multus for AMF N2, SMF N4, and UPF N3/N4/N6,
and deploys separate operator and user charging portals beside it. It also
vendors the free5GC UERANSIM chart for gNB/UE simulation over Multus N2/N3.

The default UERANSIM image is pinned to
`ghcr.io/infinitydon/ueransim:v3.2.4-rls600s`, built from upstream UERANSIM
`v3.2.4` with the radio-link heartbeat timeout extended for this single-node
lab. In this lab the image is imported into the selected worker's container
runtime because GHCR package creation for that image path may require separate
registry permissions.

The portal updates the free5GC ABMF account-balance backing data in
`policyData.ues.chargingData` and notifies the live CHF session through
`PUT /nchf-convergedcharging/v3/recharging/{ueId}`. The chart seeds both
PDU-session-level and flow-level Online charging data so PCF can allocate
rating groups during SM Policy creation.

The UE browser usage reporter and browser-side quota guard are disabled by
default. They are retained as lab troubleshooting switches, but native
CHF/SMF/UPF charging is the intended enforcement path.

## Install

UPF requires the `gtp5g` kernel module on the selected worker node. This lab
was tested on `ebpf-bng-node-02` with `gtp5g` `v0.10.2` loaded for kernel
`6.8.0-124-generic`.

```bash
helm upgrade --install free5gc-charging-stack ./free5gc-charging-stack \
  --namespace free5gc \
  --create-namespace
```

If `ghcr.io/infinitydon/free5gc-charging-portal:v0.3.3` is private, create a
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
| User | `http://<node-ip>:31381/` | Subscriber data top-up page bound to the detected subscriber. |
| UE Browser | `https://<node-ip>:31382/` | Kasm Chromium desktop embedded as sidecars in the UERANSIM UE pod. |

The user portal does not trust a browser-supplied `ueId`. It resolves the
subscriber from a trusted header (`x-subscriber-supi`) or the configured UE
source-IP/CIDR binding.

The chart also provisions the default UERANSIM subscriber
`imsi-208930000000001` through the free5GC WebConsole API during install and
upgrade.

When `ueransim.ueBrowser.enabled=true`, open the UE Browser URL and sign in as
`kasm_user` with password `free5gc`. Browse to `http://127.0.0.1:18080/`
inside Chromium. That local proxy forwards to the user portal and injects the
configured trusted subscriber header for the UE.

Chromium is launched with an HTTP/HTTPS proxy on `127.0.0.1:18888`. The proxy
runs as a dedicated user and the UE pod installs policy routing so that proxy
TCP traffic is marked and sent through `uesimtun0`. Local, Kubernetes service,
and RFC1918 destinations bypass the proxy so noVNC and in-cluster portal access
remain reachable. DNS lookup is still performed by the proxy using pod DNS.

## Multus

The default lab values pin the workload to `ebpf-bng-node-02` and use:

| Network | Master | Subnet |
| --- | --- | --- |
| N2 | `enp8s19` | `10.201.10.0/24` |
| N3 | `enp8s20` | `10.201.30.0/24` |
| N4 | `enp8s21` | `10.201.40.0/24` |
| N6 | `enp8s22` | `10.201.60.0/24` |

With `n6Gateway.enabled=true`, the chart deploys a privileged host-network
DaemonSet on the lab node that creates `10.201.60.1/24` as a host-side macvlan
gateway on `enp8s22` and masquerades N6 traffic out through `eth0`. This gives
the UPF's N6 default route a real next hop for UE internet browsing.

The UPF container is run privileged and its wrapper enables
`net.ipv4.ip_forward` inside the UPF pod network namespace. The kubelet on this
lab does not allow the same setting through pod `sysctls`, so the wrapper keeps
the chart self-contained without requiring kubelet allowlist changes.

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
