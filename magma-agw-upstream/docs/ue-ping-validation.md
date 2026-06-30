# UE Ping Validation Runbook

This runbook captures the requirements that were necessary for UERANSIM UE
internet ICMP to work through the containerized Magma 1.9 AGW chart.

The validated dataplane test was:

```sh
kubectl -n magma-agw exec deploy/agwc-ueransim-ue -- \
  ping -I uesimtun0 -c 4 -W 2 8.8.8.8
```

The working result was `4 packets transmitted, 4 received, 0% packet loss`.

The throughput smoke test command is:

```sh
kubectl -n magma-agw exec deploy/agwc-ueransim-ue -- \
  iperf3 -c <iperf3-server-node-ip> -B <ue-tunnel-ip> -t 10
```

In the lab, this command did not work through the clean Magma enforcement path.
It succeeded only after a temporary diagnostic OVS flow bypass was added for
TCP/5201. That proved the refreshed UERANSIM image and host-networked iperf3
server were functional, with `708 MBytes` transferred at `594 Mbits/sec` sender
and `591 Mbits/sec` receiver. Do not treat that bypass as a production
requirement or chart behavior. A normal deployment still needs the TCP/5201
Magma enforcement issue resolved.

## Validated Versions

Working:

```text
Magma AGW: upstream 1.9.0 containerized chart
UERANSIM: ghcr.io/infinitydon/ueransim:v3.2.4-x86-64
AGW OS: Ubuntu 20.04.6 LTS
AGW kernel: 5.4.0-216-generic
OVS: 2.15.4-10-magma with Magma GTP/QFI datapath support
```

Not validated for UE ping:

```text
ghcr.io/infinitydon/ueransim:v3.3.0-x86-64
```

The v3.3.0 image pulled and ran, and registration/PDU establishment succeeded,
but ICMP sourced from `uesimtun0` failed. Keep v3.2.4 as the default until that
datapath behavior is isolated.

## Required Topology

AGW and UERANSIM must run on separate Kubernetes worker nodes.

Validated lab topology:

```text
AGW node:      ebpf-bng-node-03-ubuntu-focal, 192.168.88.156
UERANSIM node: ebpf-bng-node-01
AGW N2 IP:     10.88.99.142/24 on magma-n2
AGW N3 IP:     192.168.60.142/24 on magma-n3
gNB N2 IP:     10.88.99.150/24
gNB N3 IP:     192.168.60.150/24
UE pool:       192.168.128.0/24
```

Node labels:

```sh
kubectl label node <agw-node> magma.io/agw-node=true --overwrite
kubectl label node <ueransim-node> magma.io/ueransim-node=true --overwrite
```

UERANSIM should not be scheduled on the AGW node.

## Required Provisioning

For full-stack deployments, subscriber provisioning must come from Orc8r/NMS,
not from the AGW-local `subscriberdb` job.

Required NMS/Orc8r objects:

- network created
- gateway registered and checked in
- APN/DNN created, default `magma.ipv4`
- subscriber `IMSI001010000000001` created with matching key/OPC
- active policy assigned, validated with `default_rule_1`

AGW-side check:

```sh
kubectl -n magma-agw exec deploy/policydb -- policydb_cli.py dump_data
```

The UE must show an active Orc8r-streamed policy, for example:

```text
global_policies: "default_rule_1"
```

If the UE has no active policy, registration/PDU setup can succeed while
dataplane forwarding still fails.

## Required AGW Node Prep

`nodePrep.enabled=true` must complete successfully on the selected AGW node.
The prep is idempotent and should verify or create:

- Open vSwitch services
- `openvswitch`, `gtp`, and `nf_conntrack` kernel modules
- `gtp_br0`
- `uplink_br0`
- patch ports between `gtp_br0` and `uplink_br0`
- `magma-n2`
- `magma-n3`
- `magma-sgi`
- `mtr0`
- `ipfix0`
- `li_port`
- IP forwarding
- UE subnet egress NAT

For real dataplane validation, use a node where Magma OVS can create a GTP-U
port. The chart probes this by creating a temporary OVS `type=gtpu` interface.
Set this when you want dataplane failures to stop the install:

```yaml
nodePrep:
  requireMagmaOvsKmod: true
```

The tested working AGW node used Ubuntu 20.04 and Magma OVS. Ubuntu 24.04 with
stock OVS did not provide the compatible Magma GTP-U datapath.

## Required NAT

The AGW host must NAT the UE subnet out an interface with upstream internet
routing. In the lab, the usable egress interface was the node default route
interface `eth0`, not `magma-sgi`.

The chart value should be:

```yaml
nodePrep:
  natEgress:
    enabled: true
    interface: ""
    sourceCidr: 192.168.128.0/24
```

An empty `interface` makes node prep detect the default-route interface.

AGW host checks:

```sh
iptables -t nat -S POSTROUTING | grep 192.168.128
iptables -S FORWARD | grep 192.168.128
ip route get 8.8.8.8
```

Expected shape:

```text
-A POSTROUTING -s 192.168.128.0/24 -o eth0 -j MASQUERADE
-A FORWARD -s 192.168.128.0/24 -o eth0 -j ACCEPT
-A FORWARD -d 192.168.128.0/24 -i eth0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
```

## Required UPF Association

`pipelined` must publish the 5G UPF node state to `sessiond` before or during
PDU establishment. The chart uses a startup wait so `pipelined` starts only
after `sessiond` is listening on `127.0.0.1:50065`.

Required values:

```yaml
startup:
  pipelined:
    waitForSessiond:
      enabled: true
      host: 127.0.0.1
      port: 50065
      timeoutSeconds: 180
```

Symptom of missing UPF association:

```text
TEID -2147483647 not found on GTP-U Downlink
```

or the AMF/gNB path advertising `0.0.0.0` and `0x7fffffff` as the UPF endpoint.

## Required Simulator Settings

Use UERANSIM v3.2.4 and keep the simulator on the separate simulator node:

```yaml
simulator:
  enabled: true
  image:
    repository: ghcr.io/infinitydon/ueransim
    tag: v3.2.4-x86-64
    pullPolicy: Always
  nodeSelector:
    magma.io/ueransim-node: "true"
  subscriber:
    provision: false
  iperf3Server:
    enabled: true
    hostNetwork: true
    port: 5201
```

Use `simulator.subscriber.provision=false` for NMS-managed deployments.

`simulator.iperf3Server.enabled=true` starts an `iperf3 -s` process on the
simulator worker using the same UERANSIM image. With `hostNetwork=true`, the
server is reached through the simulator node's LAN IP, which exercises UE
traffic through the AGW datapath and NAT instead of a Kubernetes ClusterIP.

The tested server placement was a third worker node:

```text
iperf3 server node: ebpf-bng-node-02, 192.168.88.163
```

Running the server on the UE worker was avoided because same-node pod/host
hairpin effects made troubleshooting less clear.

The UE ping command should be sourced from `uesimtun0`; no additional UE route
is required for this test when using:

```sh
ping -I uesimtun0 8.8.8.8
```

## Verification Flow

1. Confirm AGW and simulator pods are running.

```sh
kubectl -n magma-agw get pods -o wide
```

2. Confirm the UE is registered and the PDU session is up.

```sh
kubectl -n magma-agw exec deploy/agwc-ueransim-ue -- \
  /opt/UERANSIM/build/nr-cli imsi-001010000000001 --exec status
```

Expected:

```text
cm-state: CM-CONNECTED
rm-state: RM-REGISTERED
mm-state: MM-REGISTERED/NORMAL-SERVICE
5u-state: 5U1-UPDATED
```

3. Confirm `uesimtun0` exists.

```sh
kubectl -n magma-agw exec deploy/agwc-ueransim-ue -- ip addr show uesimtun0
```

Expected shape:

```text
inet 192.168.128.x/16 scope global uesimtun0
```

4. Confirm AGW policy assignment.

```sh
kubectl -n magma-agw exec deploy/policydb -- policydb_cli.py dump_data
```

5. Confirm AGW OVS has the GTP-U bridge and port.

```sh
ovs-vsctl show
ovs-ofctl dump-ports gtp_br0
```

Expected shape:

```text
Bridge gtp_br0
  Port gtpu0
    Interface gtpu0
      type: gtpu
```

6. Run the UE ping.

```sh
kubectl -n magma-agw exec deploy/agwc-ueransim-ue -- \
  ping -I uesimtun0 -c 4 -W 2 8.8.8.8
```

7. Run the UE iperf3 test.

First confirm the server pod and node:

```sh
kubectl -n magma-agw get pod -l app.kubernetes.io/component=ueransim-iperf3 -o wide
```

Then run iperf from the UE, binding the client to the UE tunnel IP:

```sh
UE_IP=$(kubectl -n magma-agw exec deploy/agwc-ueransim-ue -- \
  sh -c "ip -4 -o addr show uesimtun0 | awk '{print \$4}' | cut -d/ -f1")

kubectl -n magma-agw exec deploy/agwc-ueransim-ue -- \
  iperf3 -c <iperf3-server-node-ip> -B "$UE_IP" -t 10
```

Expected result shape after the TCP/5201 enforcement issue is resolved:

```text
[ ID] Interval           Transfer     Bitrate
[  5]   0.00-10.00  sec  ...          .../sec  sender
[  5]   0.00-10.00  sec  ...          .../sec  receiver
iperf Done.
```

Observed diagnostic success with temporary OVS TCP/5201 bypass:

```text
[  5]   0.00-10.00  sec   708 MBytes   594 Mbits/sec  606 sender
[  5]   0.00-10.02  sec   706 MBytes   591 Mbits/sec      receiver
iperf Done.
```

Observed clean-path issue still to resolve:

```text
iperf3: error - unable to send control message: Bad file descriptor
```

Packet capture showed the TCP SYN leaving `uesimtun0` and arriving at the AGW,
but not leaving the AGW host as a NATed SYN. ICMP on the same UE tunnel path
continued to work.

## Troubleshooting Ping Failure

If registration and PDU establishment work but ping fails:

1. Check that `v3.2.4-x86-64` is deployed, not `v3.3.0-x86-64`.

```sh
kubectl -n magma-agw get deploy agwc-ueransim-ue agwc-ueransim-gnb \
  -o custom-columns=NAME:.metadata.name,IMAGE:.spec.template.spec.containers[0].image
```

2. Check policy assignment in `policydb`.

3. Check NAT on the AGW host.

4. Check OVS GTP-U datapath support with `ovs-vsctl show`.

5. Check `sessiond` for an active session.

```sh
kubectl -n magma-agw logs deploy/sessiond --tail=200 | \
  grep -E 'IMSI|CreateSession|192.168.128|teid|stale|Release'
```

6. Check `pipelined` for flow programming errors.

```sh
kubectl -n magma-agw logs deploy/pipelined --tail=200 | \
  grep -E 'ERROR|WARN|GTP|gtp|192.168.128|Deadline'
```

If OVS flows still point to an old UE IP after a failed test, cleanly reattach
the simulator after restarting `sessiond` and `pipelined`.

If `iperf3` is missing in the UE container, restart the UERANSIM deployments
with `simulator.image.pullPolicy=Always` so kubelet pulls the refreshed
`v3.2.4-x86-64` image.

If ICMP works but iperf3 fails with `unable to send control message`, capture on
both sides before changing routes:

```sh
kubectl -n magma-agw exec deploy/agwc-ueransim-ue -- \
  tcpdump -nn -i uesimtun0 'tcp port 5201 or icmp'

ssh <agw-node> -- \
  sudo tcpdump -nn -i any 'host <iperf3-server-ip> and (tcp port 5201 or icmp)'
```

The lab failure mode was policy/enforcement related: the TCP SYN reached AGW
from the UE tunnel but did not egress the host NAT path. A temporary OVS bypass
validated throughput, but the durable fix should be an Orc8r/NMS policy or
Magma enforcement fix, not a manual OVS flow.
