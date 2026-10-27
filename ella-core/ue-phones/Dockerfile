FROM docker.io/library/golang:1.27.3 AS build
RUN apt-get update && apt-get install -y --no-install-recommends libpcap-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /src
ARG CORE_REVISION=c7cf03530e52a2d353d9d1cd6159943319075bf0
RUN git clone https://github.com/ellanetworks/core . && git checkout "$CORE_REVISION"
COPY app/ims_bridge.go internal/tester/scenarios/dashboard_ims.go
COPY app/server.go internal/tester/scenarios/gnb/dashboard_server.go
COPY app/browser.go internal/tester/scenarios/gnb/dashboard_browser.go
COPY app/mode.go internal/tester/scenarios/gnb/dashboard_mode.go
COPY app/mode_test.go internal/tester/scenarios/gnb/dashboard_mode_test.go
COPY app/phone_gnb.go internal/tester/scenarios/gnb/dashboard_phone_gnb.go
COPY app/browse.go internal/tester/scenarios/gnb/dashboard_browse.go
COPY app/browse_test.go internal/tester/scenarios/gnb/dashboard_browse_test.go
COPY app/ran_bridge.go internal/tester/gnb/dashboard_internet.go
COPY app/phones.html internal/tester/scenarios/gnb/phones.html
COPY app/enhancements.js internal/tester/scenarios/gnb/enhancements.js
COPY app/main.go cmd/ue-phones/main.go
# The stock voice scenario omits SMS capability. These persistent UEs need both.
RUN sed -i '/func newSubscriberUE/,/^}/s/PDUSessionID: /RequestSMS: servicesEnabled(),\n\t\tPDUSessionID: /' internal/tester/scenarios/gnb/common.go
RUN sed -i 's/"10\.6\.0\.5"/os.Getenv("IMS_ADDRESS")/' internal/tester/scenarios/ims.go
RUN gofmt -w internal/tester/scenarios/dashboard_ims.go internal/tester/scenarios/gnb/dashboard_server.go internal/tester/scenarios/gnb/dashboard_browse*.go internal/tester/scenarios/gnb/dashboard_phone_gnb.go internal/tester/gnb/dashboard_internet.go cmd/ue-phones/main.go && go test ./internal/tester/scenarios/gnb -run 'TestMobileReader|TestBrowserRoutes|TestPhoneMode|TestInternetActionsDisabled' && go build -o /ue-phones ./cmd/ue-phones
FROM docker.io/library/debian:trixie-slim
LABEL org.opencontainers.image.source="https://github.com/infinitydon/telco-helm-charts"
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 iputils-ping iputils-tracepath iputils-arping dnsutils curl wget netcat-openbsd tcpdump traceroute iptables ethtool procps jq openssl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends libpcap0.8t64 iproute2 iptables ethtool procps ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=build /ue-phones /usr/local/bin/ue-phones
COPY app/start.sh /usr/local/bin/start-phones
RUN chmod +x /usr/local/bin/start-phones
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/start-phones"]
