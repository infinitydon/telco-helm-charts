# Open5GS OAI GEO NTN Helm chart

This chart deploys a distinct 3GPP Release-17 GEO NTN RFsimulator scenario:
Open5GS 5GC, patched OAI `nr-softmodem`, and patched OAI `nr-uesoftmodem`.
The OAI source is pinned to commit `38dc378224d230a50a787f3d8e7d460314fcf770`
(`2026.w16`) with the three patches supplied by `sabbir-uoulu/open-source-5g-ntn`.

All Multus networks are non-overlapping `/28` slices of `10.62.0.0/24`.
This chart uses `10.62.0.0/26` plus `10.62.0.64/28`; the companion LEO chart
uses the next five `/28` blocks. The UE DNN pool remains `10.46.0.0/16` and is
not a Multus network.

The acceptance test requires evidence for RFsim connectivity, NGAP, RACH/RRC,
NAS registration, PDU-session establishment, an OAI tunnel interface, and IP
session creation in the UPF. Pod readiness alone is not accepted.

The UE identity is configured once under `subscriber` in `values.yaml`. Helm
renders those values into `ue.conf` and uses the same values when provisioning
Open5GS, so IMSI, key, OPC, DNN, and SST cannot drift between the UE and core.

```bash
helm upgrade --install ntn-geo . -n ntn-geo --create-namespace --wait --timeout 15m
./scripts/test.sh
```

### Successful GEO gNB log

```text
[NR_RRC] [DL] (cellID ..., UE ID 1 RNTI c582) Send RRC Setup
[NR_RRC] [UL] (cellID ..., UE ID 1 RNTI c582) Received RRCSetupComplete (RRC_CONNECTED reached)
[NR_RRC] [UL] (cellID ..., UE ID 1 RNTI c582) Received Security Mode Complete
UE RNTI c582 CU-UE-ID 1 in-sync PH 45 dB PCMAX 20 dBm, average SINR 40.0 (32 meas)
```

### Successful GEO UE log

```text
[NR_MAC] [UE 0][...][RAPROC] 4-Step RA procedure succeeded. CBRA: Contention Resolution is successful.
[NAS] Received Registration Accept with result 3GPP
[NAS] Received PDU Session Establishment Accept, UE IPv4: 10.46.0.2
[OIP] TUN Interface oaitun_ue1 successfully configured, IPv4 10.46.0.2
[PHY] k_offset: 478ms, N_Common_Ta: 238.740000ms, drift: 0.000000us/s, timing_advance_ntn: 3667039 samples, DL Doppler shift: 0.000000kHz
```

### Acceptance-test result

```text
PASS: ntn-geo gNB/UE RFsim, RACH, registration, PDU session, UE tunnel, and UPF session succeeded.
```

The ignored `container-images/oai/` directory contains the reproducible runtime
Dockerfile. No image uses `latest`.
