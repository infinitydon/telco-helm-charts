# Custom container images

This directory contains the Dockerfiles for the chart's two custom images. It
is excluded from Helm packages by `.helmignore`.

## SIPp endpoint

```bash
cd /home/ubuntu/work/telco-helm-charts/open5gs-vonr/container-images/sipp
docker build --pull -t ghcr.io/infinitydon/vonr-sipp:0.1.0 .
docker push ghcr.io/infinitydon/vonr-sipp:0.1.0
```

## Kamailio P-CSCF runtime

The final image uses the pinned `herlesupreeth/docker_open5gs` source tree as
its build context because it copies the upstream `icscf`, `scscf`, and `pcscf`
directories. Build it on the OAM VM as follows:

```bash
cd /home/ubuntu/work/docker_open5gs
git fetch origin
git checkout 7464234a9f79718df1836d24d688be745a5272d1

docker build \
  -t docker-open5gs-kamailio-base:7464234 \
  ./ims_base

docker build \
  --build-arg BASE_IMAGE=docker-open5gs-kamailio-base:7464234 \
  -f /home/ubuntu/work/telco-helm-charts/open5gs-vonr/container-images/kamailio/Dockerfile \
  -t ghcr.io/infinitydon/docker-open5gs-kamailio:7464234 \
  .

docker push ghcr.io/infinitydon/docker-open5gs-kamailio:7464234
```

No build command uses `latest`. The Kamailio base build also pins the Kamailio
source revision through the upstream `ims_base/Dockerfile` at the specified
`docker_open5gs` commit.
