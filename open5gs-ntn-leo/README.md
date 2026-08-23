# Open5GS OAI LEO NTN Helm chart

This distinct chart deploys the 3GPP Release-17 LEO NTN companion scenario:
Open5GS 5GC plus the patched OAI gNB and UE. It uses the upstream 600 km
`SAT_LEO_TRANS` orbital model, time-varying delay, continuous Doppler
compensation, and LEO-specific timing drift from
`sabbir-uoulu/open-source-5g-ntn-leo`.

The same pinned OAI `2026.w16` image is shared with the GEO chart because the
upstream projects use the same binaries and patches. This chart has independent
LEO configuration, Kubernetes names, namespace, release, and five `/28` Multus
networks (`10.62.0.80/28` through `10.62.0.144/28`) carved from the shared
`10.62.0.0/24`. Its UE DNN pool is `10.46.0.0/16`, not a Multus network.

```bash
helm upgrade --install ntn-leo . -n ntn-leo --create-namespace --wait --timeout 15m
./scripts/test.sh
```

The UE identity is configured once under `subscriber` in `values.yaml`. Helm
renders it into `ue.conf` and uses the same values for Open5GS subscriber
provisioning.

Example output from the validated LEO deployment:

```text
[NAS] Received PDU Session Establishment Accept, UE IPv4: 10.46.0.2
[OIP] TUN Interface oaitun_ue1 successfully configured, IPv4 10.46.0.2
[HW] Downlink delay 18.729825 ms, Doppler shift SAT->UE 57.341074 kHz
[NR_MAC] NTN Config Rxd. ... N_Common_Ta: 18.705848ms, drift: -46.086000us/s
[PHY] timing_advance_ntn: 287290 samples, DL Doppler shift: 57.340709kHz, UL Doppler shift: 37.211613kHz
PASS: ntn-leo gNB/UE RFsim, RACH, registration, PDU session, UE tunnel, and UPF session succeeded.
```

The acceptance test requires RFsim, NGAP, RACH/RRC, NAS registration,
PDU-session establishment, an OAI tunnel interface, a UPF session, and live
LEO timing/Doppler telemetry.
No image uses `latest`.
