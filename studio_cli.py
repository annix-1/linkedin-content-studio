"""Command line access to the Content Studio store, for the morning routine.

  python3 -I studio_cli.py list <collection> [--out FILE]      all docs as a JSON array
  python3 -I studio_cli.py get <collection> <id>
  python3 -I studio_cli.py put <collection> <id> <json-file>    create or replace
  python3 -I studio_cli.py patch <collection> <id> <json-file>  merge fields into an existing doc
  python3 -I studio_cli.py delete <collection> <id>
  python3 -I studio_cli.py batch <json-file>                     [{"op":"put|patch|delete","collection":..,"id":..,"data":{..}}]
  python3 -I studio_cli.py media <file>                          copy an image into media/, prints its media name
  python3 -I studio_cli.py archive [YYYY-MM-DD]                  rebuild that day's archive (default today)

Collections: items, ideas, trends, briefs, glossary, learning.
"""
import json, os, shutil, sys, re
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import studio_db as db


def load(p):
    with open(p) as f:
        return json.load(f)


def main(a):
    if not a:
        print(__doc__); return 1
    cmd = a[0]
    if cmd == "list":
        docs = db.list_docs(a[1])
        if "--out" in a:
            with open(a[a.index("--out") + 1], "w") as f:
                json.dump(docs, f, ensure_ascii=False, indent=1)
            print(f"{len(docs)} docs written")
        else:
            print(json.dumps(docs, ensure_ascii=False))
    elif cmd == "get":
        print(json.dumps(db.get_doc(a[1], a[2]), ensure_ascii=False))
    elif cmd in ("put", "patch"):
        d = db.write_doc(a[1], a[2], load(a[3]), merge=cmd == "patch")
        print(f"{cmd} {a[1]}/{a[2]} v{d['_v']}")
    elif cmd == "delete":
        db.delete_doc(a[1], a[2]); print(f"deleted {a[1]}/{a[2]}")
    elif cmd == "batch":
        ok = 0
        for w in load(a[1]):
            op, c, i = w["op"], w["collection"], w["id"]
            try:
                if op == "delete":
                    db.delete_doc(c, i)
                else:
                    db.write_doc(c, i, w.get("data") or {}, merge=op == "patch")
                ok += 1
            except Exception as e:
                print(f"FAILED {op} {c}/{i}: {e}")
        print(f"{ok} writes applied")
    elif cmd == "media":
        src = a[1]
        name = re.sub(r"[^A-Za-z0-9._-]", "-", os.path.basename(src))
        if not re.search(r"\.(jpg|jpeg|png|webp|gif)$", name, re.I):
            print("refused: not an image name"); return 1
        os.makedirs(db.MEDIA_DIR, exist_ok=True)
        shutil.copy(src, os.path.join(db.MEDIA_DIR, name))
        print(name)
    elif cmd == "archive":
        day = a[1] if len(a) > 1 else date.today().isoformat()
        r = db.build_archive(day)
        print(f"archive {day}: " + (json.dumps(r["counts"]) if r else "nothing to archive"))
    else:
        print(__doc__); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
