"""HTTP smoke tests for dedicated UE UIs; optional kubectl network-failure tests."""
import argparse, json, pathlib, subprocess, time, urllib.request, urllib.error
p=argparse.ArgumentParser();p.add_argument('--release',default='ue');p.add_argument('--phone-a',default='http://192.168.88.165:30880');p.add_argument('--phone-b',default='http://192.168.88.165:30881');p.add_argument('--output',default='phone-results.json');p.add_argument('--network',action='store_true');p.add_argument('--kubeconfig');p.add_argument('--namespace',default='ella-services-test');p.add_argument('--suite',choices=['essential','extended'],default='essential');a=p.parse_args()
urls={'1':a.phone_a,'2':a.phone_b};results=[]
def api(id,path,body=None):
    request=urllib.request.Request(urls[id]+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=35) as response:return json.load(response)
def state():return [api(id,'/api/state')['phones'][0] for id in ('1','2')]
def act(id,action,**extra):return api(id,'/api/action',{'phone':id,'action':action,**extra})
def passed(name):results.append({'check':name,'passed':True});print('PASS '+name,flush=True)
def await_check(name,condition):
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        if condition(state()):passed(name);return
        time.sleep(.2)
    raise AssertionError(name)
k=['kubectl']+(['--kubeconfig',a.kubeconfig] if a.kubeconfig else [])+['-n',a.namespace]
def command(deployment,container,*args,required=True):
    run=subprocess.run(k+['exec','deployment/'+deployment,'-c',container,'--',*args],capture_output=True,text=True,timeout=25)
    if required and run.returncode:raise AssertionError(run.stderr)
    return run
def curl(deployment,direct=False):
    route=['--noproxy','*','https://1.1.1.1'] if direct else ['--socks5-hostname','127.0.0.1:1080','https://example.com']
    return command(deployment,'browser','curl','-fsS','--connect-timeout','3','--max-time','10','-o','/dev/null','-w','%{http_code}',*route,required=False)
try:
    await_check('Both UEs attached with NAS SMS',lambda s:len(s)==2 and all(p['nas'] for p in s))
    for id in urls:
        if not api(id,'/api/state')['phones'][0]['registered']:act(id,'register')
    await_check('Both UEs IMS registered',lambda s:all(p['registered'] for p in s))
    for sender,receiver,text in [('1','2','Fresh A '+str(time.time_ns())),('2','1','Hi A, ça va? € '+str(time.time_ns()))]:
        number=api(receiver,'/api/state')['phones'][0]['number'];act(sender,'sms',to=number,text=text)
        await_check('NAS SMS '+sender+' to '+receiver+' received and delivered',lambda s:any(m['direction']=='received' and m['text']==text for m in s[int(receiver)-1]['messages']) and any(m['text']==text and m['status']=='delivered to UE' for m in s[int(sender)-1]['messages']))
    for sender,receiver in [('1','2'),('2','1')]:
        act(sender,'call',to=api(receiver,'/api/state')['phones'][0]['number'])
        await_check('IMS incoming '+sender+' to '+receiver,lambda s:s[int(receiver)-1]['incoming'] and s[int(receiver)-1]['call']=='early')
        act(receiver,'answer')
        await_check('IMS confirmed with bidirectional voice QFI '+sender+' to '+receiver,lambda s:all(p['call']=='confirmed' and p['tx']>5 and p['rx']>5 and isinstance(p['qfi'],list) and p['qfi'] for p in s))
        act(sender,'hangup');await_check('IMS call released '+sender+' to '+receiver,lambda s:all(p['call']=='terminated' for p in s))
    if a.suite=='extended' or a.network:
        act('1','unregister');await_check('Phone A deregistration',lambda s:not s[0]['registered'] and s[1]['registered'])
        act('1','register');await_check('Phone A reregistration',lambda s:s[0]['registered'])
    for id in urls:
        phone=api(id,'/api/state')['phones'][0];page=api(id,'/api/browse',{'phone':id,'url':'https://example.com'})
        assert page['status']==200 and page['ueIp']==phone['internetIp'] and page['text'] and page['uplinkTeid']>0 and page['downlinkTeid']>0
        passed('HTTPS reader through UE '+id)
    if a.suite=='extended' or a.network:
        try:api('1','/api/browse',{'phone':'1','url':'http://127.0.0.1'});raise AssertionError('Private destination accepted')
        except urllib.error.HTTPError as error:assert 'private and special-use' in error.read().decode();passed('Private web destination rejected')
    if a.network:
        for deployment in (a.release+'-ue-a',a.release+'-ue-b'):
            run=curl(deployment);assert run.returncode==0 and run.stdout=='200';passed(deployment+' HTTPS through UE proxy')
            assert curl(deployment,True).returncode!=0
            rules=command(deployment,'phone','iptables','-nvL','ELLA_BROWSER').stdout
            assert any(line.split()[0]!='0' for line in rules.splitlines() if 'REJECT' in line)
            passed(deployment+' direct browser egress blocked')
        try:
            command(a.release+'-ue-a','phone','ip','link','set','ellaweb0','down')
            assert curl(a.release+'-ue-a').returncode!=0;passed('UE A cannot browse while its TUN is down')
            run=curl(a.release+'-ue-b');assert run.returncode==0 and run.stdout=='200';passed('UE B unaffected by UE A tunnel interruption')
        finally:
            command(a.release+'-ue-a','phone','ip','link','set','ellaweb0','up')
            command(a.release+'-ue-a','phone','ip','route','replace','default','dev','ellaweb0','table','200')
        run=curl(a.release+'-ue-a');assert run.returncode==0 and run.stdout=='200';passed('UE A browsing recovered')
except Exception as error:
    results.append({'check':str(error),'passed':False});raise
finally:
    pathlib.Path(a.output).write_text(json.dumps(results,indent=2)+'\n',encoding='utf8')
print(f'{len(results)}/{len(results)} passed',flush=True)
