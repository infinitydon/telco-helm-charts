# UE phone dashboard validation

24 October 2026. The dedicated Helm Deployment is running. All 12 functional checks passed against it, and a browser click-through confirmed calling, answering, live packet counters, hang-up and NAS SMS delivery.

## Tested deployment

- Namespace: ella-services-test; release: ue; Deployment/Service: ue-phones.
- Chart/application: 0.1.1; image: localhost/ella-ue-phones:0.1.1, imported on ebpf-bng-node-01.
- Image manifest digest: sha256:13962e685f1e1f2ba75389114a683b6b30820d5591fe9a6d50ac2f5584d5d4ed.
- Core source pinned by the Dockerfile: c7cf03530e52a2d353d9d1cd6159943319075bf0.
- The earlier temporary application in ella-services-tester was stopped. The dedicated pod owns the two subscriber identities.

The backend reuses upstream RAN/UE and IMS libraries and exercises real NAS SMS CP/RP/TPDU handling, IMS AKA/IPsec and the Ella Core GTP-U path. No mocked network responses were used.

## Functional checks

See tests/results.json for the recorded 12 passing checks:

- Both UEs attach to 5G with NAS SMS enabled and establish IMS PDU sessions.
- Both UEs register with IMS.
- A sends an SMS to B; B receives it and A's message changes to delivered to UE.
- B replies to A with accented text and a euro symbol, preserved intact.
- In each call direction, the recipient sees an incoming call, Answer confirms both call legs, both UEs transmit and receive packets on dedicated voice QFIs, and Hang Up terminates both legs.
- IMS unregister/register works independently of NAS attachment.

Go compilation, JavaScript syntax checks, Helm lint and template rendering passed. The application rolled out successfully through Helm.

## Browser verification

The in-app browser successfully loaded the real dashboard through Kubernetes port forwarding. Verified Phone A dialing, Phone B's incoming indication and Answer control, connected status on both phones, live voice-QFI packet counters and Hang Up. Then sent the exact text "Hello from the phone UI" through Phone A's Messages panel and observed it in Phone B's inbox, with the sender showing delivered to UE.

Browser testing found that Go's byte-slice JSON encoding had exposed QFIs as a base64 string. Version 0.1.1 converts them to integer arrays. The functional check now verifies the QFI array type, and the browser flow passed after the fix.

Calls carry synthetic RTP packets, not browser microphone/speaker audio. The responsive narrow-screen layout was visually inspected; it stacks the two phone panels.

## Control-plane recovery

The original dedicated deployment was delayed by stale controllers/scheduler and severe memory pressure on an 8 GiB control-plane VM. Authorized restart attempts alone did not stabilize it. A temporary WatchList=false API-server setting was rolled back to the original configuration.

The user resized the VM to approximately 20 GiB RAM. After the resize, all four nodes were Ready, controller and scheduler leases renewed normally, and the dedicated Deployment reconciled. Memory showed approximately 12 GiB available during verification. Prometheus was not deliberately paused. No experimental API-server gate change remains.

To reopen the UI, run kubectl -n ella-services-test port-forward service/ue-phones 18080:8080 and visit http://127.0.0.1:18080. Do not run the original scenarios concurrently against these same subscriber identities.
