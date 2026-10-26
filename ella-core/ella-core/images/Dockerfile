# Pinned upstream source; no Core source patches. Build on Linux/amd64.
FROM docker.io/library/golang:1.27.3 AS source
RUN apt-get update && apt-get install -y --no-install-recommends libpcap-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /src
ARG CORE_REVISION=c7cf03530e52a2d353d9d1cd6159943319075bf0
RUN git clone https://github.com/ellanetworks/core . && git checkout "$CORE_REVISION"
FROM docker.io/library/node:24-bookworm-slim AS ui
WORKDIR /ui
COPY --from=source /src/ui/package*.json ./
RUN npm ci
COPY --from=source /src/ui/ ./
RUN npm run build
FROM source AS build
ARG CORE_REVISION=c7cf03530e52a2d353d9d1cd6159943319075bf0
COPY --from=ui /ui/dist/ /src/ui/dist/
RUN go build -trimpath -ldflags "-s -w -X github.com/ellanetworks/core/version.GitCommit=${CORE_REVISION}" -o /core ./cmd/core
FROM docker.io/library/debian:trixie-slim
ARG CORE_REVISION=c7cf03530e52a2d353d9d1cd6159943319075bf0
LABEL org.opencontainers.image.source="https://github.com/ellanetworks/core" org.opencontainers.image.revision="${CORE_REVISION}" org.opencontainers.image.licenses="BUSL-1.1"
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 iputils-ping iputils-arping iputils-tracepath dnsutils curl wget netcat-openbsd tcpdump traceroute iptables ethtool procps jq openssl ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=build /core /usr/local/bin/core
COPY --from=build /src/LICENSE /src/NOTICE /usr/share/doc/ella-core/
COPY --from=build /src/LICENSES/ /usr/share/licenses/ella-core/
ENTRYPOINT ["core"]
