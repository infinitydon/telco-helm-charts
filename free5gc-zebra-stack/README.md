# free5GC Zebra UPF Stack

This chart deploys free5GC `v4.2.2`, UERANSIM, Multus networks, an N6 gateway,
and a zebra-rs/cradle datapath that can replace the standard free5GC UPF for
this lab.

The zebra/cradle image is pinned by default to:

```text
ghcr.io/infinitydon/zebra-sh:26.7.4-nightly20260714
```

Do not use floating `latest` tags for this chart. The released
`ghcr.io/infinitydon/zebra-sh:v26.7.5` image was built and tested, but did not
pass this lab datapath test. It accepted PFCP/session setup but did not program
or use the GTP datapath (`gtp_encap=0`, `gtp_decap=0`) in either macvlan or
host-device mode.

## Datapath Modes

The chart supports two zebra/cradle attachment modes:

| Mode | Value | Multus type | Expected XDP mode |
| --- | --- | --- | --- |
| Generic XDP | `zebra.dataplane.mode=macvlan` | `macvlan` | Generic XDP fallback |
| Host-device | `zebra.dataplane.mode=hostDevice` | `host-device` | N3 native XDP; single-N6 logical children fall back to generic XDP |

The N6 gateway can also be selected independently:

| Mode | Value |
| --- | --- |
| Multus gateway pod | `n6Gateway.mode=macvlan` |
| Host network gateway | `n6Gateway.mode=hostNetwork` |

For host-device mode, set the free worker-node interfaces explicitly:

```yaml
zebra:
  dataplane:
    mode: hostDevice
  interfaces:
    n3:
      device: enp8s23
    n6:
      device: enp8s24
```

N6 is configured as one external network/device. The chart creates `n6ul` and
`n6dl` as logical interfaces inside the zebra pod because the current
zebra/cradle MUP datapath binds one VRF to one direction. Do not dedicate two
physical N6 NICs just for this split; if native XDP is required on N6, the
better long-term fix is for the datapath to support the usual operator model:
N3 in one VRF and N6 in another VRF.

## Lab Defaults

The default lab values pin workloads to `ebpf-bng-node-02` and use:

| Network | Interface | Subnet |
| --- | --- | --- |
| N2 | `enp8s19` | `10.201.10.0/24` |
| N3 | `enp8s20` or host-device `enp8s23` | `10.201.30.0/24` |
| N4 | `enp8s21` | `10.201.40.0/24` |
| N6 | `enp8s22` or host-device `enp8s24` | `10.201.60.0/24` |

Key lab addresses:

| Component | Address |
| --- | --- |
| gNB N2 | `10.201.10.20` |
| gNB N3 | `10.201.30.20` |
| SMF N4 | `10.201.40.10` |
| zebra N4 | `10.201.40.20` |
| zebra N3 | `10.201.30.10` |
| zebra N6 UL | `10.201.60.10` |
| zebra N6 DL | `10.201.60.11` |
| N6 gateway | `10.201.60.1` |
| UE pool | `10.60.128.0/17` |

The free5GC UPF is disabled by default:

```yaml
free5gc:
  deployUpf: false
```

## Install

Generic XDP / macvlan:

```bash
helm upgrade --install free5gc-zebra ./free5gc-zebra-stack \
  --namespace free5gc-zebra-test \
  --create-namespace \
  --set stackSmokeTest.enabled=true \
  --set zebra.dataplane.mode=macvlan \
  --set n6Gateway.mode=macvlan \
  --no-hooks \
  --timeout 10m \
  --wait
```

Native XDP / host-device:

```bash
helm upgrade --install free5gc-zebra ./free5gc-zebra-stack \
  --namespace free5gc-zebra-test \
  --create-namespace \
  --set stackSmokeTest.enabled=true \
  --set stackSmokeTest.iperf3.failOnError=true \
  --set zebra.dataplane.mode=hostDevice \
  --set zebra.interfaces.n3.device=enp8s23 \
  --set zebra.interfaces.n6.device=enp8s24 \
  --set n6Gateway.mode=macvlan \
  --no-hooks \
  --timeout 10m \
  --wait
```

Provision the default subscriber after the core is up:

```bash
helm template free5gc-zebra ./free5gc-zebra-stack \
  --namespace free5gc-zebra-test \
  --show-only templates/subscriber-provisioning.yaml \
  | kubectl apply -n free5gc-zebra-test -f -

kubectl wait -n free5gc-zebra-test \
  --for=condition=complete job/free5gc-zebra-subscriber-provisioning \
  --timeout=180s
```

Restart SMF/gNB/UE after provisioning to avoid the early UERANSIM attach race:

```bash
kubectl rollout restart -n free5gc-zebra-test \
  deploy/free5gc-zebra-free5gc-smf-smf \
  deploy/free5gc-zebra-ueransim-gnb \
  deploy/free5gc-zebra-ueransim-ue

kubectl rollout status -n free5gc-zebra-test deploy/free5gc-zebra-free5gc-smf-smf
kubectl rollout status -n free5gc-zebra-test deploy/free5gc-zebra-ueransim-gnb
kubectl rollout status -n free5gc-zebra-test deploy/free5gc-zebra-ueransim-ue
```

## Test

Run the smoke test:

```bash
helm test free5gc-zebra -n free5gc-zebra-test --timeout 8m
```

The smoke test checks:

- UE `uesimtun0` address assignment
- UE ping to N6 gateway
- UE ping to the configured internet target, default `8.8.8.8`
- cradle GTP counters and VRF routes
- optional `iperf3` from UE to the N6 gateway pod

The N6 gateway pod starts an `iperf3` server when `n6Gateway.iperf3.enabled`
is true. The UE side installs `iperf3` during the smoke test when
`stackSmokeTest.installIperf3` is true.

## Status Checks

Workload state:

```bash
kubectl get pods -n free5gc-zebra-test -o wide
kubectl get deploy -n free5gc-zebra-test
kubectl get network-attachment-definitions -n free5gc-zebra-test
helm status free5gc-zebra -n free5gc-zebra-test
```

Confirm the image in use:

```bash
kubectl get deploy -n free5gc-zebra-test free5gc-zebra-zebra \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Confirm XDP mode:

```bash
kubectl logs -n free5gc-zebra-test deploy/free5gc-zebra-zebra -c cradle \
  | grep 'XDP'
```

Check GTP counters:

```bash
ZEBRA_POD="$(kubectl get pod -n free5gc-zebra-test \
  -l app.kubernetes.io/name=zebra \
  -o jsonpath='{.items[0].metadata.name}')"

kubectl exec -n free5gc-zebra-test "$ZEBRA_POD" -c zebra -- \
  cradle stats --grpc unix:cradle/grpc | grep gtp
```

Check cradle routes:

```bash
kubectl exec -n free5gc-zebra-test "$ZEBRA_POD" -c zebra -- \
  cradle dump ipv4 --grpc unix:cradle/grpc --vrf 1

kubectl exec -n free5gc-zebra-test "$ZEBRA_POD" -c zebra -- \
  cradle dump ipv4 --grpc unix:cradle/grpc --vrf 2
```

Check UE tunnel and datapath manually:

```bash
UE_POD="$(kubectl get pod -n free5gc-zebra-test \
  -l component=ue \
  -o jsonpath='{.items[0].metadata.name}')"

kubectl exec -n free5gc-zebra-test "$UE_POD" -- ip -br addr show uesimtun0
kubectl exec -n free5gc-zebra-test "$UE_POD" -- \
  ping -I uesimtun0 -c 3 -W 2 10.201.60.1
kubectl exec -n free5gc-zebra-test "$UE_POD" -- \
  ping -I uesimtun0 -c 3 -W 2 8.8.8.8
```

Run iperf3 manually:

```bash
UE_IP="$(kubectl exec -n free5gc-zebra-test "$UE_POD" -- \
  sh -lc "ip -4 -o addr show uesimtun0 | awk '{print \$4}' | cut -d/ -f1")"

kubectl exec -n free5gc-zebra-test "$UE_POD" -- \
  sh -lc "command -v iperf3 >/dev/null || \
    (apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y iperf3)"

kubectl exec -n free5gc-zebra-test "$UE_POD" -- \
  iperf3 -c 10.201.60.1 -B "$UE_IP" -p 5201 -t 5
```

## Observed Lab Results

Current single-N6 host-device result with
`ghcr.io/infinitydon/zebra-sh:26.7.4-nightly20260714`:

```text
UE -> 10.201.60.1: 3/3 received, 0% loss
UE -> 8.8.8.8: 3/3 received, 0% loss
gtp_encap: increased
gtp_decap: increased
iperf3: TCP test did not complete
```

An earlier internal lab shape used two separate host-device-backed N6 legs and
reached native-style throughput, but that is not the recommended chart model
because it wastes physical interfaces for what should be one N6 network:

```text
UE -> 10.201.60.1: 3/3 received, 0% loss
UE -> 8.8.8.8: 3/3 received, 0% loss
iperf3 sender:   249 MBytes, 418 Mbits/sec
iperf3 receiver: 246 MBytes, 412 Mbits/sec
gtp_encap: 64514
gtp_decap: 191878
```

`ghcr.io/infinitydon/zebra-sh:v26.7.5` did not pass in this lab:

```text
UE -> 10.201.60.1: 0/3 received, 100% loss
gtp_encap: 0
gtp_decap: 0
```

## Build zebra-sh

A modular Dockerfile is included at `docker/zebra-sh/Dockerfile`.

Build a specific zebra-rs/cradle combination:

```bash
buildah bud \
  --build-arg ZEBRA_REF=v26.7.5 \
  --build-arg CRADLE_REF=a02afad54a22bcfa8339df2faad8e06d15d437c6 \
  -t ghcr.io/infinitydon/zebra-sh:v26.7.5 \
  -f docker/zebra-sh/Dockerfile .
```

Push it:

```bash
buildah push ghcr.io/infinitydon/zebra-sh:v26.7.5
```

Then test the image without changing chart defaults:

```bash
helm upgrade --install free5gc-zebra ./free5gc-zebra-stack \
  --namespace free5gc-zebra-test \
  --create-namespace \
  --set zebra.image.tag=v26.7.5 \
  --set zebra.dataplane.mode=hostDevice \
  --set stackSmokeTest.enabled=true \
  --no-hooks \
  --timeout 10m \
  --wait
```

