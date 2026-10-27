"""Bootstrap dependency and HA join ordering tests using empty API fixtures."""
import argparse,contextlib,io,json,os,pathlib,runpy,unittest
from unittest.mock import patch
p=argparse.ArgumentParser();p.add_argument('--script',default=str(pathlib.Path(__file__).resolve().parents[2]/'ella-core/files/bootstrap.py'));a,remaining=p.parse_known_args()
class Bootstrap(unittest.TestCase):
 def exercise(self,mode,ha=False,default_network=False,active_sessions=0,existing_core=False,n6_gateway=False,provision=True,core_nat_enabled=True):
  calls=[];ready=set();count=3 if ha else 1;nat_enabled=core_nat_enabled
  if existing_core:ready.add('http://core-0.core-peers.ns.svc.cluster.local:5002')
  def request(req,timeout):
   nonlocal nat_enabled
   base=req.full_url.split('/api/v1/')[0];path=req.full_url.split('/api/v1/')[1];body=json.loads(req.data) if req.data else None
   calls.append((base,path,req.method,body));result={}
   if path=='status':result={'initialized':base in ready,'ready':base in ready,'cluster':{'isLeader':base.endswith('-0.core-peers.ns.svc.cluster.local:5002'),'nodeId':base.split('//')[1].split('.')[0],'displayName':''}}
   elif path=='init':ready.add(base);result={'token':'test-only'}
   elif path=='auth/login':result={'token':'test-only'}
   elif path=='cluster/pki/join-tokens':result={'token':'test-join'}
   elif path=='cluster/join':ready.add(base)
   elif path=='cluster/members':result=[{'nodeId':str(i+1),'suffrage':'Voter'} for i in range(count)]
   elif path.endswith('/display-name'):result={'message':'Display name updated'}
   elif path=='networking/nat' and req.method=='GET':result={'enabled':nat_enabled}
   elif path=='networking/nat':nat_enabled=body['enabled'];result={'message':'NAT configuration updated successfully'}
   elif path=='operator' and req.method=='GET':result={'id':{'mcc':'001','mnc':'01'}}
   elif path=='networking/data-networks' and req.method=='GET' and default_network:
    result={'items':[{'name':'internet','ipv4_pool':'10.45.0.0/22','dns':'8.8.8.8','mtu':1400,'status':{'sessions':active_sessions}}]}
   elif req.method=='GET':result={'items':[]}
   return io.BytesIO(json.dumps({'result':result}).encode())
  env={'CORE_NAME':'core','NAMESPACE':'ns','CLUSTER_DOMAIN':'cluster.local','REPLICAS':str(count),'TOPOLOGY':'ha' if ha else 'standalone','UE_MODE':mode,'PROVISION':str(provision).lower(),'N6_GATEWAY_ENABLED':str(n6_gateway).lower(),'IMS_API':'http://ims','SMSC_API':'http://smsc','ADMIN_EMAIL':'lab@example.com','ADMIN_PASSWORD':'test-only','IMS_ADDRESS':'10.6.0.5','SMSC_ADDRESS_HOST':'smsc','CORE_ADDRESS_HOST':'core-active','MEMBER_DISPLAY_NAME_ENABLED':'true','MEMBER_DISPLAY_NAME_TEMPLATE':'{pod}.{namespace}'}
  if default_network:env['INTERNET_POOL']='10.208.0.0/16'
  with patch.dict(os.environ,env),patch('urllib.request.urlopen',side_effect=request),patch('socket.gethostbyname',return_value='10.0.0.1'),contextlib.redirect_stdout(io.StringIO()):
   try:runpy.run_path(a.script,run_name='__main__')
   except SystemExit as exit:
    if provision or exit.code!=0:raise
  return calls
 def test_internet_never_contacts_service_apis(self):
  calls=self.exercise('internet')
  self.assertFalse(any(base in ('http://ims','http://smsc') for base,_,_,_ in calls))
  self.assertFalse(any('/sms' in path or '/ims' in path for _,path,_,_ in calls))
  dn=[body['name'] for _,path,method,body in calls if path=='networking/data-networks' and method=='POST']
  self.assertEqual(dn,['internet'])
 def test_combined_provisions_both_services(self):
  calls=self.exercise('internet-ims-sms')
  self.assertTrue(any(base=='http://ims' for base,_,_,_ in calls));self.assertTrue(any(base=='http://smsc' for base,_,_,_ in calls))
  dn=[body['name'] for _,path,method,body in calls if path=='networking/data-networks' and method=='POST'];self.assertEqual(dn,['internet','ims'])
 def test_ha_found_init_then_joins_two_voters(self):
  calls=self.exercise('internet',True)
  joins=[(base,body) for base,path,_,body in calls if path=='cluster/join']
  self.assertEqual(len(joins),2)
  self.assertTrue(all(body['suffrage']=='voter' and body['seedAddresses']==['core-0.core-peers.ns.svc.cluster.local:7000'] for _,body in joins))
  self.assertLess(next(i for i,x in enumerate(calls) if x[1]=='init'),next(i for i,x in enumerate(calls) if x[1]=='cluster/join'))
 def test_ha_sets_names_from_statefulset_pod_and_namespace(self):
  calls=self.exercise('internet',True)
  updates=[(path,body) for _,path,method,body in calls if method=='PUT' and path.endswith('/display-name')]
  self.assertEqual(updates,[(f'cluster/members/core-{i}/display-name',{'displayName':f'core-{i}.ns'}) for i in range(3)])
 def test_standalone_does_not_set_cluster_member_names(self):
  calls=self.exercise('internet')
  self.assertFalse(any(path.endswith('/display-name') for _,path,_,_ in calls))
 def test_lab_gateway_disables_core_nat_before_provisioning(self):
  calls=self.exercise('internet',n6_gateway=True,provision=False)
  updates=[body for _,path,method,body in calls if path=='networking/nat' and method=='PUT']
  self.assertEqual(updates,[{'enabled':False}])
 def test_no_lab_gateway_leaves_core_nat_untouched(self):
  calls=self.exercise('internet',n6_gateway=False,provision=False)
  self.assertFalse(any(path=='networking/nat' for _,path,_,_ in calls))
 def test_lab_gateway_keeps_core_nat_disabled_without_rewriting_it(self):
  calls=self.exercise('internet',n6_gateway=True,provision=False,core_nat_enabled=False)
  self.assertTrue(any(path=='networking/nat' and method=='GET' for _,path,method,_ in calls))
  self.assertFalse(any(path=='networking/nat' and method=='PUT' for _,path,method,_ in calls))
 def test_ha_combined_connects_ims_to_every_hss(self):
  calls=self.exercise('internet-ims-sms',True)
  peers=[body for base,path,method,body in calls if base=='http://ims' and path=='diameter/peers' and method=='POST']
  self.assertEqual(len(peers),3)
  self.assertTrue(all(p['applications']==['cx','rx'] for p in peers))
 def test_custom_pool_replaces_core_seeded_default(self):
  calls=self.exercise('internet',default_network=True)
  updates=[body for _,path,method,body in calls if path=='networking/data-networks/internet' and method=='PUT']
  self.assertEqual(len(updates),1)
  self.assertEqual(updates[0]['ipv4_pool'],'10.208.0.0/16')
 def test_pool_change_refuses_active_sessions(self):
  with self.assertRaisesRegex(RuntimeError,'Detach UEs'):
   self.exercise('internet',default_network=True,active_sessions=1)
 def test_upgrade_preserves_custom_network_with_active_sessions(self):
  calls=self.exercise('internet',default_network=True,active_sessions=1,existing_core=True)
  self.assertFalse(any(path=='networking/data-networks/internet' and method=='PUT' for _,path,method,_ in calls))
if __name__=='__main__':unittest.main(argv=['test-bootstrap']+remaining)
