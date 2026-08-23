# Validation

Validated on MicroK8s v1.35.6 on 2026-08-23 using the pinned OAI NTN runtime image.

- gNB established NGAP with Open5GS AMF.
- UE completed RFsim synchronization, RACH/RRC, NAS registration, and PDU-session establishment.
- UE tunnel `oaitun_ue1` received `10.46.0.2/24`; Open5GS UPF created the matching session.
- Live UE telemetry showed changing LEO propagation state, including approximately 18.7 ms downlink delay, 57.34 kHz downlink Doppler, NTN timing advance, and approximately -46 microseconds/second drift.

Run `scripts/test.sh` to repeat these checks, including the LEO timing/Doppler assertion.
