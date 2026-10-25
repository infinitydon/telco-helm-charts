# Ella Core integration lab

This chart deploys the pinned v1.20.0 Core used by the IMS/SMSC integration tests, its Multus attachments, a permanent troubleshooting sidecar and the optional tester pod. The Core database is ephemeral: uninstalling/recreating the lab resets its configuration. The full ella-core-5g-chart is a separate HA/PVC deployment; it also supports the configurable troubleshooting sidecar.

From the repository's ella-core directory (custom runtime images are pulled from GHCR):

```sh
helm upgrade --install core ./ella-core-lab -n ella-services-test --create-namespace --set bootstrap.enabled=false --wait
helm upgrade --install core-ui ./ella-core-ui -n ella-services-test -f tests/services/core-ui-values.yaml --wait
helm upgrade --install ims ./ella-ims -n ella-services-test -f tests/services/ims-values.yaml --wait
helm upgrade --install smsc ./ella-smsc -n ella-services-test --wait
helm upgrade core ./ella-core-lab -n ella-services-test --reuse-values \
  --set bootstrap.enabled=true --set-file bootstrap.password=/secure/ella-admin-password --wait
helm upgrade --install ue ./ue-phones -n ella-services-test --wait
```

Use Helm 3 with --wait; on Helm 4 use --wait=legacy. The newer watcher strategy stalled during the recorded lab upgrade, while the legacy strategy completed. No host-side provisioning script is required: the post-install/post-upgrade Job runs Python inside Kubernetes. It initializes or logs in, configures Core/IMS/SMSC and idempotently provisions the 36 lab subscriber identities. bootstrap.email defaults to lab@example.com. Keep the password input outside Git. Alternatively set bootstrap.existingSecret to a Secret with email/password keys, rather than supplying bootstrap.password.

Keep bootstrap disabled until IMS/SMSC and their UI/API Services exist. Repeating the enabled upgrade restores subscribers deleted by the registration scenarios. Set bootstrap.coreApi/imsApi/smscApi and the address-host values for different release names. The headless ella-core-lab-diameter Service resolves to the current Core pod IP, allowing UE coreN2 to use DNS instead of a hardcoded pod address.

## Troubleshooting

```sh
kubectl -n ella-services-test exec -it deployment/ella-core-lab -c troubleshoot -- bash
# Inside the sidecar:
curl http://127.0.0.1:5002/api/v1/status
ip address
ip route show table all
ss -lnp
tcpdump -ni any 'sctp or udp port 2152'
```

The sidecar shares Core's network namespace and, by default, process namespace. The config is mounted read-only at /config; it does not mount the database. It includes bash, curl, dig, ip, ss and tcpdump. It runs with NET_ADMIN/NET_RAW for network diagnosis, rather than privileged mode. Configure troubleshooting.enabled/image/shareProcessNamespace/resources in values.yaml. The pinned netshoot image is overrideable.

In this lab, the same sidecar also installs the source route from the internet UE pool to the N6 gateway. Keep it enabled when using internetRoute.enabled, or provide the route externally. The full HA chart's diagnostic sidecar only provides tools and does not install lab-specific routes.

The N6 and RAN bridges are node-local, so Core, IMS and UE pods must share the selected node. tester.enabled creates the standalone integration runner; disable it when no tests are needed. The tester image is published on GHCR. Configure tester.image/pullPolicy to override it and tester.imagePullSecrets for a private registry. The UE chart accepts imagePullSecrets independently.

## Remove

```sh
helm uninstall ue ims smsc core-ui core -n ella-services-test
```

This removes the lab workloads and their chart-managed resources. IMS/SMSC PVCs belong to their respective charts; back up any data you need before a clean reset.

## Select a deployment mode (Linux)

Run these commands from the repository's ella-core directory with Helm, kubectl and an existing kubeconfig. Store the admin password in a protected file outside Git. Installation/provisioning is handled by Helm; optional tests use python3.

### Internet only

~~~sh
helm upgrade --install core ./ella-core-lab -n ella-services-test --create-namespace \
  -f ella-core-lab/examples/internet.yaml --set bootstrap.enabled=false --wait
helm upgrade --install core-ui ./ella-core-ui -n ella-services-test --wait
helm upgrade core ./ella-core-lab -n ella-services-test --reuse-values \
  --set bootstrap.enabled=true --set-file bootstrap.password=/secure/ella-admin-password --wait
helm upgrade --install ue ./ue-phones -n ella-services-test \
  -f ue-phones/examples/internet.yaml --wait
python3 ue-phones/tests/internet-smoke.py --host <node-ip>
~~~

Do not install IMS/SMSC for this mode. Bootstrap contacts only Core, provisions only the internet DNN/policy, and creates the lab subscribers. Each UE requests one internet PDU session without NAS SMS capability. No IMS TUN, P-CSCF discovery, SIP client or IPsec resources are created. Each UI opens the Browser app and hides call/message/IMS-registration controls.

### Internet, IMS and NAS SMS

~~~sh
helm upgrade --install core ./ella-core-lab -n ella-services-test --create-namespace --set bootstrap.enabled=false --wait
helm upgrade --install core-ui ./ella-core-ui -n ella-services-test --wait
helm upgrade --install ims ./ella-ims -n ella-services-test -f tests/services/ims-values.yaml --wait
helm upgrade --install smsc ./ella-smsc -n ella-services-test --wait
helm upgrade core ./ella-core-lab -n ella-services-test --reuse-values \
  -f ella-core-lab/examples/internet-ims-sms.yaml --set bootstrap.enabled=true \
  --set-file bootstrap.password=/secure/ella-admin-password --wait
helm upgrade --install ue ./ue-phones -n ella-services-test \
  -f ue-phones/examples/internet-ims-sms.yaml --wait
python3 ue-phones/tests/smoke.py --network
~~~

The default mode is internet-ims-sms for backward compatibility. Keep Core bootstrap.mode and UE mode aligned. Both accept only internet or internet-ims-sms. Switching the UE mode recreates its pods and clears their ephemeral browser profiles/history. Provisioning is additive: switching an existing Core to internet does not delete previous IMS policies, service peers or persistent IMS/SMSC data. Omit those releases on a fresh internet-only install; on an existing lab stop/uninstall them separately when desired. Never run the scenario tester concurrently with persistent UEs using the same IMSIs.
