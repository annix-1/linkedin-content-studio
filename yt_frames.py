"""Download the first storyboard sprite sheet of a YouTube video (or Short) for the
Content Studio filmstrip preview.

Usage: python3 -I yt_frames.py <video_id> <out_dir>
Writes <out_dir>/<video_id>-frames.<ext> and prints JSON:
  {"file": ..., "cols": 3, "rows": 3, "count": 9, "w": 320, "h": 180, "intervalMs": 10000}
Prints {"error": ...} and exits 1 when the video has no usable storyboard.
"""
import json, os, re, subprocess, sys

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def fetch(url, out=None):
    cmd = ["curl", "-sL", "-m", "20", "-A", UA, "-H", "Accept-Language: en-US", url]
    if out:
        cmd += ["-o", out]
        subprocess.run(cmd, check=True)
        return None
    return subprocess.run(cmd, check=True, capture_output=True).stdout.decode("utf-8", "replace")


def main(vid, out_dir):
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", vid):
        raise SystemExit(json.dumps({"error": "bad video id"}))
    html = fetch(f"https://www.youtube.com/watch?v={vid}")
    m = re.search(r'"spec":"([^"]+storyboard[^"]+)"', html)
    if not m:
        print(json.dumps({"error": "no storyboard spec"})); sys.exit(1)
    parts = m.group(1).replace("\\u0026", "&").split("|")
    base, levels = parts[0], parts[1:]
    # Pick the largest level whose frames fit a card (<= 320 wide).
    best = None
    for i, lv in enumerate(levels):
        f = lv.split("#")
        w, h, total, cols, rows, interval, name, sigh = int(f[0]), int(f[1]), int(f[2]), int(f[3]), int(f[4]), int(f[5]), f[6], f[7]
        if w <= 320:
            best = (i, w, h, total, cols, rows, interval, name, sigh)
    if not best:
        print(json.dumps({"error": "no level"})); sys.exit(1)
    i, w, h, total, cols, rows, interval, name, sigh = best
    page = name.replace("$M", "0") if "$M" in name else name
    url = base.replace("$L", str(i)).replace("$N", page) + "&sigh=" + sigh
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, f"{vid}-frames.bin")
    fetch(url, tmp)
    kind = subprocess.run(["file", "-b", tmp], capture_output=True, text=True).stdout
    ext = "webp" if "Web/P" in kind else "jpg" if "JPEG" in kind else None
    if not ext or os.path.getsize(tmp) > 2_000_000:
        os.remove(tmp); print(json.dumps({"error": "not an image"})); sys.exit(1)
    path = os.path.join(out_dir, f"{vid}-frames.{ext}")
    os.replace(tmp, path)
    count = min(total, cols * rows)
    print(json.dumps({"file": path, "cols": cols, "rows": rows, "count": count, "w": w, "h": h, "intervalMs": interval or None}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
