# Open5GS 5G SA with DRA Networks

This chart is an isolated Open5GS 5G lab that creates every secondary
protocol network with the `dra-linux-networks` macvlan driver. It does not use
Multus, NetworkAttachmentDefinitions, or CNI secondary attachments.

## Components

- Open5GS NRF, AUSF, UDM, UDR, PCF, NSSF, AMF, SMF, and UPF
- MongoDB and Open5GS WebUI
- UERANSIM gNB and UE
- Automatic subscriber provisioning
- Pinned netshoot `v0.15` tooling for N6 ping and iperf3 testing

## DRA Networks

The chart divides `10.60.0.0/24` into separate `/28` protocol networks:

| Interface | Subnet | Fixed endpoints |
| --- | --- | --- |
| N2 | `10.60.0.0/28` | AMF `.2`, gNB `.10` |
| N3 | `10.60.0.16/28` | UPF `.18`, gNB `.26` |
| N4 | `10.60.0.32/28` | SMF `.34`, UPF `.35` |
| N6 | `10.60.0.48/28` | UPF `.50`, iperf3 server `.60` |

Each network has its own DRA `IPPool` and `ResourceClaimTemplate`. Claim
requests and interfaces are explicitly named `n2`, `n3`, `n4`, or `n6`.
Static addresses are reserved in the pools and requested through
claim-specific Pod annotations.

| Pod | Claims |
| --- | --- |
| AMF | `n2` |
| SMF | `n4` |
| UPF | `n3`, `n4`, `n6` |
| gNB | `n2`, `n3` |
| Data/iperf3 server | `n6` |

SBI, MongoDB, WebUI, and UE-to-gNB radio emulation stay on the default
Kubernetes Pod network.

## Prerequisites

- Kubernetes 1.34 or newer with `resource.k8s.io/v1`
- `dra-linux-networks` v0.5.0 or newer installed and healthy
- DeviceClass `linux-net-macvlan`
- Shared parent `enp8s20` advertised on DRA-enabled workers
- Worker label `linux-net.dra.infinitydon.com/enabled=true`
- SCTP support on the worker nodes

## Install

Use the dedicated namespace so this implementation remains separate from the
Multus-based chart:

```powershell
$env:KUBECONFIG = "C:\path\to\kubeconfig"
helm upgrade --install dra5g .\open5gs-5g-dra `
  --namespace open5gs-5g-dra --create-namespace `
  --wait --timeout 10m
```

The WebUI defaults to NodePort `30082`. Sign in with `admin / 1423` and change
the default password after first login.

## Verify

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\open5gs-5g-dra\scripts\test.ps1 `
  -Namespace open5gs-5g-dra -Release dra5g `
  -Kubeconfig $env:KUBECONFIG
```

The test verifies protocol-named DRA interfaces, rejects `netN` names, checks
UE registration and PDU-session establishment, pings `10.60.0.60` through
`uesimtun0`, and runs iperf3 over the same path.

Inspect allocations and persistent DRA network status with:

```powershell
kubectl get resourceclaims,ipallocations -n open5gs-5g-dra
kubectl get ippools
kubectl get pods -n open5gs-5g-dra `
  -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{.metadata.annotations.linux-net\.dra\.infinitydon\.com/network-status}{"\n\n"}{end}'
```
