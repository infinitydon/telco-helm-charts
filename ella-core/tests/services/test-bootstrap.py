"""Verify bootstrap API dependencies against an initially empty API fixture."""
import argparse,io,json,os,pathlib,runpy,unittest
from unittest.mock import patch
p=argparse.ArgumentParser();p.add_argument('--script',default=str(pathlib.Path(__file__).resolve().parents[2]/'ella-core-lab/files/bootstrap.py'));a,remaining=p.parse_known_args()
class BootstrapModes(unittest.TestCase):
 def exercise(self,mode):
  calls=[]
  def request(req,timeout):
   body=json.loads(req.data) if req.data else None
   calls.append((req.full_url,req.method,body))
   result={}
   if req.full_url.endswith('/status'):result={'initialized':False}
   elif req.full_url.endswith('/init'):result={'token':'test-token'}
   elif req.full_url.endswith('/operator') and req.method=='GET':result={'id':{'mcc':'001','mnc':'01'}}
   elif req.method=='GET':result={'items':[]}
   return io.BytesIO(json.dumps({'result':result}).encode())
  env={'UE_MODE':mode,'CORE_API':'http://core','IMS_API':'http://ims','SMSC_API':'http://smsc','ADMIN_EMAIL':'lab@example.com','ADMIN_PASSWORD':'test-only','IMS_ADDRESS':'10.6.0.5','SMSC_ADDRESS_HOST':'smsc','CORE_ADDRESS_HOST':'core'}
  with patch.dict(os.environ,env),patch('urllib.request.urlopen',side_effect=request),patch('socket.gethostbyname',return_value='10.0.0.1'):
   runpy.run_path(a.script,run_name='__main__')
  return calls
 def test_internet_has_no_ims_or_sms_dependency(self):
  calls=self.exercise('internet')
  self.assertTrue(all(url.startswith('http://core/') for url,_,_ in calls))
  self.assertFalse(any('/operator/ims' in u or '/operator/sms' in u for u,_,_ in calls))
  dn=[body['name'] for url,method,body in calls if url.endswith('/networking/data-networks') and method=='POST']
  self.assertEqual(dn,['internet'])
 def test_combined_provisions_both_networks_and_services(self):
  calls=self.exercise('internet-ims-sms')
  dn=[body['name'] for url,method,body in calls if url.endswith('/networking/data-networks') and method=='POST']
  self.assertEqual(dn,['internet','ims'])
  self.assertTrue(any(u.startswith('http://ims/') for u,_,_ in calls))
  self.assertTrue(any(u.startswith('http://smsc/') for u,_,_ in calls))
if __name__=='__main__':unittest.main(argv=['test-bootstrap']+remaining)
