import json, os, socket, time, urllib.request

CORE=os.environ['CORE_API']; IMS=os.environ['IMS_API']; SMSC=os.environ['SMSC_API']
headers={}
def api(base, method, path, body=None, auth=False):
    data=None if body is None else json.dumps(body).encode()
    request=urllib.request.Request(base+'/api/v1/'+path, data=data, method=method, headers={'Content-Type':'application/json', **(headers if auth else {})})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response).get('result', {})
for base in (CORE, IMS, SMSC):
    for attempt in range(120):
        try: api(base,'GET','status' if base==CORE else 'operator'); break
        except Exception:
            if attempt==119: raise
            time.sleep(1)
status=api(CORE,'GET','status')
credentials={'email':os.environ['ADMIN_EMAIL'],'password':os.environ['ADMIN_PASSWORD']}
auth=api(CORE,'POST','auth/login' if status['initialized'] else 'init',credentials)
headers['Authorization']='Bearer '+auth['token']
def core(method,path,body=None): return api(CORE,method,path,body,True)
def ensure(path,name,body):
    if not any(x['name']==name for x in core('GET',path).get('items',[])): core('POST',path,body)
operator=core('GET','operator')
if operator['id']['mcc']!='001' or operator['id']['mnc']!='01': core('PUT','operator/id',{'mcc':'001','mnc':'01'})
core('PUT','operator/tracking',{'supportedTacs':['000001']})
ensure('profiles','default',{'name':'default','ue_ambr_uplink':'100 Mbps','ue_ambr_downlink':'100 Mbps'})
ensure('slices','default',{'name':'default','sst':1,'sd':'102030'})
core('PUT','slices/default',{'sst':1,'sd':'102030'})
for dn,pool in [('internet','10.45.0.0/16'),('ims','10.60.0.0/16')]:
    ensure('networking/data-networks',dn,{'name':dn,'ipv4_pool':pool,'dns':'8.8.8.8','mtu':1500})
    name='default' if dn=='internet' else 'ims'
    ensure('policies',name,{'name':name,'profile_name':'default','slice_name':'default','data_network_name':dn,'session_ambr_uplink':'100 Mbps','session_ambr_downlink':'100 Mbps','var5qi':9 if dn=='internet' else 5,'arp':8})
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
peer(IMS,'diameter/peers',{'host':'','address':socket.gethostbyname(os.environ['CORE_ADDRESS_HOST']),'port':3868,'transport':'sctp','applications':['cx','rx']})
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
print('Core, IMS and SMSC provisioned; 36 lab subscriber identities available.')
