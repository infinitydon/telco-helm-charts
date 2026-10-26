# UERANSIM for Ella Core

This chart uses upstream [UERANSIM v3.3.0](https://github.com/aligungr/UERANSIM/releases/tag/v3.3.0), the latest stable release checked on October 26, 2026. The old free5gc image tag v4.2.2 was a different image/version line; the default now contains an unmodified build of the aligungr release at commit 6bf5a1a96aaef6ae8778b9d8b477ac6e2bbf8156.

One Pod runs the native gNB and UE, with N2/N3 on the Kubernetes pod network and RLS on loopback. A supervisor resolves the active Core Service, waits for Core readiness, and restarts both native processes when the active endpoint changes. This works with standalone and three-member Core HA. Readiness requires a UE tunnel address and live native processes. Recovery is reattachment, not uninterrupted sessions or a radio handover.

## Install

Prefer the optional component in the consolidated release:

```sh
helm upgrade --install ella ./ella-core/ella-stack -n ella-services-test \
  -f ./ella-core/ella-stack/examples/standalone-internet-ims-sms.yaml \
  --set core.admin.existingSecret=ella-lab-admin --set ueransim.enabled=true \
  --wait --wait-for-jobs --timeout 8m
```

The same option works with ha-internet.yaml, ha-internet-ims-sms.yaml and standalone-internet.yaml. The Core presets provision the chart's public lab subscriber. For an independently installed chart, provision that subscriber on Core first:

```sh
helm install ran ./ella-core/ueransim-5g-chart -n ella-services-test \
  --set core.host=ella-core-active --wait --timeout 5m
helm test ran -n ella-services-test
kubectl -n ella-services-test exec deployment/ran-ueransim -- \
  curl -fsS http://127.0.0.1:8080/healthz
```

Dependencies are vendored. Installation is Helm only; image building is optional. Linux nodes need SCTP and /dev/net/tun. The supplied image targets Linux/amd64 and includes Python and Linux IP, DNS, HTTP and packet-capture tools. The privileged Pod configures its own network namespace. Set nodeSelector, affinity and tolerations for your nodes.

## Configuration

- core.host defaults to ella-core-active. A bare Service name uses core.namespace (default: the release namespace) and core.clusterDomain; a full DNS name or IPv4 address is also accepted. Use the active headless NGAP Service to follow HA leadership.
- The default IMSI is 001018900000100, with the public fixture key/OPc in values.yaml. Set subscriber and session values to match Core. subscriber.existingSecret can reference a same-namespace Secret with key and opc fields; those values are then omitted from the ConfigMap.
- session defaults to internet, SST 1, SD 102030. Configure gnb.nci/idLength for a different radio identity. Independent instances need unique radio and subscriber identities.
- This is the native upstream internet UE/gNB simulator. IMS calls and NAS SMS testing continue to use the dedicated UE phone/Core tester components.

The runtime needs no Core admin token or Kubernetes API permissions. A ClusterIP health Service exposes status without SIM credentials. The default image is digest-pinned; its release tag is ghcr.io/infinitydon/ella-services-tester:ueransim-v3.3.0-tools1. images/Dockerfile reproduces the source build and includes the upstream AGPL license/source revision.

## Tests and migration

See [native simulator validation](../tests/simulators/README.md). Essential checks verify native registration/PDU state and ICMP, DNS and HTTPS bound to the UE address. The optional core-tester protocol suite shares fixture IMSIs: pause all UE phone/native simulator deployments before running it; the runner checks for conflicting owners.

Chart 2.0.0 replaces the former split gNB/UE deployments, node-specific Multus interfaces, numeric-member-ID discovery and API-token sidecars. Uninstall the old UERANSIM release before installing 2.0.0 to avoid duplicate ownership of its subscriber. Core does not need to be uninstalled. Replace old ellaCore/interface values with core.host/core.namespace; image is now a full immutable image reference. Old chart sources remain in Git history.
