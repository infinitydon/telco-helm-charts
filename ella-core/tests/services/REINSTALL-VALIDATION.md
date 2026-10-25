# Clean reinstall validation — 25 October 2026

The ella-services-test namespace was removed and recreated, including fresh IMS/SMSC PVCs and a fresh ephemeral Core database. Before deletion, the previous Core database archive and release values were saved outside Git under the task workspace's .local/reinstall-backup directory. The previous login account was provisioned again with the same credentials from an external Kubernetes Secret; credentials are not committed.

All lab workloads now install through Helm: core (ella-core-lab), core-ui (ella-core-ui), ims (ella-ims), smsc (ella-smsc), and ue (ue-phones). The Core chart owns its network attachments, headless Diameter/NGAP discovery Service and tester pod. Its post-upgrade bootstrap Job ran successfully, initialized Core/IMS/SMSC and created the 36 expected subscriber identities. After the registration tests deleted their test identities, rerunning the hook restored them. The UEs attached using ella-core-lab-diameter:38412 without a pod-IP override.

## Functional results

- **24/24 integration scenarios passed:** 20 NAS SMS scenarios and four IMS registration/call scenarios across 4G/5G. Includes idle, injected, memory-full, switched-off, repeated messages, unserved service centre, denied SMS, absent-then-alert and withdrawal. See reinstall-results.json; the Python runner preserves a redacted log for each scenario outside Git.
- **2/2 Helm API smoke tests passed:** IMS and SMSC, using MicroK8s Helm 3.20.2. Do not use --logs together with automatic hook-pod deletion; Helm otherwise reports a missing log pod after the test has succeeded.
- **22/22 phone/browser checks passed:** both NAS attachments and IMS registrations; SMS both ways with accented text/euro and actual receipt; both call directions with confirmed voice-QFI media; release and registration cycling; HTTPS reader through each UE and private-destination rejection; each browser UID's proxy HTTPS; direct-egress rejection with firewall counters; UE A tunnel interruption, continued UE B access and UE A recovery. See ../../ue-phones/tests/reinstall-results.json. The cross-platform smoke.py script replaces the need for PowerShell tests.
- **Diagnostic sidecar verified:** bash, curl, dig, ip, ss and tcpdump are available; the sidecar sees the Core process and reaches its loopback API. tcpdump captured an actual TCP packet to 127.0.0.1:5002. Core runs 2/2 containers with zero restarts. No ephemeral debug container was injected.
- Chart lint passed for the new lab chart, updated HA Core chart and UE chart. Rendering troubleshooting.enabled=false omits the HA chart's diagnostic container. Python sources compile. The older HA/v1.10.1 deployment was rendered/linted, not installed as part of the v1.20.0 lab test.

Helm 4's watcher wait strategy stalled during the first bootstrap upgrade; rollback and --wait=legacy completed it successfully. The README uses ordinary Helm 3 --wait and documents the Helm 4 alternative. This was a client wait-strategy issue, not a missing or unhealthy Core workload.

## Cluster cleanup

The pre-cleanup snapshot contained 5,368 pods: 53 non-terminal and 5,315 terminal records. Removed 4,990 Failed and 325 Succeeded records, mostly old monitoring evictions/completions. Two old Failed CPE pods had deletion timestamps from the previous day and no finalizers; normal deletion left them terminating, so they were force-removed. The current CPE deployment stayed ready. No healthy unrelated workload was deleted or restarted.

Most recorded eviction messages referred to historical DiskPressure/ephemeral-storage exhaustion. At final verification, all four nodes were Ready with DiskPressure=False and MemoryPressure=False. The cluster contained **53 Running pods, all ready**, with no Pending, Failed, Succeeded or terminating pod records. Control-plane root disk had 7.1 GiB available and worker 01 had 30 GiB available at the recorded check. No active pressure or recurring eviction was observed.

The full pre-cleanup pod metadata and deletion logs are stored outside Git in .local. Test hook pods are automatically deleted after success. The lab API/UI endpoints remain Core :30502, Phone A :30880 and Phone B :30881 on 192.168.88.165; the admin login is unchanged.
