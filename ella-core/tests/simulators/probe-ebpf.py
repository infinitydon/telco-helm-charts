"""Run inside PacketRusher's container; report only its own BPF objects."""
import json,pathlib,re,subprocess
state=json.loads(subprocess.check_output(['curl','-fsS','http://127.0.0.1:8080/healthz']))
program_ids=set();link_ids=set()
for pid in state['pids']:
    for path in pathlib.Path('/proc/'+str(pid)+'/fdinfo').iterdir():
        try:info=path.read_text()
        except OSError:continue
        program_ids.update(map(int,re.findall(r'prog_id:\s+(\d+)',info)))
        link_ids.update(map(int,re.findall(r'link_id:\s+(\d+)',info)))
programs=[{k:p[k] for k in ('id','name','type')} for p in json.loads(subprocess.check_output(['bpftool','-j','prog','show'])) if p.get('id') in program_ids]
links=[p for p in json.loads(subprocess.check_output(['bpftool','-j','link','show'])) if p.get('id') in link_ids]
assert state['backend']=='ebpf'
assert {'encap','decap','uplink'} <= {p['name'] for p in programs}
assert {p['id'] for p in programs if p['name'] in ('encap','decap','uplink')} <= {p['prog_id'] for p in links}
print(json.dumps({'programs':programs,'links':links}))
