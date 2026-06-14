# Open5GS 4G Lab

This chart is a compact LTE/EPC lab intended for learning. It deploys MongoDB,
Open5GS, an srsRAN eNB and UE, and an SGi test endpoint.

## Components

- HSS, MME, SGW-C, SGW-U, SMF/PGW-C, UPF/PGW-U, and PCRF
- Open5GS WebUI for viewing and managing subscribers
- srsRAN 4G eNB and UE using ZeroMQ as the virtual radio
- A subscriber created before the simulator starts; WebUI does not replace it
- A data pod at `10.55.0.100` for the end-to-end ping

## Multus interfaces

| Interface | Protocol or purpose | Subnet | Endpoints |
| --- | --- | --- | --- |
| S1-MME | SCTP/S1AP | `10.41.0.0/24` | MME `.2`, eNB `.10` |
| S11 | GTPv2-C | `10.42.0.0/24` | MME `.2`, SGW-C `.3` |
| S5-C | GTPv2-C | `10.43.0.0/24` | SGW-C `.2`, SMF `.3` |
| S6a | Diameter | `10.44.0.0/24` | MME `.2`, HSS `.3` |
| Gx | Diameter | `10.45.0.0/24` | SMF `.2`, PCRF `.3` |
| Sxa | PFCP | `10.47.0.0/24` | SGW-C `.2`, SGW-U `.3` |
| Sxb | PFCP | `10.48.0.0/24` | SMF `.2`, UPF `.3` |
| S1-U | GTP-U | `10.49.0.0/24` | SGW-U `.2`, eNB `.10` |
| S5-U | GTP-U | `10.50.0.0/24` | SGW-U `.2`, UPF `.3` |
| SGi | User data | `10.55.0.0/24` | UPF `.2`, test pod `.100` |

Open5GS advertises one SGW-U GTP-U endpoint. The chart adds a host route at
the UPF so traffic for that endpoint traverses the dedicated S5-U Multus
network while the eNB uses the dedicated S1-U network.

## Prerequisites

- Kubernetes with Multus installed
- The `bridge`, `static`, and `tuning` CNI plugins
- SCTP support on the worker node
- `kubectl` and Helm 3
- One worker matching `nodeSelector` in `values.yaml`

## Install

```powershell
$env:KUBECONFIG = "C:\path\to\kubeconfig"
helm upgrade --install open5gs-4g .\open5gs-4g `
  --namespace open5gs-4g --create-namespace --wait --timeout 5m
```

Change `nodeSelector` or subscriber values with a values file when needed.
The included subscriber credentials are lab-only defaults.

## WebUI

The WebUI uses the default Kubernetes pod network and does not require a
Multus interface. The existing automatic subscriber provisioning remains
enabled.

```powershell
kubectl port-forward -n open5gs-4g `
  service/open5gs-4g-open5gs-4g-webui 9999:9999
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
kubectl logs -n open5gs-4g deploy/open5gs-4g-open5gs-4g-simulator -c ue
kubectl exec -n open5gs-4g deploy/open5gs-4g-open5gs-4g-simulator -c ue -- `
  ping -I tun_srsue -c 5 10.55.0.100
```

Expected results include `Network attach successful`, UE address
`10.46.0.2`, and zero packet loss. `scripts/test.ps1` automates these checks.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\open5gs-4g\scripts\test.ps1 -Namespace open5gs-4g
```

## Troubleshooting

```powershell
kubectl get pods -n open5gs-4g -o wide
kubectl get network-attachment-definitions -n open5gs-4g
kubectl logs -n open5gs-4g deploy/open5gs-4g-open5gs-4g-mme
kubectl logs -n open5gs-4g deploy/open5gs-4g-open5gs-4g-smf
```
