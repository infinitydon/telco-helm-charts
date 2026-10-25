# UE phone dashboard validation

24 October 2026. The dedicated Helm Deployment is running. All 12 functional checks passed against it, and a browser click-through confirmed calling, answering, live packet counters, hang-up and NAS SMS delivery.

## Tested deployment

- Namespace: ella-services-test; release: ue; Deployment/Service: ue-phones.
- Chart/application: 0.2.2; image: localhost/ella-ue-phones:0.2.2, imported on ebpf-bng-node-01.
- Image manifest digest: sha256:5a84a20096fd55bc9fd95a9ecf7fc52ecb4122f6a0bd116870dd202128a0d27e.
- Core source pinned by the Dockerfile: c7cf03530e52a2d353d9d1cd6159943319075bf0.
- The earlier temporary application in ella-services-tester was stopped. The dedicated pod owns the two subscriber identities.

The backend reuses upstream RAN/UE and IMS libraries and exercises real NAS SMS CP/RP/TPDU handling, IMS AKA/IPsec and the Ella Core GTP-U path. No mocked network responses were used.

## Ringing, SMS alerts and UE web browsing (0.2.2)

The original 12 functional checks passed again through NodePort after adding the internet data tunnels. Three additional web checks passed: Phone A HTTPS browsing from UE IP 10.45.0.1, Phone B HTTPS browsing from UE IP 10.45.0.2, and rejection of a private loopback destination. See tests/web-results.json. Both public page fetches returned HTTP 200 with non-empty reader text and the corresponding PDU-session TEIDs. HTTPS browsing was also checked while both IMS call legs remained confirmed.

Browser click-through verified:

- A fixed page-level ringing banner and pulsing incoming-phone frame remain visible while that phone is using its Browser tab.
- The larger Answer control connects the call; the ringing alert disappears after answer.
- A newly received SMS creates a preview alert, an unread tab badge, an inbox banner and a browser-title indication while the recipient is browsing.
- Open message switches to that inbox and clears the unread indication.
- The optional alert-sound control toggles on successfully; it defaults off until the user enables it.
- The Browser tab fetched and rendered Example Domain with UE IP, HTTP 200, byte count and duration displayed.

DNS and web sockets bind to the internet UE address and traverse its TUN, N3/GTP-U, Core and the N6 NAT gateway. Core's source policy route was added using a network helper without restarting its ephemeral database. The fixture manifest now carries the equivalent sidecar for fresh deployments. The gateway translates both untranslated UE addresses and Core's built-in N6 NAT source. Neighbor entries were refreshed after replacing the gateway during validation.

Browsing is an IPv4 HTTP/HTTPS reader view. Page scripts, logins, forms, images and downloads are not executed or fetched by the user's browser. TLS verification, public-destination restrictions, redirect limits and request/body limits remain enabled. This is not full interactive browser emulation.

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

The UI now uses a NodePort Service: open http://192.168.88.165:30880 directly. All 12 functional checks were rerun successfully through this NodePort, and the browser loaded both live phone panels. ClusterIP, NodePort and LoadBalancer variants rendered successfully; ClusterIP omits nodePort. LoadBalancer provisioning itself was not exercised. Do not run the original scenarios concurrently against these same subscriber identities.
