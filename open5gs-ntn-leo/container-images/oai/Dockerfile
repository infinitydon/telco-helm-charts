FROM ubuntu:24.04

ARG OAI_COMMIT=38dc378224d230a50a787f3d8e7d460314fcf770
LABEL org.opencontainers.image.source="https://gitlab.eurecom.fr/oai/openairinterface5g" \
      org.opencontainers.image.revision="${OAI_COMMIT}" \
      org.opencontainers.image.description="Patched OAI 5G NR gNB/UE runtime for GEO and LEO NTN RFsimulator"

ENV DEBIAN_FRONTEND=noninteractive \
    OAI_HOME=/opt/oai \
    LD_LIBRARY_PATH=/opt/oai

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates iproute2 iputils-ping libsctp1 libconfig9 \
      libyaml-cpp0.8 procps tcpdump && \
    rm -rf /var/lib/apt/lists/*

COPY nr-softmodem /opt/oai/nr-softmodem
COPY nr-uesoftmodem /opt/oai/nr-uesoftmodem
COPY lib/ /opt/oai/

RUN chmod 0755 /opt/oai/nr-softmodem /opt/oai/nr-uesoftmodem && \
    ln -s /opt/oai/nr-softmodem /usr/local/bin/nr-softmodem && \
    ln -s /opt/oai/nr-uesoftmodem /usr/local/bin/nr-uesoftmodem

WORKDIR /opt/oai
ENTRYPOINT ["/bin/bash", "-lc"]
CMD ["nr-softmodem --help"]
