# free5GC Charging Portal Helm Chart

This chart deploys the lab top-up portal for free5GC CHF charging data.

The portal expects an existing free5GC deployment with MongoDB and, for live session refresh, CHF. It updates:

`policyData.ues.chargingData`

and can notify CHF with:

`PUT /nchf-convergedcharging/v3/recharging/{ueId}?ratingGroup={ratingGroup}`

## Install

```bash
helm upgrade --install free5gc-charging-portal ./free5gc-charging-portal \
  --namespace free5gc \
  --create-namespace \
  --set config.mongoUri=mongodb://mongodb:27017 \
  --set config.chfBaseUrl=http://chf:8000 \
  --set auth.operatorPin=change-me
```

If the GHCR package is still private, create a pull secret in the target namespace and add:

```bash
--set imagePullSecrets[0].name=ghcr-pull
```

For the lab NodePort default:

```text
http://<node-ip>:31380/
```

## Notes

- The image tag is pinned to `v0.1.1`; do not use bare `latest`.
- `auth.existingSecret` can be used instead of putting PIN/token values in Helm values.
- Self-service top-up is fictitious/demo behavior and can be disabled with `config.endUserSelfTopup=false`.
