"""Run real Core tester integration scenarios using kubectl (Python 3, any OS)."""
import argparse, json, os, pathlib, subprocess, sys, urllib.request

ESSENTIAL=['sms/5g_mo_mt','sms/4g_mo_mt','ims/5g_call','ims/4g_call']
EXTENDED=[f'sms/{access}_{test}' for test in ('mo_mt','idle_recipient','injected','memory_full','switched_off','back_to_back','unserved_service_centre','not_granted') for access in ('5g','4g')]
EXTENDED += ['ims/5g_registration','ims/5g_call','ims/4g_registration','ims/4g_call']
EXTENDED += [f'sms/{access}_{test}' for test in ('absent_then_alert','withdrawal') for access in ('5g','4g')]
p=argparse.ArgumentParser();p.add_argument('--core-selector',default='app.kubernetes.io/name=ella-core');p.add_argument('--core-service',default='ella-core');p.add_argument('--smsc-service',default='ella-ella-smsc');p.add_argument('--namespace',default='ella-services-test');p.add_argument('--kubeconfig');p.add_argument('--core-api',default='http://192.168.88.165:30502');p.add_argument('--email',default='lab@example.com');p.add_argument('--output',default='./integration-results');p.add_argument('--scenario',action='append')
p.add_argument('--suite',choices=['essential','extended'],default='essential',help='Essential: bidirectional NAS SMS and IMS calls on 5G/4G; extended: all 24 protocol scenarios')
a=p.parse_args();out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=True)
k=['kubectl']+(['--kubeconfig',a.kubeconfig] if a.kubeconfig else [])+['-n',a.namespace]
def get(*args):return json.loads(subprocess.check_output(k+list(args),text=True))
owners=get('get','pods','-l','app.kubernetes.io/name in (ue-phones,ueransim,packetrusher)','-o','json')['items']
owners=[x['metadata']['name'] for x in owners if x.get('status',{}).get('phase') not in ('Succeeded','Failed')]
if owners:sys.exit('Pause UE phone/UERANSIM/PacketRusher deployments and wait for their Pods to stop before protocol tests (shared test IMSIs): '+', '.join(owners))
core=next(p for p in get('get','pods','-l',a.core_selector,'-o','json')['items'] if p.get('status',{}).get('phase')=='Running' and not p['metadata'].get('deletionTimestamp'))
# Follow the consolidated leader Service when HA is active.
try:
    slices=get('get','endpointslices','-l','kubernetes.io/service-name='+a.core_service,'-o','json')
    addresses={ip for item in slices['items'] for e in item['endpoints'] for ip in e['addresses']}
    core=next(p for p in get('get','pods','-l',a.core_selector,'-o','json')['items'] if p.get('status',{}).get('podIP') in addresses and not p['metadata'].get('deletionTimestamp'))
except (StopIteration,subprocess.CalledProcessError):pass
tester=get('get','pod','ella-services-tester','-o','json')
n3=next((x['ips'][0] for x in json.loads(tester['metadata'].get('annotations',{}).get('k8s.v1.cni.cncf.io/network-status','[]')) if x.get('interface')=='net1'),tester['status']['podIP'])
password=os.environ.get('ELLA_LAB_PASSWORD');
if not password:sys.exit('Set ELLA_LAB_PASSWORD in the environment')
request=urllib.request.Request(a.core_api+'/api/v1/auth/login',data=json.dumps({'email':a.email,'password':password}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=30) as response:token=json.load(response)['result']['token']
results=[]
for scenario in a.scenario or (ESSENTIAL if a.suite=='essential' else EXTENDED):
    port=36412 if '/4g_' in scenario else 38412
    cmd=k+['exec','ella-services-tester','--','core-tester','run',scenario,'--ella-core-n2-address',core['status']['podIP']+':'+str(port),'--gnb',f"lab,n2={tester['status']['podIP']},n3={n3}",'--ip-version','ipv4','--ella-api-address','http://'+a.core_service+':5002','--ella-api-token',token]
    if scenario.startswith('sms/'):cmd+=['--smsc-api-address','http://'+a.smsc_service+':5010']
    try:
        run=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=300)
        code,log=run.returncode,run.stdout
    except subprocess.TimeoutExpired as error:code,log=124,str(error.stdout or 'Scenario timed out')
    (out/(scenario.replace('/','-')+'.log')).write_text(log.replace(token,'<redacted>').replace(password,'<redacted>'),encoding='utf8')
    results.append({'scenario':scenario,'exitCode':code,'passed':code==0})
    (out/'results.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf8')
    print(f"{'PASS' if code==0 else 'FAIL'} {scenario} (exit {code})",flush=True)
print(f"{sum(r['passed'] for r in results)}/{len(results)} passed",flush=True)
sys.exit(0 if all(r['passed'] for r in results) else 1)
