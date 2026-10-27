# Consolidated chart validation

The default acceptance suite is now `tests/smoke.py`: Helm health checks plus
12 essential phone checks, using the same command for standalone and HA.
The optional service protocol runner defaults to four scenarios:
`sms/5g_mo_mt`, `sms/4g_mo_mt`, `ims/5g_call`, and `ims/4g_call`.
All four passed in both recorded full topology runs below. The original
22-check phone suite is retained with `--network`; the original 24 protocol
scenarios are retained with `--suite extended`. The expanded results and known
failures below are historical evidence, not removed or relabelled as passing.

## Fresh separate-stack install (October 27, 2026)

After removing the three prior Ella lab releases and their dedicated test
namespaces, two independent releases were installed from the N2/N3 test
presets: `ella-sa` in namespace `ella-sa` and `ella-ha` in namespace
`ella-ha`. Both completed Helm installation with `--wait --wait-for-jobs`.
Their pods use separate N6/N2/N3 subnets and distinct Core/phone NodePorts.
Both releases were left running. Other cluster releases and namespaces were
not included in the cleanup.

The Core, IMS and SMSC health hook Pods reached `Completed`. Helm 4.2.1's
aggregate `helm test` command did not return on the fresh SA release after
creating its hooks, so it was stopped and its completed hook Pods were cleaned
up. Do not count the aggregate SA hook command as a pass. The successful
waited install, topology check, phone suite and native UE suites provide the
SA acceptance evidence instead.

| Fresh release | Topology check | Phone essential suite | Native UE suite |
| --- | --- | --- | --- |
| `ella-sa` | 1 Core ready; Services and routes aligned | 12/12 passed | UERANSIM + PacketRusher 11/11 passed |
| `ella-ha` | 3 Core members ready; elected leader, Services and routes aligned | 12/12 passed | UERANSIM 5/5; PacketRusher 6/6 passed |

Both native simulators registered and established PDU sessions. PacketRusher's
own eBPF attachment check passed with no fallback. ICMP, DNS and HTTPS through
the UE passed for both simulators in both topologies. The phone checks covered
UE attachment, IMS registration, bidirectional NAS SMS, bidirectional IMS
calls with voice QFI, release, and HTTPS over each UE. These are clean
installation checks, not a new leader-failure test. The separate fresh HA
deployment's expanded protocol-edge suite was not run; prior extended HA SMS
limitations remain as recorded below.

Follow-up UI update: both releases were upgraded to `ella-stack` 1.3.0 and all
four phone Pods pulled `ghcr.io/infinitydon/ella-ue-phones:0.4.6` (manifest
`sha256:52fa32be76c46bf45ebc29486ff5323c8f932dc653310485e4e906484fee9587`).
The Phone A page rendered separate **Core / Internet IP** and **IMS IP** values;
live API responses verified both address fields for both phones in SA and HA.
Both phone Deployments are Ready in each namespace.

The test presets select compatible kernel nodes for this cluster. Their
`nodeSelector`/affinity hostnames are examples and must be adapted or removed
for another cluster with different node names and kernel capabilities.

The new defaults were exercised on Linux against the running standalone lab:
12/12 phone checks and 4/4 protocol scenarios passed. The HA essential baseline
is extracted from the recorded full run, including 12/12 phone checks before
and after failover, rather than claiming a new HA deployment run. See the
essential-* summaries under tests/results.

Live runs: October 25, 2026 US Eastern / October 26 UTC, namespace
`ella-services-test`, release `ella`. Results below distinguish the phone
acceptance tests from the broader upstream protocol scenarios. HA is not a
claim of uninterrupted RAN sessions, calls, or replicated IMS/SMSC processes.

## Installation and migration

Before cleanup, Core's authenticated API backup, consistent IMS/SMSC database
archives, and all five releases' values/manifests were saved outside Git.
The previous Core, UI, IMS, SMSC and UE releases were removed. Subsequent matrix
resets deleted only the disposable lab's exact Core PVC names; the existing
admin Secret and unrelated namespace workloads were preserved.

Each preset was installed from empty test databases using Linux MicroK8s Helm
3.20.2, ordinary Helm bootstrap Jobs and public images. No host installation
script, Windows script, node-local image import or image-pull credential was
required. Helm 4 upgrades were additionally exercised with `--wait=legacy`.
The internet-to-combined standalone service-mode upgrade was also tested.

Core runs on Linux 6.8 nodes. HA uses three separate hosts and three voter
members, stable Raft FQDNs and separate bound PVCs. IMS/phones use one worker;
SMSC uses the control-plane node. Shared N6 is macvlan on eth0. The lab has
local-path storage, a dedicated N6 gateway and a separate Core controller; this does not test a
permanent host/storage failure or provide IMS/SMSC high availability.

## Final matrix

| Preset | Phone checks | Helm tests | Expanded protocol suite |
| --- | --- | --- | --- |
| standalone-internet | 12/12 | 1/1 | Not applicable |
| standalone-internet-ims-sms | 22/22 | 3/3 | 24/24 |
| ha-internet | 12/12, also after failover | 1/1 | Not applicable |
| ha-internet-ims-sms | 22/22 before/after failover and after fixture restoration | 3/3 | **21/24, partial** |

The broader HA run failed `sms/5g_injected` (no SMS received before timeout),
`sms/5g_absent_then_alert` (expected no-paging-response attempt not observed),
and `sms/4g_withdrawal` (expected IMSI-detached attempt instead returned
service_not_subscribed). All four IMS protocol scenarios passed in that run.
These three SMS failures remain open; their root cause is not established.
Earlier development runs also showed different HA SMS failures, so the
expanded HA suite is not reliably passing. Do not interpret passing phone
checks or Core Raft recovery as full HA SMS certification.

The final running lab uses standalone-internet-ims-sms, whose full protocol
suite passed. Its final fresh reinstall passed another 22/22 phone checks and
all three Helm hooks. Chromium UID download through UE A returned HTTP 200
for a 138,612-byte HTTPS document. Both service modes and both Core topologies remain selectable.
All UE data/protocol matrix tests used IPv4; IPv6 was not validated.

The 12 internet checks cover two dedicated Services, internet-only TUN/session
state, rejected IMS/SMS actions, public ICMP and DNS, and Chromium UID HTTPS
through each UE's SOCKS/data path. ICMP defaults to 8.8.8.8 and is configurable
with `--icmp-host`; 1.1.1.1 stopped answering ICMP during testing while DNS,
HTTPS and the alternate public ICMP destination worked.

The 22 combined checks cover both NAS attachments and IMS registrations, SMS
both directions including accented text, confirmed calls and bidirectional
voice-QFI media, release and registration cycling, HTTPS through each UE,
private destination/direct browser egress rejection, one UE tunnel failing
without disrupting the other, and tunnel recovery. Calls carry synthetic test
media; browser microphone/speaker audio is not connected.

Helm tests probe Core readiness and, in combined mode, IMS and SMSC APIs.
The 24-scenario suite contains 20 4G/5G NAS SMS scenarios and four IMS
registration/call scenarios. Phones are paused during this suite to avoid
duplicate IMSI ownership. Registration scenarios delete a test subscriber;
bootstrap is rerun before restoring the final phone deployments.

## Recovery

| HA mode | Leader Service changed | All Core members ready | Reattached phone checks |
| --- | --- | --- | --- |
| Internet | 5.7 seconds | 14.8 seconds | 12/12 |
| Internet + IMS/SMS | 7.3 seconds | 21.0 seconds | 22/22 |

All three PVC UIDs were preserved in both tests. The combined-mode recovery
run was repeated from a clean chart install after disabling gateway ICMP
redirects; it needed no host command, database clearing or Helm upgrade to
restore IMS registration/calls, SMS and browsing after UE reattachment.

The fault test deletes the current Core leader Pod, waits for another member
to lead, checks both Service selectors and all three retained PVC UIDs, and
reattaches fresh UE processes. It then repeats the phone checks without a Helm
upgrade and verifies current member API addresses match Pod IPs, all three
members are voters, and the gateway return route follows the leader. Existing
IMS registration records remain in the IMS database during this test.

## Fixes exercised

- A normal bootstrap Job initializes/joins members while Helm waits. Phone
  initialization waits for the current release revision's successful Job and
  completed Core rollout, instead of treating an HTTP listener as UE readiness.
- Services select the elected leader; the controller reconciles drift and
  preserves its selector across Helm upgrades. The separate N6 gateway updates
  UE return routes to follow that leader. Gateway ICMP redirects are disabled:
  otherwise IMS caches a direct route to the old Core and bypasses updated
  gateway routes after an election.
- IMS maintains a peer for every Core identity. The leader is preferred for
  realm routing, while remembered HSS identities remain reachable. Peer Pod
  addresses are refreshed after replacement.
- Pod-local N6 checksum completion handles same-host macvlan traffic and UE
  TUN delivery. Core disables GRO/GSO/TSO on its own datapath interfaces; no
  host NIC settings are changed.
- The older released Core image retained stale peer API addresses after Pod
  replacement. The chart pins an unmodified upstream source build containing
  member-address reconciliation, with its matching UI and Linux IP tools.

## Versions and static checks

Core source: `c7cf03530e52a2d353d9d1cd6159943319075bf0`, version string
`v1.20.0`, a post-release snapshot rather than a new official release.
Public image: `ghcr.io/infinitydon/ellacore:c7cf03530e52-tools2`, manifest
`sha256:926206d7e1b4e4d64ef3f9f91211ec5630951f33ae62c33c694fbd4f83d6bf91`.
The running status API reports that source revision. Anonymous registry pull,
the compiled binary and Linux connectivity utilities were checked. The build
uses unmodified pinned upstream source, its frontend, and LICENSE/NOTICE files.
Upstream `TestReconcileClusterMembers` database tests passed on Linux.

IMS: `sha-2c8873dc8744`; SMSC: `sha-6e7a275024fb`; tester:
`c7cf03530e52-tools1`; phones: `0.4.1`; Chromium/noVNC: `0.3.4`.
See child values for complete image references. Custom runtime architecture
is Linux/amd64.

Helm lint passed for all five active charts. Four bootstrap fixtures and three
render test groups passed, covering four presets, all three UI Service types,
and invalid mode/topology/dependency combinations. ClusterIP/NodePort/
LoadBalancer manifests were rendered; server validation was exercised for
LoadBalancer. NodePort was used for live access. No external load-balancer
allocation was tested. A server-aware Helm dry run rejected an unsafe
standalone-to-HA database reuse attempt. Vendored dependency versions resolve.

## Reproduce

Use the Linux installation commands and presets in [README.md](README.md).
After Helm completes, wait for both phone Deployments before running their
acceptance tests. For the optional upstream scenarios, use the command in
[the service test guide](../tests/services/README.md), pause phones, and supply
the admin password through the environment rather than a command argument.

```sh
python3 ella-core/ella-stack/tests/test-bootstrap.py
python3 ella-core/ella-stack/tests/test-render.py
python3 ella-core/ella-stack/tests/check-topology.py --topology ha \
  --admin-secret ella-lab-admin --core-api http://NODE_IP:30502 \
  --output topology.json
# Deliberately replaces the leader Pod in the disposable test namespace:
python3 ella-core/ella-stack/tests/failover.py --before topology.json \
  --output failover.json
```

Sanitized final acceptance/scenario summaries are stored under tests/results.
Credentials, full database archives and authenticated runner logs remain
outside the repository.
