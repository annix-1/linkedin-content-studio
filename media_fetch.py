"""Fetch preview images for Content Studio cards into media/.

  python3 -I media_fetch.py page <url> <item-id>       og:image of a web page -> media/<item-id>.<ext>
  python3 -I media_fetch.py youtube <video-id> <item-id>
        thumbnail -> media/<item-id>.jpg, plus the 9-frame filmstrip via yt_frames.py

Prints one JSON line, e.g. {"thumb": "i-x.jpg"} or {"thumb": "i-x.jpg", "frames": {...}}
or {"error": "..."}. Only real images under 2 MB are kept. Nothing downloaded is ever run.
"""
import html, ipaddress, json, os, re, socket, subprocess, sys, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import studio_db as db

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
MAX = 2_000_000
ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
SIGS = [(b"\xff\xd8\xff", "jpg"), (b"\x89PNG", "png"), (b"GIF8", "gif")]


def public_url(url):
    """Only fetch public http(s) addresses: never this computer or the local network,
    even if a scanned page or a redirect points there."""
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError("only http(s) links")
    for info in socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80)):
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError("refused: link points to a private or local address")
    return url


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_CheckedRedirect)


def get(url, limit=MAX + 1):
    req = urllib.request.Request(public_url(url), headers={"User-Agent": UA, "Accept-Language": "en-US"})
    with _opener.open(req, timeout=15) as r:
        return r.read(limit)


def kind(data):
    for sig, ext in SIGS:
        if data.startswith(sig):
            return ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_image(data, item_id):
    ext = kind(data)
    if not ext or len(data) > MAX:
        return None
    os.makedirs(db.MEDIA_DIR, exist_ok=True)
    name = f"{item_id}.{ext}"
    with open(os.path.join(db.MEDIA_DIR, name), "wb") as f:
        f.write(data)
    return name


def og_image(url):
    page = get(url, 3_000_000).decode("utf-8", "replace")
    for pat in (r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image'):
        m = re.search(pat, page, re.I)
        if m:
            return html.unescape(m.group(1))
    return None


def main(a):
    if len(a) != 3 or a[0] not in ("page", "youtube") or not ID_RE.match(a[2]):
        print(__doc__); return 1
    mode, target, item_id = a
    try:
        if mode == "page":
            if not target.startswith(("http://", "https://")):
                raise ValueError("url must start with http(s)://")
            img = og_image(target)
            if not img or "static.licdn.com" in img:  # LinkedIn's generic logo is not a preview
                print(json.dumps({"error": "no usable og:image"})); return 1
            name = save_image(get(img), item_id)
            print(json.dumps({"thumb": name} if name else {"error": "not an image or too big"}))
            return 0 if name else 1
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", target):
            raise ValueError("bad video id")
        out = {"thumb": save_image(get(f"https://i.ytimg.com/vi/{target}/hqdefault.jpg"), item_id)}
        r = subprocess.run([sys.executable, "-I", os.path.join(db.ROOT, "yt_frames.py"), target, db.MEDIA_DIR],
                           capture_output=True, text=True)
        try:
            fr = json.loads(r.stdout.strip().splitlines()[-1])
            if "file" in fr:
                fr["asset"] = os.path.basename(fr.pop("file"))
                out["frames"] = fr
        except (ValueError, IndexError):
            pass
        print(json.dumps(out)); return 0
    except Exception as e:  # report, never crash the routine
        print(json.dumps({"error": str(e)[:200]})); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
