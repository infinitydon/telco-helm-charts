# GHCR image validation — 25 October 2026

Three custom Linux/amd64 runtime images were rebuilt and pushed to GHCR:

| Image | Tag | Manifest digest |
| --- | --- | --- |
| ghcr.io/infinitydon/ella-services-tester | c7cf03530e52-tools1 | sha256:bd49c0c831fd58556c979b68af826b3e3d8fa72484e672f23f9c06aad19ac5ab |
| ghcr.io/infinitydon/ella-ue-phones | 0.3.4 | sha256:e4d0ab256faeead6d4596b061baf3d616ab147b2198d9f4c317a45679a48b98b |
| ghcr.io/infinitydon/ella-ue-browser | 0.3.4 | sha256:7f6416fc1472b7d893b300551ffb6706d10462359f5cace3d80f806ce98362f7 |

The phone image also runs the N6 gateway. Upstream Core/IMS/SMSC and netshoot images remain pinned to their existing upstream registries. Obsolete local experimental tags were not published.

All three images include ip/ss, ping/arping, tracepath/traceroute, dig/nslookup, curl/wget, nc, tcpdump, iptables, ethtool, procps, jq and openssl. The tester Dockerfile now checks out its pinned Core revision itself, so its build does not depend on an external source checkout.

## Pull and deployment verification

The new GHCR names were absent from the worker's MicroK8s image store before rollout. No archive import was performed. Kubelet events recorded successful registry pulls for all three names; running imageIDs match the manifest digests above. See [ghcr-images.json](ghcr-images.json). Phone, browser, gateway and tester containers are ready.

All three packages are public. Anonymous containerd pulls succeeded for every image without registry credentials. The lab pull Secret was deleted, and both Helm releases now have empty imagePullSecrets. The integration tester was recreated with imagePullPolicy Always and successfully pulled/started without credentials. Default chart installs require no registry login, node image import or installation script. Private-registry overrides remain supported through tester.imagePullSecrets (Core lab) and imagePullSecrets (UE chart).

The consolidated installation order is documented in [ella-stack](../../ella-stack/README.md). Following removal of registry credentials, all 22 phone/data-path smoke checks passed again. See [public-pull phone results](../../ue-phones/tests/ghcr-public-results.json).

## Results

- 24/24 upstream IMS/SMS scenarios passed using the GHCR tester: 20 NAS SMS and four IMS scenarios across 4G/5G. See [ghcr-results.json](ghcr-results.json).
- 2/2 IMS/SMSC Helm API hooks passed.
- 22/22 dedicated-phone checks passed: bidirectional SMS (including accented/euro text), both IMS call directions with voice QFI, registration, per-UE HTTPS, direct browser egress rejection and independent TUN failure/recovery. See [phone results](../../ue-phones/tests/ghcr-results.json).
- All 17 documented utility commands were found in the tester and browser; the phone/gateway share the same tool-equipped image. Tested ip address, ss listeners, DNS of the Core Service, local API HTTP 200, and actual tcpdump ICMP capture.
- Phone A (10.45.0.2) and B (10.45.0.1) each pinged 1.1.1.1 with zero loss and resolved example.com via 8.8.8.8, binding to their own UE data IP. These addresses may change after recreation.
- Browser remains non-root with dropped capabilities and loopback-only direct egress. Its SOCKS HTTPS succeeds; direct public HTTPS fails as expected. Installing tools does not grant raw sockets or bypass isolation.
- Deliberate Chromium termination recovered in 22.3 seconds, preserving example.com, profile and IMS registration with zero phone-container restarts. See [recovery result](../../ue-phones/tests/ghcr-browser-recovery.json).
- Six noVNC reconnect unit tests passed; both changed charts linted successfully. Runtime images were tested on amd64 only.
