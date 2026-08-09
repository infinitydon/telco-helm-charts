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
