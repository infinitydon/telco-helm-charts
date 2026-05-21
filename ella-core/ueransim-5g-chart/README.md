# UERANSIM 5G — Helm Chart

5G UE/gNB simulator for end-to-end testing of the Ella Core private network. Deploys a separate gNB and UE with dynamic AMF leader discovery.

## Architecture

```
Deployment: ueransim-gnb  (1 replica)
  ┌─────────────────────────────────────────────────────────┐
  │ Init: config-gen (alpine, runs once)                     │
  │   1. Reads API token from mounted Secret file            │
  │   2. Queries /api/v1/cluster/members                    │
  │   3. Extracts leader N2 IP from raftAddress (strips port)│
  │   4. Reads local N2/N3 IPs from Multus interfaces        │
  │   5. Generates gnb.yaml with leader as AMF               │
  │   6. Writes initial leader IP to /shared/leader-ip       │
  │                                                          │
  │ Sidecar: leader-watch (alpine, runs continuously)        │
  │   - Polls /api/v1/cluster/members every 10s              │
  │   - Extracts leader N2 IP from raftAddress               │
  │   - Writes current leader IP to /shared/leader-ip        │
  │                                                          │
  │ Main: gnb (bash wrapper → nr-gnb)                        │
  │   - Wrapper monitors /shared/leader-ip for changes       │
  │   - On leader change: sed-updates gnb.yaml + restarts    │
  │     nr-gnb automatically (no pod restart needed)         │
  │   - ngapIp → local N2 IP (macvlan)                       │
  │   - gtpIp  → local N3 IP (macvlan)                       │
  │   - AMF    → leader N2 IP:38412                          │
  │   - RLS    → UDP 4997 (UE connection)                    │
  └─────────────────────────────────────────────────────────┘

Deployment: ueransim-ue  (1 replica)
  ┌────────────────────────────────────────────┐
  │ Main: nr-ue                                 │
  │   gnbSearchList → [ueransim-gnb]           │
  │   Connects to gNB over RLS (UDP 4997)      │
  │   PDU session via gNB → Ella Core          │
  └────────────────────────────────────────────┘

Service: ueransim-gnb (ClusterIP, UDP 4997)
  Internal RLS link between UE → gNB

Volumes (shared via emptyDir):
  /shared       — leader-ip file (written by sidecar, read by wrapper)
  /config       — gnb.yaml (written by init, updated by wrapper)
  /tmp/api-token — API token (mounted from Secret)
```

**Automatic leader failover**: The sidecar polls the Ella Core API every 10 seconds. When the leader changes (HA failover), the sidecar writes the new leader's N2 IP to `/shared/leader-ip`. The gNB wrapper detects the change within 5 seconds and restarts `nr-gnb` with the updated AMF address — no pod restart or manual intervention needed. Total failover time: ~15 seconds (sidecar poll + wrapper poll + gNB restart).

## Prerequisites

- **Ella Core chart deployed** and healthy in the `ella-core` namespace
- **Multus CNI** and **Whereabouts** configured (same cluster as Ella Core)
- **Host interfaces** available for N2 and N3 macvlan attachment
- **API token secret** created by the Ella Core bootstrap job (`ella-core-ueransim-api-token`)
- **No RBAC required** — API token is mounted as a file, all API calls use curl directly

## Configuration

See `values.yaml` for all options:

| Section | Purpose |
|----------|---------|
| `image` | UERANSIM container image (`free5gc/ueransim:v4.2.2`) |
| `ellaCore` | Connection to Ella Core: namespace, service name, API port, token secret |
| `gnb` | gNB parameters: NCI, TAC, slices |
| `subscriber` | UE credentials: SUPI, MCC/MNC, key, OPC, AMF |
| `interfaces.n2/n3` | Host interface and IP for gNB radio/user-plane attachment |

### IP Planning

The gNB needs its own N2 and N3 IPs — these must be in the **same subnets** as the Ella Core N2/N3 networks but **different addresses** from the core nodes.

Default allocation:
```
Ella Core:  N2 10.10.0.10-12,  N3 10.10.1.10-12
UERANSIM:   N2 10.10.0.20,     N3 10.10.1.20
```

## Installation

```bash
# Deploy in the same namespace as Ella Core (recommended)
helm install ueransim /home/ubuntu/ueransim-5g-chart \
  --namespace ella-core \
  --kubeconfig <path-to-kubeconfig>

# Or in its own namespace
helm install ueransim /home/ubuntu/ueransim-5g-chart \
  --namespace ueransim \
  --create-namespace \
  --set ellaCore.namespace=ella-core
```

The chart requires cross-namespace access if deployed outside `ella-core`. The RBAC is scoped to the specific pod and secret resources it needs.

## How It Connects to Ella Core

1. **Init container** runs once before gNB starts:
   - Reads API token from mounted Secret file (`/tmp/api-token/token`)
   - Calls `GET /api/v1/cluster/members` to find the leader
   - Extracts the leader's N2 IP from `raftAddress` (e.g. `10.10.0.10:7000` → `10.10.0.10`)
   - Discovers local N2/N3 IPs from Multus interfaces
   - Generates initial `/config/gnb.yaml` and writes leader IP to `/shared/leader-ip`

2. **Sidecar** runs continuously alongside gNB:
   - Polls `GET /api/v1/cluster/members` every 10 seconds
   - Detects leader changes and updates `/shared/leader-ip`

3. **gNB wrapper** manages the gNB process:
   - Reads `/shared/leader-ip`, starts `nr-gnb` with current leader as AMF
   - Monitors for leader IP changes every 5 seconds
   - On change: sed-updates `/config/gnb.yaml` AMF address, kills old `nr-gnb`, starts new one

4. **UE** connects to gNB over the internal RLS link (UDP 4997) with pre-configured subscriber credentials.

## Handling Leader Changes

Leader changes are handled **automatically** — no manual intervention needed:

1. Ella Core leader changes (failover, rolling upgrade)
2. Sidecar detects new leader within 10 seconds (next poll cycle)
3. Wrapper detects updated `/shared/leader-ip` within 5 seconds
4. Wrapper kills old `nr-gnb`, starts new one with updated AMF address
5. gNB re-establishes NGAP connection to new leader

Total recovery time: ~15-20 seconds.

To observe the failover in action:

```bash
# Watch sidecar logs for leader detection
kubectl -n ella-core logs deployment/ueransim-gnb -c leader-watch -f

# Watch gNB wrapper for restart events
kubectl -n ella-core logs deployment/ueransim-gnb -c gnb -f
```

## Verification

```bash
# Check deployments are running
kubectl -n ella-core get deployments

# Check gNB init logs — shows leader discovery
kubectl -n ella-core logs deployment/ueransim-gnb -c config-gen

# Check gNB connected successfully
kubectl -n ella-core logs deployment/ueransim-gnb -c gnb | grep -i "ngsetup\|amf"

# Check UE registration status via Ella Core API
TOKEN=$(curl -s -X POST http://<node-ip>:30502/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@ellanetworks.com","password":"changeme"}' | \
  grep -o '"token":"[^"]*"' | cut -d'"' -f4)

curl -s -H "Authorization: Bearer ${TOKEN}" \
  http://<node-ip>:30502/api/v1/subscribers/001010000000001 | python3 -m json.tool
```

A successful setup shows the subscriber with `"registered": true` and a PDU session established.

## Troubleshooting

**Init container can't read token**: Verify the Secret exists — `kubectl -n ella-core get secret ella-core-ueransim-api-token`. If missing, the Ella Core bootstrap job may not have run; re-install or re-run the bootstrap hook.

**Sidecar can't reach API**: Check `kubectl -n ella-core logs deployment/ueransim-gnb -c leader-watch`. Verify the `ella-core-api` service exists in the target namespace.

**gNB can't reach AMF**: Verify N2 IPs are in the same subnet and the host interfaces are on the same L2 domain. Check `kubectl -n ella-core logs deployment/ueransim-gnb -c gnb`.

**gNB not restarting on leader change**: Check that the wrapper script is running: `kubectl -n ella-core logs deployment/ueransim-gnb -c gnb`. Verify the sidecar is updating `/shared/leader-ip`: `kubectl -n ella-core logs deployment/ueransim-gnb -c leader-watch`.

**UE not registering**: Verify the subscriber credentials in `values.yaml` match what was provisioned in Ella Core. The subscriber must exist before the UE can attach.
