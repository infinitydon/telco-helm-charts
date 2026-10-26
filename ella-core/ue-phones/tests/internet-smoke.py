"""Internet-only acceptance checks. Run with python3; requires kubectl and a provisioned lab."""
import argparse,json,pathlib,subprocess,urllib.request,urllib.error
p=argparse.ArgumentParser();p.add_argument('--release',default='ue');p.add_argument('--host',default='192.168.88.165');p.add_argument('--icmp-host',default='8.8.8.8');p.add_argument('--kubeconfig');p.add_argument('--namespace',default='ella-services-test');p.add_argument('--output',default='internet-results.json');a=p.parse_args()
k=['kubectl']+(['--kubeconfig',a.kubeconfig] if a.kubeconfig else [])+['-n',a.namespace]
results=[]
def command(deployment,container,*args):
 return subprocess.check_output(k+['exec','deployment/'+deployment,'-c',container,'--',*args],text=True,timeout=30).strip()
def passed(name):results.append({'check':name,'passed':True});print('PASS '+name,flush=True)
for id,port,dep in [('1',30880,a.release+'-ue-a'),('2',30881,a.release+'-ue-b')]:
 base='http://'+a.host+':'+str(port)
 with urllib.request.urlopen(base+'/api/state',timeout=10) as r:state=json.load(r)
 phone=state['phones'][0]
 assert state['ready'] and state['mode']=='internet' and phone['internetIp'] and not phone['registered'] and not phone['nas'] and not phone['ip']
 passed(dep+' internet attached without IMS/SMS')
 links=json.loads(command(dep,'phone','ip','-j','address'))
 assert any(x['ifname']=='ellaweb0' for x in links) and not any(x['ifname'].startswith('ellatesterims') for x in links)
 assert not command(dep,'phone','ip','xfrm','state')
 passed(dep+' internet TUN only; no IMS TUN or IPsec state')
 for action in ('register','sms','call'):
  req=urllib.request.Request(base+'/api/action',data=json.dumps({'phone':id,'action':action}).encode(),headers={'Content-Type':'application/json'})
  try:urllib.request.urlopen(req,timeout=10);raise AssertionError(action+' was accepted')
  except urllib.error.HTTPError as e:assert e.code==403
 passed(dep+' IMS/SMS actions rejected')
 command(dep,'phone','ping','-I',phone['internetIp'],'-c','2','-W','3',a.icmp_host);passed(dep+' public ICMP via UE')
 assert command(dep,'phone','dig','-b',phone['internetIp'],'@8.8.8.8','example.com','+short','+time=3','+tries=1')
 passed(dep+' public DNS via UE')
 assert command(dep,'browser','curl','-fsS','--socks5-hostname','127.0.0.1:1080','--max-time','20','-o','/dev/null','-w','%{http_code}','https://example.com')=='200'
 passed(dep+' Chromium UID HTTPS through UE proxy')
pathlib.Path(a.output).write_text(json.dumps(results,indent=2)+'\n',encoding='utf8');print(str(len(results))+'/'+str(len(results))+' passed')
