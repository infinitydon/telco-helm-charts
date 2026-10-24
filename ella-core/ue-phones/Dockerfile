FROM docker.io/library/golang:1.27.3 AS build
RUN apt-get update && apt-get install -y --no-install-recommends libpcap-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /src
ARG CORE_REVISION=c7cf03530e52a2d353d9d1cd6159943319075bf0
RUN git clone https://github.com/ellanetworks/core . && git checkout "$CORE_REVISION"
COPY app/ims_bridge.go internal/tester/scenarios/dashboard_ims.go
COPY app/server.go internal/tester/scenarios/gnb/dashboard_server.go
COPY app/phones.html internal/tester/scenarios/gnb/phones.html
COPY app/main.go cmd/ue-phones/main.go
# The stock voice scenario omits SMS capability. These persistent UEs need both.
RUN sed -i '/func newSubscriberUE/,/^}/s/PDUSessionID: /RequestSMS: true,\n\t\tPDUSessionID: /' internal/tester/scenarios/gnb/common.go
RUN gofmt -w internal/tester/scenarios/dashboard_ims.go internal/tester/scenarios/gnb/dashboard_server.go cmd/ue-phones/main.go && go build -o /ue-phones ./cmd/ue-phones
FROM docker.io/library/debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends libpcap0.8t64 iproute2 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=build /ue-phones /usr/local/bin/ue-phones
COPY app/start.sh /usr/local/bin/start-phones
RUN chmod +x /usr/local/bin/start-phones
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/start-phones"]
