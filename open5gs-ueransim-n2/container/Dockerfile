FROM golang:1.24.7-bookworm AS build
ARG SOURCE_COMMIT=3306db6301a9b88da8176a9b4185edd722f33c10
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/DBGR18/N2-SCTP-middleware.git /src && cd /src && git checkout "$SOURCE_COMMIT"
WORKDIR /src
COPY 0001-support-rsa-ca.patch /tmp/0001-support-rsa-ca.patch
RUN git apply /tmp/0001-support-rsa-ca.patch
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/middleware ./cmd/middleware && \
    CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/gnb_proxy ./cmd/gnb_proxy

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/middleware /usr/local/bin/middleware
COPY --from=build /out/gnb_proxy /usr/local/bin/gnb_proxy
ENTRYPOINT ["/usr/local/bin/middleware"]
