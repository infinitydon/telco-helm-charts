# Open5GS + UERANSIM + zero-trust N2

This chart installs a minimal Open5GS 5G SA core, one UERANSIM gNB, one UERANSIM UE, Multus networks, a `gnb_proxy` sidecar, and a two-replica N2 middleware tier.

The N2 path is:

`UERANSIM gNB -> localhost SCTP -> gnb_proxy -> QUIC/mTLS Service -> HA middleware -> SCTP -> Open5GS AMF`

The tunnel implementation is built from the upstream `DBGR18/N2-SCTP-middleware` commit `3306db6301a9b88da8176a9b4185edd722f33c10`. That upstream repository did not declare a license when this chart was produced; keep the resulting image private unless the author supplies redistribution terms.

## Prerequisites

- Kubernetes with Multus and the NetworkAttachmentDefinition CRD
- A Multus-compatible parent interface on every eligible node
- Helm 3
- The five configured Multus subnets must not overlap existing lab networks

## Install

Review `multusDefaults.master`, the subnets, static addresses, and `n2Tunnel.service.clusterIP`, then run:

```console
helm upgrade --install n2lab . --namespace n2lab --create-namespace --wait --timeout 15m
```

The chart creates its PKI only on the first install and preserves it on upgrades using Helm's `lookup`. For GitOps rendering, create an equivalent Secret separately and set `n2Tunnel.pki.existingSecret`.

## Validate

```console
kubectl -n n2lab get pods -o wide
kubectl -n n2lab logs deploy/n2lab-open5gs-ueransim-n2-gnb -c gnb-proxy
kubectl -n n2lab logs deploy/n2lab-open5gs-ueransim-n2-middleware
kubectl -n n2lab logs deploy/n2lab-open5gs-ueransim-n2-amf
kubectl -n n2lab logs deploy/n2lab-open5gs-ueransim-n2-ue -c ue
```

Expected messages include `QUIC mTLS session established`, `gNB QUIC connected`, `gNB-N2 accepted`, and successful UE registration/session establishment.

## Measured middleware failure behavior

An active-session failure test was performed on the `n2lab` deployment:

1. The middleware pod holding the live QUIC association was deleted.
2. Kubernetes kept the middleware Service available and immediately created a replacement replica.
3. Open5GS logged removal of the gNB N2 connection.
4. The existing `gnb_proxy` did not reconnect the interrupted association automatically.
5. Restarting UERANSIM gNB caused the sidecar to accept a new SCTP association, establish a new QUIC mTLS session through the healthy middleware Service, and complete NG Setup successfully.

The middleware Deployment is highly available for new associations, but this upstream proxy implementation does not provide transparent failover for an already-established N2 association.
