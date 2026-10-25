# Ella Core UI Service

Helm-managed UI/API access for an existing Core deployment. This chart creates only a Service, so changing access does not restart Core or touch its database. The full ella-core-5g-chart already includes configurable UI/API Services; this companion chart serves the independently deployed integration-lab Core or another existing deployment.

From the repository's ella-core directory:

```sh
helm upgrade --install core-ui ./ella-core-ui -n ella-services-test -f tests/services/core-ui-values.yaml
```

The lab UI is http://192.168.88.165:30502/. Use the account initialized by the lab bootstrap; credentials are not stored in this chart.

Configure access through values:

```yaml
service:
  name: ella-core-lab
  type: NodePort # ClusterIP, NodePort, LoadBalancer
  port: 5002
  targetPort: 5002
  nodePort: 30502 # 0 requests automatic allocation; ignored for ClusterIP
  annotations: {}
selector:
  app: ella-core-lab
```

For another existing Core deployment, set selector to its pod labels and targetPort to its UI/API listening port. A blank service.name defaults to RELEASE-ui. Each Service type can also be selected with --set service.type=ClusterIP or --set service.type=LoadBalancer.

Migration of an existing unmanaged Service needs --take-ownership on the first install only. The running lab has already been migrated to release core-ui; subsequent changes use an ordinary helm upgrade. No configuration script is needed. Uninstalling this release removes the UI Service but leaves Core running.
