"""Essential native UE registration, PDU and bound-source data-path checks."""
import argparse,ipaddress,json,pathlib,subprocess,time
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--release',default='ella');p.add_argument('--namespace',default='ella-services-test')
p.add_argument('--kubeconfig');p.add_argument('--ueransim-release');p.add_argument('--packetrusher-release')
p.add_argument('--simulator',choices=['all','ueransim','packetrusher'],default='all')
p.add_argument('--ue-pool',default='10.45.0.0/16');p.add_argument('--output',default='simulator-results.json')
a=p.parse_args();results=[]
k=['kubectl']+(['--kubeconfig',a.kubeconfig] if a.kubeconfig else [])+['-n',a.namespace]
def get(*args):return json.loads(subprocess.check_output(k+list(args),text=True))
def execute(pod,*args,input=None,required=True):
    run=subprocess.run(k+['exec']+(['-i'] if input else [])+[pod,'--',*args],input=input,capture_output=True,text=True,timeout=40)
    if required and run.returncode:raise AssertionError(run.stderr+' '+run.stdout)
    return run.stdout
def passed(kind,check,**details):
    results.append({'simulator':kind,'check':check,'passed':True,**details});print('PASS '+kind+': '+check,flush=True)
try:
    for kind in (['ueransim','packetrusher'] if a.simulator=='all' else [a.simulator]):
        release=getattr(a,kind+'_release') or a.release
        pods=get('get','pods','-l',f'app.kubernetes.io/name={kind},app.kubernetes.io/instance={release}','-o','json')['items']
        pod=next(x for x in pods if not x['metadata'].get('deletionTimestamp'))
        name=pod['metadata']['name'];deadline=time.monotonic()+180
        while True:
            try:
                state=json.loads(execute(name,'curl','-fsS','--max-time','3','http://127.0.0.1:8080/healthz'))
                assert state['ready'] and state['ueIPv4'];break
            except (AssertionError,ValueError):
                if time.monotonic()>deadline:raise
                time.sleep(2)
        ip=state['ueIPv4'][0];assert ipaddress.ip_address(ip) in ipaddress.ip_network(a.ue_pool)
        passed(kind,'UE address allocated',ueIP=ip,coreIP=state['coreIP'],generation=state['generation'],podUID=pod['metadata']['uid'])
        if kind=='ueransim':
            version=execute(name,'nr-gnb','--version',required=False).strip();assert version=='v3.3.0'
            settings=json.loads(execute(name,'cat','/settings/settings.json'))
            status=execute(name,'nr-cli','imsi-'+settings['subscriber']['imsi'],'--exec','status')
            assert 'MM-REGISTERED/NORMAL-SERVICE' in status and 'CM-CONNECTED' in status
        else:
            version=execute(name,'/packetrusher/packetrusher','--version').strip();assert version.endswith('v2.0.0')
            status=json.loads(execute(name,'/packetrusher/packetrusher','control','--socket','/run/simulator/control.sock','--ue','1','--action','wait','--timeout','10s'))
            assert status['ues'][0]['ready'] and status['ues'][0]['active_pdu_sessions']
            proof=json.loads(execute(name,'python3','-',input=pathlib.Path(__file__).with_name('probe-ebpf.py').read_text()))
            passed(kind,'Own eBPF programs attached (no fallback)',**proof)
        passed(kind,'Stable release, registered and PDU established',version=version)
        execute(name,'ping','-I',ip,'-c','2','-W','3','8.8.8.8');passed(kind,'ICMP through UE')
        assert execute(name,'dig','-b',ip,'@8.8.8.8','example.com','+short','+time=3','+tries=2').strip()
        passed(kind,'DNS through UE')
        assert execute(name,'curl','-fsS','--interface',ip,'--connect-timeout','5','--max-time','20','-o','/dev/null','-w','%{http_code}','https://example.com')=='200'
        passed(kind,'HTTPS through UE')
except Exception as error:
    results.append({'passed':False,'error':str(error)});raise
finally:pathlib.Path(a.output).write_text(json.dumps(results,indent=2)+'\n',encoding='utf8')
print(f'{len(results)}/{len(results)} passed')
