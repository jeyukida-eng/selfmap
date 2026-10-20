"""YFCC100M(Flickr CC 사진, AWS Open Data 'multimedia-commons' 미러)에서 거북선 참고 사진 4장을 받는다.
실행: /opt/bvenv/bin/python refs/fetch_refs_yfcc.py            # refs_manifest.json의 4장 재다운로드(+MD5 확인)
      /opt/bvenv/bin/python refs/fetch_refs_yfcc.py --scan     # 65GB 메타데이터 재검색 → refs/yfcc_candidates.json (약 15분, 8병렬)
Wikimedia가 차단된 환경용 대안. 이미지 키 = md5(download_url)을 바이트별 '%x'(0 미패딩)로 이어 붙인 문자열.
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "refs_manifest.json")
BUCKET = "https://multimedia-commons.s3.amazonaws.com"
SQL = BUCKET + "/tools/etc/yfcc100m_dataset.sql"
SQL_SIZE = 65644027904
KEYWORDS = r"(turtle\+?ship|turtleship|geobuk|kobukson|kobuk\+?seon|%EA%B1%B0%EB%B6%81%EC%84%A0|거북선|panokseon)"


def mirror_url(download_url):
    k = "".join("%x" % b for b in hashlib.md5(download_url.encode()).digest())
    return f"{BUCKET}/data/images/{k[:3]}/{k[3:6]}/{k}.jpg"


def fetch_manifest():
    man = json.load(open(MANIFEST))
    for v in man["views"]:
        dst = os.path.join(HERE, v["file"])
        data = urllib.request.urlopen(v["mirror"], timeout=60).read()
        md5 = hashlib.md5(data).hexdigest()
        if v.get("md5") and v["md5"] != md5:
            raise SystemExit(f"MD5 mismatch for {v['id']}: {md5}")
        open(dst, "wb").write(data)
        print(f"[ok] {v['id']} <- {v['flickr_page']} ({v['license']}, {v['author']})")


def scan_chunk(rng):
    s, e = rng
    cmd = f"curl -s -r {s}-{e} {SQL} | LC_ALL=C grep -a -o -i -E '.{{0,400}}{KEYWORDS}.{{0,1500}}'"
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, errors="replace").stdout


def scan(n=8):
    rngs = [(SQL_SIZE * i // n, SQL_SIZE * (i + 1) // n + 2000) for i in range(n)]
    with cf.ThreadPoolExecutor(n) as ex:
        txt = "".join(ex.map(scan_chunk, rngs))
    out = {}
    for m in re.finditer(r"(\d+@N\d\d)([^\x00-\x1f]{1,40}?)(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\.0", txt):
        user, seg = m.group(1), txt[m.end():m.end() + 1500]
        u = re.search(r"http://www\.flickr\.com/photos/" + re.escape(user) +
                      r"/(\d+)/(http://farm\d+\.staticflickr\.com/\d+/\d+_[0-9a-f]+\.jpg)(Attribution[^h]*?)"
                      r"http://creativecommons\.org/licenses/([a-z\-]+/[\d.]+)/", seg)
        body = urllib.parse.unquote_plus(seg[:u.start()]) if u else ""
        if not u or not re.search(KEYWORDS, body, re.I) or u.group(1) in out:
            continue
        out[u.group(1)] = dict(author=urllib.parse.unquote_plus(m.group(2)), taken=m.group(3), text=body[:300],
                               flickr_page=f"https://www.flickr.com/photos/{user}/{u.group(1)}/",
                               license=f"CC {u.group(4).upper()}", mirror=mirror_url(u.group(2)))
    json.dump(out, open(os.path.join(HERE, "yfcc_candidates.json"), "w"), ensure_ascii=False, indent=1)
    print(f"{len(out)} candidates -> refs/yfcc_candidates.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    a = ap.parse_args()
    scan() if a.scan else fetch_manifest()
