# redroid host support

`binder-modules-daemonset.yaml` prepares labeled Ubuntu 24.04 workers for
redroid. The privileged init container installs the signed
`linux-modules-extra-$(uname -r)` package when `binder_linux` is absent, loads
Binder, and writes persistent `modules-load.d` and `modprobe.d` configuration.

Label only nodes intended to run privileged Android workloads:

```bash
kubectl label node <worker> redroid.io/enabled=true
kubectl apply -f redroid-support/binder-modules-daemonset.yaml
kubectl -n kube-system rollout status ds/redroid-binder-modules
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

The supplied test manifest includes a dedicated UERANSIM UE using IMSI
`001010000000002`. Android HTTP and HTTPS traffic is sent to a local HTTP proxy,
forwarded to a SOCKS server bound to `uesimtun0`, and carried over that UE's PDU
session. The original chart UE remains deployed separately.

The Android product name is customized to `UERANSIM-5G-SA-Phone`. After boot,
the manifest also enables Android SystemUI's demo mobile-network indicator and
shows `5G` in the status bar. This icon represents the verified lab data path;
it is cosmetic rather than radio telemetry because redroid has no modem or
Android Radio Interface Layer. UERANSIM registration, PDU-session logs, tunnel
address, and interface counters remain the authoritative status sources.

## Windows client with Winget

Open PowerShell and install Android Platform Tools and scrcpy:

```powershell
winget install --id Google.PlatformTools --exact
winget install --id Genymobile.scrcpy --exact
```

Open a new PowerShell window after installation so the updated `PATH` is used.

Start a session:

```powershell
adb start-server
adb connect 192.168.88.98:30555
adb devices
scrcpy -s 192.168.88.98:30555
```

Closing the scrcpy window, or pressing `Ctrl+C` in its PowerShell window, stops
screen viewing and control but leaves the ADB connection available. Disconnect
this redroid instance with:

```powershell
adb disconnect 192.168.88.98:30555
```

To stop the local ADB background service and disconnect every ADB device:

```powershell
adb kill-server
```

To start another session later, repeat `adb connect` followed by `scrcpy`; ADB
will automatically start its local service if it is not already running.
