"""Essential live checks for either topology; no subscriber edits or UE restarts."""
import argparse,json,pathlib,subprocess,sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--release',default='ella');p.add_argument('--namespace',default='ella-services-test')
p.add_argument('--host',required=True);p.add_argument('--kubeconfig')
p.add_argument('--mode',choices=['internet','internet-ims-sms'])
p.add_argument('--output',default='stack-smoke-results.json')
a=p.parse_args()
helm=['helm']+(['--kubeconfig',a.kubeconfig] if a.kubeconfig else [])
mode=a.mode
if not mode:
    values=json.loads(subprocess.check_output(helm+['get','values',a.release,'-n',a.namespace,'-o','json'],text=True)) or {}
    mode=values.get('global',{}).get('mode','internet')
if mode not in ('internet','internet-ims-sms'):p.error('Unsupported installed mode: '+str(mode))
print('Essential checks: '+mode+' (standalone or HA)',flush=True)
subprocess.run(helm+['test',a.release,'-n',a.namespace,'--timeout','90s'],check=True)
tests=pathlib.Path(__file__).resolve().parents[2]/'ue-phones/tests'
cmd=[sys.executable,str(tests/('internet-smoke.py' if mode=='internet' else 'smoke.py')),
     '--release',a.release,'--namespace',a.namespace,'--output',a.output]
if a.kubeconfig:cmd+=['--kubeconfig',a.kubeconfig]
if mode=='internet':cmd+=['--host',a.host]
else:cmd+=['--phone-a',f'http://{a.host}:30880','--phone-b',f'http://{a.host}:30881','--suite','essential']
sys.exit(subprocess.call(cmd))
