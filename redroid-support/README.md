# redroid host support

`binder-modules-daemonset.yaml` prepares labeled Ubuntu 24.04 workers for
redroid. The privileged init container installs the signed
`linux-modules-extra-$(uname -r)` package when `binder_linux` is absent, loads
Binder, and writes persistent `modules-load.d` and `modprobe.d` configuration.

Label only nodes intended to run privileged Android workloads:

```bash
kubectl label node <worker> redroid.io/enabled=true
kubectl apply -f redroid-support/binder-modules-daemonset.yaml
kubectl -n redroid-system rollout status ds/redroid-binder-modules
```

Modern kernels expose Binder through BinderFS. Static `/dev/binder*` devices
are therefore not required on the host; each privileged redroid instance can
mount its own BinderFS. Configure redroid with `androidboot.use_memfd=true` so
the deprecated `ashmem` module is not required.

## Android smoke test

`redroid-test.yaml` runs one privileged Android 12 instance on a Binder-enabled
worker and exposes ADB on NodePort `30555`. The image uses the immutable
`redroid/redroid:12.0.0_64only-240527` tag. Do not expose the ADB NodePort to an
untrusted network.

```bash
kubectl apply -f redroid-support/redroid-test.yaml
kubectl -n redroid wait --for=condition=Ready pod/redroid-test-0 --timeout=10m
adb connect <worker-address>:30555
```

This manifest validates Android independently of the simulated 5G user plane.
Attaching Android application traffic to UERANSIM or PacketRusher requires a
separate routing sidecar or VRF/network-namespace integration.
