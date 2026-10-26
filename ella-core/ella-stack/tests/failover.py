"""Deliberately replace the current Core leader Pod; verify election and PVC retention."""
import argparse,json,pathlib,subprocess,time
p=argparse.ArgumentParser();p.add_argument('--namespace',default='ella-services-test');p.add_argument('--release',default='ella');p.add_argument('--before',required=True);p.add_argument('--output',default='failover.json');a=p.parse_args()
k=['kubectl','-n',a.namespace];before=json.loads(pathlib.Path(a.before).read_text());old=before['leader'];uid=next(m['uid'] for m in before['members'] if m['pod']==old);name=a.release+'-core'
def get(*args):return json.loads(subprocess.check_output(k+list(args),text=True))
start=time.monotonic();subprocess.check_call(k+['delete','pod',old,'--wait=false'])
elected=None;deadline=start+180
while time.monotonic()<deadline:
 try:
  active=get('get','service',name+'-active','-o','json')['spec']['selector']['statefulset.kubernetes.io/pod-name']
  pods=get('get','pods','-l','app.kubernetes.io/name=ella-core,app.kubernetes.io/instance='+a.release,'-o','json')['items']
  replacement=next(p for p in pods if p['metadata']['name']==old and p['metadata']['uid']!=uid)
  if active!=old and elected is None:elected=time.monotonic()-start
  if active!=old and len(pods)==3 and all(not p['metadata'].get('deletionTimestamp') and p.get('status',{}).get('containerStatuses') and all(c['ready'] for c in p['status']['containerStatuses']) for p in pods):break
 except (KeyError,StopIteration,subprocess.CalledProcessError):pass
 time.sleep(1)
else:raise AssertionError('HA failover/rejoin timed out')
claims=[]
for claim in before['claims']:
 current=get('get','pvc',claim['name'],'-o','json');assert current['metadata']['uid']==claim['uid'];claims.append(claim)
assert get('get','service',name,'-o','json')['spec']['selector']['statefulset.kubernetes.io/pod-name']==active
result={'passed':True,'oldLeader':old,'newLeader':active,'electionServiceSeconds':round(elected,1),'allMembersReadySeconds':round(time.monotonic()-start,1),'pvcUIDsPreserved':claims,'replacementUID':replacement['metadata']['uid']}
pathlib.Path(a.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result),flush=True)
