FROM docker.io/library/debian:trixie-slim
LABEL org.opencontainers.image.source="https://github.com/infinitydon/telco-helm-charts"
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 iputils-ping iputils-tracepath iputils-arping dnsutils curl wget netcat-openbsd tcpdump traceroute iptables ethtool procps jq openssl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends chromium chromium-sandbox novnc websockify xvfb x11vnc x11-utils curl ca-certificates fonts-liberation && rm -rf /var/lib/apt/lists/* && useradd -u 1000 -m browser
RUN apt-get update && apt-get install -y --no-install-recommends openbox fontconfig && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends tini && rm -rf /var/lib/apt/lists/*
COPY start-browser.sh /usr/local/bin/start-browser
COPY remote.html /usr/share/novnc/remote.html
COPY connection.js /usr/share/novnc/connection.js
COPY browser-state.py /usr/local/bin/browser-state
RUN chmod +x /usr/local/bin/start-browser /usr/local/bin/browser-state
USER 1000:1000
ENV HOME=/home/browser DISPLAY=:99
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/local/bin/start-browser"]
