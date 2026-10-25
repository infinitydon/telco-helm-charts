FROM docker.io/library/debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends chromium chromium-sandbox novnc websockify xvfb x11vnc x11-utils curl ca-certificates fonts-liberation && rm -rf /var/lib/apt/lists/* && useradd -u 1000 -m browser
RUN apt-get update && apt-get install -y --no-install-recommends openbox fontconfig && rm -rf /var/lib/apt/lists/*
COPY start-browser.sh /usr/local/bin/start-browser
COPY remote.html /usr/share/novnc/remote.html
RUN chmod +x /usr/local/bin/start-browser
USER 1000:1000
ENV HOME=/home/browser DISPLAY=:99
ENTRYPOINT ["/usr/local/bin/start-browser"]
