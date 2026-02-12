"""
Minimal IPython kernel wrapped by srt.

Usage:
    srt --settings srt-config.json python3 kernel.py

Provides:
    POST /exec  {"code": "..."} -> {"output": "...", "vars": [...]}
    GET  /vars                  -> [{"name": "x", "type": "int", "summary": "42"}, ...]
    GET  /var/<name>            -> {"value": ...}
    POST /reset                 -> {"status": "ok"}
"""

import json
import sys
import io
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# kernel namespace — persists across /exec calls
_ns = {}

def execute(code: str) -> tuple[str, list[str]]:
    """Execute code in kernel namespace, return (stdout, var_names)."""
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        # try eval first (expression), fall back to exec (statement)
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

    output = buf.getvalue()
    var_names = [k for k in _ns if not k.startswith("_")]
    return output, var_names


def get_vars() -> list[dict]:
    """List all user variables with type and summary."""
    result = []
    for k, v in _ns.items():
        if k.startswith("_"):
            continue
        summary = repr(v)
        if len(summary) > 100:
            summary = summary[:97] + "..."
        result.append({"name": k, "type": type(v).__name__, "summary": summary})
    return result


def get_var(name: str) -> dict:
    """Get a single variable's value."""
    if name not in _ns:
        return {"error": f"Variable '{name}' not found"}
    v = _ns[name]
    try:
        json.dumps(v)  # test JSON-serializable
        return {"value": v}
    except (TypeError, ValueError):
        return {"value": repr(v)}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        path = urlparse(self.path).path

        if path == "/exec":
            code = body.get("code", "")
            output, var_names = execute(code)
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
            name = path[5:]  # strip "/var/"
            self._respond(get_var(name))

        elif path == "/health":
            self._respond({"status": "ok"})

        else:
            self._respond({"error": "not found"}, 404)

    def _respond(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        pass  # silence request logs


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"kernel listening on 127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
