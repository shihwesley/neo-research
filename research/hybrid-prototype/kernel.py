"""
Same kernel as srt-prototype but runs inside Docker.
The hybrid model: Docker for execution isolation, srt wraps the MCP server on host.
"""

import json
import sys
import io
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

_ns = {}

def execute(code: str) -> tuple[str, list[str]]:
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        try:
            result = eval(code, _ns)
            if result is not None:
                print(repr(result))
        except SyntaxError:
            exec(code, _ns)
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
    finally:
        sys.stdout = old_stdout
    return buf.getvalue(), [k for k in _ns if not k.startswith("_")]

def get_vars():
    result = []
    for k, v in _ns.items():
        if k.startswith("_"):
            continue
        s = repr(v)
        if len(s) > 100:
            s = s[:97] + "..."
        result.append({"name": k, "type": type(v).__name__, "summary": s})
    return result

def get_var(name):
    if name not in _ns:
        return {"error": f"Variable '{name}' not found"}
    v = _ns[name]
    try:
        json.dumps(v)
        return {"value": v}
    except (TypeError, ValueError):
        return {"value": repr(v)}

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        path = urlparse(self.path).path
        if path == "/exec":
            output, var_names = execute(body.get("code", ""))
            self._respond({"output": output, "vars": var_names})
        elif path == "/reset":
            _ns.clear()
            self._respond({"status": "ok"})
        else:
            self._respond({"error": "not found"}, 404)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/vars":
            self._respond(get_vars())
        elif path.startswith("/var/"):
            self._respond(get_var(path[5:]))
        elif path == "/health":
            self._respond({"status": "ok"})
        else:
            self._respond({"error": "not found"}, 404)

    def _respond(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args):
        pass

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"kernel listening on 0.0.0.0:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
