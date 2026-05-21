# Ella Core 5G — Helm Chart

Production-ready 5G core network for private networks, deployed as an HA Raft cluster on Kubernetes with Multus CNI and Whereabouts IPAM.

## Architecture

```
StatefulSet (OrderedReady, 3 replicas)
  ella-core-0  ──  N2:10.10.0.10  N3:10.10.1.10  N6:10.10.2.10  (node-1, initial leader)
  ella-core-1  ──  N2:10.10.0.11  N3:10.10.1.11  N6:10.10.2.11  (node-2, follower)
  ella-core-2  ──  N2:10.10.0.12  N3:10.10.1.12  N6:10.10.2.12  (node-3, follower)

  Raft (TCP 7000)  →  bound to Pod IP, advertised as pod FQDN (stable DNS)
  API  (HTTP 5002) →  bound to Pod IP  (security: not 0.0.0.0)
  N2   (SCTP 38412) → macvlan on host interface (gNB attachment)
  N3   (GTP-U)      → macvlan on host interface
  N6   (UPF data)   → macvlan on host interface
```

**Key design decision**: Raft uses pod FQDNs (`ella-core-{i}.ella-core.<ns>.svc.cluster.local`) for peer addresses and advertise-address. This is natively supported by Ella Core v1.10.1+ (see [discussion #1310](https://github.com/ellanetworks/core/discussions/1310)). Pod DNS names are maintained by Kubernetes and always resolve to the current Pod IP — no dependency on Whereabouts IP stability for clustering.

## Prerequisites

- Kubernetes cluster with Multus CNI installed
- Whereabouts CNI plugin (v0.9.3+) for IPAM
- Physical interfaces available on each node for N2, N3, N6 (macvlan bridge mode)
- Host interfaces must be up (no IP needed — macvlan handles addressing)

## Configuration

See `values.yaml` for all options. The critical sections:

| Section | Purpose |
|----------|---------|
| `multus.n2/n3/n6` | Host interface (`master`), subnet, and IP range for each plane |
| `admin` | Admin credentials for API access |
| `statefulset.replicas` | Cluster size (must be odd: 1, 3, or 5) |
| `service` | API exposure (`NodePort` or `ClusterIP`) |
| `ueransim.subscriber` | Test subscriber auto-provisioned by bootstrap job |

## Installation

```bash
# Install (creates namespace if needed)
helm install ella-core . \
  --namespace ella-core \
  --create-namespace \
  --kubeconfig <path-to-kubeconfig>

# Or with custom values
helm install ella-core . \
  --namespace ella-core \
  --create-namespace \
  --set multus.n2.master=ens20 \
  --set multus.n2.subnet=192.168.10.0/24 \
  --set multus.n2.rangeStart=192.168.10.100
```

## Post-Install: Bootstrap Job

A post-install hook runs automatically and handles:

1. **Admin user** — Creates admin account (idempotent)
2. **API tokens** — Creates `helm-automation` and `ueransim` tokens; stores ueransim token in Secret `ella-core-ueransim-api-token`
3. **Join tokens** — Mints Raft join tokens for follower nodes (stored in Secrets `ella-core-join-token-{2..N}`)
4. **Subscriber provisioning** — Creates the test subscriber from `ueransim.subscriber` (idempotent — skips if already exists)
5. **Per-node N6 config** — Pushes BGP/NAT configuration to each node

## Verifying the Cluster

```bash
# Check pod status
kubectl -n ella-core get pods

# Get cluster membership (via NodePort, default 30502)
TOKEN=$(curl -s -X POST http://<node-ip>:30502/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@ellanetworks.com","password":"changeme"}' | \
  grep -o '"token":"[^"]*"' | cut -d'"' -f4)

curl -s -H "Authorization: Bearer ${TOKEN}" \
  http://<node-ip>:30502/api/v1/cluster/members | python3 -m json.tool

# Check subscriber was provisioned
curl -s -H "Authorization: Bearer ${TOKEN}" \
  http://<node-ip>:30502/api/v1/subscribers | python3 -m json.tool
```

Expected: 3 nodes, all `voter` suffrage, one `isLeader: true`, all `drainState: active`. Raft addresses should show pod FQDNs (e.g. `ella-core-0.ella-core.ella-core.svc.cluster.local:7000`).

## Testing HA Failover

### Step-by-step failover test

**1. Check pre-failover state:**

```bash
NS=ella-core
API_NODE=$(kubectl get node -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')

# Get API token
TOKEN=$(curl -s -X POST http://${API_NODE}:30502/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@ellanetworks.com","password":"changeme"}' | \
  grep -o '"token":"[^"]*"' | cut -d'"' -f4)

# Check cluster members (all use FQDNs)
curl -s -H "Authorization: Bearer ${TOKEN}" \
  http://${API_NODE}:30502/api/v1/cluster/members | python3 -m json.tool

# Check leader service (always routes to leader)
curl -s http://${API_NODE}:30503/api/v1/status | python3 -m json.tool

# Note the current leader and leader service selector
kubectl -n ${NS} get svc ella-core-leader-api \
  -o jsonpath='{.spec.selector.statefulset\.kubernetes\.io/pod-name}'
```

**2. Trigger failover — delete the leader pod:**

```bash
# Find and delete the leader pod (use nodeId from step 1: pod = ella-core-{nodeId-1})
LEADER_POD=$(kubectl -n ${NS} get svc ella-core-leader-api \
  -o jsonpath='{.spec.selector.statefulset\.kubernetes\.io/pod-name}')
kubectl -n ${NS} delete pod ${LEADER_POD}
```

**3. Watch the failover — leader detection (sidecar):**

```bash
# Watch the leader-watcher detect the change (~10-15s)
kubectl -n ${NS} logs -f deploy/ella-core-leader-watcher --tail=50

# Watch pod recovery
kubectl -n ${NS} get pods -w
```

**4. Verify cluster recovered:**

```bash
# Cluster membership — leader should have moved to a different nodeId
curl -s -H "Authorization: Bearer ${TOKEN}" \
  http://${API_NODE}:30502/api/v1/cluster/members | python3 -m json.tool

# Leader service should route to the new leader
curl -s http://${API_NODE}:30503/api/v1/status | python3 -m json.tool

# Service selector should now point to the new leader pod
kubectl -n ${NS} get svc ella-core-leader-api \
  -o jsonpath='{.spec.selector.statefulset\.kubernetes\.io/pod-name}'
```

**5. Verify the restarted pod rejoined correctly:**

```bash
# All raftAddress values must be FQDNs, not IPs
curl -s -H "Authorization: Bearer ${TOKEN}" \
  http://${API_NODE}:30502/api/v1/cluster/members | \
  python3 -c "import sys,json;[print(m['raftAddress']) for m in json.load(sys.stdin)['result']]"
```

Expected: all three lines show FQDNs like `ella-core-X.ella-core.<ns>.svc.cluster.local:7000`. If any show raw IPs, the FQDN re-resolution failed and the cluster will break on the next pod restart.

### Full node replacement (simulates disk failure)

```bash
NS=ella-core

# 1. Scale down to 2 replicas (remove node-3)
kubectl -n ${NS} scale statefulset ella-core --replicas=2

# 2. Delete the PVC of the removed node
kubectl -n ${NS} delete pvc data-ella-core-2

# 3. Scale back up — node-3 gets a new PVC, fresh DB, re-joins via join token
kubectl -n ${NS} scale statefulset ella-core --replicas=3

# 4. Check cluster health
curl -s -H "Authorization: Bearer ${TOKEN}" \
  http://${API_NODE}:30502/api/v1/cluster/members | python3 -m json.tool
```

### One-liner: watch leader changes live

```bash
kubectl -n ella-core logs -f deploy/ella-core-leader-watcher
```

## RAN (gNB) Configuration

Point gNBs to all N2 IPs as an AMF set. With default values:
```
AMF 1: 10.10.0.10
AMF 2: 10.10.0.11
AMF 3: 10.10.0.12
```

NGAP port: `38412`. The UERANSIM chart handles this dynamically (see its README).

## Rolling Upgrade

```bash
# 1. Drain the last node
kubectl -n ella-core exec ella-core-2 -c core -- \
  curl -s -X POST http://localhost:5002/api/v1/cluster/members/3/drain

# 2. Update image
kubectl -n ella-core set image statefulset/ella-core \
  core=ghcr.io/ellanetworks/ella-core:v1.11.0

# 3. Resume
kubectl -n ella-core exec ella-core-2 -c core -- \
  curl -s -X POST http://localhost:5002/api/v1/cluster/members/3/resume
```

Pods restart one at a time (OrderedReady). The cluster remains available as long as a quorum of nodes is up.

## Troubleshooting

**Pod stuck in Pending**: Check Multus NADs exist (`kubectl -n ella-core get network-attachment-definitions`). Verify host interfaces are up on the node.

**Follower can't join**: Check the init container log (`kubectl -n ella-core logs ella-core-1 -c config-gen`). Verify the join token Secret exists (`kubectl -n ella-core get secret ella-core-join-token-2`). Re-run the bootstrap job if needed.

**Invalid token errors**: The pod's PVC may contain stale data. Delete the PVC and let the pod recreate it, then re-run the bootstrap job.
