"""Bootstrap dependency and HA join ordering tests using empty API fixtures."""
import argparse,contextlib,io,json,os,pathlib,runpy,unittest
from unittest.mock import patch
p=argparse.ArgumentParser();p.add_argument('--script',default=str(pathlib.Path(__file__).resolve().parents[2]/'ella-core/files/bootstrap.py'));a,remaining=p.parse_known_args()
class Bootstrap(unittest.TestCase):
 def exercise(self,mode,ha=False,default_network=False,active_sessions=0,existing_core=False):
  calls=[];ready=set();count=3 if ha else 1
  if existing_core:ready.add('http://core-0.core-peers.ns.svc.cluster.local:5002')
  def request(req,timeout):
   base=req.full_url.split('/api/v1/')[0];path=req.full_url.split('/api/v1/')[1];body=json.loads(req.data) if req.data else None
   calls.append((base,path,req.method,body));result={}
   if path=='status':result={'initialized':base in ready,'ready':base in ready,'cluster':{'isLeader':base.endswith('-0.core-peers.ns.svc.cluster.local:5002')}}
   elif path=='init':ready.add(base);result={'token':'test-only'}
   elif path=='auth/login':result={'token':'test-only'}
   elif path=='cluster/pki/join-tokens':result={'token':'test-join'}
   elif path=='cluster/join':ready.add(base)
   elif path=='cluster/members':result=[{'nodeId':str(i+1),'suffrage':'Voter'} for i in range(count)]
   elif path=='operator' and req.method=='GET':result={'id':{'mcc':'001','mnc':'01'}}
   elif path=='networking/data-networks' and req.method=='GET' and default_network:
    result={'items':[{'name':'internet','ipv4_pool':'10.45.0.0/22','dns':'8.8.8.8','mtu':1400,'status':{'sessions':active_sessions}}]}
   elif req.method=='GET':result={'items':[]}
   return io.BytesIO(json.dumps({'result':result}).encode())
  env={'CORE_NAME':'core','NAMESPACE':'ns','CLUSTER_DOMAIN':'cluster.local','REPLICAS':str(count),'TOPOLOGY':'ha' if ha else 'standalone','UE_MODE':mode,'PROVISION':'true','IMS_API':'http://ims','SMSC_API':'http://smsc','ADMIN_EMAIL':'lab@example.com','ADMIN_PASSWORD':'test-only','IMS_ADDRESS':'10.6.0.5','SMSC_ADDRESS_HOST':'smsc','CORE_ADDRESS_HOST':'core-active'}
  if default_network:env['INTERNET_POOL']='10.208.0.0/16'
  with patch.dict(os.environ,env),patch('urllib.request.urlopen',side_effect=request),patch('socket.gethostbyname',return_value='10.0.0.1'),contextlib.redirect_stdout(io.StringIO()):
   runpy.run_path(a.script,run_name='__main__')
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
