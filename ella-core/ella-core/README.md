# Unified Ella Core chart

This is the single Core implementation used by [ella-stack](../ella-stack/README.md). Install ella-stack for the complete Core/IMS/SMSC/phone application. This base chart is also independently installable when only Core is required.

It replaces the old IP-based and FQDN HA chart variants, the ella-core-lab chart and the UI-only chart. topology=standalone runs one StatefulSet member; topology=ha runs three members with DNS-based Raft discovery, per-node PVCs and host anti-affinity. UI/API exposure, diagnostics and optional lab routing are part of the chart. No separate UI application or UI chart is needed.

Supply admin.existingSecret or admin.password before enabling bootstrap. The ordinary bootstrap Job initializes and joins Core through the v1.20 APIs; use Helm --wait --wait-for-jobs. The optional provisioning.enabled fixture creates public test subscribers and selected services, while normal deployments can provision their own users/subscribers through the Core UI/API.

In HA mode, the bootstrap Job assigns each member a persistent display name through the Core cluster API. By default the Cluster page shows `{pod}.{namespace}` (for example, `ella-ha-core-0.ella-ha-test`) and retains the generated short node ID beside it. Configure `memberDisplayName.enabled` or `memberDisplayName.template`; supported placeholders are `{pod}` and `{namespace}`, and rendered names must be no longer than 63 bytes. This is an operator-facing name; Core continues to generate and manage its internal node identity.

The base Core chart defaults N2/N3 to the Kubernetes pod network; the `ella-stack` umbrella enables a second Multus macvlan by default. For a base-chart install, set `network.n2n3.enabled=true` and provide `network.n2n3.coreInterfaceAddresses`, one address per Core replica. This address is assigned to `net2`, where Core binds both SCTP N2 and GTP-U N3. UE radios must attach to that same Layer 2 and reach the configured N2 address. Standalone assigns all configured Core N2/N3 interface addresses to its single Pod; HA assigns one per StatefulSet ordinal. N6 is a separate Multus macvlan (`net1`); configure its Core addresses under `network.n6.coreAddresses`. A shared macvlan N6 supports separate hosts. A node-local bridge is supported only for standalone deployments. All Core hosts require Linux 6.6+ for TCX. See values.yaml and the umbrella guide for static addressing, Service types, diagnostics, persistence and migration constraints.

Core controller permissions are restricted to reading and patching its two Services. It has no privileged network access. The optional lab N6 gateway is deployed separately as `n6Gateway`; it provides the sample N6 network's upstream route and Kubernetes egress. When enabled, bootstrap disables Ella Core NAT so the gateway can SNAT the internet UE pool once; without the gateway, Core's own NAT setting is left unchanged. Disable the lab gateway when N6 uses an external router. The bootstrap Job has no Kubernetes API permissions. Diagnostics provide a separate shell and Linux network tools alongside Core. Standalone or three-node Core HA does not imply that singleton IMS/SMSC, ongoing voice media or UE RAN sessions are automatically replicated.

Expose the Core API/UI with `service.type: ClusterIP`, `NodePort` or
`LoadBalancer`; set `service.nodePort` only for NodePort. Use the separate
umbrella chart for phone UIs, IMS/SMSC, the lab gateway and native radios.
When the gateway is enabled it owns UE-pool SNAT and routes IMS return traffic
through the elected Core member; the Core's own NAT is disabled by bootstrap.

The default image is an unmodified upstream c7cf03530e52 source build (v1.20.0 version string), pinned by digest. It includes the member-address reconciliation needed after Pod IP changes; this post-release snapshot is explicitly distinguished from the older official v1.20.0 image. See the umbrella image-provenance section and images/Dockerfile. Validated architecture: Linux/amd64.
