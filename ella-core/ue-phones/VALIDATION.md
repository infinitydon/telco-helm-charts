# UE phone validation

Browser recovery update: [0.3.3 validation](BROWSER-RECOVERY-VALIDATION.md), including the OOM diagnosis and live crash/hang recovery results.

Latest clean reinstall: [25 October 2026 results](../tests/services/REINSTALL-VALIDATION.md). All 24 integration scenarios, both Helm API tests and 22 phone/browser checks passed after namespace/PVC recreation.


25 October 2026. Two independent UE Deployments and UI Services are running, with a Chromium/noVNC sidecar and separate browser profile for each subscriber.

## Tested deployment

- Namespace ella-services-test; Helm release ue, revision 10; chart/application 0.3.0.
- Phone A: Deployment ue-ue-a, Service ue-ue-a-ui, http://192.168.88.165:30880/.
- Phone B: Deployment ue-ue-b, Service ue-ue-b-ui, http://192.168.88.165:30881/.
- Simulator image localhost/ella-ue-phones:0.3.0, manifest sha256:fe74def8d3b7a833fc98c9c6542f4c859ab5a58051d0437cf5b25b205894e52f.
- Browser image localhost/ella-ue-browser:0.3.0, manifest sha256:69947db3269199a505283619ac798d6f43d789166a03d85056c019e803cc4907.
- Browser packages: Debian Chromium 156.0.8078.47 and noVNC 1.6.0. Chromium runs as UID 1000 with dropped container capabilities; no --no-sandbox flag is used.
- Core source remains pinned to c7cf03530e52a2d353d9d1cd6159943319075bf0. The shared legacy ue-phones Deployment and Service have been removed.
- The existing N6 gateway remains on image 0.2.3; it is unchanged by this application/browser update.

## Chromium and dedicated UEs (0.3.0)

- 12/12 split-smoke checks passed: independent NAS attachment and IMS registration; SMS both directions with matching received text, including accents and euro, and delivery status derived from the other UE's actual receipt; calls both directions with confirmed voice-QFI media; hang-up; deregistration/reregistration. See tests/split-results.json.
- 7/7 browser-network checks passed: HTTPS via each UE-bound SOCKS proxy; direct browser-UID egress rejected with firewall counters; Phone A cannot fetch with its TUN down; Phone B continues; Phone A recovers after restoring its TUN and source route. See tests/browser-network-results.json. Bringing a TUN down removes its source route, so the fault-injection script restores both in its finally block.
- 3/3 reader checks passed through the two dedicated Services, including private destination rejection. See tests/web-results.json.
- Browser click-through loaded Wikipedia with its original CSS, globe image and JavaScript-generated fundraising UI through Phone A, then collapsed the banner through noVNC input. Phone B independently loaded Example Domain. Both UIs showed their respective UE data IPs; the browser logs recorded the corresponding website connections. Mobile emulation and the virtual display use 500×900 portrait dimensions to avoid Chromium's minimum-window clipping.
- TestMobileReader and TestBrowserRoutes passed during the image build. The latter checks route registration and rejection of cross-origin noVNC requests. JavaScript syntax, Helm lint, and rendering both dedicated Services as ClusterIP/NodePort/LoadBalancer passed.

Browser DNS and TCP sockets bind to the UE internet address. A second source policy rule points to an unreachable route if the tunnel route disappears, preventing fallthrough to the pod's main route. IPv4 and IPv6 owner rules block new direct egress from browser UID 1000. SOCKS supports public IPv4 TCP ports 80/443; QUIC is disabled. noVNC, VNC and CDP listen on loopback only. Browser profiles and message history are ephemeral. IMS calls still use synthetic RTP rather than browser microphone/speaker audio.

## Earlier validation

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

## Mobile reader and call action contrast (0.2.3)

The image build passes TestMobileReader, covering retained headings/lists/emphasis and rewritten relative links, plus removal of scripts, styles, images, frames and event handlers. Twelve call/SMS checks and three UE web checks passed. The final deployment also fetched the CERN World Wide Web project page through Phone B (10.45.0.2, HTTP 200), preserving its heading and inline links. Browser QA verified green Answer and red Decline during ringing, red End after answer, and gray unavailable actions.

Final local image manifest: sha256:c03278e33b880e51dd6f5b0619769242449394718f680f82ed7e6cbc357cef85. Pages use a mobile User-Agent and a formatted mobile reader; original site CSS/JavaScript and images remain excluded.

## Address entry (0.3.1)

The address field accepts bare hostnames and paths, defaults them to HTTPS, preserves explicit HTTP/HTTPS, and handles protocol-relative addresses and host:port input. Seven normalization cases, JavaScript syntax, Helm lint and the existing image-build tests passed. Live browser verification submitted www.google.com without a scheme; the field expanded it to https://www.google.com and Chromium navigated through the UE connection. Simulator image manifest: sha256:744872ae850709e04a82a7b87a5e6da8efb55398783250690cec7f2e55f897ba. Browser image remains 0.3.0.
