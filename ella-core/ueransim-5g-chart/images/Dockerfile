FROM debian:bookworm-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends git cmake make g++ libsctp-dev lksctp-tools ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git clone https://github.com/aligungr/UERANSIM . && git checkout 6bf5a1a96aaef6ae8778b9d8b477ac6e2bbf8156
RUN cmake -DCMAKE_BUILD_TYPE=Release -S . -B build && cmake --build build -j 4
FROM debian:bookworm-slim
LABEL org.opencontainers.image.source="https://github.com/infinitydon/telco-helm-charts" org.opencontainers.image.version="v3.3.0" org.opencontainers.image.revision="6bf5a1a96aaef6ae8778b9d8b477ac6e2bbf8156"
RUN apt-get update && apt-get install -y --no-install-recommends python3 libsctp1 iproute2 iputils-ping dnsutils curl wget tcpdump traceroute ethtool jq procps ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/build/nr-gnb /src/build/nr-ue /src/build/nr-cli /opt/ueransim/
COPY --from=build /src/LICENSE /usr/share/doc/ueransim/LICENSE
ENV PATH="/opt/ueransim:${PATH}"
CMD ["nr-gnb", "--help"]
