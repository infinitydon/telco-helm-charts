import json, os, socket, time, urllib.request, urllib.error
from urllib.parse import quote
NAME=os.environ['CORE_NAME']; NS=os.environ['NAMESPACE']; DOMAIN=os.environ['CLUSTER_DOMAIN']
COUNT=int(os.environ['REPLICAS']); HA=os.environ['TOPOLOGY']=='ha'
MODE=os.environ['UE_MODE']; SERVICES=MODE=='internet-ims-sms'
headers={}
credentials={'email':os.environ['ADMIN_EMAIL'],'password':os.environ['ADMIN_PASSWORD']}
def node(i): return f'http://{NAME}-{i}.{NAME}-peers.{NS}.svc.{DOMAIN}:5002'
def api(base,method,path,body=None,auth=False):
    request=urllib.request.Request(base+'/api/v1/'+path, data=None if body is None else json.dumps(body).encode(),method=method,headers={'Content-Type':'application/json', **(headers if auth else {})})
    with urllib.request.urlopen(request,timeout=180 if path=='init' else 10) as response: return json.load(response).get('result',{})
def until(check,description,seconds=240):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        try:
            value=check()
            if value:return value
        except (urllib.error.URLError,TimeoutError,OSError):pass
        time.sleep(2)
    raise RuntimeError('Timed out: '+description)
CORE=node(0)
status=until(lambda:api(CORE,'GET','status'),'initial Core API')
# Existing clusters may have elected another node since the last install.
if HA and status.get('initialized'):
    for i in range(COUNT):
        candidate=until(lambda i=i:api(node(i),'GET','status'),f'node {i} status')
        if candidate.get('cluster',{}).get('isLeader'):CORE=node(i);status=candidate;break
FRESH=not status.get('initialized')
if FRESH:
    auth=api(CORE,'POST','init',credentials)
else:auth=api(CORE,'POST','auth/login',credentials)
headers['Authorization']='Bearer '+auth['token']
until(lambda:api(CORE,'GET','status').get('ready'),'leader ready')
if HA:
    for i in range(COUNT):
        target=node(i)
        if target==CORE:continue
        status=until(lambda:api(target,'GET','status'),f'follower {i} API')
        if not status.get('initialized'):
            token=api(CORE,'POST','cluster/pki/join-tokens',{'ttlSeconds':1800},True)['token']
            seed=CORE.removeprefix('http://').replace(':5002',':7000')
            api(target,'POST','cluster/join',{'token':token,'seedAddresses':[seed],'suffrage':'voter'})
        until(lambda:api(target,'GET','status').get('ready'),f'follower {i} joined')
        print(f'Core member {i+1} ready',flush=True)
    until(lambda:(lambda members:len(members)==COUNT and all(x.get('suffrage','').lower()=='voter' for x in members))(api(CORE,'GET','cluster/members',auth=True)),'all cluster voters')
    if os.environ.get('MEMBER_DISPLAY_NAME_ENABLED','true')=='true':
        template=os.environ.get('MEMBER_DISPLAY_NAME_TEMPLATE','{pod}.{namespace}')
        for i in range(COUNT):
            member_status=api(node(i),'GET','status').get('cluster',{})
            node_id=member_status.get('nodeId')
            if not node_id:raise RuntimeError(f'Core member {i} did not report its node ID')
            display_name=template.replace('{pod}',f'{NAME}-{i}').replace('{namespace}',NS)
            if len(display_name.encode('utf-8'))>63:
                raise RuntimeError(f'Display name for {NAME}-{i} exceeds Ella Core\'s 63-byte limit: {display_name}')
            if '{' in display_name or '}' in display_name:
                raise RuntimeError(f'Unsupported placeholder in member display-name template: {template}')
            if member_status.get('displayName')!=display_name:
                until(lambda:api(CORE,'PUT',f'cluster/members/{quote(str(node_id),safe="")}/display-name',{'displayName':display_name},True),f'set display name for {NAME}-{i}',seconds=120)
                print(f'Set Core member {NAME}-{i} display name to {display_name}',flush=True)
def core(method,path,body=None): return api(CORE,method,path,body,True)
if os.environ.get('N6_GATEWAY_ENABLED')=='true':
    nat=core('GET','networking/nat')
    if nat.get('enabled',True):
        core('PUT','networking/nat',{'enabled':False})
        print('Disabled Ella Core NAT; the separate lab N6 gateway performs internet-pool SNAT.',flush=True)
if os.environ['PROVISION']!='true':
    print('Core initialized; subscriber/service provisioning disabled.');raise SystemExit(0)
IMS=os.environ['IMS_API']; SMSC=os.environ['SMSC_API']
if SERVICES:
    for base in (IMS,SMSC):until(lambda base=base:api(base,'GET','operator'),'service API '+base)
def ensure(path,name,body):
    if not any(x['name']==name for x in core('GET',path).get('items',[])): core('POST',path,body)
operator=core('GET','operator')
if operator['id']['mcc']!='001' or operator['id']['mnc']!='01': core('PUT','operator/id',{'mcc':'001','mnc':'01'})
core('PUT','operator/tracking',{'supportedTacs':['000001']})
ensure('profiles','default',{'name':'default','ue_ambr_uplink':'100 Mbps','ue_ambr_downlink':'100 Mbps'})
ensure('slices','default',{'name':'default','sst':1,'sd':'102030'})
core('PUT','slices/default',{'sst':1,'sd':'102030'})
for dn,pool in ([('internet',os.environ.get('INTERNET_POOL','10.45.0.0/16')),('ims',os.environ.get('IMS_POOL','10.60.0.0/16'))] if SERVICES else [('internet',os.environ.get('INTERNET_POOL','10.45.0.0/16'))]):
    networks={x['name']:x for x in core('GET','networking/data-networks').get('items',[])}
    desired={'ipv4_pool':pool,'dns':'8.8.8.8','mtu':1500}
    if dn not in networks:core('POST','networking/data-networks',{'name':dn,**desired})
    elif (FRESH or os.environ.get('RECONCILE_DATA_NETWORKS')=='true') and any(networks[dn].get(k)!=v for k,v in desired.items()):
        current=networks[dn]
        if current.get('ipv4_pool')!=pool and current.get('status',{}).get('sessions',0):
            raise RuntimeError('Detach UEs before changing the '+dn+' IP pool')
        if current.get('ipv6_pool'):desired['ipv6_pool']=current['ipv6_pool']
        core('PUT','networking/data-networks/'+dn,desired)
    name='default' if dn=='internet' else 'ims'
    ensure('policies',name,{'name':name,'profile_name':'default','slice_name':'default','data_network_name':dn,'session_ambr_uplink':'100 Mbps','session_ambr_downlink':'100 Mbps','var5qi':9 if dn=='internet' else 5,'arp':8})
if SERVICES:
    core('PUT','operator/sms',{'smsNumber':'+15550000000'})
    core('PUT','operator/ims',{'pcscfAddresses':[os.environ['IMS_ADDRESS']]})
    def peer(base,path,value,authenticated=False):
        items=api(base,'GET',path,auth=authenticated).get('items',[])
        api(base,'PUT' if items else 'POST',path+'/'+str(items[0]['id']) if items else path,value,authenticated)
    peer(CORE,'operator/sms/smsc-peers',{'diameterIdentity':'smsc.node.epc.mnc001.mcc001.3gppnetwork.org','address':socket.gethostbyname(os.environ['SMSC_ADDRESS_HOST']),'port':3868,'serviceCentres':['+15550000000']},True)
    operator={'mcc':'001','mnc':'01','numbering':{'country_code':'1','national_prefix':'1','international_prefix':'011'}}
    api(IMS,'PUT','operator',operator)
    api(SMSC,'PUT','operator',{**operator,'service_centre_address':'+15550000000'})
    api(SMSC,'PUT','delivery',{'default_validity_seconds':3600,'retry_intervals_seconds':[600]})
    # Keep every Core Diameter identity reachable. Existing IMS registrations
    # remember their HSS identity even after another Core becomes Raft leader.
    peers=sorted(api(IMS,'GET','diameter/peers').get('items',[]),key=lambda x:x['id'])
    for i in range(COUNT):
        host=f'{NAME}-{i}.{NAME}-peers.{NS}.svc.{DOMAIN}'
        value={'host':'','address':socket.gethostbyname(host),'port':3868,'transport':'sctp','applications':['cx','rx'],'priority':10 if node(i)==CORE else 20}
        api(IMS,'PUT' if i<len(peers) else 'POST','diameter/peers/'+str(peers[i]['id']) if i<len(peers) else 'diameter/peers',value)
    for app in ('cx','rx'): api(IMS,'PUT','diameter/routes/'+app,{'realm':'epc.mnc001.mcc001.3gppnetwork.org'})
    api(IMS,'PUT','policy',{'interface':'rx'})
existing={x['imsi'] for x in core('GET','subscribers?per_page=100').get('items',[])}
def subscriber(imsi,number):
    if imsi not in existing:
        core('POST','subscribers',{'imsi':imsi,'key':'640f441067cd56f1474cbcacd7a0588f','opc':'cb698a2341629c3241ae01de9d89de4f','sequenceNumber':'000000000022','profile_name':'default','msisdn':number})
        existing.add(imsi)
for prefix in ('7','8'):
    for n in (100,101,200,201,300,301,400,500,501,600,700,800,900,1000,1100):
        subscriber('00101'+prefix+'9'+f'{n:08}', '' if n==600 else '+1555'+prefix+f'{n:06}')
    for n in (1,3,4): subscriber('00101'+prefix+'4000000'+f'{n:02}','+1555'+prefix+'4000'+f'{n:02}')
print(f'{MODE} provisioned; 36 lab subscriber identities available.')
