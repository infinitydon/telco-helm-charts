# Open5GS 5G SA Lab

This chart is a compact standalone 5G lab intended for learning. It deploys
MongoDB, the Open5GS 5G core, UERANSIM, and an N6 test endpoint.

## Components

- NRF, AUSF, UDM, UDR, PCF, NSSF, AMF, SMF, and UPF
- Open5GS WebUI for viewing and managing subscribers
- UERANSIM gNB and UE
- A subscriber created before the UE starts; WebUI does not replace it
- A data pod at `10.54.0.100` for the end-to-end ping

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
http://<worker-node-ip>:30082
```

The proxy image is private by default. Create an image pull secret and set:

```yaml
imagePullSecrets:
  - name: ghcr-ueransim-phone
```

Set `phoneUi.enabled=false` to deploy the original command-line-only UE.

## Verify

```powershell
kubectl logs -n open5gs-5g deploy/open5gs-5g-open5gs-5g-ue
kubectl exec -n open5gs-5g deploy/open5gs-5g-open5gs-5g-ue -- `
  ping -I uesimtun0 -c 5 10.54.0.100
kubectl exec -n open5gs-5g deploy/open5gs-5g-open5gs-5g-ue `
  -c phone-proxy -- verify-ue-path
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
