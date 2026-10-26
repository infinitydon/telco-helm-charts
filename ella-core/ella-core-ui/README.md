# ella-core-ui - consolidated

This chart implementation has been replaced by [ella-stack](../ella-stack/README.md) and the single [ella-core](../ella-core/README.md) base chart. This directory is a migration pointer, not an installable chart.

Use one of the four ella-stack/examples presets for standalone or three-node HA, with internet-only or internet plus IMS/SMS. DNS-based Raft discovery, persistent storage, UI/API Service options, diagnostics and mode-aware provisioning are now in the unified implementation. IMS/SMSC and UE phones remain optional dependencies and independently installable charts.

This is an explicit migration, not a drop-in upgrade. Back up Core and IMS/SMSC data and save existing Helm values. Uninstall old releases, then install the consolidated release using the new values schema. Do not reuse a standalone database as HA or delete PVCs without a verified backup. Old chart source remains available in Git history before the consolidation commit.

The lab migration performed for this change saved Core's API backup, IMS/SMSC archives and release values/manifests outside Git before cleaning the five old lab releases.
