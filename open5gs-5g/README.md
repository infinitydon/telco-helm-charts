# Open5GS 5G SA Lab

This chart is a compact standalone 5G lab intended for learning. It deploys
MongoDB, the Open5GS 5G core, UERANSIM, and an N6 test endpoint.

## Components

- NRF, AUSF, UDM, UDR, PCF, NSSF, AMF, SMF, and UPF
- Open5GS WebUI for viewing and managing subscribers
- UERANSIM gNB and UE
- A subscriber created before the UE starts; WebUI does not replace it
- A data pod at `10.54.0.100` for the end-to-end ping
- A dedicated iperf3 server pod on N6 at `10.54.0.101`
- A private LibreSpeed server on N6 at `10.54.0.102` for browser-based tests
- An optional WebAssembly scenario runner sharing the UE network namespace

## Multus interfaces

The chart defaults to `macvlan` NADs in bridge mode with `enp8s19` as the
master interface. Override `multusDefaults` or an individual `multus` entry
when another CNI type, master interface, or mode is required. Static workload
addresses are assigned in pod annotations.

| Interface | Protocol or purpose | Subnet | Endpoints |
| --- | --- | --- | --- |
| RLS | Simulated UE radio link (UDP 4997) | `10.55.0.0/24` | gNB `.10`, UE `.20` |
| N2 | SCTP/NGAP | `10.51.0.0/24` | AMF `.2`, gNB `.10` |
| N3 | GTP-U | `10.52.0.0/24` | UPF `.2`, gNB `.10` |
| N4 | PFCP | `10.53.0.0/24` | SMF `.2`, UPF `.3` |
| N6 | User data | `10.54.0.0/24` | UPF `.2`, test pod `.100`, iperf3 `.101`, LibreSpeed `.102` |

The service-based interfaces between 5G core functions use ordinary
Kubernetes Services on the default pod network. SBI does not use Multus.
The UE-to-gNB simulated radio link has its own Multus network and does not
traverse a Kubernetes Service. A node-selected DaemonSet raises the kernel UDP
socket buffer defaults and maxima to tolerate tunneled traffic bursts. This is
a node-wide sysctl change and can be disabled with
`ueransim.nodeUdpTuning.enabled=false` when the node is managed externally.

## Prerequisites

- Kubernetes with Multus installed
- The `macvlan` and `static` CNI plugins
- Worker nodes with the `multusDefaults.master` interface, default `enp8s19`
- SCTP support on the worker node
- `kubectl` and Helm 3
- One worker matching `nodeSelector` in `values.yaml`

## Install

```powershell
$env:KUBECONFIG = "C:\path\to\kubeconfig"
helm upgrade --install open5gs-5g .\open5gs-5g `
  --namespace open5gs-5g --create-namespace --wait --timeout 5m
```

## WebUI

The WebUI uses the default Kubernetes pod network, like the 5G SBI, and does
not require a Multus interface. The existing automatic subscriber
provisioning remains enabled.

The service defaults to NodePort `30081`. Open
`http://<worker-node-ip>:30081` and sign in with username `admin` and password
`1423`. Change the default password after signing in. Subscribers created in
the WebUI are stored in the same MongoDB database as the automatically
provisioned lab subscriber.

Set `webui.enabled=false` to disable the WebUI. Override
`webui.service.type` or `webui.service.nodePort` when NodePort is unsuitable
or port `30081` is already allocated.

## UE phone browser

The UERANSIM UE pod includes a mobile-sized Chromium UI and a fail-closed
SOCKS5 proxy. The proxy waits for `uesimtun*` and binds its outbound sockets to
that interface, so browser traffic cannot silently use the pod's Kubernetes
interface.

The phone UI defaults to NodePort `30082`:

```text
https://<worker-node-ip>:30082
```

The browser container generates a self-signed certificate by default. Accept
the browser warning for the lab address, or provide a certificate trusted by
your clients. Chromium starts maximized in the portrait session with its URL
and navigation controls visible. It uses an Android mobile user-agent, touch
events, and the configured `390x844` viewport so responsive sites select their
mobile layouts. Its web traffic is forced through the UE tunnel. A chart-managed
responsive phone shell frames the embedded Selkies client and displays the
simulated 5G connection state without requiring a separate UI image.

On desktop-sized screens, the shell also shows a live UE telemetry rail. It
refreshes every three seconds and reports registration and PDU state,
active `uesimtun*` interface and address, live downlink/uplink rate, configured
gNB endpoint, PLMN, slice, DNN, masked IMSI, session uptime, and the latest
WASM test result. Rates are calculated from the tunnel interface byte counters
and automatically displayed as bps, Kbps, Mbps, or Gbps. The HTTPS phone
server proxies this telemetry internally from the runner; no additional public
service is required.

The proxy image is private by default. Create an image pull secret and set:

```yaml
imagePullSecrets:
  - name: ghcr-ueransim-phone
```

Set `phoneUi.enabled=false` to deploy the original command-line-only UE.

## Browser speed test

The chart deploys LibreSpeed directly on N6 with the fixed image tag
`ghcr.io/librespeed/speedtest:6.2.0-alpine`. Open the following URL inside the
phone UI or redroid Android browser:

```text
http://10.54.0.102:8080
```

The direct N6 address is intentional: requests travel through the Android
proxy or phone proxy, `uesimtun0`, UERANSIM gNB, Open5GS UPF, and then N6. The
service is ClusterIP only and is provided for Kubernetes health and
administration; using it from outside the UE is not an end-to-end 5G test.
LibreSpeed telemetry and client public-IP lookup are disabled by default, so
the course UI does not collect or display students' public addresses. Override
`addresses.librespeedN6` when `.102` is already allocated, or set
`librespeed.enabled=false` to omit the server.
The default lab profile uses one download stream and one upload stream with
eight-second phases. A 40 Mbit/s bidirectional lab-link ceiling is enforced at
the LibreSpeed N6 egress for downloads and at `uesimtun*` for uploads. This is
intentional: UERANSIM simulates both RLS and GTP-U in software and sustained
line-rate bursts can starve its radio heartbeat. Adjust the stream profile
under `librespeed.test` and the ceiling under `ueransim.trafficShaping`.

## UE WebAssembly scenarios

The optional `wasm-runner` sidecar executes fuel-limited WebAssembly modules
without replacing the UE, browser, or fail-closed proxy. It mounts the same
UERANSIM `ue.yaml` as the UE container and derives the IMSI, PLMN, gNB search
endpoint, DNN, and requested slice directly from that file. It discovers the
active interface matching `phoneUi.tunnelPattern` and obtains its address,
gateway, and counters from the live network namespace. This avoids duplicating
UE configuration in runner environment variables. It has its own web UI on
NodePort `30083`:

```text
http://<worker-node-ip>:30083
```

Run the built-in HTTP scenario there independently of the phone UI. Requests
are sent to the existing SOCKS5 proxy, whose outbound sockets are bound to
`uesimtun0`.

Built-in WASM scenarios include:

- `builtin-http`: HTTP status, redirect, response size, and server
- `builtin-tcp`: SOCKS-routed TCP connection time
- `builtin-tls`: TLS handshake time, protocol, cipher, and certificate subject
- `builtin-download`: selectable 10 MB, 100 MB, or 1 GB test file with
  live bytes, completion percentage, elapsed time, and calculated throughput
- `builtin-ping`: four ICMP probes bound directly to `uesimtun0`
- `builtin-traceroute`: up to 12 hops bound directly to `uesimtun0`
- `builtin-iperf3`: a three-second TCP throughput test to the dedicated N6 server

Each selection supplies an operational default target: Cloudflare trace for
HTTP, Cloudflare HTTPS for TCP and TLS, and Tele2's public speed-test files for
downloads. Tele2 provides sparse HTTP test files at the selectable 10 MB,
100 MB, and 1 GB sizes. The target remains editable.
Ping and traceroute default to `10.54.0.100`; iperf3 defaults to the dedicated
chart-managed server at `10.54.0.101:5201`.

The runner refuses to execute when `uesimtun0` is missing. The phone UI remains
available separately through NodePort `30082`. Override
`wasmRunner.service.type` or `wasmRunner.service.nodePort` when needed.

To add custom modules, create a ConfigMap containing files named `*.wasm` and
set `wasmRunner.existingScenarioConfigMap`. Modules must export `run`, export
their memory as `memory`, and may import:

```wat
(import "ue" "log" (func $log (param i32 i32)))
(import "ue" "http_get" (func $http_get (result i32)))
(import "ue" "tcp_connect" (func $tcp_connect (result i32)))
(import "ue" "tls_handshake" (func $tls_handshake (result i32)))
(import "ue" "download_test" (func $download_test (result i32)))
(import "ue" "ping_test" (func $ping_test (result i32)))
(import "ue" "traceroute_test" (func $traceroute_test (result i32)))
(import "ue" "iperf3_test" (func $iperf3_test (result i32)))
```

The HTTP target is selected in the runner page. Set
`wasmRunner.enabled=false` to omit only this sidecar.

## Full Android UE with redroid

Enable `redroid.enabled=true` to run Android in the same Kubernetes pod and
network namespace as the chart's UERANSIM UE. The UE creates `uesimtun0`; an
custom HTTP/HTTPS forward proxy resolves DNS through the UE and binds every
outbound socket directly to that interface. This uses the chart's existing
subscriber and does not create a second simulated UE.

The optional Binder DaemonSet is installed in `kube-system` and targets only
nodes labelled `redroid.io/enabled=true`:

```powershell
kubectl label node <worker> redroid.io/enabled=true
helm upgrade --install open5gs .\open5gs-5g -n open5gs --create-namespace `
  --set redroid.enabled=true `
  --set redroid.binder.enabled=true
```

All container images use versioned tags. ADB is exposed on NodePort `30555` by
default. Do not expose it to an untrusted network.

```powershell
winget install --id Google.PlatformTools --exact
winget install --id Genymobile.scrcpy --exact
adb connect <worker-node-ip>:30555
scrcpy -s <worker-node-ip>:30555
```

The Android model is `UERANSIM-5G-SA-Phone`. Its SystemUI 5G indicator is a
visual representation of the verified UERANSIM data path, not modem telemetry;
redroid does not provide a cellular modem or Android RIL.

Disable Android without removing the rest of the core with
`redroid.enabled=false`.

## Verify

```powershell
kubectl logs -n open5gs-5g deploy/open5gs-5g-open5gs-5g-ue
kubectl exec -n open5gs-5g deploy/open5gs-5g-open5gs-5g-ue -- `
  ping -I uesimtun0 -c 5 10.54.0.100
kubectl exec -n open5gs-5g deploy/open5gs-5g-open5gs-5g-ue `
  -c phone-proxy -- verify-ue-path
kubectl exec -n open5gs-5g deploy/open5gs-5g-open5gs-5g-ue `
  -c wasm-runner -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8090/api/status').read().decode())"
```

Expected results include successful registration, a PDU session with
`uesimtun0`, and zero packet loss. `scripts/test.ps1` automates these checks.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\open5gs-5g\scripts\test.ps1 -Namespace open5gs-5g
```

## Troubleshooting

```powershell
kubectl get pods -n open5gs-5g -o wide
kubectl get network-attachment-definitions -n open5gs-5g
kubectl logs -n open5gs-5g deploy/open5gs-5g-open5gs-5g-amf
kubectl logs -n open5gs-5g deploy/open5gs-5g-open5gs-5g-smf
```
