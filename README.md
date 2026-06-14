# Telco Helm Charts

This repository contains small, teaching-oriented telecom labs.

| Chart | Core | RAN simulator | End-to-end check |
| --- | --- | --- | --- |
| `open5gs-4g` | Open5GS EPC | srsRAN 4G eNB and UE | UE attach and ping over SGi |
| `open5gs-5g` | Open5GS 5G SA | UERANSIM gNB and UE | UE registration, PDU session, and ping over N6 |

Both charts create their own Multus `NetworkAttachmentDefinition` resources.
See each chart's README for the interface list, addressing, installation, and
verification commands.
