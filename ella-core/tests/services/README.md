# IMS and SMSC integration lab

This disposable lab validates the two independent charts against Ella Core v1.20.0. It uses Ella Core's existing `core-tester` rather than creating a new NAS SMS implementation. The upstream runner simulates real RAN/UE NAS signalling and sends IMS traffic through GTP-U and the Core user plane.

Requirements: Helm 3+, kubectl, PowerShell 7, Multus with bridge/static/host-local plugins, a default RWO StorageClass, kernel SCTP, XFRM and TUN support. Run on kernel 6.6+ for TCX. The sample pins the lab Core, IMS and tester to `ebpf-bng-node-01`; change that node in all three manifests/values for another cluster. Bridge attachments are node-local, so these workloads must share a node. SMSC uses the pod network and may run elsewhere.

The lab Core and tester require privileged pods. Their interfaces are confined to pod namespaces; the lab does not use host networking. Core mounts `/sys/fs/bpf`. Core's database is ephemeral; chart databases are persistent. Only deploy this fixture in a dedicated test namespace: bootstrap sets operator configuration and creates test subscribers with public test keys.

## Deploy

From the repository's `ella-core` directory:

```powershell
$ns='ella-services-test'
kubectl create namespace $ns
kubectl -n $ns apply -f tests/services/n6-lab.yaml
kubectl -n $ns apply -f tests/services/core-lab.yaml
helm upgrade --install ims ./ella-ims -n $ns -f tests/services/ims-values.yaml
helm upgrade --install smsc ./ella-smsc -n $ns
```

The `ella-ran` bridge uses 10.204.0.0/24. The N6 bridge uses Core 10.6.0.2 and IMS 10.6.0.5. UE IMS addresses use 10.60.0.0/16. Change these ranges if they overlap existing networks. Core advertises its pod IP for N2 and Diameter. Its image digest is pinned to the tested v1.20.0 build.

`ims-values.yaml` adds a route back to the UE pool and disables transmit checksum offload on the virtual N6 interface. This matches [upstream's IMS fixture](https://github.com/ellanetworks/core/blob/c7cf03530e52a2d353d9d1cd6159943319075bf0/integration/compose/ims/ims.yaml). Without this setting, partial UDP checksums from the virtual interface can arrive unchanged at the simulated UE's TUN, causing the UE kernel to discard SIP challenges. This setting belongs to the virtual test topology; determine offload requirements separately for physical interfaces.

## Build the runner

Build on the selected Linux node with Buildah (or Docker), using the pinned upstream source:

```sh
git clone https://github.com/ellanetworks/core ella-services-core-tester
cd ella-services-core-tester
git checkout c7cf03530e52a2d353d9d1cd6159943319075bf0
# Copy this directory's Dockerfile.tester into the source checkout.
sudo buildah bud --layers -f Dockerfile.tester -t localhost/ella-services-tester:c7cf03530e52 .
sudo buildah push localhost/ella-services-tester:c7cf03530e52 docker-archive:/tmp/ella-services-tester.tar:localhost/ella-services-tester:c7cf03530e52
sudo microk8s ctr images import /tmp/ella-services-tester.tar
```

Import into the runtime used by kubelet on the selected node. For a different runtime, adjust the import command or publish to your own registry and change tester-pod.yaml. The chart images themselves are upstream public images; no custom IMS or SMSC build is needed.

```powershell
kubectl -n $ns apply -f tests/services/tester-pod.yaml
kubectl -n $ns wait pod/ella-services-tester --for=condition=Ready --timeout=120s
```

## Provision

Core UI/API is available through NodePort **30502**: http://<node-ip>:30502/ (current lab: http://192.168.88.165:30502/). Login uses the email and password supplied to bootstrap; credentials are kept outside Git.

Change only its Service without restarting Core:

~~~powershell
./tests/services/configure-core-ui.ps1 -ServiceType NodePort -NodePort 30502
# Alternatives: -ServiceType ClusterIP, or -ServiceType LoadBalancer
# -NodePort 0 requests automatic allocation; ignored for ClusterIP.
~~~

The script accepts Namespace, Kubeconfig, Port and TargetPort overrides. Do not reapply the entire Core fixture just to change UI access: its database is ephemeral.

In separate terminals, forward the IMS/SMSC APIs:

```powershell
kubectl -n ella-services-test port-forward deployment/ims-ella-ims 25020:5020
kubectl -n ella-services-test port-forward deployment/smsc-ella-smsc 15010:5010
```

Find current Core/SMSC pod IPs with `kubectl -n ella-services-test get pods -o wide`. Choose a private password and keep it outside the repository:

```powershell
./tests/services/bootstrap.ps1 -CoreApi http://<node-ip>:30502 -ImsApi http://127.0.0.1:25020 -CoreAddress <core-pod-ip> -SmscAddress <smsc-pod-ip> -ImsAddress 10.6.0.5 -Password $env:ELLA_LAB_PASSWORD
```

Bootstrap initializes or logs in to the Core, configures the operator, slice, IMS policies, Diameter peers and SMSC settings, and provisions subscribers. Registration tests intentionally delete their registration subscriber at the end; rerun bootstrap before repeating those tests. Rerun bootstrap with updated IPs after a Core/SMSC pod address changes. Existing chart SQLite settings survive pod replacement.

## Validate

```powershell
helm test ims -n ella-services-test
helm test smsc -n ella-services-test
./tests/services/run-scenarios.ps1 -Password $env:ELLA_LAB_PASSWORD -OutputDirectory ./results
# Additional store-and-forward and service withdrawal checks:
./tests/services/run-scenarios.ps1 -Password $env:ELLA_LAB_PASSWORD -OutputDirectory ./recovery-results -Scenarios sms/5g_absent_then_alert,sms/4g_absent_then_alert,sms/5g_withdrawal,sms/4g_withdrawal
```

The runner discovers the Core and tester interface addresses, writes a log per scenario and machine-readable results.json, and exits nonzero if any scenario fails. Run it sequentially: scenarios bind the same simulated RAN ports. The default matrix includes 16 NAS SMS scenarios and four IMS registration/call scenarios. IMS registration covers UDP/TCP, AKA/IPsec, resynchronization and subscriber deletion; calls verify upstream's SIP/RTP/QoS assertions. This is functional testing, not a throughput or HA benchmark.

See [VALIDATION.md](VALIDATION.md) for recorded results and tested versions. Smoke-test command completion was verified with MicroK8s Helm 3.20.2 on the control-plane node. Windows Helm 4.2.1 completed the hook but hung during hook deletion in this environment; use Helm 3 for the smoke-test command if that occurs.

## UERANSIM evaluation

[l1jht/ueransim-ims](https://github.com/l1jht/ueransim-ims) is a patch against UERANSIM, not a complete standalone source tree. It adds in-process SIP/AKA, calls, RTP and SIP MESSAGE. SIP MESSAGE implements SMS over IMS; Ella SMSC instead exposes Diameter SGd/S6c for SMS over NAS. Thus that fork alone cannot test Ella SMSC's mobile-originated NAS path. Ella Core already provides the required NAS CP/RP/TPDU simulator and 4G/5G SMS scenarios, so no UERANSIM SMS patch was necessary. The recorded results use Core's runner; the linked fork was reviewed but not used for these validation claims.

## Remove the lab

```powershell
helm uninstall ims smsc -n ella-services-test
kubectl delete namespace ella-services-test
```

Uninstall removes chart-owned PVCs; copy database backups first if needed. Deleting the test namespace removes the ephemeral Core and runner. Keep build caches or remove them separately on the build node.
