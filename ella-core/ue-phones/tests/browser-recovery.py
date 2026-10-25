"""Deliberate browser-sidecar fault test. Open a public webpage before running."""
import argparse, json, pathlib, subprocess, time, urllib.request, urllib.parse
p=argparse.ArgumentParser();p.add_argument('--component',choices=['Chromium','websockify','x11vnc','Xvfb'],default='Chromium');p.add_argument('--freeze',action='store_true');p.add_argument('--kubeconfig');p.add_argument('--namespace',default='ella-services-test');p.add_argument('--url',default='http://192.168.88.165:30880');p.add_argument('--output',default='browser-recovery.json');a=p.parse_args()
k=['kubectl']+(['--kubeconfig',a.kubeconfig] if a.kubeconfig else [])+['-n',a.namespace]
def run(*args,required=True):
    result=subprocess.run(k+list(args),capture_output=True,text=True,timeout=15)
    if required and result.returncode:raise RuntimeError(result.stderr)
    return result.stdout

def pod():
    return next(p for p in json.loads(run('get','pods','-l','ella-phone=ue-a','-o','json'))['items'] if not p['metadata'].get('deletionTimestamp'))
def containers(value):return {c['name']:c for c in value['status']['containerStatuses']}
def browser(*args):return run('exec','deployment/ue-ue-a','-c','browser','--',*args)
def phone():
    with urllib.request.urlopen(a.url+'/api/state',timeout=3) as r:return json.load(r)['phones'][0]
def await_value(check,seconds=90):
    limit=time.monotonic()+seconds
    while time.monotonic()<limit:
        try:
            value=check()
            if value:return value
        except Exception:pass
        time.sleep(1)
    raise AssertionError('Recovery condition timed out')

before=pod();counts=containers(before);state=phone()
assert state['registered'] and state['nas'], 'Register the UE before testing browser recovery'
last=await_value(lambda: browser('/usr/local/bin/browser-state','read').strip() if browser('/usr/local/bin/browser-state','read').strip().startswith('http') else None,15)
marker='recovery-'+str(time.time_ns())
browser('sh','-ec','printf %s '+marker+' > /home/browser/profile/.recovery-marker')
start=time.monotonic();signal='STOP' if a.freeze else 'KILL'
browser('bash','-ec','kill -'+signal+' "$(cat /tmp/browser-'+a.component+'.pid)"')
try:
    def recovered():
        current=pod();c=containers(current)
        return current if c['browser']['restartCount']>counts['browser']['restartCount'] and c['browser'].get('ready') and c['browser'].get('started') else None
    after=await_value(recovered);new_counts=containers(after)
    assert after['metadata']['uid']==before['metadata']['uid'], 'Pod was replaced instead of recovering the browser'
    assert new_counts['phone']['restartCount']==counts['phone']['restartCount'], 'UE container restarted'
    assert browser('cat','/home/browser/profile/.recovery-marker')==marker, 'Profile did not survive'
    def restored():
        pages=json.loads(browser('curl','-fsS','http://127.0.0.1:9222/json/list'))
        return next((x for x in pages if x.get('type')=='page' and urllib.parse.urlsplit(x.get('url','')).hostname==urllib.parse.urlsplit(last).hostname),None)
    page=await_value(restored,30);end=await_value(lambda:phone())
    assert end['registered'] and end['nas'] and end['internetIp']==state['internetIp'], 'UE state changed'
    result={'fault':signal+' '+a.component,'passed':True,'recoverySeconds':round(time.monotonic()-start,1),'browserRestartBefore':counts['browser']['restartCount'],'browserRestartAfter':new_counts['browser']['restartCount'],'ueRestartCount':new_counts['phone']['restartCount'],'profilePreserved':True,'restoredHost':urllib.parse.urlsplit(page['url']).hostname,'ueRegistered':end['registered']}
    pathlib.Path(a.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result),flush=True)
finally:
    if a.freeze:
        try:
            if containers(pod())['browser']['restartCount']==counts['browser']['restartCount']:browser('bash','-ec','kill -CONT "$(cat /tmp/browser-'+a.component+'.pid)"')
        except Exception:pass
    run('exec','deployment/ue-ue-a','-c','browser','--','rm','-f','/home/browser/profile/.recovery-marker',required=False)
