# IMS and SMSC integration lab

This disposable lab validates the two independent charts against Ella Core v1.20.0. It uses Ella Core's existing `core-tester` rather than creating a new NAS SMS implementation. The upstream runner simulates real RAN/UE NAS signalling and sends IMS traffic through GTP-U and the Core user plane.

Requirements: Helm 3+, kubectl, Python 3 for optional host-side tests, Multus with bridge/static/host-local plugins, a default RWO StorageClass, kernel SCTP, XFRM and TUN support. Run on kernel 6.6+ for TCX. The sample pins the lab Core, IMS and tester to `ebpf-bng-node-01`; change that node in all three manifests/values for another cluster. Bridge attachments are node-local, so these workloads must share a node. SMSC uses the pod network and may run elsewhere.

The lab Core and tester require privileged pods. Their interfaces are confined to pod namespaces; the lab does not use host networking. Core mounts `/sys/fs/bpf`. Core's database is ephemeral; chart databases are persistent. Only deploy this fixture in a dedicated test namespace: bootstrap sets operator configuration and creates test subscribers with public test keys.

## Deploy

Installation is Helm-only. Follow [ella-core-lab/README.md](../../ella-core-lab/README.md) for the complete install order, the in-cluster provisioning Job and the diagnostic shell. It deploys Core, its network attachments and tester pod; the independent IMS, SMSC, UI Service and UE charts complete the lab. No host setup script is required.

The raw core-lab.yaml, n6-lab.yaml and tester-pod.yaml files are retained as legacy fixtures; do not apply them alongside the corresponding Helm resources.

The `ella-ran` bridge uses 10.204.0.0/24. The N6 bridge uses Core 10.6.0.2 and IMS 10.6.0.5. UE IMS addresses use 10.60.0.0/16. Change these ranges if they overlap existing networks. Core advertises its pod IP for N2 and Diameter. Its image digest is pinned to the tested v1.20.0 build.

`ims-values.yaml` adds a route back to the UE pool and disables transmit checksum offload on the virtual N6 interface. This matches [upstream's IMS fixture](https://github.com/ellanetworks/core/blob/c7cf03530e52a2d353d9d1cd6159943319075bf0/integration/compose/ims/ims.yaml). Without this setting, partial UDP checksums from the virtual interface can arrive unchanged at the simulated UE's TUN, causing the UE kernel to discard SIP challenges. This setting belongs to the virtual test topology; determine offload requirements separately for physical interfaces.

## Build the runner

The Core lab chart pulls `ghcr.io/infinitydon/ella-services-tester:c7cf03530e52-tools1`. No local build or image import is required. The image includes `ip`, `ss`, `ping`, `dig`, `nslookup`, `curl`, `wget`, `nc`, `tcpdump`, `tracepath`, `traceroute`, `iptables`, `ethtool` and `jq`.

To rebuild on Linux from this directory, the Dockerfile checks out its pinned upstream Core revision itself:

```sh
buildah login ghcr.io
buildah bud --layers -f Dockerfile.tester -t ghcr.io/infinitydon/ella-services-tester:c7cf03530e52-tools1 .
buildah push ghcr.io/infinitydon/ella-services-tester:c7cf03530e52-tools1
```

Core, IMS and SMSC use their existing upstream images. Core provides these diagnostic tools through its troubleshooting sidecar.

## UI access

The Core UI is http://<node-ip>:30502/ (current lab: http://192.168.88.165:30502/). Configure the ella-core-ui chart through tests/services/core-ui-values.yaml. Login uses the initialized admin account.

## Validate

```sh
helm test ims -n ella-services-test
helm test smsc -n ella-services-test
# Supply the initialized admin password in ELLA_LAB_PASSWORD.
python3 tests/services/run-scenarios.py --output ./integration-results
```

The cross-platform Python runner discovers the Core and tester interface addresses, writes a log per scenario and machine-readable results.json, and exits nonzero if any scenario fails. Run it sequentially: scenarios bind the same simulated RAN ports. The default matrix includes 20 NAS SMS scenarios and four IMS registration/call scenarios. IMS registration covers UDP/TCP, AKA/IPsec, resynchronization and subscriber deletion; calls verify upstream's SIP/RTP/QoS assertions. This is functional testing, not a throughput or HA benchmark.

See [VALIDATION.md](VALIDATION.md) for recorded results and tested versions. Smoke-test command completion was verified with MicroK8s Helm 3.20.2 on the control-plane node. Windows Helm 4.2.1 completed the hook but hung during hook deletion in this environment; use Helm 3 for the smoke-test command if that occurs.

## UERANSIM evaluation

[l1jht/ueransim-ims](https://github.com/l1jht/ueransim-ims) is a patch against UERANSIM, not a complete standalone source tree. It adds in-process SIP/AKA, calls, RTP and SIP MESSAGE. SIP MESSAGE implements SMS over IMS; Ella SMSC instead exposes Diameter SGd/S6c for SMS over NAS. Thus that fork alone cannot test Ella SMSC's mobile-originated NAS path. Ella Core already provides the required NAS CP/RP/TPDU simulator and 4G/5G SMS scenarios, so no UERANSIM SMS patch was necessary. The recorded results use Core's runner; the linked fork was reviewed but not used for these validation claims.

## Remove the lab

```sh
helm uninstall ue ims smsc core-ui core -n ella-services-test
kubectl delete namespace ella-services-test
```

Uninstall removes chart-owned PVCs; copy database backups first if needed. Deleting the test namespace removes the ephemeral Core and runner. Keep build caches or remove them separately on the build node.
