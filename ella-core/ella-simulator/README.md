# Shared simulator library

This Helm library provides the common Deployment, configuration, health Service and native-process supervisor for the UERANSIM and PacketRusher application charts. It is not independently installed. The application charts vendor its archive.

The supervisor uses the active Core Service and public status API, without Core credentials or Kubernetes permissions. Core endpoint changes trigger clean native-process reattachment. Readiness reflects live processes and UE data-session addresses. Native configuration lives in a memory-backed per-Pod volume; the HTTP status response contains no SIM credentials.
