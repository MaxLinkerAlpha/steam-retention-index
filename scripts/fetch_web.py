#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 steamcommunity.com/achievements/<appid> 抓取「名称 + 描述 + 全球百分比」。

为什么需要它：
  ISteamUserStats/GetSchemaForGame 对 hidden:1 的成就**连 description 字段都不返回**，
  所以隐藏剧情成就的语义只能靠人肉查 wiki 或客户端截图。
  而新版成就页是 SSR 的 React 应用，脱水状态里同时带着：
    renderContext.queryData -> queries[i].state.data.groups[].achievements[]  (internal_key/api_name/name/description/hidden)
    renderContext.queryData -> queries[j].state.data.percentages             (internal_key -> 百分比)
  两者用 internal_key 关联，一次请求即可拿到全量「隐藏成就 + 描述 + 百分比」，且不需要 API key。

用法：
    python scripts/fetch_web.py 1643320            # 抓一个
    python scripts/fetch_web.py 1643320 2050650    # 抓多个
    python scripts/fetch_web.py --all              # 抓 games.json 里全部（缺的才抓）
    python scripts/fetch_web.py --all --force      # 全部重抓（刷新快照）

输出：data/raw/steam_web/<appid>.json
    {"appid":..,"game":..,"snapshot":..,"source":"steamcommunity/achievements","count":N,
     "achievements":[{"name","desc","hidden","pct","api_name","internal_key"}]}
"""
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "raw", "steam_web")
SNAP = time.strftime("%Y-%m-%d %H:%M")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def parse(html):
    """返回 (app_name, [achievements])"""
    m = re.search(r'<script type="application/json" id="valve-ssr-data"[^>]*>(.*?)</script>',
                  html, re.S)
    if not m:
        raise RuntimeError("找不到 valve-ssr-data（页面结构可能变了）")
    d = json.loads(m.group(1))
    rc = d.get("renderContext") or {}
    qd = rc.get("queryData")
    if isinstance(qd, str):
        qd = json.loads(qd)
    queries = (qd or {}).get("queries") or []

    schema, pcts, app_name = None, {}, None
    for q in queries:
        data = (q.get("state") or {}).get("data") or {}
        if not isinstance(data, dict):
            continue
        if isinstance(data.get("groups"), list):
            for grp in data["groups"]:
                for a in (grp.get("achievements") or []):
                    schema = schema or []
                    schema.append(a)
            app_name = app_name or data.get("appName")
        if isinstance(data.get("percentages"), dict):
            pcts.update({str(k): v for k, v in data["percentages"].items()})
    if not schema:
        raise RuntimeError("拿不到成就 schema")

    rows = []
    for a in schema:
        p = pcts.get(str(a.get("internal_key")))
        rows.append({
            "name": a.get("name") or "",
            "desc": a.get("description") or "",
            "hidden": bool(a.get("hidden")),
            "pct": round(float(p), 1) if p is not None else None,
            "api_name": a.get("api_name") or "",
            "internal_key": a.get("internal_key"),
        })
    return app_name, rows


def fetch(appid, force=False):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "%d.json" % appid)
    if os.path.exists(path) and not force:
        return json.load(open(path, encoding="utf-8"))
    url = "https://steamcommunity.com/achievements/%d" % appid
    app_name, rows = parse(get(url))
    data = {"appid": appid, "game": app_name, "snapshot": SNAP,
            "source": "steamcommunity/achievements", "count": len(rows),
            "achievements": rows}
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return data


def main(argv):
    force = "--force" in argv
    ids = []
    if "--all" in argv:
        g = json.load(open(os.path.join(ROOT, "data", "games.json"), encoding="utf-8"))["games"]
        ids = [x["appid"] for x in g if x["appid"] not in (1190460, 261570)]
    else:
        ids = [int(x) for x in argv if x.isdigit()]
    if not ids:
        print(__doc__)
        return 1
    for a in ids:
        try:
            d = fetch(a, force=force)
            hid = sum(1 for x in d["achievements"] if x["hidden"])
            nodesc = sum(1 for x in d["achievements"] if not x["desc"])
            print("%-9d %-46s n=%3d hidden=%3d 无描述=%2d" %
                  (a, (d["game"] or "?")[:46], d["count"], hid, nodesc))
        except Exception as e:
            print("%-9d FAIL %s: %s" % (a, type(e).__name__, e))
        time.sleep(0.4)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
