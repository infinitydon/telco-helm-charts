# Native simulator acceptance tests

These tests verify UERANSIM v3.3.0 and PacketRusher v2.0.0 against the consolidated Ella Core, using the internet DNN. Both optional components can be enabled with:

```sh
helm upgrade --install ella ./ella-core/ella-stack -n ella-services-test \
  -f ./ella-core/ella-stack/examples/standalone-internet-ims-sms.yaml \
  --set core.admin.existingSecret=ella-lab-admin \
  --set ueransim.enabled=true,packetrusher.enabled=true \
  --wait --wait-for-jobs --timeout 8m
python3 ella-core/tests/simulators/smoke.py
```

Choose --simulator ueransim or --simulator packetrusher for a single component. Set --release/--namespace/--kubeconfig as needed. Independent installs can use --ueransim-release and --packetrusher-release. --ue-pool defaults to 10.45.0.0/16. Core subscribers must match the chart values; the sample Core provisioning Job creates these public fixture identities. Select a Linux 6.6+ simulator node for PacketRusher eBPF.

## Essential checks

Each simulator must report a UE address from the expected pool, its exact stable binary version, native registered/PDU state, ICMP and DNS traffic bound to its UE address, and HTTPS bound to that address. PacketRusher additionally proves its native process owns attached encap, decap and uplink eBPF programs: the probe reads that process's BPF descriptors and checks their program/link IDs. It does not count another Pod's or Core's programs as evidence.

The total is five UERANSIM checks and six PacketRusher checks. DNS uses up to two UDP attempts with a three-second timeout per attempt; an initial one-query probe saw a transient DNS timeout before subsequent queries and HTTPS succeeded. This is basic compatibility testing, not a throughput, packet-loss or large-scale UE benchmark. The one-UE-per-simulator configuration is the validated setup.

## Live validation, October 26, 2026

| Core preset | Native checks | Helm hooks | Native checks after leader replacement |
| --- | --- | --- | --- |
| Standalone internet | 11/11 | 3/3 | Not applicable |
| Standalone internet + IMS/SMS | 11/11 | 5/5 | Not applicable |
| HA internet | 11/11 | 3/3 | 11/11 |
| HA internet + IMS/SMS | 11/11 | 5/5 | 11/11 |

Both native simulator Pods retained their UIDs and container restart counts after each HA leader replacement; their process generations advanced. Internet HA selected a new Core in 2.6 seconds and all members were ready in 13.2 seconds. Combined HA took 4.1 seconds / 14.7 seconds. All three Core PVC UIDs were preserved. These measurements describe this test run, not a recovery-time guarantee.

The main standalone combined release also passed 11/11 native checks and 12/12 essential phone checks with both native simulators enabled. The phone UIs and native UEs use distinct default identities. The separate core-tester protocol suite shares native fixture identities and must be run with all simulated UE deployments paused; its preflight rejects active owners. See ../services/README.md.

The matrix used a dedicated ella-simulator-test namespace, separate N6 addresses (10.207.0.0/24), internet UE pool 10.208.0.0/16 and IMS pool 10.209.0.0/16. It did not reset the main phone lab. Core ran on three compatible Linux 6.8 hosts for HA; both simulators ran on a Linux 6.8 worker. Core topology checks verified a three-voter Raft membership on three hosts, current Pod API addresses, stable Raft DNS identities and correct leader Service/return routes.

HA recovery deliberately deleted the current Core leader Pod. Both simulators had to switch Core endpoint, advance their process generation, retain their Pod UIDs and container restart counts, and pass all 11 checks again. Reattachment is expected; uninterrupted sessions/traffic and a permanent host failure were not tested.

The isolated pool test exposed that Core seeds an internet data network before bootstrap. Fresh provisioning now reconciles the requested pool rather than skipping the seeded default. Upgrades preserve existing network settings (including UI edits) unless core.provisioning.reconcileDataNetworks is explicitly enabled. Explicit pool changes with active sessions are rejected, and IPv6 pools are retained. Regression tests cover the fresh seeded-default update, active-session guard and upgrade preservation. The main lab's existing internet /22 pool and 1400-byte MTU were retained during the final upgrade.

## Image provenance

Stable releases were verified against the upstream GitHub latest-release APIs on October 26, 2026, excluding prereleases/drafts:

- UERANSIM v3.3.0: 6bf5a1a96aaef6ae8778b9d8b477ac6e2bbf8156. Native C++ source is unmodified; the Dockerfile includes its license and Linux tools. Public tools tag: ghcr.io/infinitydon/ella-services-tester:ueransim-v3.3.0-tools1. Digest: sha256:eef4162e9dd65c80c3689437e4b34b9dd7eb5924fd5ee9c6a6ea43b30f68d512.
- PacketRusher v2.0.0: 6fef144296d4b1595e690a3d8e55c2a25407077b. The image derives from the official release digest sha256:919f5d42d8a5abcd181756082b921250620a80806efaf9d4ff3ae249faed6dab and adds Linux tools/Python/bpftool and its license, without modifying the binary. Public tools tag: ghcr.io/infinitydon/ella-services-tester:packetrusher-v2.0.0-tools2. Digest: sha256:6b5d2402c1d6ccc0b84084c1762f4203968bf30a1cf8d4bfa0be9f8537527099.

Chart values pin the tools image digests. The supplied images target Linux/amd64 and can be reproduced using images/Dockerfile in each application chart. Charts are installed with Helm; no host build/setup script or image import is required. The optional core-tester extended HA SMS limitations from the earlier validation remain documented separately; native acceptance tests do not relabel those cases as passing.

Static checks cover the optional dependencies, explicit eBPF selection (auto is rejected), chart rendering/lint, bootstrap configuration and dependency packaging. Sanitized live results are under results/. Credentials and full build/authentication logs are kept outside Git. Test workloads and their dedicated namespace are removed after the matrix.
