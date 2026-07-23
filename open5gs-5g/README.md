# Open5GS 5G SA Lab

This chart is a compact standalone 5G lab intended for learning. It deploys
MongoDB, the Open5GS 5G core, UERANSIM, and an N6 test endpoint.

## Components

- NRF, AUSF, UDM, UDR, PCF, NSSF, AMF, SMF, and UPF
- Open5GS WebUI for viewing and managing subscribers
- UERANSIM gNB and UE
- A subscriber created before the UE starts; WebUI does not replace it
- A data pod at `10.54.0.100` for the end-to-end ping
- An optional WebAssembly scenario runner sharing the UE network namespace

## Multus interfaces

The chart defaults to `macvlan` NADs in bridge mode with `enp8s19` as the
master interface. Override `multusDefaults` or an individual `multus` entry
when another CNI type, master interface, or mode is required. Static workload
addresses are assigned in pod annotations.

| Interface | Protocol or purpose | Subnet | Endpoints |
| --- | --- | --- | --- |
| N2 | SCTP/NGAP | `10.51.0.0/24` | AMF `.2`, gNB `.10` |
| N3 | GTP-U | `10.52.0.0/24` | UPF `.2`, gNB `.10` |
| N4 | PFCP | `10.53.0.0/24` | SMF `.2`, UPF `.3` |
| N6 | User data | `10.54.0.0/24` | UPF `.2`, test pod `.100` |

The service-based interfaces between 5G core functions use ordinary
Kubernetes Services on the default pod network. SBI does not use Multus.

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
and navigation controls visible. Its web traffic is forced through the UE
tunnel. A chart-managed responsive phone shell frames the embedded Selkies
client and displays the simulated 5G connection state without requiring a
separate UI image.

The proxy image is private by default. Create an image pull secret and set:

```yaml
imagePullSecrets:
  - name: ghcr-ueransim-phone
```

Set `phoneUi.enabled=false` to deploy the original command-line-only UE.

## UE WebAssembly scenarios

The optional `wasm-runner` sidecar executes fuel-limited WebAssembly modules
without replacing the UE, browser, or fail-closed proxy. Open
`http://127.0.0.1:8090` inside the simulated phone's Chromium browser to run
the built-in HTTP scenario. Requests are sent to the existing SOCKS5 proxy,
whose outbound sockets are bound to `uesimtun0`.

The runner refuses to execute when `uesimtun0` is missing. Its API listens
only on the pod loopback interface and is not published as another NodePort.
The phone UI remains available through NodePort `30082`.

To add custom modules, create a ConfigMap containing files named `*.wasm` and
set `wasmRunner.existingScenarioConfigMap`. Modules must export `run`, export
their memory as `memory`, and may import:

```wat
(import "ue" "log" (func $log (param i32 i32)))
(import "ue" "http_get" (func $http_get (result i32)))
```

The HTTP target is selected in the runner page. Set
`wasmRunner.enabled=false` to omit only this sidecar.

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
