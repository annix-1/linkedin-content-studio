"""Content Studio local server.

  python3 -I server.py            serves http://localhost:8020 (or the port in config.json)

Serves the board (content-studio.html), images from media/, and a small JSON API
over the SQLite store in data/studio.db. No third-party packages needed.

The server refuses to start until setup has verified the Taplio LinkedIn MCP
connection (config.json -> taplioLinkedInMcp.verifiedAt). The board's daily
content comes from that MCP, so without it there is nothing to show.
"""
import json, mimetypes, os, re, sys, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import studio_db as db

CONFIG_PATH = os.path.join(db.ROOT, "config.json")
PAGE = os.path.join(db.ROOT, "content-studio.html")
MEDIA_RE = re.compile(r"^[A-Za-z0-9._-]+\.(jpg|jpeg|png|webp|gif)$", re.I)

MCP_GATE = """
================================================================
  Content Studio needs the Taplio LinkedIn MCP. It is required.
================================================================
The daily scan reads LinkedIn through the Taplio LinkedIn MCP.
Connect it first, then ask your AI assistant to finish setup:

  1. Watch the 3-minute setup video:
     https://www.youtube.com/watch?v=afjA8ifgo6A
  2. Get the Taplio LinkedIn MCP:
     https://taplio.com/taplio-linkedin-mcp
  3. Claude Code (terminal) users can also run:
     claude mcp add --transport http taplio https://mcp.taplio.com

Then tell your assistant: "The Taplio LinkedIn MCP is connected,
continue the Content Studio setup." It will verify the connection
and record it in config.json.
"""


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH) as f:
        return json.load(f)


IMAGE_SIGS = (b"\xff\xd8\xff", b"\x89PNG", b"GIF8")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PORT = 8020  # set at startup from config.json / $PORT


def is_image(data):
    return data.startswith(IMAGE_SIGS) or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")


class Handler(BaseHTTPRequestHandler):
    def _local_only(self):
        """Block other websites from reaching the board: DNS rebinding (Host) and
        cross-site writes (Origin). Only pages served from this board may write."""
        allowed = {f"localhost:{PORT}", f"127.0.0.1:{PORT}"}
        if self.headers.get("Host", "") not in allowed:
            self._send(403, {"error": "forbidden host"}); return False
        origin = self.headers.get("Origin")
        if self.command != "GET" and origin not in {f"http://{h}" for h in allowed}:
            self._send(403, {"error": "forbidden origin"}); return False
        return True

    def log_message(self, fmt, *args):
        if "/api/version" not in self.path:
            sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _route(self):
        p = urlparse(self.path)
        parts = [unquote(x) for x in p.path.strip("/").split("/") if x]
        return p, parts

    def do_GET(self):
        if not self._local_only():
            return
        p, parts = self._route()
        try:
            if not parts or parts == ["index.html"]:
                with open(PAGE, "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if parts[0] == "media" and len(parts) == 2 and MEDIA_RE.match(parts[1]):
                fp = os.path.join(db.MEDIA_DIR, parts[1])
                if not os.path.exists(fp):
                    return self._send(404, {"error": "not found"})
                with open(fp, "rb") as f:
                    return self._send(200, f.read(), mimetypes.guess_type(fp)[0] or "application/octet-stream")
            if parts[0] == "api":
                if parts[1:] == ["version"]:
                    return self._send(200, {"v": db.version_stamp()})
                if parts[1:2] == ["archive"]:
                    if len(parts) == 2:
                        return self._send(200, db.list_archive())
                    a = db.read_archive(parts[2]) if DAY_RE.match(parts[2]) else None
                    return self._send(200 if a else 404, a or {"error": "no archive for that day"})
                if len(parts) == 2:
                    return self._send(200, db.list_docs(parts[1]))
                if len(parts) == 3:
                    d = db.get_doc(parts[1], parts[2])
                    return self._send(200 if d else 404, d or {"error": "not found"})
            self._send(404, {"error": "not found"})
        except ValueError as e:
            self._send(400, {"error": str(e)})

    def do_PUT(self):
        self._write(merge=False)

    def do_PATCH(self):
        self._write(merge=True)

    def _write(self, merge):
        if not self._local_only():
            return
        p, parts = self._route()
        if len(parts) != 3 or parts[0] != "api":
            return self._send(404, {"error": "not found"})
        try:
            data = json.loads(self._body() or b"{}")
            if not isinstance(data, dict):
                raise ValueError("body must be a JSON object")
            self._send(200, db.write_doc(parts[1], parts[2], data, merge=merge))
        except KeyError as e:
            self._send(404, {"error": str(e)})
        except ValueError as e:
            self._send(400, {"error": str(e)})

    def do_DELETE(self):
        if not self._local_only():
            return
        p, parts = self._route()
        if len(parts) != 3 or parts[0] != "api":
            return self._send(404, {"error": "not found"})
        try:
            db.delete_doc(parts[1], parts[2]); self._send(200, {"deleted": True})
        except ValueError as e:
            self._send(400, {"error": str(e)})

    def do_POST(self):
        if not self._local_only():
            return
        p, parts = self._route()
        if parts != ["api", "upload"]:
            return self._send(404, {"error": "not found"})
        name = (parse_qs(p.query).get("name") or ["upload.jpg"])[0]
        name = re.sub(r"[^A-Za-z0-9._-]", "-", os.path.basename(name))
        if not MEDIA_RE.match(name):
            return self._send(400, {"error": "Only jpg, png, webp or gif images."})
        body = self._body()
        if not body or len(body) > 8_000_000:
            return self._send(400, {"error": "Images must be under 8 MB."})
        if not is_image(body):
            return self._send(400, {"error": "That file is not a jpg, png, webp or gif image."})
        stem, ext = os.path.splitext(name)
        name = f"m-{stem[:40]}-{int(time.time())}{ext.lower()}"
        os.makedirs(db.MEDIA_DIR, exist_ok=True)
        with open(os.path.join(db.MEDIA_DIR, name), "wb") as f:
            f.write(body)
        self._send(200, {"id": name, "url": "/media/" + name})


if __name__ == "__main__":
    cfg = load_config()
    if cfg is None:
        print("No config.json yet. Ask your AI assistant to run the setup in SETUP.md first.")
        print(MCP_GATE)
        sys.exit(1)
    if not (cfg.get("taplioLinkedInMcp") or {}).get("verifiedAt"):
        print(MCP_GATE)
        sys.exit(1)
    PORT = int(os.environ.get("PORT") or cfg.get("port") or 8020)
    db.connect().close()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Content Studio running at http://localhost:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
