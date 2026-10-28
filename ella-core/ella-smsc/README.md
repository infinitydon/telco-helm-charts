# Ella SMSC Helm chart

Deploys the upstream beta image with one replica, a persistent SQLite volume, API probes and a Helm API smoke test. The Recreate strategy prevents two writers opening the same database. No HA claim is made.

```sh
helm upgrade --install smsc ./ella-smsc --namespace ella-services --create-namespace
helm test smsc --namespace ella-services
kubectl port-forward --namespace ella-services svc/smsc-ella-smsc 5010:5010
```

The image is pinned to an upstream Git SHA tag. Override image.repository/tag to select a different build. The container runs the application directly, bypassing the image's Pebble service wrapper.

By default an init container substitutes the pod IP for diameter.address. Explicit addresses must exist on an interface in the pod. podAnnotations accepts existing Multus network attachments; hostNetwork is optional. A headless Diameter service provides endpoint discovery. Peers configured with literal pod IPs must be updated after a pod IP changes; use fixed Multus addresses for durable protocol endpoints. Do not advertise a ClusterIP as the bind address.

The consolidated ella-stack chart attaches SMSC to the Core N6 Multus network and assigns the stable address in global.network.n6.smscAddress (default 10.6.0.6), after the configurable N6 Core addresses, gateway and IMS address. It configures the SMSC Diameter listener and Core SMSC peer with that address. Keep it unique and in the same subnet as global.network.n6.coreAddresses. The SMSC HTTP API remains reachable through its ClusterIP Service; its Diameter peer uses the direct Multus address.

SMSC needs kernel SCTP support and routable SCTP port 3868. In the SMSC API/UI configure MCC/MNC, numbering, service centre and delivery policy. In Core, enable Diameter, add an SMSC peer using the SMSC's actual address and Diameter identity, configure the SMS number and give subscribers MSISDNs.

This SMSC handles SGd/S6c and SMS over NAS. The linked UERANSIM IMS fork's SIP MESSAGE support does not exercise this interface. The lab uses Ella Core's existing NAS SMS scenario runner instead.

Persistence defaults to a 1Gi ReadWriteOnce PVC using the default StorageClass. Set persistence.existingClaim to reuse storage, or persistence.enabled=false for disposable testing. Back up SQLite before deleting storage. The chart does not delete external claims. API readiness checks process availability, not a connected Core or successful subscriber traffic.

These upstream beta APIs have no authentication. Keep their Services internal and use port forwarding or a protected management network. Only the API Service type is configurable; protocol endpoints stay direct.

See [the integration lab](../tests/services/README.md) for provisioning and validation. Values expose node placement, resources, image pull secrets, additional volumes and init containers.

Upstream: [ellanetworks/smsc](https://github.com/ellanetworks/smsc).
