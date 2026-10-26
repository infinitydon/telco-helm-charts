FROM ghcr.io/hewlettpackard/packetrusher:v2.0.0@sha256:919f5d42d8a5abcd181756082b921250620a80806efaf9d4ff3ae249faed6dab
LABEL org.opencontainers.image.source="https://github.com/infinitydon/telco-helm-charts" org.opencontainers.image.version="v2.0.0" org.opencontainers.image.revision="6fef144296d4b1595e690a3d8e55c2a25407077b"
RUN apt-get update && apt-get install -y --no-install-recommends python3 bpftool dnsutils curl wget tcpdump traceroute ethtool jq procps && rm -rf /var/lib/apt/lists/*
ADD https://raw.githubusercontent.com/HewlettPackard/PacketRusher/6fef144296d4b1595e690a3d8e55c2a25407077b/LICENSE /usr/share/doc/packetrusher/LICENSE
