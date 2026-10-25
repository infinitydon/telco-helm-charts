# Ella IMS Helm chart

Deploys the upstream beta image with one replica, a persistent SQLite volume, API probes and a Helm API smoke test. The Recreate strategy prevents two writers opening the same database. No HA claim is made.

```sh
helm upgrade --install ims ./ella-ims --namespace ella-services --create-namespace
helm test ims --namespace ella-services
kubectl port-forward --namespace ella-services svc/ims-ella-ims 5020:5020
```

The image is pinned to an upstream Git SHA tag. Override image.repository/tag to select a different build. The container runs the application directly, bypassing the image's Pebble service wrapper.

By default an init container substitutes the pod IP for diameter.address and sip.addresses. Explicit addresses must exist on an interface in the pod. podAnnotations accepts existing Multus network attachments; hostNetwork is optional. A headless Diameter service provides endpoint discovery. Peers configured with literal pod IPs must be updated after a pod IP changes; use fixed Multus addresses for durable protocol endpoints. Do not advertise a ClusterIP as the bind address.

IMS needs NET_ADMIN for kernel XFRM/IPsec. Allow SCTP Diameter, SIP UDP/TCP, the configured protected SIP ports and ESP (IP protocol 50) on the direct IMS address. A normal Kubernetes Service cannot proxy ESP. Route the UE IMS address pool back through Core's N6 address. The headless SIP service discovers endpoints; it does not configure that routing.

Use the IMS API/UI to configure MCC/MNC, numbering, Core's Diameter peer (applications cx/rx), Cx/Rx realms and the rx policy function. In Core, enable Diameter, provision the ims DNN and policies, set P-CSCF addresses and give subscribers MSISDNs. Optional n5 accepts the native upstream N5 config; use extraVolumes/extraVolumeMounts for TLS files.

Persistence defaults to a 1Gi ReadWriteOnce PVC using the default StorageClass. Set persistence.existingClaim to reuse storage, or persistence.enabled=false for disposable testing. Back up SQLite before deleting storage. The chart does not delete external claims. API readiness checks process availability, not a connected Core or successful subscriber traffic.

These upstream beta APIs have no authentication. Keep their Services internal and use port forwarding or a protected management network. Only the API Service type is configurable; protocol endpoints stay direct.

See [the integration lab](../tests/services/README.md) for provisioning and validation. Values expose node placement, resources, image pull secrets, additional volumes and init containers.

Upstream: [ellanetworks/ims](https://github.com/ellanetworks/ims).
