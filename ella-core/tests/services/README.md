# IMS and SMSC integration lab

This disposable lab validates the two independent charts against Ella Core v1.20.0. It uses Ella Core's existing `core-tester` rather than creating a new NAS SMS implementation. The upstream runner simulates real RAN/UE NAS signalling and sends IMS traffic through GTP-U and the Core user plane.

Requirements: Helm 3+, kubectl, Python 3 for optional tests, Multus with macvlan support, a default RWO StorageClass, kernel SCTP, XFRM and TUN support. Core requires kernel 6.6+ for TCX. See the stack chart for shared N6 networking and three-node HA requirements.

The lab Core and tester require privileged pods. Core mounts `/sys/fs/bpf`; Core, IMS and SMSC databases are persistent in the consolidated chart. Only deploy the presets in a dedicated test namespace: bootstrap configures the operator and creates subscribers with public test keys.

## Deploy

Use [ella-stack](../../ella-stack/README.md) for the consolidated Linux Helm install and all four deployment presets. It owns Core, its UI Service and networking, selected IMS/SMSC resources, phones, diagnostics and the optional tester under one release. The raw historical YAML fixtures in this directory are retained only as records of the earlier lab layout; they are not the consolidated installation procedure.

## Build the runner

The stack chart pulls `ghcr.io/infinitydon/ella-services-tester:c7cf03530e52-tools1`. No local build or image import is required. The image includes `ip`, `ss`, `ping`, `dig`, `nslookup`, `curl`, `wget`, `nc`, `tcpdump`, `tracepath`, `traceroute`, `iptables`, `ethtool` and `jq`.

To rebuild on Linux from this directory, the Dockerfile checks out its pinned upstream Core revision itself:

```sh
buildah login ghcr.io
buildah bud --layers -f Dockerfile.tester -t ghcr.io/infinitydon/ella-services-tester:c7cf03530e52-tools1 .
buildah push ghcr.io/infinitydon/ella-services-tester:c7cf03530e52-tools1
```

Core uses the pinned source build documented in ella-stack and also includes a troubleshooting sidecar. IMS and SMSC use upstream images.

## UI access

The Core UI is http://NODE_IP:30502/. Configure core.service in ella-stack. Login uses the initialized admin account from core.admin or its existing Secret.

## Validate

```sh
helm test ella -n ella-services-test
kubectl -n ella-services-test scale deployment ella-ue-a ella-ue-b --replicas=0
# Supply the initialized admin password in ELLA_LAB_PASSWORD.
python3 ella-core/tests/services/run-scenarios.py \
  --core-selector app.kubernetes.io/name=ella-core --core-service ella-core \
  --smsc-service ella-ella-smsc --core-api http://NODE_IP:30502 \
  --output ./integration-results
# Essential tests do not delete subscribers. Restore the phones afterward:
kubectl -n ella-services-test scale deployment ella-ue-a ella-ue-b --replicas=1
```

The cross-platform Python runner discovers the Core and tester interface addresses, writes a log per scenario and machine-readable results.json, and exits nonzero if any scenario fails. Run it sequentially: scenarios bind the same simulated RAN ports. The default essential suite has four scenarios: bidirectional NAS SMS and IMS calls on both 5G and 4G. Add --suite extended for the original 24 scenarios (20 NAS SMS and four IMS registration/call scenarios). The extended registration tests delete a subscriber; rerun the same Helm preset before restoring phones after that suite. Extended IMS registration covers UDP/TCP, AKA/IPsec, resynchronization and subscriber deletion; calls verify upstream's SIP/RTP/QoS assertions. This is functional testing, not a throughput or HA benchmark.

See [stack validation](../../ella-stack/VALIDATION.md) for the consolidated chart results. [Earlier validation](VALIDATION.md) records the historical separate-release installation.

## UERANSIM evaluation

[l1jht/ueransim-ims](https://github.com/l1jht/ueransim-ims) is a patch against UERANSIM, not a complete standalone source tree. It adds in-process SIP/AKA, calls, RTP and SIP MESSAGE. SIP MESSAGE implements SMS over IMS; Ella SMSC instead exposes Diameter SGd/S6c for SMS over NAS. Thus that fork alone cannot test Ella SMSC's mobile-originated NAS path. Ella Core already provides the required NAS CP/RP/TPDU simulator and 4G/5G SMS scenarios, so no UERANSIM SMS patch was necessary. The recorded results use Core's runner; the linked fork was reviewed but not used for these validation claims.

## Remove the lab

```sh
helm uninstall ella -n ella-services-test
```

Uninstall removes IMS/SMSC chart PVCs but retains Core StatefulSet PVCs. Back up databases first; explicitly delete only the intended test PVCs when resetting a disposable lab. Namespace deletion also removes Secrets and retained PVCs, so it is not required for ordinary uninstall.
