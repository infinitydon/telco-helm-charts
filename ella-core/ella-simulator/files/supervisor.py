"""Run a native gNB/UE against the active Core; reattach on endpoint changes."""
import http.server,json,os,pathlib,signal,socket,subprocess,threading,time,urllib.request
os.umask(0o077)

settings=json.loads(pathlib.Path('/settings/settings.json').read_text())
kind=settings['simulator']; sub=settings['subscriber']; gnb=settings['gnb']; session=settings['session']
for key in ('key','opc'):
    sub[key]=os.environ.get('SIM_'+key.upper(),sub.get(key,''))
out=pathlib.Path('/run/simulator');out.mkdir(parents=True,exist_ok=True)
state={'ready':False,'simulator':kind,'generation':0,'backend':settings.get('backend','tun')}
children=[];stopping=False

def addresses():
    links=json.loads(subprocess.check_output(['ip','-j','-4','address'],text=True))
    prefix='uesimtun' if kind=='ueransim' else 'val'
    return [a['local'] for link in links if link['ifname'].startswith(prefix)
            for a in link.get('addr_info',[]) if a['family']=='inet' and a['scope']=='global']

def configure(core):
    pod=(os.environ.get('N2N3_ADDRESS','') or os.environ['POD_IP']).split('/')[0];sd=int(session['sd'],16);sst=session['sst']
    core_address=select_n2_address()
    imsi=sub['imsi'].removeprefix('imsi-');mcc=sub['mcc'];mnc=sub['mnc']
    if kind=='ueransim':
        radio={'mcc':mcc,'mnc':mnc,'nci':gnb['nci'],'idLength':gnb['idLength'],'tac':int(gnb['tac'],16),
               'linkIp':'127.0.0.1','ngapIp':pod,'gtpIp':pod,'amfConfigs':[{'address':core_address,'port':38412}],
               'slices':[{'sst':sst,'sd':sd}],'ignoreStreamIds':True}
        ue={'supi':'imsi-'+imsi,'mcc':mcc,'mnc':mnc,'key':sub['key'],'op':sub['opc'],'opType':'OPC',
            'amf':sub['amf'],'imei':'356938035643803','imeiSv':'4370816125816151',
            'gnbSearchList':['127.0.0.1'],'uacAic':{'mps':False,'mcs':False},
            'uacAcc':{'normalClass':0,**{'class'+str(i):False for i in range(11,16)}},
            'sessions':[{'type':'IPv4','apn':session['dnn'],'slice':{'sst':sst,'sd':sd}}],
            'configured-nssai':[{'sst':sst,'sd':sd}],'default-nssai':[{'sst':sst,'sd':sd}],
            'integrity':{'IA1':True,'IA2':True,'IA3':True},'ciphering':{'EA1':True,'EA2':True,'EA3':True},
            'integrityMaxRate':{'uplink':'full','downlink':'full'}}
        for name,value in [('gnb',radio),('ue',ue)]:
            (out/(name+'.yaml')).write_text(json.dumps(value))
        return [['nr-gnb','-c',str(out/'gnb.yaml')],['nr-ue','-c',str(out/'ue.yaml')]]
    config={'gnodeb':{'controlif':{'ip':pod,'port':9487},'dataif':{'ip':pod,'port':2152},
                     'plmnlist':{'mcc':mcc,'mnc':mnc,'tac':gnb['tac'],'gnbidlength':24,'cellid':0,'gnbid':gnb['id']},
                     'slicesupportlist':{'sst':f'{sst:02x}','sd':session['sd']}},
            'ue':{'hplmn':{'mcc':mcc,'mnc':mnc},'msin':imsi[len(mcc+mnc):],
                  'routingindicator':'0000','protectionScheme':0,'pdusessiontype':'IPv4','tunnelmtu':1400,
                  'key':sub['key'],'opc':sub['opc'],'amf':sub['amf'],'sqn':'000000000000',
                  'dnn':session['dnn'],'snssai':{'sst':f'{sst:02x}','sd':session['sd']},
                  'integrity':{'nia0':False,'nia1':False,'nia2':True,'nia3':False},
                  'ciphering':{'nea0':True,'nea1':False,'nea2':True,'nea3':False}},
            'amfif':[{'ip':core_address,'port':38412}],'logs':{'level':4}}
    (out/'packetrusher.yaml').write_text(json.dumps(config))
    return [['/packetrusher/packetrusher','--config',str(out/'packetrusher.yaml'),
             '--tunnel-backend',settings['backend'],'--metrics-addr','127.0.0.1:9090',
             '--report-json',str(out/'report.json'),'multi-ue','-n',str(settings['ueCount']),
             '--tunnel','--tunnel-vrf=false','--control-socket',str(out/'control.sock')]]

def select_n2_address():
    addresses=[x.strip() for x in os.environ.get('CORE_N2_ADDRESSES','').split(',') if x.strip()]
    hosts=[x.strip() for x in os.environ.get('CORE_MEMBER_HOSTS','').split(',') if x.strip()]
    active_id=''
    try:
        with urllib.request.urlopen('http://'+socket.gethostbyname(os.environ['CORE_HOST'])+':'+str(settings['core']['apiPort'])+'/api/v1/status',timeout=2) as response:
            active_id=json.load(response).get('result',{}).get('cluster',{}).get('nodeId','')
    except (OSError,ValueError):
        pass
    if active_id:
        for host,address in zip(hosts,addresses):
            try:
                with urllib.request.urlopen('http://'+host+':'+str(settings['core']['apiPort'])+'/api/v1/status',timeout=2) as response:
                    if json.load(response).get('result',{}).get('cluster',{}).get('nodeId')==active_id:return address
            except (OSError,ValueError):
                continue
    return addresses[0] if addresses else socket.gethostbyname(os.environ['CORE_HOST'])

def stop():
    state['ready']=False
    for child in reversed(children):
        if child.poll() is None:child.send_signal(signal.SIGINT)
    for child in reversed(children):
        try:child.wait(timeout=6)
        except subprocess.TimeoutExpired:child.kill();child.wait()
    children.clear()

def shutdown(*_):
    global stopping
    stopping=True

class Health(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body=json.dumps(state).encode()
        self.send_response(200 if state['ready'] else 503);self.send_header('Content-Type','application/json')
        self.end_headers();self.wfile.write(body)
    def log_message(self,*_):pass

for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,shutdown)
threading.Thread(target=http.server.ThreadingHTTPServer(('0.0.0.0',8080),Health).serve_forever,daemon=True).start()
current=None;started=0;misses=0
try:
    while not stopping:
        try:
            core=socket.gethostbyname(os.environ['CORE_HOST'])
            with urllib.request.urlopen('http://'+core+':'+str(settings['core']['apiPort'])+'/api/v1/status',timeout=2) as response:
                status=json.load(response)['result']
            cluster=status.get('cluster',{})
            if not status.get('ready') or (cluster.get('enabled') and not cluster.get('isLeader')):raise RuntimeError('Core not active/ready')
            target=(core,cluster.get('nodeId','standalone'));misses=0
            if target!=current or any(c.poll() is not None for c in children) or (children and not addresses() and time.monotonic()-started>120):
                stop();current=target;started=time.monotonic()
                state.update(coreIP=core,generation=state['generation']+1,ready=False)
                print('Starting '+kind+' against active Core '+core+' generation '+str(state['generation']),flush=True)
                for cmd in configure(core):
                    children.append(subprocess.Popen(cmd));time.sleep(1)
            ips=addresses()
            expected=1 if kind=='ueransim' else settings['ueCount']
            state.update(ready=len(ips)>=expected and all(c.poll() is None for c in children),ueIPv4=ips,pids=[c.pid for c in children])
        except (OSError,ValueError,RuntimeError,KeyError) as error:
            state['ready']=False;misses+=1
            if misses>=3 and children:stop();current=None
            print('Waiting for active Core: '+str(error),flush=True)
        time.sleep(3)
finally:stop()
