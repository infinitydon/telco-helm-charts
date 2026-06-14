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
- The `bridge`, `static`, and `tuning` CNI plugins
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

```powershell
kubectl port-forward -n open5gs-5g `
  service/open5gs-5g-open5gs-5g-webui 9999:9999
```

Open `http://localhost:9999` and sign in with username `admin` and password
`1423`. Change the default password after signing in. Subscribers created in
the WebUI are stored in the same MongoDB database as the automatically
provisioned lab subscriber.

Set `webui.enabled=false` to disable the WebUI. The service defaults to
`ClusterIP`; `webui.service.type` and `webui.service.nodePort` can expose it
as a NodePort when required.

## Verify

```powershell
kubectl logs -n open5gs-5g deploy/open5gs-5g-open5gs-5g-ue
kubectl exec -n open5gs-5g deploy/open5gs-5g-open5gs-5g-ue -- `
  ping -I uesimtun0 -c 5 10.54.0.100
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
