# UE phone dashboard validation

24 October 2026. Application build and all **12 functional checks passed** against the existing Ella Core/IMS/SMSC lab. See [the machine-readable results](tests/results.json).

The same compiled application was temporarily executed in `ella-services-tester`, whose existing Multus RAN attachment and TUN device provide the required access. It used the two real simulated subscribers, NAS SMS CP/RP/TPDU handling, IMS AKA/IPsec and the Ella Core GTP-U path. No mocked network responses were used.

Verified:

- Both UEs attach to 5G with NAS SMS enabled and establish IMS PDU sessions.
- Both UEs register with IMS.
- A sends an SMS to B; B's NAS stack receives it and A's message changes to `delivered to UE`.
- B replies to A with accented text and a euro symbol, preserved intact.
- In each call direction, the recipient sees an incoming call, the Answer action confirms both call legs, both UEs transmit and receive packets on voice QFIs, and Hang Up terminates both legs.
- IMS unregister/register works independently of NAS attachment.
- Go application compilation, JavaScript syntax checking and Helm lint succeeded. The Deployment and Service templates render successfully.

The browser automation runtime could not initialize on this host (`failed to write kernel assets`), so an automated browser click-through and screenshot were not completed. Functional checks exercise the same HTTP actions the phone UI uses.

## Deployment status at handoff

The `ue` Helm release was created, but its Deployment was not reconciled into a ReplicaSet. Before the application deployment, the shared scheduler lease had already been stale for several hours. Authorized control-plane recovery attempts restarted kubelite and dqlite. A temporary `WatchList=false` API-server setting did not stabilize the node and was **rolled back to the original configuration**. The control-plane node showed severe memory pressure, with Prometheus using approximately 2.5 GiB on an 8 GiB VM.

The user chose to shut down the control-plane VM and increase RAM. Prometheus was not deliberately paused, and no further control-plane changes were made after that decision. The dedicated application pod and final browser check therefore remain pending that VM resize. Do not interpret the application functional results as successful validation of the dedicated Deployment.

After the VM returns:

1. Check Kubernetes API health, controller/scheduler leases, all node readiness and workload status.
2. Deploy/upgrade `ue` with this chart and the current Core N2 address, then wait for `deployment/ue-phones` to become available.
3. Ensure the temporary application in `ella-services-tester` has stopped before starting the same subscriber identities in the dedicated pod.
4. Port-forward `service/ue-phones` and rerun `tests/smoke.ps1`; then inspect the phone panels in a browser.

The built image `localhost/ella-ue-phones:0.1.0` is imported on `ebpf-bng-node-01`. The Dockerfile pins Core source revision `c7cf03530e52a2d353d9d1cd6159943319075bf0`. Existing IMS/SMSC charts remain separate.
