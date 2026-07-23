FROM python:3.13.5-slim-bookworm

ARG WASMTIME_PY_VERSION=47.0.1
ARG REQUESTS_VERSION=2.34.2
ARG PYSOCKS_VERSION=1.7.1

RUN pip install --no-cache-dir \
      "wasmtime==${WASMTIME_PY_VERSION}" \
      "requests==${REQUESTS_VERSION}" \
      "PySocks==${PYSOCKS_VERSION}" \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends iperf3 iproute2 iputils-ping traceroute \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 wasm

COPY app.py /opt/wasm-runner/app.py

USER 10001:10001
WORKDIR /opt/wasm-runner

ENV LISTEN_HOST=127.0.0.1 \
    LISTEN_PORT=8090 \
    UE_INTERFACE=uesimtun0 \
    SOCKS_PROXY=socks5h://127.0.0.1:1080 \
    SCENARIO_DIR=/scenarios \
    DEFAULT_TARGET=https://example.com \
    REQUEST_TIMEOUT_SECONDS=20 \
    WASM_FUEL=1000000

EXPOSE 8090

ENTRYPOINT ["python", "/opt/wasm-runner/app.py"]
