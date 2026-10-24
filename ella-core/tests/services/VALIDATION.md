# Validation: 24 October 2026

Result: **24/24 functional scenarios passed**, plus both chart API smoke tests.

Cluster: Kubernetes v1.36.2, namespace `ella-services-test`. Core, IMS and runner used `ebpf-bng-node-01` (Ubuntu 22.04, kernel 6.8); SMSC used `ebpf-bng-node-03-ubuntu-focal`. The lab remains deployed for inspection. Existing BNG releases were not changed.

| Component | Tested image/source |
| --- | --- |
| Ella Core | v1.20.0, revision `34f32e94365a92a16a2a5cf933a811cca9960ed9`, image digest `sha256:89fd9b01308cef5127606ac1073b43e0f5d31724acae61e0ee0d3dbac5c91367` |
| Ella IMS | `ghcr.io/ellanetworks/ella-ims:sha-2c8873dc8744` |
| Ella SMSC | `ghcr.io/ellanetworks/ella-smsc:sha-6e7a275024fb` |
| Scenario runner | Built from Core source `c7cf03530e52a2d353d9d1cd6159943319075bf0` |

Chart versions: `ella-ims-0.1.0` and `ella-smsc-0.1.0`. Final release revisions: IMS 5, SMSC 3. Both applications had Ready pods and bound 1Gi RWO claims.

## Functional matrix

Each row ran over both 4G and 5G:

| Scenario | Result |
| --- | --- |
| Mobile-originated and mobile-terminated SMS, both directions, GSM7/UCS2 text | Pass |
| Idle recipient paging | Pass |
| API-injected SMS | Pass |
| Memory-full recovery | Pass |
| Switched-off subscriber | Pass |
| Back-to-back delivery | Pass |
| Unserved service centre | Pass |
| SMS not granted without MSISDN | Pass |
| Absent recipient followed by reachability alert | Pass |
| SMS service withdrawal and restoration | Pass |
| IMS registration over UDP/TCP, AKA/IPsec, resynchronization and deletion | Pass |
| IMS call with media, voice QoS and release assertions | Pass |

The first ten rows account for 20 SMS scenarios; the last two account for four IMS scenarios. See [results.json](results.json) for individual scenario names and exit codes. The final functional run completed around 11:37 America/New_York.

## Deployment checks

- Helm lint passed for both charts.
- Default and alternate values rendered, including ephemeral storage, existing claims and host networking.
- Kubernetes server dry-run accepted the rendered IMS resources.
- Both API Helm hooks passed using MicroK8s Helm 3.20.2 on the control-plane node; the command returned success. The local Windows Helm 4.2.1 client ran successful hooks but hung waiting for hook deletion, so it was not used to certify smoke-test command completion. Chart installation/upgrades with Helm 4 succeeded.
- IMS was replaced during validation. SQLite peer/operator settings remained present, the Cx/Rx connection reopened, and all final scenarios passed with the route/offload init container applied automatically.
- Core/SMSC SGd/S6c and Core/IMS Cx/Rx peers reached `open`.

## Resolved setup issues and limits

The initial fixture retained Core's built-in default slice without SD 102030. Bootstrap now updates that slice to match the runner. SIP challenges also initially reached the runner with partial UDP checksums. Disabling TX checksum offload on the IMS virtual N6 interface, as upstream does in its Docker integration fixture, resolved this; the lab values now apply that setting on every pod creation.

Tests use simulated UEs and exercise the Core user plane. They do not certify physical handsets, video calls, UERANSIM fork interoperability, HA, performance or production security. No new SMS emulator was required: Core's upstream NAS SMS simulator covers the relevant path. The chart defaults use dynamic pod addresses; fixed Multus addresses are recommended for durable protocol endpoints. The sample bridge networks are node-local.
