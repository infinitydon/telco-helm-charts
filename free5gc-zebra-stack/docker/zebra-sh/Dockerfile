# zebra-rs plus cradle runtime image.
#
# Build a pinned release or commit:
#   buildah bud \
#     --build-arg ZEBRA_REF=v26.7.5 \
#     --build-arg CRADLE_REF=a02afad54a22bcfa8339df2faad8e06d15d437c6 \
#     -t ghcr.io/infinitydon/zebra-sh:v26.7.5 \
#     -f docker/zebra-sh/Dockerfile .

ARG RUST_IMAGE=docker.io/library/rust:1-slim-bookworm
ARG RUNTIME_IMAGE=docker.io/library/debian:bookworm-slim
ARG ZEBRA_REPO=https://github.com/zebra-rs/zebra-rs.git
ARG ZEBRA_REF=v26.7.4
ARG CRADLE_REPO=https://github.com/cradle-rs/cradle-rs.git
ARG CRADLE_REF=a02afad54a22bcfa8339df2faad8e06d15d437c6

FROM ${RUST_IMAGE} AS zebra-builder

ARG ZEBRA_REPO
ARG ZEBRA_REF

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git libprotobuf-dev make pkg-config protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN git clone "${ZEBRA_REPO}" . \
    && git checkout --quiet "${ZEBRA_REF}"

ENV RUSTFLAGS="--cfg tokio_unstable"

RUN cargo build --release --bin zebra-rs --bin vtyctl --bin vtyhelper \
    && strip target/release/zebra-rs target/release/vtyctl target/release/vtyhelper

FROM ${RUST_IMAGE} AS cradle-builder

ARG CRADLE_REPO
ARG CRADLE_REF

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates clang git libelf-dev libprotobuf-dev llvm make pkg-config protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN git clone "${CRADLE_REPO}" . \
    && git checkout --quiet "${CRADLE_REF}"

RUN rustup component add rust-src \
    && cargo install bpf-linker \
    && cargo build --release -p cradle \
    && strip target/release/cradle

FROM ${RUNTIME_IMAGE}

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates iproute2 libcap2-bin \
    && rm -rf /var/lib/apt/lists/*

COPY --from=zebra-builder /src/target/release/zebra-rs /usr/bin/zebra-rs
COPY --from=zebra-builder /src/target/release/vtyctl /usr/bin/vtyctl
COPY --from=zebra-builder /src/target/release/vtyhelper /usr/bin/vtyhelper
COPY --from=zebra-builder /src/zebra-rs/yang/*.yang /etc/zebra-rs/yang/
COPY --from=cradle-builder /src/target/release/cradle /usr/bin/cradle

RUN setcap 'cap_net_bind_service,cap_net_admin,cap_net_broadcast,cap_net_raw=ep' /usr/bin/zebra-rs \
    && setcap 'cap_net_admin,cap_net_raw,cap_sys_admin,cap_bpf,cap_perfmon=ep' /usr/bin/cradle || true

VOLUME /etc/zebra-rs

ENTRYPOINT ["/usr/bin/zebra-rs"]
