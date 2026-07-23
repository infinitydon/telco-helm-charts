import html
import importlib.metadata
import json
import os
import pathlib
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import requests
import socks
import wasmtime


HOST = os.getenv("LISTEN_HOST", "127.0.0.1")
PORT = int(os.getenv("LISTEN_PORT", "8090"))
UE_INTERFACE = os.getenv("UE_INTERFACE", "uesimtun0")
SOCKS_PROXY = os.getenv("SOCKS_PROXY", "socks5h://127.0.0.1:1080")
SCENARIO_DIR = pathlib.Path(os.getenv("SCENARIO_DIR", "/scenarios"))
DEFAULT_TARGET = os.getenv("DEFAULT_TARGET", "https://example.com")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
WASM_FUEL = int(os.getenv("WASM_FUEL", "1000000"))

BUILTIN_FUNCTIONS = {
    "builtin-http": "http_get",
    "builtin-tcp": "tcp_connect",
    "builtin-tls": "tls_handshake",
    "builtin-download": "download_test",
    "builtin-egress": "egress_ip",
}


def builtin_wat(function_name):
    return f"""
    (module
      (import "ue" "log" (func $log (param i32 i32)))
      (import "ue" "{function_name}" (func $test (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "WASM scenario started")
      (func (export "run") (result i32)
        i32.const 0
        i32.const 21
        call $log
        call $test))
    """

state_lock = threading.Lock()
state = {
    "running": False,
    "last_run": None,
}


def interface_ready():
    return pathlib.Path(f"/sys/class/net/{UE_INTERFACE}").exists()


def scenario_names():
    names = list(BUILTIN_FUNCTIONS)
    if SCENARIO_DIR.exists():
        names.extend(sorted(path.stem for path in SCENARIO_DIR.glob("*.wasm")))
    return names


def load_scenario(name):
    if name in BUILTIN_FUNCTIONS:
        return wasmtime.wat2wasm(builtin_wat(BUILTIN_FUNCTIONS[name]))
    candidate = (SCENARIO_DIR / f"{name}.wasm").resolve()
    if candidate.parent != SCENARIO_DIR.resolve() or not candidate.is_file():
        raise ValueError(f"unknown scenario: {name}")
    return candidate.read_bytes()


def run_scenario(name, target):
    started = time.time()
    result = {
        "scenario": name,
        "target": target,
        "interface": UE_INTERFACE,
        "proxy": SOCKS_PROXY,
        "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "logs": [],
    }
    if not interface_ready():
        raise RuntimeError(f"{UE_INTERFACE} is not present; refusing fallback routing")

    config = wasmtime.Config()
    config.consume_fuel = True
    engine = wasmtime.Engine(config)
    store = wasmtime.Store(engine)
    store.set_fuel(WASM_FUEL)
    module = wasmtime.Module(engine, load_scenario(name))
    linker = wasmtime.Linker(engine)
    request_result = {}

    def target_endpoint(default_port):
        parsed = requests.utils.urlparse(target)
        if not parsed.hostname:
            raise ValueError("target URL must contain a hostname")
        return parsed.hostname, parsed.port or default_port

    def proxy_socket(host, port):
        parsed = requests.utils.urlparse(SOCKS_PROXY)
        connection = socks.socksocket()
        connection.set_proxy(
            socks.SOCKS5,
            parsed.hostname,
            parsed.port or 1080,
            rdns=True,
        )
        connection.settimeout(REQUEST_TIMEOUT)
        connection.connect((host, port))
        return connection

    def guest_log(caller, pointer, length):
        memory = caller.get("memory")
        if memory is None:
            raise RuntimeError("guest does not export memory")
        message = bytes(memory.read(caller, pointer, pointer + length)).decode(
            "utf-8", errors="replace"
        )
        result["logs"].append(message)

    def http_get():
        response = requests.get(
            target,
            proxies={"http": SOCKS_PROXY, "https": SOCKS_PROXY},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": "UERANSIM-WASM-Runner/0.2.0"},
        )
        request_result.update(
            {
                "test": "http",
                "status": response.status_code,
                "finalUrl": response.url,
                "bytes": len(response.content),
                "server": response.headers.get("server", ""),
            }
        )
        return response.status_code

    def tcp_connect():
        host, port = target_endpoint(443)
        began = time.perf_counter()
        with proxy_socket(host, port):
            latency = round((time.perf_counter() - began) * 1000, 2)
        request_result.update(
            {
                "test": "tcp",
                "host": host,
                "port": port,
                "connectMs": latency,
                "ok": True,
            }
        )
        return 0

    def tls_handshake():
        host, port = target_endpoint(443)
        began = time.perf_counter()
        raw = proxy_socket(host, port)
        context = ssl.create_default_context()
        with context.wrap_socket(raw, server_hostname=host) as secure:
            certificate = secure.getpeercert()
            subject = dict(
                item for group in certificate.get("subject", ()) for item in group
            )
            request_result.update(
                {
                    "test": "tls",
                    "host": host,
                    "port": port,
                    "handshakeMs": round((time.perf_counter() - began) * 1000, 2),
                    "protocol": secure.version(),
                    "cipher": secure.cipher()[0],
                    "certificateSubject": subject.get("commonName", ""),
                    "ok": True,
                }
            )
        return 0

    def download_test():
        began = time.perf_counter()
        response = requests.get(
            target,
            proxies={"http": SOCKS_PROXY, "https": SOCKS_PROXY},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            stream=True,
            headers={"User-Agent": "UERANSIM-WASM-Runner/0.2.0"},
        )
        response.raise_for_status()
        total = sum(len(chunk) for chunk in response.iter_content(65536) if chunk)
        seconds = max(time.perf_counter() - began, 0.001)
        request_result.update(
            {
                "test": "download",
                "status": response.status_code,
                "bytes": total,
                "durationMs": round(seconds * 1000, 2),
                "megabitsPerSecond": round((total * 8) / seconds / 1_000_000, 3),
                "ok": True,
            }
        )
        return 0

    def egress_ip():
        response = requests.get(
            "https://api.ipify.org",
            proxies={"http": SOCKS_PROXY, "https": SOCKS_PROXY},
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "UERANSIM-WASM-Runner/0.2.0"},
        )
        response.raise_for_status()
        request_result.update(
            {
                "test": "egress",
                "publicIp": response.text.strip(),
                "ok": True,
            }
        )
        return 0

    linker.define_func(
        "ue",
        "log",
        wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], []),
        guest_log,
        access_caller=True,
    )
    linker.define_func(
        "ue",
        "http_get",
        wasmtime.FuncType([], [wasmtime.ValType.i32()]),
        http_get,
    )
    for import_name, callback in (
        ("tcp_connect", tcp_connect),
        ("tls_handshake", tls_handshake),
        ("download_test", download_test),
        ("egress_ip", egress_ip),
    ):
        linker.define_func(
            "ue",
            import_name,
            wasmtime.FuncType([], [wasmtime.ValType.i32()]),
            callback,
        )
    instance = linker.instantiate(store, module)
    exported_run = instance.exports(store).get("run")
    if exported_run is None:
        raise RuntimeError("scenario must export a run function")
    wasm_result = exported_run(store)
    result["wasmResult"] = wasm_result
    result["request"] = request_result
    result["ok"] = bool(
        request_result.get("ok", 200 <= int(wasm_result) < 400)
    )
    result["durationMs"] = round((time.time() - started) * 1000)
    return result


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>UE WASM Lab</title>
  <style>
    :root { color-scheme: dark; font: 15px system-ui, sans-serif; }
    body { margin: 0; padding: 22px; background: #07111f; color: #e6f7ff; }
    main { max-width: 700px; margin: auto; }
    h1 { margin-bottom: 4px; } .sub { color: #91a9bc; margin-top: 0; }
    form, pre { background: #0d1d2e; border: 1px solid #1c4259; border-radius: 14px; padding: 16px; }
    label { display:block; margin: 10px 0 5px; color:#a5f3fc; }
    input, select, button { box-sizing:border-box; width:100%; padding:11px; border-radius:9px; border:1px solid #31556a; }
    input, select { background:#07111f; color:#fff; } button { margin-top:15px; background:#0891b2; color:#fff; font-weight:700; }
    button:disabled { opacity:.5; } .ready { color:#34d399; } .down { color:#fb7185; }
    pre { min-height:150px; white-space:pre-wrap; overflow-wrap:anywhere; }
  </style>
</head>
<body><main>
  <h1>UE WebAssembly Lab</h1>
  <p class="sub">Sandboxed scenarios routed through <strong>uesimtun0</strong></p>
  <p id="health">Checking UE path…</p>
  <form id="runner">
    <label for="scenario">Scenario</label><select id="scenario"></select>
    <label for="target">Target URL</label><input id="target" type="url" value="__DEFAULT_TARGET__" required>
    <button id="run" type="submit">Run through 5G UE</button>
  </form>
  <h2>Result</h2><pre id="result">No scenario run yet.</pre>
</main>
<script>
const health = document.querySelector('#health');
const scenario = document.querySelector('#scenario');
const result = document.querySelector('#result');
const button = document.querySelector('#run');
const targets = {
  'builtin-http': 'https://www.cloudflare.com/cdn-cgi/trace',
  'builtin-tcp': 'https://www.cloudflare.com',
  'builtin-tls': 'https://www.cloudflare.com',
  'builtin-download': 'https://speed.cloudflare.com/__down?bytes=1000000',
  'builtin-egress': 'https://api.ipify.org'
};
async function refresh() {
  const r = await fetch('/api/status'); const s = await r.json();
  health.className = s.ready ? 'ready' : 'down';
  health.textContent = s.ready ? `Ready — ${s.interface} and SOCKS proxy configured` : `Not ready — ${s.interface} missing`;
  scenario.replaceChildren(...s.scenarios.map(n => Object.assign(document.createElement('option'), {value:n,textContent:n})));
}
scenario.addEventListener('change', () => {
  if (targets[scenario.value]) document.querySelector('#target').value = targets[scenario.value];
});
document.querySelector('#runner').addEventListener('submit', async e => {
  e.preventDefault(); button.disabled = true; result.textContent = 'Running…';
  try {
    const body = new URLSearchParams({scenario:scenario.value,target:document.querySelector('#target').value});
    const r = await fetch('/api/run', {method:'POST',body});
    result.textContent = JSON.stringify(await r.json(), null, 2);
  } catch (e) { result.textContent = String(e); }
  button.disabled = false; refresh();
});
refresh().catch(e => { health.className='down'; health.textContent=String(e); });
</script></body></html>""".replace("__DEFAULT_TARGET__", html.escape(DEFAULT_TARGET, quote=True))


class Handler(BaseHTTPRequestHandler):
    def send_json(self, code, value):
        body = json.dumps(value, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path in ("/healthz", "/api/status"):
            ready = interface_ready()
            self.send_json(
                200 if self.path == "/api/status" or ready else 503,
                {
                    "ready": ready,
                    "interface": UE_INTERFACE,
                    "proxy": SOCKS_PROXY,
                    "runtime": f"wasmtime-py {importlib.metadata.version('wasmtime')}",
                    "scenarios": scenario_names(),
                    "state": state,
                },
            )
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/run":
            self.send_json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        fields = parse_qs(self.rfile.read(length).decode())
        name = fields.get("scenario", ["builtin-http"])[0]
        target = fields.get("target", [DEFAULT_TARGET])[0]
        if not target.startswith(("http://", "https://")):
            self.send_json(400, {"error": "target must use http or https"})
            return
        with state_lock:
            if state["running"]:
                self.send_json(409, {"error": "a scenario is already running"})
                return
            state["running"] = True
        try:
            output = run_scenario(name, target)
            code = 200 if output["ok"] else 502
            with state_lock:
                state["last_run"] = output
            self.send_json(code, output)
        except Exception as exc:
            failure = {"ok": False, "scenario": name, "target": target, "error": str(exc)}
            with state_lock:
                state["last_run"] = failure
            self.send_json(500, failure)
        finally:
            with state_lock:
                state["running"] = False

    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} - {fmt % args}", flush=True)


if __name__ == "__main__":
    print(
        f"WASM runner listening on http://{HOST}:{PORT}; "
        f"egress proxy={SOCKS_PROXY}, interface={UE_INTERFACE}",
        flush=True,
    )
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
