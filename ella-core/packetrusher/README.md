# PacketRusher for Ella Core

[PacketRusher v2.0.0](https://github.com/HewlettPackard/PacketRusher/releases/tag/v2.0.0) is the latest stable release checked on October 26, 2026. This chart runs its native UE/gNB with the explicit ebpf tunnel backend. An unavailable eBPF backend is an error; the chart does not select auto fallback. Linux 6.6+ with BTF, SCTP and /dev/net/tun is required on the simulator node.

## Install

Enable the component in the consolidated release:

```sh
helm upgrade --install ella ./ella-core/ella-stack -n ella-services-test \
  -f ./ella-core/ella-stack/examples/standalone-internet-ims-sms.yaml \
  --set core.admin.existingSecret=ella-lab-admin --set packetrusher.enabled=true \
  --wait --wait-for-jobs --timeout 8m
```

The same setting works with all four Core presets, including HA. UERANSIM and the phone UIs can coexist when using their distinct default subscriber identities. An independent install against an already provisioned Core is:

```sh
helm install load ./ella-core/packetrusher -n ella-services-test \
  --set core.host=ella-core-active --wait --timeout 5m
helm test load -n ella-services-test
kubectl -n ella-services-test exec deployment/load-packetrusher -- \
  /packetrusher/packetrusher control --socket /run/simulator/control.sock \
  --ue 1 --action wait --timeout 30s
```

Dependencies and the supervisor are included in the charts; no host installation script or gtp5g kernel-module build is required. The privileged Pod loads TCX eBPF programs in its own network namespace. Configure `networkAttachment`, `n2n3Address` and `coreN2Addresses` to attach N2/N3 to a dedicated Multus network. The image targets Linux/amd64. Set nodeSelector/affinity to compatible nodes.

## Configuration and operation

The default IMSI is 001018900000200, internet DNN, SST 1 and SD 102030, using the public Core fixture key/OPc. ueCount defaults to one; larger counts require consecutive subscriber identities provisioned on Core and appropriate resources. Only the one-UE lab setup is validated here. subscriber.existingSecret accepts a same-namespace Secret with key and opc fields. core.host/core.namespace/core.clusterDomain select the active Core Service, as in the UERANSIM chart.

The supervisor monitors the active Core's public readiness endpoint. On leader/Pod-IP changes it stops PacketRusher cleanly and starts a fresh registration/PDU session. Its control socket is /run/simulator/control.sock; local procedure metrics are at 127.0.0.1:9090/metrics, and the report is written to /run/simulator/report.json on shutdown. Pod readiness requires the requested number of UE addresses. This is reattachment after Core failure, not uninterrupted traffic or a performance benchmark.

The default image is the unmodified official v2.0.0 binary plus Python, bpftool, DNS/HTTP and packet-capture tools and its Apache license. images/Dockerfile pins the official image by digest. The public tools tag is ghcr.io/infinitydon/ella-services-tester:packetrusher-v2.0.0-tools2; values.yaml pins its digest. backend=userspace is an explicit optional setting; validation requires the default backend=ebpf.

See [native simulator validation](../tests/simulators/README.md) for the essential registration/traffic tests and process-owned eBPF attachment proof. The optional core-tester protocol suite shares these fixture identities: pause simulated UE deployments before running it. Runtime operation needs no Core admin token or Kubernetes API permissions.
