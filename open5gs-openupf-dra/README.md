# Open5GS Core With OpenUPF DRA

This chart deploys Open5GS 5G core NFs with the built-in Open5GS UPF disabled
and OpenUPF deployed as a split UPF:

- SMU handles PFCP/N4 toward Open5GS SMF and backend management for FPUs.
- LBU owns the DPDK N3/N6 packet I/O and steers traffic to backend FPUs.
- FPU pods perform the session-aware UPF packet processing.

The chart is intentionally separate from `open5gs-5g-dra`, which remains the
reference Open5GS-only DRA lab.

## Components

- Open5GS NRF, AUSF, UDM, UDR, PCF, NSSF, AMF, and SMF
- OpenUPF SMU, LBU, and configurable FPU workers as singleton Deployments
- MongoDB and Open5GS WebUI
- UERANSIM gNB, 10 UE StatefulSet replicas by default, and an N6 iperf3 server

## Tested Lab Split

The validated topology keeps kernel and DPDK paths separate:

| Purpose | Value |
| --- | --- |
| Kernel DRA parent for Open5GS core, gNB, data, and SMU N4 | `enp8s20` |
| LBU DPDK VFs | `0000:04:00.0`, `0000:05:00.0` |
| FPU DPDK VFs | `0000:03:00.0`, `0000:02:00.0` |
| SMU service ClusterIP | `10.152.183.55` |
| LBU service ClusterIP | `10.152.183.158` |

The chart uses the `10.60.0.0/24` lab range:

| Interface | Subnet | Fixed endpoints |
| --- | --- | --- |
| N2 | `10.60.0.0/28` | AMF `.2`, gNB `.10` |
| N3 | `10.60.0.16/28` | LBU `.18`, gNB `.26` |
| N4 | `10.60.0.32/28` | SMF `.34`, SMU `.35` |
| N6 | `10.60.0.48/28` | LBU `.50`, data `.60` |

## Prerequisites

- Kubernetes with `resource.k8s.io/v1`
- `dra-linux-networks` installed and healthy
- DeviceClass `linux-net-macvlan` for kernel interfaces
- DeviceClass `linux-net-dpdk-intel-vf` for OpenUPF DPDK VFs
- Free Intel `iavf` VFs advertised by DRA as DPDK devices
- Pull secret for the OpenUPF image if the image is private
- Worker label `linux-net.dra.infinitydon.com/enabled=true`
- SCTP support on the worker nodes

OpenUPF currently expects SMU/LBU management peers as IPs in config, so this
chart uses stable ClusterIP values for the OpenUPF SMU and LBU services.

## Install

Review `values.yaml` and adjust at least:

- `nodeSelector`
- `dra.parentInterface`
- `openupf.services.smu.clusterIP`
- `openupf.services.lbu.clusterIP`
- `openupf.dpdk.lbu.pciAddresses`
- `openupf.dpdk.fpu.pciAddresses`

Then install:

```powershell
$env:KUBECONFIG = "C:\path\to\kubeconfig"
helm upgrade --install openupf-core .\open5gs-openupf-dra `
  --namespace open5gs-openupf --create-namespace `
  --wait --timeout 10m
```

The default values start `simulator.gnb.replicas=1` and
`simulator.ue.replicas=10`. UE pods run as a StatefulSet so each pod gets a
stable ordinal and a distinct IMSI derived from `subscriber.imsi`.
The OpenUPF NFs run as Deployments with `Recreate` strategy, so a crashed SMU,
LBU, or FPU is recreated by Kubernetes instead of staying down as a completed
or failed bare Pod.

## Verify

Check PFCP sessions and backend state from SMU:

```powershell
kubectl -n open5gs-openupf exec deploy/openupf-core-open5gs-openupf-dra-openupf-smu -- `
  sh -lc "printf 'show_all_session\nres_stat\nquit\n' | /opt/upf/bin/cli smu 2>&1 || true"
```

`backend: 255 2 Active: 2` means two FPU backend workers are registered and
usable. Confirm that they are actually forwarding traffic:

```powershell
kubectl -n open5gs-openupf exec deploy/openupf-core-open5gs-openupf-dra-openupf-fpu-1 -- `
  sh -lc "printf 'stats\nquit\n' | /opt/upf/bin/cli fpu 2>&1 || true"
kubectl -n open5gs-openupf exec deploy/openupf-core-open5gs-openupf-dra-openupf-fpu-2 -- `
  sh -lc "printf 'stats\nquit\n' | /opt/upf/bin/cli fpu 2>&1 || true"
```

The validated 10-UE run registered 10 UEs, established 10 PDU sessions,
completed per-tunnel ping, ran 5 Mbit/s UDP iperf per tunnel with 0% loss, and
showed both FPUs forwarding user-plane packets.
