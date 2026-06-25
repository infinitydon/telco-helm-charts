# Telco Helm Charts

This repository contains Helm charts for beginner-friendly Open5GS labs and
high-availability Ella Core private 5G deployments.

## Chart Catalog

| Chart | Purpose | Secondary networking | Validation or companion |
| --- | --- | --- | --- |
| [`open5gs-4g`](open5gs-4g/) | Open5GS EPC learning lab | LTE signaling and user-plane interfaces | Included srsRAN eNB/UE attach and SGi ping |
| [`open5gs-5g`](open5gs-5g/) | Open5GS standalone 5G learning lab | N2, N3, N4, and N6 | Included UERANSIM registration, PDU session, and N6 ping |
| [`open5gs-5g-dra`](open5gs-5g-dra/) | Open5GS standalone 5G using DRA macvlan | DRA N2, N3, N4, and N6 | UERANSIM registration, PDU session, ping, and iperf3 |
| [`open5gs-openupf-dra`](open5gs-openupf-dra/) | Open5GS 5G core with OpenUPF split UPF | DRA macvlan for Open5GS/SMU N4 and Intel VF DPDK for LBU/FPU | OpenUPF backend validation, 10-UE registration, ping, and iperf3 |
| [`ella-core-5g-chart`](ella-core/ella-core-5g-chart/) | HA Ella Core cluster using stable N2 addresses for Raft | N2, N3, and N6 | Bootstrap provisioning and HA failover workflow |
| [`ella-core-5g-chart-fqdn`](ella-core/ella-core-5g-chart-fqdn/) | HA Ella Core cluster using Kubernetes pod FQDNs for Raft | N2, N3, and N6 | Bootstrap provisioning and HA failover workflow |
| [`ueransim-5g-chart`](ella-core/ueransim-5g-chart/) | UERANSIM gNB and UE for Ella Core | gNB N2 and N3 | Dynamic Ella Core leader discovery and UE registration |

## Open5GS Labs

The Open5GS charts are compact, self-contained labs intended for learning.
Each chart includes its RAN simulator, subscriber provisioning, WebUI, and an
automated end-to-end test. `open5gs-4g` and `open5gs-5g` use Multus secondary
networks; `open5gs-5g-dra` uses DRA macvlan without secondary CNI attachments.
`open5gs-openupf-dra` keeps `open5gs-5g-dra` intact and provides a separate
Open5GS plus OpenUPF split-UPF reference chart. The 5G SBI and all WebUIs use
the default Kubernetes Pod network.

## Ella Core

The Ella Core charts deploy an HA Raft cluster and include automatic admin,
API-token, join-token, subscriber, and N6 configuration. Choose one core
variant:

- `ella-core-5g-chart` advertises stable Multus N2 addresses as Raft peers.
- `ella-core-5g-chart-fqdn` advertises Kubernetes pod FQDNs as Raft peers.

Deploy `ueransim-5g-chart` alongside the selected Ella Core chart for
end-to-end gNB and UE testing. It discovers the active Ella Core leader and
updates the gNB after failover.

See each chart's README for prerequisites, address planning, installation,
and verification commands.
