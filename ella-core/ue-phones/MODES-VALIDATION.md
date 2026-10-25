# Mode and Linux validation — 25 October 2026

Chart ue-phones 0.4.1 and ella-core-lab 0.2.0 support internet and internet-ims-sms. The default remains internet-ims-sms. Source, Helm schemas, templates, bootstrap and phone UI were reviewed together; invalid mode values are rejected by Helm.

The new public image ghcr.io/infinitydon/ella-ue-phones:0.4.1 was built on Linux, pushed and deployed from GHCR. Tested manifest: sha256:661ceb613a24674a8c0836bb3966ed72a0f689a289a40da90f02a52c5ae65f51. Chromium remains on the previously validated 0.3.4 image.

## Internet only

Stopped both IMS/SMSC deployments and both old UEs. Upgraded Core with bootstrap.mode=internet; its Helm hook succeeded without contacting either service. Upgraded UEs with mode=internet and the new image. No IMS/SMSC replicas were running during acceptance tests.

12/12 checks passed using python3 and kubectl on the Ubuntu control-plane VM: both UEs attached without NAS SMS capability or IMS registration, only ellaweb0 was created, no ellatesterims interface or kernel IPsec state existed, register/SMS/call API actions returned 403, and each UE passed public ICMP, DNS and HTTPS through its own proxy. See [internet-results.json](tests/internet-results.json).

The first connectivity probe ran during gateway replacement; the old gateway's neighbor mapping had not settled and ICMP failed. After rollout/neighbor convergence the complete 12-check run passed. Interface and policy inspection plus gateway capture confirmed the actual N6/GTP data path. Tests require the full gateway/Core/UE rollout and working public DNS/HTTPS.

Browser UI inspection confirmed Browser is selected automatically, the internet IP is shown, and registration/call/message controls are hidden. Internet-only bootstrap was tested as an upgrade of the existing Core; it deliberately preserves earlier service policies/peers. The documented fresh install omits IMS/SMSC releases and provisions only the internet DNN/policy.

## Internet plus IMS/SMS

Restored IMS/SMSC, upgraded Core with bootstrap.mode=internet-ims-sms and the UEs with matching mode. 22/22 Linux phone/data-path checks passed: bidirectional accented NAS SMS and receipt, both IMS call directions with confirmed voice-QFI traffic, registration cycling, per-UE HTTPS, browser direct-egress rejection and independent tunnel failure/recovery. Both Helm API tests passed. See [combined-mode-results.json](tests/combined-mode-results.json). The lab is left running in combined mode.

## Linux support and source checks

Removed all seven legacy PowerShell scripts introduced under ella-core. Helm is the installer/provisioner; optional acceptance tests are standard-library Python 3, and image builds use Linux Docker/Buildah. The Ella Core tree has no .ps1/.bat/.cmd files or Windows-specific executable/path commands. Historical validation notes retain the actual client versions used during earlier runs. LF checkout rules cover shell, Python and Dockerfiles.

The new mode/action Go tests and existing browser/reader Go tests passed during the Linux image build. Six charts linted successfully; both mode schemas reject invalid values. The independent upstream 24-scenario runner was previously validated and its image is unchanged by this update.

Two Python bootstrap tests passed on Linux against an initially empty API fixture: internet creates only the internet DNN and never contacts IMS/SMSC or service-related Core endpoints; combined mode creates both DNNs and provisions both services. The mode-change UI reloads when its state reports a different mode, preventing stale hidden controls after switching.

Final 0.4.1 validation repeated both acceptance suites successfully. The already-open internet-only UI reloaded automatically after switching to combined mode and restored the Calls, Messages and IMS registration controls. Review also corrected the fresh install order: install Core with bootstrap disabled, create the UI/API Service, then enable the provisioning hook.
