"""Verify live Core topology, DNS identity, leader routing and persistent claims."""
import argparse,base64,json,pathlib,subprocess,time,urllib.request
p=argparse.ArgumentParser();p.add_argument('--admin-secret');p.add_argument('--core-api',default='http://192.168.88.165:30502');p.add_argument('--release',default='ella');p.add_argument('--namespace',default='ella-services-test');p.add_argument('--topology',choices=['standalone','ha'],required=True);p.add_argument('--output',default='topology.json');a=p.parse_args()
k=['kubectl','-n',a.namespace];name=a.release+'-core'
def get(*args):return json.loads(subprocess.check_output(k+list(args),text=True))
def execute(pod,container,*args):return subprocess.check_output(k+['exec',pod,'-c',container,'--',*args],text=True,timeout=15)
pods=get('get','pods','-l','app.kubernetes.io/name=ella-core,app.kubernetes.io/instance='+a.release,'-o','json')['items'];pods=[p for p in pods if not p['metadata'].get('deletionTimestamp')]
assert len(pods)==(3 if a.topology=='ha' else 1)
records=[];claims=[]
for pod in pods:
 assert all(c['ready'] for c in pod['status']['containerStatuses'])
 status=json.loads(execute(pod['metadata']['name'],'troubleshoot','curl','-fsS','http://'+pod['status']['podIP']+':5002/api/v1/status'))['result']
 assert status['ready'] and status['cluster']['enabled']==(a.topology=='ha')
 records.append({'pod':pod['metadata']['name'],'uid':pod['metadata']['uid'],'node':pod['spec']['nodeName'],'podIP':pod['status']['podIP'],'cluster':status['cluster']})
 for v in pod['spec']['volumes']:
  if 'persistentVolumeClaim' in v:
   claim=get('get','pvc',v['persistentVolumeClaim']['claimName'],'-o','json');assert claim['status']['phase']=='Bound';claims.append({'name':claim['metadata']['name'],'uid':claim['metadata']['uid']})
leaders=[r for r in records if r['cluster'].get('isLeader') or not r['cluster']['enabled']];assert len(leaders)==1
leader=leaders[0]['pod']
for service in (name,name+'-active'):
 assert get('get','service',service,'-o','json')['spec']['selector']['statefulset.kubernetes.io/pod-name']==leader
if a.topology=='ha':assert len({r['node'] for r in records})==3
controller=get('get','pods','-l','app='+name+'-controller','-o','json')['items'][0]['metadata']['name']
route=json.loads(execute(controller,'controller','ip','-j','route','get','10.60.0.100'))[0]
expected='10.6.0.'+str(int(leader.rsplit('-',1)[1])+2);assert route['gateway']==expected
result={'topology':a.topology,'passed':True,'leader':leader,'members':records,'claims':claims,'imsReturnGateway':expected}
if a.admin_secret and a.topology=='ha':
 secret=get('get','secret',a.admin_secret,'-o','json')['data']
 credentials={key:base64.b64decode(secret[key]).decode() for key in ('email','password')}
 req=urllib.request.Request(a.core_api+'/api/v1/auth/login',data=json.dumps(credentials).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as response:token=json.load(response)['result']['token']
 req=urllib.request.Request(a.core_api+'/api/v1/cluster/members',headers={'Authorization':'Bearer '+token})
 with urllib.request.urlopen(req,timeout=30) as response:members=json.load(response)['result']
 assert len(members)==3 and all(m['suffrage'].lower()=='voter' for m in members)
 assert all('.svc.' in m['raftAddress'] for m in members)
 expected_api={r['cluster']['nodeId']:'http://'+r['podIP']+':5002' for r in records}
 deadline=time.monotonic()+60
 while any(m['apiAddress']!=expected_api[m['nodeId']] for m in members):
  assert time.monotonic()<deadline, 'Cluster member API addresses did not converge to current Pod IPs'
  time.sleep(2)
  with urllib.request.urlopen(req,timeout=30) as response:members=json.load(response)['result']
 result['raftMembers']=members
pathlib.Path(a.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print('PASS '+a.topology+': '+str(len(records))+' ready Core pods, leader '+leader+', Services/routes aligned')
