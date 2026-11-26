#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量抓取：标题 → appid → 官方成就名/描述/隐藏标记 + 全球解锁率

输出
  data/games.json            清单（appid、英文名、类型、发行日、原始标题）
  data/raw/steam/<appid>.json 每个游戏的原始数据（schema + percentages 合并，含快照时间）

凭证：STEAM_WEB_API_KEY（环境变量 > ../.env > 报错）。从不打印 key。

用法
  python scripts/fetch_steam.py            # 抓 data/titles.txt 里所有标题
  python scripts/fetch_steam.py --force    # 忽略已有缓存重抓
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TITLES = os.path.join(ROOT, "data", "titles.txt")
GAMES = os.path.join(ROOT, "data", "games.json")
RAW = os.path.join(ROOT, "data", "raw", "steam")
SNAP = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M +08")


def load_key():
    k = os.environ.get("STEAM_WEB_API_KEY", "").strip()
    if k:
        return k
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line.startswith("STEAM_WEB_API_KEY="):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v
    sys.exit("缺少 STEAM_WEB_API_KEY（环境变量或 .env）")


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "retention/3.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:                                     # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(1.2)


def search(title):
    q = urllib.parse.quote(title)
    d = get("https://store.steampowered.com/api/storesearch/?term=%s&l=english&cc=US" % q)
    items = [x for x in d.get("items", []) if x.get("type") == "app"]
    return items[0]["id"] if items else None


def appinfo(appid):
    d = get("https://store.steampowered.com/api/appdetails?appids=%d&l=english&cc=US" % appid)
    node = d.get(str(appid), {})
    if not node.get("success"):
        return None
    it = node["data"]
    return {"name": it.get("name"), "release": (it.get("release_date") or {}).get("date"),
            "genres": [g["description"] for g in it.get("genres", [])]}


def achievements(appid, key):
    q = urllib.parse.urlencode({"key": key, "appid": appid, "l": "english"})
    sch = get("https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/?" + q)
    pct = get("https://api.steampowered.com/ISteamUserStats/"
              "GetGlobalAchievementPercentagesForApp/v2/?gameid=%d" % appid)
    pm = {x["name"]: float(x["percent"]) for x in pct["achievementpercentages"]["achievements"]}
    rows = []
    for a in (sch.get("game", {}).get("availableGameStats", {}) or {}).get("achievements", []) or []:
        rows.append({"api": a.get("name"), "name": a.get("displayName") or "",
                     "desc": a.get("description") or "", "hidden": bool(a.get("hidden")),
                     "pct": pm.get(a.get("name"))})
    rows.sort(key=lambda r: -(r["pct"] or 0))
    return rows


def main():
    force = "--force" in sys.argv
    key = load_key()
    os.makedirs(RAW, exist_ok=True)
    titles = [l.strip() for l in open(TITLES, encoding="utf-8") if l.strip()]
    games = json.load(open(GAMES, encoding="utf-8")) if os.path.exists(GAMES) else {}
    by_title = {g["title"]: g for g in games.get("games", [])}

    for title in titles:
        if not force and title in by_title and os.path.exists(
                os.path.join(RAW, "%d.json" % by_title[title]["appid"])):
            continue
        try:
            appid = search(title)
            if not appid:
                print("  MISS   %s" % title)
                continue
            info = appinfo(appid)
            if not info:
                print("  NOINFO %-40s %d" % (title, appid))
                continue
            path = os.path.join(RAW, "%d.json" % appid)
            if os.path.exists(path) and not force:
                data = json.load(open(path, encoding="utf-8"))
            else:
                rows = achievements(appid, key)
                data = {"appid": appid, "game": info["name"], "snapshot": SNAP,
                        "count": len(rows), "achievements": rows}
                json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            by_title[title] = {"title": title, "appid": appid, "name": info["name"],
                               "release": info["release"], "genres": info["genres"],
                               "count": data["count"]}
            print("  OK  %-44s %-9d %-38s %3d" % (title[:44], appid, info["name"][:38], data["count"]))
        except Exception as e:                                # noqa: BLE001
            print("  FAIL %-40s %s" % (title[:40], type(e).__name__))
        time.sleep(0.25)

    out = {"snapshot": SNAP, "games": sorted(by_title.values(), key=lambda g: g["title"].lower())}
    json.dump(out, open(GAMES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n总计 %d 款 -> data/games.json" % len(out["games"]))


if __name__ == "__main__":
    main()
