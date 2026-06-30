# UERANSIM iperf3 Policy

The AGW chart can deploy a host-networked UERANSIM `iperf3` server for UE
throughput testing. The fullstack chart includes an optional
`provisioning.iperf3Policy` block that adds explicit TCP/5201 uplink and
downlink matches to the default Orc8r policy rule.

Example:

```yaml
provisioning:
  iperf3Policy:
    enabled: true
    serverCidr: 192.168.88.163/32
    ueCidr: 192.168.128.20/32
    port: 5201
```

In the lab, the policy update streamed to AGW `policydb`, but clean-path iperf3
still failed with:

```text
iperf3: error - unable to send control message: Bad file descriptor
```

Packet capture showed TCP SYNs leaving `uesimtun0` and arriving at AGW, but not
egressing the AGW host NAT path. A temporary diagnostic OVS bypass for TCP/5201
proved the UE image and iperf3 server were functional:

```text
[  5]   0.00-10.00  sec   708 MBytes   594 Mbits/sec  606 sender
[  5]   0.00-10.02  sec   706 MBytes   591 Mbits/sec      receiver
iperf Done.
```

Do not rely on manual OVS flows as a deployment requirement. Treat the remaining
work as a Magma policy/enforcement datapath issue.
