import html
import importlib.metadata
import json
import os
import pathlib
import re
import socket
import ssl
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import requests
import socks
import wasmtime
import yaml


HOST = os.getenv("LISTEN_HOST", "127.0.0.1")
PORT = int(os.getenv("LISTEN_PORT", "8090"))
UE_INTERFACE_PATTERN = os.getenv("UE_INTERFACE_PATTERN", "uesimtun*")
UE_CONFIG_PATH = pathlib.Path(
    os.getenv("UE_CONFIG_PATH", "/etc/ueransim/ue.yaml")
)
SOCKS_PROXY = os.getenv("SOCKS_PROXY", "socks5h://127.0.0.1:1080")
SCENARIO_DIR = pathlib.Path(os.getenv("SCENARIO_DIR", "/scenarios"))
DEFAULT_TARGET = os.getenv("DEFAULT_TARGET", "https://example.com")
PING_TARGET = os.getenv("PING_TARGET", "10.54.0.100")
IPERF3_TARGET = os.getenv("IPERF3_TARGET", "10.54.0.101:5201")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
WASM_FUEL = int(os.getenv("WASM_FUEL", "1000000"))
RUNNER_STARTED = time.time()

BUILTIN_FUNCTIONS = {
    "builtin-http": "http_get",
    "builtin-tcp": "tcp_connect",
    "builtin-tls": "tls_handshake",
    "builtin-download": "download_test",
    "builtin-ping": "ping_test",
    "builtin-traceroute": "traceroute_test",
    "builtin-iperf3": "iperf3_test",
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
traffic_lock = threading.Lock()
traffic_sample = {"checked": 0.0, "rx": 0, "tx": 0}


def ue_interface():
    candidates = sorted(
        path.name for path in pathlib.Path("/sys/class/net").glob(
            UE_INTERFACE_PATTERN
        )
    )
    for name in candidates:
        if live_interface_address(name):
            return name
    return candidates[0] if candidates else ""


def interface_ready():
    return bool(ue_interface())


def live_interface_address(interface=None):
    interface = interface or ue_interface()
    if not interface:
        return ""
    try:
        completed = subprocess.run(
            ["ip", "-json", "address", "show", "dev", interface],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        for address in json.loads(completed.stdout)[0].get("addr_info", []):
            if address.get("family") == "inet":
                return address["local"]
    except (OSError, subprocess.SubprocessError, ValueError, IndexError, KeyError):
        pass
    return ""


def format_bitrate(bits_per_second):
    units = ("bps", "Kbps", "Mbps", "Gbps", "Tbps")
    value = max(float(bits_per_second), 0.0)
    for unit in units:
        if value < 1000 or unit == units[-1]:
            precision = 0 if value >= 100 else 1 if value >= 10 else 2
            return f"{value:.{precision}f} {unit}"
        value /= 1000


def tunnel_throughput(interface):
    try:
        rx = int(pathlib.Path(
            f"/sys/class/net/{interface}/statistics/rx_bytes"
        ).read_text().strip())
        tx = int(pathlib.Path(
            f"/sys/class/net/{interface}/statistics/tx_bytes"
        ).read_text().strip())
    except (OSError, ValueError):
        return {"rxBps": 0, "txBps": 0, "rxRate": "0 bps", "txRate": "0 bps"}

    now = time.monotonic()
    with traffic_lock:
        elapsed = now - traffic_sample["checked"]
        if traffic_sample["checked"] and elapsed > 0:
            rx_bps = max(0, (rx - traffic_sample["rx"]) * 8 / elapsed)
            tx_bps = max(0, (tx - traffic_sample["tx"]) * 8 / elapsed)
        else:
            rx_bps = tx_bps = 0
        traffic_sample.update(checked=now, rx=rx, tx=tx)
    return {
        "rxBps": round(rx_bps),
        "txBps": round(tx_bps),
        "rxRate": format_bitrate(rx_bps),
        "txRate": format_bitrate(tx_bps),
    }


def ue_config():
    try:
        parsed = yaml.safe_load(UE_CONFIG_PATH.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return {}
    session = (parsed.get("sessions") or [{}])[0] or {}
    network_slice = session.get("slice") or {}
    slice_sd = network_slice.get("sd", "")
    if isinstance(slice_sd, int):
        slice_sd = f"0x{slice_sd:06x}"
    supi = str(parsed.get("supi", ""))
    imsi = supi.removeprefix("imsi-")
    gnb_list = parsed.get("gnbSearchList") or []
    return {
        "imsi": imsi,
        "plmn": f'{parsed.get("mcc", "")}-{parsed.get("mnc", "")}'.strip("-"),
        "servingGnb": str(gnb_list[0]) if gnb_list else "",
        "slice": (
            f'SST {network_slice.get("sst", "")} / '
            f"SD {slice_sd}"
        ),
        "dnn": str(session.get("apn", session.get("dnn", ""))),
    }


def masked_imsi(imsi):
    if len(imsi) < 9:
        return imsi
    return f"{imsi[:5]}••••••{imsi[-4:]}"


def ue_status():
    interface = ue_interface()
    tunnel_ip = live_interface_address(interface)
    active = bool(tunnel_ip)
    config = ue_config()
    throughput = tunnel_throughput(interface) if active else {
        "rxBps": 0, "txBps": 0, "rxRate": "0 bps", "txRate": "0 bps"
    }
    with state_lock:
        last_run = state["last_run"]
        running = state["running"]
    last_test = None
    if last_run:
        last_test = {
            "scenario": last_run.get("scenario"),
            "ok": last_run.get("ok"),
            "durationMs": last_run.get("durationMs"),
            "target": last_run.get("target"),
        }
        request = last_run.get("request") or {}
        for key in ("avgMs", "receivedMbps", "status"):
            if key in request:
                last_test[key] = request[key]
    return {
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "registration": "Registered" if active else "Not registered",
        "pduSession": "Active" if active else "Inactive",
        "tunnelInterface": interface or "Pending",
        "tunnelIp": tunnel_ip or "Pending",
        **throughput,
        "servingGnb": config.get("servingGnb", ""),
        "gnbState": "Connected" if active else "Searching",
        "plmn": config.get("plmn", ""),
        "slice": config.get("slice", ""),
        "dnn": config.get("dnn", ""),
        "imsi": masked_imsi(config.get("imsi", "")),
        "configSource": str(UE_CONFIG_PATH),
        "uptimeSeconds": int(time.time() - RUNNER_STARTED),
        "testRunning": running,
        "lastTest": last_test,
    }


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
    interface = ue_interface()
    started = time.time()
    result = {
        "scenario": name,
        "target": target,
        "interface": interface,
        "proxy": SOCKS_PROXY,
        "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "logs": [],
    }
    if not interface:
        raise RuntimeError(
            f"no interface matches {UE_INTERFACE_PATTERN}; refusing fallback routing"
        )

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

    def target_host():
        parsed = requests.utils.urlparse(
            target if "://" in target else f"//{target}"
        )
        if not parsed.hostname:
            raise ValueError("target must contain a hostname or IP address")
        return parsed.hostname, parsed.port

    def run_command(arguments, timeout=None):
        completed = subprocess.run(
            arguments,
            capture_output=True,
            text=True,
            timeout=timeout or REQUEST_TIMEOUT,
            check=False,
        )
        output = (completed.stdout + completed.stderr).strip()
        if completed.returncode != 0:
            raise RuntimeError(
                f"{arguments[0]} failed with exit code {completed.returncode}: {output}"
            )
        return output

    def interface_address():
        output = run_command(
            ["ip", "-json", "address", "show", "dev", interface]
        )
        for address in json.loads(output)[0].get("addr_info", []):
            if address.get("family") == "inet":
                return address["local"]
        raise RuntimeError(f"{interface} has no IPv4 address")

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

    def ping_test():
        host, _ = target_host()
        output = run_command(
            ["ping", "-n", "-I", interface, "-c", "4", "-W", "2", host],
            timeout=15,
        )
        loss = re.search(r"([\d.]+)% packet loss", output)
        timing = re.search(
            r"=\s*([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s*ms", output
        )
        request_result.update(
            {
                "test": "ping",
                "host": host,
                "interface": interface,
                "packetLossPercent": float(loss.group(1)) if loss else None,
                "minMs": float(timing.group(1)) if timing else None,
                "avgMs": float(timing.group(2)) if timing else None,
                "maxMs": float(timing.group(3)) if timing else None,
                "output": output,
                "ok": not loss or float(loss.group(1)) < 100,
            }
        )
        return 0

    def traceroute_test():
        host, _ = target_host()
        output = run_command(
            [
                "traceroute",
                "-n",
                "-i",
                interface,
                "-m",
                "12",
                "-w",
                "2",
                "-q",
                "1",
                host,
            ],
            timeout=35,
        )
        hops = [line.strip() for line in output.splitlines()[1:] if line.strip()]
        destination = socket.gethostbyname(host)
        reached = any(
            re.search(rf"(^|\s){re.escape(destination)}(\s|$)", hop)
            for hop in hops
        )
        request_result.update(
            {
                "test": "traceroute",
                "host": host,
                "destinationIp": destination,
                "interface": interface,
                "hopCount": len(hops),
                "timedOutHops": sum(hop.endswith("*") for hop in hops),
                "completed": True,
                "reachedDestination": reached,
                "hops": hops,
                "ok": reached,
            }
        )
        return 0

    def iperf3_test():
        host, requested_port = target_host()
        port = requested_port or 5201
        source = interface_address()
        output = run_command(
            [
                "iperf3",
                "-c",
                host,
                "-p",
                str(port),
                "-B",
                source,
                "-J",
                "-t",
                "3",
            ],
            timeout=20,
        )
        report = json.loads(output)
        sent = report["end"]["sum_sent"]
        received = report["end"]["sum_received"]
        request_result.update(
            {
                "test": "iperf3",
                "server": host,
                "port": port,
                "source": source,
                "seconds": round(received["seconds"], 3),
                "sentMbps": round(sent["bits_per_second"] / 1_000_000, 3),
                "receivedMbps": round(
                    received["bits_per_second"] / 1_000_000, 3
                ),
                "retransmits": sent.get("retransmits"),
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
        ("ping_test", ping_test),
        ("traceroute_test", traceroute_test),
        ("iperf3_test", iperf3_test),
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
    <label for="target">Target URL, host, or IP</label><input id="target" value="__DEFAULT_TARGET__" required>
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
  'builtin-ping': '__PING_TARGET__',
  'builtin-traceroute': '__PING_TARGET__',
  'builtin-iperf3': '__IPERF3_TARGET__'
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
  e.preventDefault();
  button.disabled = true;
  const selected = scenario.value;
  const started = Date.now();
  const timer = setInterval(() => {
    const seconds = Math.floor((Date.now() - started) / 1000);
    result.textContent = `Running ${selected} through the UE… ${seconds}s elapsed.\n` +
      'Ping normally takes about 3s; iperf3 about 3s; traceroute can take up to 35s.';
  }, 250);
  try {
    const body = new URLSearchParams({scenario:scenario.value,target:document.querySelector('#target').value});
    const r = await fetch('/api/run', {method:'POST',body});
    clearInterval(timer);
    result.textContent = JSON.stringify(await r.json(), null, 2);
  } catch (e) {
    clearInterval(timer);
    result.textContent = String(e);
  }
  button.disabled = false; refresh();
});
refresh().catch(e => { health.className='down'; health.textContent=String(e); });
</script></body></html>""".replace(
    "__DEFAULT_TARGET__", html.escape(DEFAULT_TARGET, quote=True)
).replace(
    "__PING_TARGET__", html.escape(PING_TARGET, quote=True)
).replace(
    "__IPERF3_TARGET__", html.escape(IPERF3_TARGET, quote=True)
)


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
        elif self.path == "/api/ue-status":
            self.send_json(200, ue_status())
        elif self.path in ("/healthz", "/api/status"):
            ready = interface_ready()
            self.send_json(
                200 if self.path == "/api/status" or ready else 503,
                {
                    "ready": ready,
                    "interface": ue_interface(),
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
        url_scenarios = {"builtin-http", "builtin-download"}
        if name in url_scenarios and not target.startswith(("http://", "https://")):
            self.send_json(400, {"error": "this scenario target must use http or https"})
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
        f"egress proxy={SOCKS_PROXY}, interface-pattern={UE_INTERFACE_PATTERN}",
        flush=True,
    )
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
