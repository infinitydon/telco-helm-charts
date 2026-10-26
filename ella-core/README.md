# Ella Core charts

Install [ella-stack](ella-stack/README.md) for one Helm release containing Core,
its UI/API Service, diagnostics, optional IMS/SMSC, and dedicated UE phone/browser
UIs. Four presets cover standalone or three-node Core HA, each with internet-only
or internet plus IMS/SMS services. See [live validation](ella-stack/VALIDATION.md)
for results and limitations.

The [ella-core](ella-core/README.md) base chart is the single Core implementation.
[ella-ims](ella-ims), [ella-smsc](ella-smsc), and [ue-phones](ue-phones) remain
independently installable components and are dependencies of ella-stack.

The previous ella-core-5g-chart, ella-core-5g-chart-fqdn, ella-core-lab, and
ella-core-ui directories contain migration pointers only. Back up existing
databases and values before replacing those releases. Their source remains in
Git history. Tests and historical fixtures live under tests/services;
UERANSIM and PacketRusher are independently installable native simulators and
optional ella-stack components. Enable ueransim.enabled or packetrusher.enabled
with any of the four presets; see [native validation](tests/simulators/README.md).
