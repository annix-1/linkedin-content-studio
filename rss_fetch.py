"""Read a Reddit (or any Atom/RSS) feed as plain JSON for the morning routine.

  python3 -I rss_fetch.py <feed-url> [max-entries]

Examples:
  python3 -I rss_fetch.py "https://www.reddit.com/r/linkedin/top/.rss?t=week"
  python3 -I rss_fetch.py "https://www.reddit.com/r/linkedin/comments/<id>/<slug>/.rss"   (a thread's comments)

Prints a JSON array of {title, link, updated, text}. Reddit rate-limits: wait a few
seconds between calls. On a 429 it prints {"error": "rate-limited"}.
"""
import html, json, re, sys, urllib.error, urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def clean(s):
    s = html.unescape(html.unescape(s or ""))
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def main(a):
    if not a or not a[0].startswith("https://"):
        print(__doc__); return 1
    n = int(a[1]) if len(a) > 1 else 25
    try:
        req = urllib.request.Request(a[0], headers={"User-Agent": UA})
        xml = urllib.request.urlopen(req, timeout=15).read(3_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        print(json.dumps({"error": "rate-limited" if e.code == 429 else f"http {e.code}"})); return 1
    except Exception as e:
        print(json.dumps({"error": str(e)[:200]})); return 1
    out = []
    for e in re.findall(r"<(?:entry|item)>(.*?)</(?:entry|item)>", xml, re.S)[:n]:
        g = lambda pat: (re.search(pat, e, re.S) or [None, None])[1]
        out.append({
            "title": clean(g(r"<title[^>]*>(.*?)</title>")),
            "link": g(r'<link[^>]*href="([^"]+)"') or clean(g(r"<link>(.*?)</link>")),
            "updated": clean(g(r"<(?:updated|pubDate)>(.*?)</(?:updated|pubDate)>")),
            "text": clean(g(r"<(?:content|description)[^>]*>(.*?)</(?:content|description)>"))[:600],
        })
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
