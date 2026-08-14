# Telco Helm Charts

This repository contains Helm charts for beginner-friendly Open5GS labs and
high-availability Ella Core private 5G deployments.

## Chart Catalog

| Chart | Purpose | Secondary networking | Validation or companion |
| --- | --- | --- | --- |
| [`open5gs-4g`](open5gs-4g/) | Open5GS EPC learning lab | LTE signaling and user-plane interfaces | Included srsRAN eNB/UE attach and SGi ping |
| [`open5gs-5g`](open5gs-5g/) | Open5GS standalone 5G learning lab | N2, N3, N4, and N6 | Included UERANSIM registration, PDU session, and N6 ping |
| [`open5gs-5g-dra`](open5gs-5g-dra/) | Open5GS standalone 5G using DRA macvlan | DRA N2, N3, N4, and N6 | UERANSIM registration, PDU session, ping, and iperf3 |
| [`open5gs-ueransim-secure-n2`](open5gs-ueransim-secure-n2/) | Open5GS and UERANSIM with a gNB sidecar proxy and HA QUIC/mTLS middleware securing N2 | Separate Multus `secure-n2` proxy path and `core-n2` AMF path, plus N3, N4, N6, and simulated radio networks | Floating middleware VIP, cross-worker failover, NG Setup replay, supervised UE re-registration, and PDU-session validation |
| [`open5gs-openupf-dra`](open5gs-openupf-dra/) | Open5GS 5G core with OpenUPF split UPF | DRA macvlan for Open5GS/SMU N4 and Intel VF DPDK for LBU/FPU | OpenUPF backend validation, 10-UE registration, ping, and iperf3 |
| [`magma-ebpf`](magma-ebpf/) | Guarded workflow for Magma AGW with the TOSSI eBPF GTP-U datapath | Host-level AGW N3/S1-U eBPF TC attachment | Helm lint/template, server dry-run, and safe Helm test |
| [`magma-agw-upstream`](magma-agw-upstream/) | Magma 1.9.0 upstream containerized AGW baseline | Host-networked AGW services | Helm lint/template and server dry-run |
| [`free5gc-charging-portal`](free5gc-charging-portal/) | Lab top-up portal for free5GC CHF charging quota | Uses existing free5GC MongoDB and CHF services | Operator and self-service fictitious credit top-up |
| [`free5gc-charging-stack`](free5gc-charging-stack/) | free5GC v4.2.2 core with charging top-up portal | Multus N2, N3, N4, and N6 | Stack smoke test for portal health and Multus NADs |
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

`open5gs-ueransim-secure-n2` is the secured-N2 reference lab. UERANSIM connects
to a local `gnb_proxy` sidecar over SCTP; the proxy carries NGAP through an
mTLS-authenticated QUIC tunnel to an HA middleware StatefulSet. A kube-vip
leader makes one middleware replica authoritative on the Multus `secure-n2`
network, while a separate Multus `core-n2` network carries SCTP from the active
middleware to Open5GS AMF. The proxy reconnects and replays NG Setup after a
leader failure, and the supervised UE process can re-register when it detects
a lost registration or PDU session.

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
