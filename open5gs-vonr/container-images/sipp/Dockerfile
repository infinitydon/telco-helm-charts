FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      iproute2 \
      iputils-ping \
      sip-tester \
      tcpdump && \
    rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/usr/bin/sipp"]
CMD ["-v"]
