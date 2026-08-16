# Open5GS two-UE simulated VoNR

This Helm chart deploys an Open5GS standalone 5G core, one UERANSIM gNB,
two separately provisioned UERANSIM UEs (`1001` and `1002`), SIPp endpoints,
and a small Kamailio registration/routing proxy. The core and simulator are
adapted from `infinitydon/telco-helm-charts/open5gs-5g`; the Kamailio image is
built on the OAM VM from `herlesupreeth/docker_open5gs` commit
`7464234a9f79718df1836d24d688be745a5272d1`.

This is a repeatable VoNR signaling simulation, not a production IMS. Both
UEs establish 5G PDU sessions, register SIP contacts through those tunnels,
and complete an INVITE/180/200/ACK/BYE dialog through the N6-side proxy. SDP
offers PCMU, but the acceptance test does not generate or measure RTP media.

## Address plan

Every data-plane network consumes a non-overlapping `/28` carved from an
existing lab `/24`:

| Network | Subnet |
| --- | --- |
| N2 | `10.51.0.32/28` |
| N3 | `10.52.0.32/28` |
| N4 | `10.53.0.32/28` |
| N6 / SIP proxy | `10.54.0.32/28` |
| UERANSIM radio simulation | `10.55.0.32/28` |
| UE DNN pool | `10.46.0.0/28` |

All container images have explicit, immutable version tags; `latest` is not
used. The GHCR images are private, so create the referenced pull secret before
installing (never commit the token):

```bash
kubectl create namespace vonr
kubectl -n vonr create secret docker-registry ghcr \
  --docker-server=ghcr.io --docker-username=YOUR_GITHUB_USER \
  --docker-password="$GITHUB_TOKEN"
```

## Install from the OAM VM

```bash
export KUBECONFIG=/home/ubuntu/kubeconfig
cd /home/ubuntu/work/telco-helm-charts
helm lint ./open5gs-vonr
helm upgrade --install vonr ./open5gs-vonr -n vonr --create-namespace \
  --set 'imagePullSecrets[0].name=ghcr' --wait --timeout 15m
./open5gs-vonr/scripts/test.sh
```

The workloads are pinned to MicroK8s workers because the Multus macvlan
master (`enp6s19`) exists there. The acceptance script also rejects omitted
image tags and `latest`, waits for the deployments, confirms both PDU sessions,
registers both SIP users, and places one call from `1001` to `1002`.
