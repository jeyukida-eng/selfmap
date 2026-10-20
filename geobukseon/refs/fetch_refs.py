"""Fetch CC-licensed turtle-ship reference photos from Wikimedia Commons, one per design view.
Run: /opt/bvenv/bin/python refs/fetch_refs.py [--pick bow34="File:Foo.jpg" ...] [--dry-run]
Writes refs/ref_<view>.jpg (long side 1600 px thumbnail) and refs/refs_manifest.json.
Exit codes: 0 ok, 1 nothing suitable found for some view, 2 network/API failure.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DESIGN = os.path.join(ROOT, "design", "geobukseon_design.json")
MANIFEST = os.path.join(HERE, "refs_manifest.json")
API = "https://commons.wikimedia.org/w/api.php"
UA = "GeobukseonRefFetcher/1.0 (Blender photoreal study; contact: local user) python-urllib"
LONG_SIDE = 1600
TIMEOUT = 20

CATEGORIES = ["Category:Turtle ships", "Category:Geobukseon"]
SEARCHES = ["Geobukseon", "turtle ship replica", "거북선"]

# keyword scoring per view id (title + description, lower-case)
VIEW_KEYWORDS = {
    "bow34": {"+": ["bow", "front", "dragon", "head", "yongdu", "prow", "용두", "선수"], "-": ["stern", "interior", "inside", "model", "drawing"]},
    "side": {"+": ["side", "broadside", "profile", "full", "whole", "replica", "tongyeong", "yeosu", "통영", "여수"],
             "-": ["interior", "inside", "detail", "model", "drawing"]},
    "stern34": {"+": ["stern", "rear", "back", "rudder", "선미"], "-": ["interior", "inside", "model", "drawing"]},
    "aerial": {"+": ["aerial", "above", "top", "roof", "deck", "spikes", "drone", "bird"], "-": ["interior", "inside", "model", "drawing"]},
}
OK_LICENSE = re.compile(r"(cc[- ]?by|cc0|cc-zero|public domain|pd-)", re.I)


class NetError(RuntimeError):
    pass


def api(params):
    params = dict(params, format="json", formatversion="2")
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise NetError(f"Commons API request failed: {e}") from e


def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
    except (urllib.error.URLError, OSError) as e:
        raise NetError(f"image download failed: {e}") from e
    if not data.startswith(b"\xff\xd8"):
        raise NetError(f"downloaded data is not a JPEG: {url}")
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    return len(data)


def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def candidates():
    titles = set()
    for cat in CATEGORIES:
        cont = {}
        for _ in range(5):
            res = api(dict(action="query", list="categorymembers", cmtitle=cat, cmtype="file", cmlimit="200", **cont))
            for m in res.get("query", {}).get("categorymembers", []):
                titles.add(m["title"])
            if "continue" not in res:
                break
            cont = res["continue"]
    for q in SEARCHES:
        res = api(dict(action="query", list="search", srsearch=q, srnamespace="6", srlimit="100"))
        for m in res.get("query", {}).get("search", []):
            titles.add(m["title"])
    return sorted(t for t in titles if t.lower().endswith((".jpg", ".jpeg")))


def imageinfo(titles):
    out = {}
    titles = list(titles)
    for i in range(0, len(titles), 40):
        res = api(dict(action="query", prop="imageinfo", titles="|".join(titles[i:i + 40]),
                       iiprop="url|size|extmetadata|mime"))
        for p in res.get("query", {}).get("pages", []):
            if "imageinfo" not in p:
                continue
            ii = p["imageinfo"][0]
            md = ii.get("extmetadata", {})
            out[p["title"]] = {
                "title": p["title"],
                "width": ii.get("width"), "height": ii.get("height"),
                "original_url": ii.get("url"), "page_url": ii.get("descriptionurl"),
                "license": strip_html(md.get("LicenseShortName", {}).get("value", "")),
                "license_url": md.get("LicenseUrl", {}).get("value", ""),
                "artist": strip_html(md.get("Artist", {}).get("value", "")),
                "credit": strip_html(md.get("Credit", {}).get("value", "")),
                "description": strip_html(md.get("ImageDescription", {}).get("value", ""))[:400],
                "date": strip_html(md.get("DateTimeOriginal", {}).get("value", "")),
            }
    return out


def thumb_url(title, w, h):
    key = "iiurlwidth" if (w or 0) >= (h or 0) else "iiurlheight"
    res = api({"action": "query", "prop": "imageinfo", "titles": title, "iiprop": "url", key: str(LONG_SIDE)})
    pages = res.get("query", {}).get("pages", [])
    if not pages or "imageinfo" not in pages[0]:
        raise NetError(f"no imageinfo for {title}")
    ii = pages[0]["imageinfo"][0]
    return ii.get("thumburl") or ii.get("url")


def score(info, vid):
    text = (info["title"] + " " + info["description"]).lower()
    kw = VIEW_KEYWORDS.get(vid, {"+": [], "-": []})
    s = sum(3 for k in kw["+"] if k in text) - sum(5 for k in kw["-"] if k in text)
    if (info["width"] or 0) >= 1600 or (info["height"] or 0) >= 1600:
        s += 1
    if (info["width"] or 0) > (info["height"] or 0):
        s += 1  # landscape preferred
    return s


def parse_picks(items):
    picks = {}
    for it in items or []:
        if "=" not in it:
            raise SystemExit(f"--pick expects view=\"File:Name.jpg\", got {it!r}")
        k, v = it.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if not v.startswith("File:"):
            v = "File:" + v
        picks[k.strip()] = v
    return picks


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pick", action="append", metavar='VIEW="File:..."', help="force a Commons file for a view")
    ap.add_argument("--dry-run", action="store_true", help="choose files and print, do not download")
    args = ap.parse_args()

    with open(DESIGN, encoding="utf-8") as f:
        design = json.load(f)
    views = [(v["id"], os.path.join(ROOT, v["ref"])) for v in design["views"]]
    picks = parse_picks(args.pick)
    unknown = set(picks) - {v for v, _ in views}
    if unknown:
        raise SystemExit(f"unknown view id(s) in --pick: {sorted(unknown)}")
    today = datetime.date.today().isoformat()

    try:
        titles = candidates() if len(picks) < len(views) else []
        info = imageinfo(set(titles) | set(picks.values()))
        print(f"[refs] {len(titles)} candidate JPEGs, {len(info)} with metadata")
        used, manifest, missing = set(), {"accessed": today, "source": "Wikimedia Commons", "views": {}}, []
        for vid, path in views:
            if vid in picks:
                choice = info.get(picks[vid])
                if choice is None:
                    print(f"[refs] {vid}: picked file not found on Commons: {picks[vid]}", file=sys.stderr)
                    missing.append(vid)
                    continue
            else:
                pool = [i for i in info.values() if OK_LICENSE.search(i["license"]) and i["title"] not in used]
                pool.sort(key=lambda i: (-score(i, vid), i["title"]))
                choice = pool[0] if pool and score(pool[0], vid) > 0 else None
                if choice is None:
                    print(f"[refs] {vid}: no suitable CC-licensed photo found", file=sys.stderr)
                    missing.append(vid)
                    continue
            used.add(choice["title"])
            entry = dict(choice, file=os.path.relpath(path, ROOT), picked_by="user" if vid in picks else "auto",
                         accessed=today)
            if not args.dry_run:
                entry["thumb_url"] = thumb_url(choice["title"], choice["width"], choice["height"])
                entry["bytes"] = download(entry["thumb_url"], path)
            manifest["views"][vid] = entry
            print(f"[refs] {vid}: {choice['title']}  ({choice['license']}; {choice['artist'][:60]})")
    except NetError as e:
        print(f"[refs] ERROR: network/API failure - {e}", file=sys.stderr)
        print("[refs] Wikimedia Commons is unreachable from this environment (blocked or offline). "
              "No files were written. Re-run where commons.wikimedia.org and upload.wikimedia.org are reachable, "
              "or place refs/ref_<view>.jpg manually and record them in refs/refs_manifest.json.", file=sys.stderr)
        return 2

    if not args.dry_run:
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        print(f"[refs] wrote {MANIFEST}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
