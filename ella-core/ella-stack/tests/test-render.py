"""Render all presets and reject unsafe combinations; requires Helm on PATH."""
import pathlib, subprocess, unittest

CHART = pathlib.Path(__file__).resolve().parents[1]

def render(*options, valid=True):
    run = subprocess.run(['helm', 'template', 'ella', str(CHART), '--namespace',
                          'ella-services-test', '--set', 'core.admin.password=test-only',
                          *options], capture_output=True, text=True)
    if valid and run.returncode:
        raise AssertionError(run.stderr)
    if not valid:
        assert run.returncode, 'Unsafe configuration unexpectedly rendered'
    return run.stdout

class Render(unittest.TestCase):
    def test_four_presets(self):
        for topology in ('standalone', 'ha'):
            for mode in ('internet', 'internet-ims-sms'):
                with self.subTest(topology=topology, mode=mode):
                    text = render('-f', str(CHART/'examples'/f'{topology}-{mode}.yaml'))
                    self.assertIn('replicas: '+('3' if topology == 'ha' else '1'), text)
                    self.assertIn('ella-core-bootstrap', text)
                    self.assertIn('MEMBER_DISPLAY_NAME_TEMPLATE', text)
                    self.assertIn('"{pod}.{namespace}"', text)
                    self.assertEqual('image: "ghcr.io/ellanetworks/ella-ims:' in text,
                                     mode == 'internet-ims-sms')
                    self.assertEqual('image: "ghcr.io/ellanetworks/ella-smsc:' in text,
                                     mode == 'internet-ims-sms')
                    if mode == 'internet-ims-sms':
                        self.assertIn("k8s.v1.cni.cncf.io/networks: 'ella-core-n6'", text)
                        self.assertIn('address: "10.6.0.6"', text)
                        self.assertIn('ip address replace 10.6.0.6/$prefix dev net1', text)

    def test_service_types(self):
        for kind in ('ClusterIP', 'NodePort', 'LoadBalancer'):
            text = render('--set', 'phones.enabled=true,core.provisioning.enabled=true',
                          '--set', f'core.service.type={kind},phones.service.type={kind}')
            self.assertIn('type: '+kind, text)

    def test_optional_native_simulators(self):
        text = render('--set', 'ueransim.enabled=true,packetrusher.enabled=true,phones.enabled=true,core.provisioning.enabled=true')
        self.assertIn('name: ella-ueransim', text)
        self.assertIn('name: ella-packetrusher', text)
        self.assertIn('"backend": "ebpf"', text)
        self.assertIn('interfaces:\n      n2: {name: net2}\n      n3: {name: net2}', text)
        self.assertGreaterEqual(text.count('ella-core-n2n3'), 4)
        self.assertIn('10.211.0.2,10.211.0.3,10.211.0.4', text)
        self.assertIn('N2N3_ADDRESS', text)
        self.assertNotIn('apiTokenSecret', text)
        render('--set', 'packetrusher.enabled=true,packetrusher.backend=auto', valid=False)

    def test_member_display_name_template_is_configurable(self):
        text = render('--set-json', 'core.memberDisplayName.template="{namespace}-{pod}"')
        self.assertIn('value: "{namespace}-{pod}"', text)
        disabled = render('--set', 'core.memberDisplayName.enabled=false')
        self.assertIn('MEMBER_DISPLAY_NAME_ENABLED, value: "false"', disabled)

    def test_controller_logs_have_timestamps_and_actionable_events(self):
        text = render('-f', str(CHART/'examples'/'ha-internet-ims-sms.yaml'))
        for message in ('date -u', 'Active Core leader changed',
                        'No ready Core leader found', 'Reconciled Service selector',
                        'UE return routes', 'IMS Diameter peer', 'command failed exit='):
            with self.subTest(message=message):
                self.assertIn(message, text)

    def test_n6_gateway_is_separate_from_controller(self):
        text = render('-f', str(CHART/'examples'/'ha-internet-ims-sms.yaml'))
        self.assertIn('name: ella-core-n6-gateway', text)
        self.assertIn('app: ella-core-n6-gateway', text)
        self.assertIn('N6_GATEWAY_ENABLED, value: "true"', text)
        controller = text.split('kind: Deployment\nmetadata: {name: ella-core-controller}', 1)[1].split('\n---', 1)[0]
        gateway = text.split('kind: Deployment\nmetadata: {name: ella-core-n6-gateway}', 1)[1].split('\n---', 1)[0]
        self.assertIn('securityContext: {privileged: false}', controller)
        self.assertNotIn('k8s.v1.cni.cncf.io/networks', controller)
        self.assertIn('securityContext: {privileged: true}', gateway)
        self.assertIn('k8s.v1.cni.cncf.io/networks: "ella-core-n6"', gateway)
        standalone = render('--set', 'core.topology=standalone,core.n6Gateway.enabled=false,core.controller.gatewayEnabled=false')
        self.assertNotIn('ella-core-n6-gateway', standalone)
        self.assertIn('N6_GATEWAY_ENABLED, value: "false"', standalone)

    def test_invalid_combinations(self):
        for values in ('global.mode=invalid', 'core.topology=invalid',
                       'core.topology=ha,global.network.type=bridge',
                       'global.mode=internet-ims-sms,ims.enabled=false',
                       'core.topology=ha,core.controller.enabled=false',
                       'phones.enabled=true,core.provisioning.enabled=false'):
            with self.subTest(values=values):
                render('--set', values, valid=False)

if __name__ == '__main__':
    unittest.main()
