# Unified Ella Core chart

This is the single Core implementation used by [ella-stack](../ella-stack/README.md). Install ella-stack for the complete Core/IMS/SMSC/phone application. This base chart is also independently installable when only Core is required.

It replaces the old IP-based and FQDN HA chart variants, the ella-core-lab chart and the UI-only chart. topology=standalone runs one StatefulSet member; topology=ha runs three members with DNS-based Raft discovery, per-node PVCs and host anti-affinity. UI/API exposure, diagnostics and optional lab routing are part of the chart. No separate UI application or UI chart is needed.

Supply admin.existingSecret or admin.password before enabling bootstrap. The ordinary bootstrap Job initializes and joins Core through the v1.20 APIs; use Helm --wait --wait-for-jobs. The optional provisioning.enabled fixture creates public test subscribers and selected services, while normal deployments can provision their own users/subscribers through the Core UI/API.

Core N3/N2 use the pod network and N6 uses the configured Multus attachment. A shared macvlan N6 supports separate hosts; a node-local bridge is supported only for standalone deployments. All Core hosts require Linux6.6+ for TCX. See values.yaml and the umbrella guide for networking, Services, diagnostics, persistence and migration constraints.

Core controller permissions are restricted to reading and patching its two Services. The bootstrap Job has no Kubernetes API permissions. Diagnostics provide a separate shell and Linux network tools alongside Core. Standalone or three-node Core HA does not imply that singleton IMS/SMSC, ongoing voice media or UE RAN sessions are automatically replicated.

The default image is an unmodified upstream c7cf03530e52 source build (v1.20.0 version string), pinned by digest. It includes the member-address reconciliation needed after Pod IP changes; this post-release snapshot is explicitly distinguished from the older official v1.20.0 image. See the umbrella image-provenance section and images/Dockerfile. Validated architecture: Linux/amd64.
