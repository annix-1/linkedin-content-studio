"""Content Studio local data store (SQLite) and daily archive.

One table of JSON documents keyed by (collection, id). Used by server.py (the
board) and studio_cli.py (the morning routine), so the routine never needs the
server running.
"""
import json, os, re, sqlite3, threading, time
from datetime import date, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "data", "studio.db")
MEDIA_DIR = os.path.join(ROOT, "media")
ARCHIVE_DIR = os.path.join(ROOT, "archive")
COLLECTIONS = {"items", "ideas", "trends", "briefs", "glossary", "learning"}
_lock = threading.Lock()


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS docs (
        collection TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1, updated_at REAL NOT NULL,
        PRIMARY KEY (collection, id))""")
    return con


def _check(coll, doc_id=None):
    if coll not in COLLECTIONS:
        raise ValueError(f"unknown collection {coll!r}")
    if doc_id is not None and (not doc_id or "/" in doc_id or len(doc_id) > 200):
        raise ValueError(f"bad id {doc_id!r}")


def _row(r):
    d = json.loads(r[2]); d["id"] = r[1]; d["_v"] = r[3]
    return d


def list_docs(coll):
    _check(coll)
    with connect() as con:
        return [_row(r) for r in con.execute("SELECT collection,id,data,version FROM docs WHERE collection=?", (coll,))]


def get_doc(coll, doc_id):
    _check(coll, doc_id)
    with connect() as con:
        r = con.execute("SELECT collection,id,data,version FROM docs WHERE collection=? AND id=?", (coll, doc_id)).fetchone()
    return _row(r) if r else None


def _merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            _merge(a[k], v)
        else:
            a[k] = v
    return a


def write_doc(coll, doc_id, data, merge=False):
    _check(coll, doc_id)
    data = {k: v for k, v in data.items() if k not in ("id", "_v")}
    with _lock, connect() as con:
        r = con.execute("SELECT data,version FROM docs WHERE collection=? AND id=?", (coll, doc_id)).fetchone()
        if merge:
            if not r:
                raise KeyError(f"{coll}/{doc_id} does not exist")
            data = _merge(json.loads(r[0]), data)
        version = (r[1] + 1) if r else 1
        con.execute("INSERT OR REPLACE INTO docs (collection,id,data,version,updated_at) VALUES (?,?,?,?,?)",
                    (coll, doc_id, json.dumps(data, ensure_ascii=False), version, time.time()))
    _touch_archive(data)
    d = dict(data); d["id"] = doc_id; d["_v"] = version
    return d


def delete_doc(coll, doc_id):
    _check(coll, doc_id)
    with _lock, connect() as con:
        con.execute("DELETE FROM docs WHERE collection=? AND id=?", (coll, doc_id))
    _bump()


_last_change = [time.time()]


def _bump():
    _last_change[0] = time.time()


def version_stamp():
    with connect() as con:
        r = con.execute("SELECT MAX(updated_at), COUNT(*) FROM docs").fetchone()
    return f"{r[0] or 0:.4f}-{r[1]}-{_last_change[0]:.4f}"


# ---------- daily archive ----------

def _day(ts):
    return str(ts)[:10] if ts else None


def _touch_archive(data):
    _bump()
    days = {date.today().isoformat()}
    for k in ("decidedAt", "createdAt", "keptAt", "updatedAt"):
        d = _day(data.get(k))
        if d and len(d) == 10:
            days.add(d)
    for d in days:
        try:
            build_archive(d)
        except Exception as e:  # the archive must never block a write
            print("archive error", d, e)


def build_archive(day):
    items = list_docs("items"); ideas = list_docs("ideas"); trends = list_docs("trends")
    glossary = list_docs("glossary"); briefs = {b["id"]: b for b in list_docs("briefs")}
    idea_by = {d["id"]: d for d in ideas}
    on = lambda d, *keys: any(_day(d.get(k)) == day for k in keys)
    saved = [i for i in items if i.get("status") == "kept" and on(i, "decidedAt")]
    passed = [i for i in items if i.get("status") == "rejected" and on(i, "decidedAt")]
    followed = [t for t in trends if t.get("status") == "kept" and on(t, "decidedAt")]
    crossed_t = [t for t in trends if t.get("status") == "rejected" and on(t, "decidedAt")]
    picked = [d for d in ideas if (d.get("status") == "picked" and on(d, "decidedAt")) or (d.get("manual") and on(d, "createdAt"))]
    terms = [g for g in glossary if g.get("status") != "dismissed" and not g.get("auto") and on(g, "keptAt", "createdAt", "updatedAt")]
    brief = briefs.get(day)
    if not (saved or passed or followed or crossed_t or picked or terms):
        return None

    def item_view(i):
        return {k: i.get(k) for k in ("id", "title", "url", "source", "creator", "thumb", "likes", "note", "tags", "preview")} | {
            "ideas": [idea_by[x]["title"] for x in (i.get("ideaIds") or []) if x in idea_by]}

    doc = {
        "date": day,
        "headline": brief.get("headline") if brief else None,
        "saved": [item_view(i) for i in saved],
        "trendsFollowed": [{k: t.get(k) for k in ("id", "title", "said", "community")} for t in followed],
        "ideas": [{"id": d["id"], "hook": d.get("title"), "explain": d.get("explain"), "manual": bool(d.get("manual")),
                   "status": d.get("status"), "notes": d.get("notes"),
                   "linked": [i["title"] for i in items if d["id"] in (i.get("ideaIds") or []) or i["id"] in (d.get("itemIds") or [])]} for d in picked],
        "glossaryKept": [{k: g.get(k) for k in ("term", "kind", "meaning")} for g in terms],
        "counts": {"saved": len(saved), "passed": len(passed), "trendsFollowed": len(followed),
                   "trendsCrossed": len(crossed_t), "ideas": len(picked), "terms": len(terms)},
        "builtAt": datetime.now().isoformat(timespec="seconds"),
    }
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    with open(os.path.join(ARCHIVE_DIR, f"{day}.json"), "w") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    with open(os.path.join(ARCHIVE_DIR, f"{day}.md"), "w") as f:
        f.write(_markdown(doc))
    return doc


def _markdown(a):
    d = datetime.strptime(a["date"], "%Y-%m-%d")
    out = [f"# Content Studio archive: {d.strftime('%a %d %b %Y')}", ""]
    if a["headline"]:
        out += [f"**Brief:** {a['headline']}", ""]
    c = a["counts"]
    out += [f"{c['saved']} saved · {c['passed']} passed · {c['trendsFollowed']} trends followed · {c['ideas']} ideas picked or added", ""]
    if a["trendsFollowed"]:
        out += ["## Trends I followed", ""]
        for t in a["trendsFollowed"]:
            s, m = t.get("said") or {}, t.get("community") or {}
            out += [f"- **{t['title']}**", f"  - They say ({s.get('who','')}): {s.get('text','')}", f"  - People say: {m.get('text','')}"]
        out.append("")
    if a["saved"]:
        out += ["## Saved pieces", ""]
        for i in a["saved"]:
            link = f"[{i['title']}]({i['url']})" if i.get("url") else i["title"]
            out.append(f"- {link} · {i.get('creator') or i.get('source') or ''}")
            if i["ideas"]:
                out.append(f"  - For idea: {'; '.join(i['ideas'])}")
            if i.get("likes"):
                out.append(f"  - What I like: {i['likes']}")
            if i.get("note"):
                out.append(f"  - Notes: {i['note']}")
        out.append("")
    if a["ideas"]:
        out += ["## Ideas I picked or added", ""]
        for d in a["ideas"]:
            out.append(f"- **{d['hook']}**{' (my idea)' if d['manual'] else ''}")
            if d.get("explain"):
                out.append(f"  - {d['explain']}")
            if d["linked"]:
                out.append(f"  - Linked: {'; '.join(d['linked'])}")
            if d.get("notes"):
                out.append(f"  - Notes: {d['notes']}")
        out.append("")
    if a["glossaryKept"]:
        out += ["## Glossary terms I kept", ""] + [f"- **{g['term']}** ({g.get('kind')}): {g.get('meaning') or ''}" for g in a["glossaryKept"]] + [""]
    return "\n".join(out)


def list_archive():
    if not os.path.isdir(ARCHIVE_DIR):
        return []
    out = []
    for f in sorted(os.listdir(ARCHIVE_DIR), reverse=True):
        if f.endswith(".json"):
            try:
                with open(os.path.join(ARCHIVE_DIR, f)) as fh:
                    a = json.load(fh)
                out.append({"date": a["date"], "headline": a.get("headline"), "counts": a.get("counts", {})})
            except Exception:
                pass
    return out


def read_archive(day):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day or ""):
        return None
    p = os.path.join(ARCHIVE_DIR, f"{day}.json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)
