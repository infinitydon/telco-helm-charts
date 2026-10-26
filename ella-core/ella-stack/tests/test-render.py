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
                    self.assertEqual('image: "ghcr.io/ellanetworks/ella-ims:' in text,
                                     mode == 'internet-ims-sms')
                    self.assertEqual('image: "ghcr.io/ellanetworks/ella-smsc:' in text,
                                     mode == 'internet-ims-sms')

    def test_service_types(self):
        for kind in ('ClusterIP', 'NodePort', 'LoadBalancer'):
            text = render('--set', 'phones.enabled=true,core.provisioning.enabled=true',
                          '--set', f'core.service.type={kind},phones.service.type={kind}')
            self.assertIn('type: '+kind, text)

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
