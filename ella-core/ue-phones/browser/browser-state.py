#!/usr/bin/python3
"""Local browser-stack health and best-effort last-page checkpoint."""
import http.client, json, os, pathlib, socket, subprocess, sys, urllib.parse
PROFILE=pathlib.Path(os.environ.get('HOME','/home/browser'))/'profile'
PAGE=PROFILE/'.ella-last-url'
def get(port,path):
    client=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
    try:
        client.request('GET',path);response=client.getresponse()
        if response.status!=200:raise RuntimeError(f'HTTP {port} returned {response.status}')
        return response.read()
    finally:client.close()
def valid(url):
    try:return urllib.parse.urlsplit(url).scheme in ('http','https') and bool(urllib.parse.urlsplit(url).hostname)
    except ValueError:return False
mode=sys.argv[1] if len(sys.argv)>1 else 'health'
if mode=='read':
    try:url=PAGE.read_text().strip()
    except OSError:url='about:blank'
    print(url if valid(url) else 'about:blank')
elif mode=='remember':
    try:
        pages=json.loads(get(9222,'/json/list'))
        url=next((p['url'] for p in pages if p.get('type')=='page' and valid(p.get('url',''))),None)
        if url and (not PAGE.exists() or PAGE.read_text()!=url):
            temporary=PAGE.with_suffix('.tmp');temporary.write_text(url);temporary.chmod(0o600);temporary.replace(PAGE)
    except Exception:pass
else:
    try:
        subprocess.run(['xdpyinfo','-display',':99'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=2)
        with socket.create_connection(('127.0.0.1',5900),timeout=2) as vnc:
            if not vnc.recv(12).startswith(b'RFB '):raise RuntimeError('Invalid VNC handshake')
        get(6080,'/remote.html');json.loads(get(9222,'/json/version'))
        print('X display, VNC, noVNC and Chromium ready')
    except Exception as error:print('Browser unhealthy: '+str(error),file=sys.stderr);sys.exit(1)
