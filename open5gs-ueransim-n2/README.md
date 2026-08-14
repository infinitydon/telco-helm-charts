# Open5GS + UERANSIM + zero-trust N2

This chart installs a minimal Open5GS 5G SA core, one UERANSIM gNB, one UERANSIM UE, Multus networks, a `gnb_proxy` sidecar, and a two-replica N2 middleware tier.

The N2 path is:

`UERANSIM gNB -> localhost SCTP -> gnb_proxy -> secure-n2 Multus VIP (QUIC/mTLS) -> active middleware -> core-n2 Multus (SCTP) -> Open5GS AMF`

The middleware is a two-replica StatefulSet with required pod anti-affinity across two `workload-type=general` workers. A pinned kube-vip `v1.2.2` sidecar elects one replica and makes `10.61.0.1` authoritative on its `secure-n2` interface. The proxy always targets that VIP.

The tunnel implementation is built from the upstream `DBGR18/N2-SCTP-middleware` commit `3306db6301a9b88da8176a9b4185edd722f33c10`. That upstream repository did not declare a license when this chart was produced; keep the resulting image private unless the author supplies redistribution terms.

## Prerequisites

- Kubernetes with Multus and the NetworkAttachmentDefinition CRD
- A Multus-compatible parent interface on every eligible node
- Helm 3
- The parent `10.61.0.0/24` is divided into six non-overlapping `/28` Multus networks: `secure-n2`, `core-n2`, `n3`, `n4`, `n6`, and `rls`

## Install

Review `multusDefaults.master`, the subnets, static addresses, and worker label, then run:

```console
helm upgrade --install n2lab . --namespace n2lab --create-namespace --wait --timeout 15m
```

The chart creates its PKI only on the first install and preserves it on upgrades using Helm's `lookup`. For GitOps rendering, create an equivalent Secret separately and set `n2Tunnel.pki.existingSecret`.

## Validate

```console
kubectl -n n2lab get pods -o wide
kubectl -n n2lab logs deploy/n2lab-open5gs-ueransim-n2-gnb -c gnb-proxy
kubectl -n n2lab logs statefulset/n2lab-open5gs-ueransim-n2-middleware -c middleware
kubectl -n n2lab get lease plndr-cp-lock
kubectl -n n2lab logs deploy/n2lab-open5gs-ueransim-n2-amf
kubectl -n n2lab logs deploy/n2lab-open5gs-ueransim-n2-ue -c ue
```

Expected messages include `QUIC mTLS session established`, `gNB QUIC connected`, `gNB-N2 accepted`, and successful UE registration/session establishment.

## Measured middleware VIP failure behavior

An active-session failure test was performed on the `n2lab` deployment:

1. The elected VIP leader (`middleware-1`, `10.61.0.20` on `core-n2`) was deleted at `14:22:11Z`.
2. The Lease moved to `middleware-0`; the proxy detected QUIC loss, reconnected to the unchanged `10.61.0.1` VIP, and replayed its cached NG Setup Request at `14:22:23Z`.
3. Open5GS accepted the replacement N2 association from `10.61.0.19` and restored its gNB count to one.
4. UERANSIM logged a successful NG Setup Response at `14:22:23Z`.
5. The gNB pod UID remained `35729797-caed-4251-967d-54c5dfc7ee65`; neither UERANSIM nor its SCTP association to the local proxy was restarted.

Observed recovery was about 12 seconds with a 10-second QUIC idle timeout and 5-second VIP lease. This restores N2 signaling without restarting the gNB pod; messages in flight during the outage are not transactionally replayed. The proxy modification specifically caches and replays NG Setup, not arbitrary UE signaling.
