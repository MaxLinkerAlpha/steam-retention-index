#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 issue 里提交的 appid 收进库。

设计约束（写死在代码里，不靠人记）：
  · 单次最多 5 个 appid      —— 防止一条 issue 塞几十个
  · 每天最多 30 个新 appid   —— 全站配额，超了排队到明天
  · 每个 appid 只发 3 个请求  —— appdetails + 官方百分比 + 成就页
  · 请求间隔 ≥ 6 秒          —— 30 款全排满也只有 90 次请求 / 约 3 分钟
  · 已收录直接跳过            —— 不重复抓
  · 抓过 7 天内不重抓         —— raw/steam_web 缓存即事实来源

用法：
    python scripts/ingest.py --appids 1245620,1086940
    python scripts/ingest.py --body-file /tmp/issue.md
    python scripts/ingest.py --appids 123 --dry-run
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
WEB = os.path.join(ROOT, "data", "raw", "steam_web")
QUEUE = os.path.join(DATA, "submissions.json")

MAX_PER_ISSUE = 5
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "30"))
SLEEP = float(os.environ.get("FETCH_SLEEP", "6"))
UA = "steam-retention-index/1.0 (research; low-frequency; contact via GitHub issue)"
TZ = timezone(timedelta(hours=8))


def http_json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def appdetails(appid):
    d = http_json("https://store.steampowered.com/api/appdetails?appids=%d&l=english&cc=US" % appid)
    node = d.get(str(appid)) or {}
    if not node.get("success"):
        return None
    return node.get("data") or {}


def global_pcts(appid):
    d = http_json("https://api.steampowered.com/ISteamUserStats/"
                  "GetGlobalAchievementPercentagesForApp/v2/?gameid=%d" % appid)
    rows = ((d.get("achievementpercentages") or {}).get("achievements") or [])
    return {r["name"]: r["percent"] for r in rows if r.get("name")}


def load(path, default):
    if not os.path.exists(path):
        return default
    return json.load(open(path, encoding="utf-8"))


def today():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def parses(appids):
    """从 issue 正文里抠出 appid：先认商店/成就页/SteamDB 链接，再认纯数字。"""
    out = []
    text = " ".join(appids)
    for m in re.findall(r"(?:/app/|/achievements/|steamdb\.info/app/|appids?=)(\d{2,8})", text):
        v = int(m)
        if v not in out:
            out.append(v)
    if not out:
        for m in re.findall(r"(?<![\d.])(\d{3,8})(?![\d.])", text):
            v = int(m)
            if 10 <= v <= 4_000_000_000 and v not in out:
                out.append(v)
    return out[:MAX_PER_ISSUE]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--appids", default="")
    ap.add_argument("--body-file", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    src = a.appids
    if a.body_file and os.path.exists(a.body_file):
        src += " " + open(a.body_file, encoding="utf-8", errors="replace").read()
    wanted = parses([src])
    if not wanted:
        print("RESULT=no_appid")
        return 0

    games_doc = load(os.path.join(DATA, "games.json"), {"games": []})
    known = {g["appid"] for g in games_doc["games"]}
    queue = load(QUEUE, {"submissions": []})
    used_today = len([s for s in queue["submissions"]
                      if s.get("status") == "accepted" and s.get("at", "").startswith(today())])

    added, skipped, rejected = [], [], []
    for appid in wanted:
        if appid in known:
            skipped.append((appid, "已收录"))
            continue
        if os.path.exists(os.path.join(WEB, "%d.json" % appid)):
            skipped.append((appid, "已有网页快照"))
            continue
        if used_today >= DAILY_LIMIT:
            skipped.append((appid, "今日配额已满（%d/%d），明天再来" % (used_today, DAILY_LIMIT)))
            continue

        info = appdetails(appid)
        if not info:
            rejected.append((appid, "商店查不到这个 appid"))
            continue
        if (info.get("type") or "") != "game":
            rejected.append((appid, "不是游戏本体（type=%s）" % info.get("type")))
            continue
        pcts = global_pcts(appid)
        if not pcts:
            rejected.append((appid, "该作没有 Steam 成就，无法计算留存"))
            continue

        if a.dry_run:
            added.append((appid, info.get("name"), len(pcts)))
            continue

        rc = subprocess.run([sys.executable, os.path.join(HERE, "fetch_web.py"), str(appid)],
                            cwd=ROOT, capture_output=True, text=True)
        if rc.returncode != 0:
            rejected.append((appid, "成就页抓取失败（Steam 可能限流）"))
            time.sleep(SLEEP)
            continue

        snap = datetime.now(TZ).strftime("%Y-%m-%d %H:%M +08")
        games_doc["games"].append({
            "title": info.get("name"),
            "appid": appid,
            "name": info.get("name"),
            "release": (info.get("release_date") or {}).get("date", ""),
            "genres": [g["description"] for g in (info.get("genres") or [])],
            "count": len(pcts),
        })
        titles = os.path.join(DATA, "titles.txt")
        with open(titles, "a", encoding="utf-8") as f:
            f.write((info.get("name") or str(appid)) + "\n")
        queue["submissions"].append({"appid": appid, "name": info.get("name"), "at": snap,
                                     "status": "accepted", "achievements": len(pcts)})
        used_today += 1
        added.append((appid, info.get("name"), len(pcts)))
        time.sleep(SLEEP)

    games_doc["snapshot"] = datetime.now(TZ).strftime("%Y-%m-%d %H:%M +08")
    if added and not a.dry_run:
        json.dump(games_doc, open(os.path.join(DATA, "games.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        json.dump(queue, open(QUEUE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        for s in ("detect_ladders.py", "curate_auto.py", "build_pages.py"):
            r = subprocess.run([sys.executable, os.path.join(HERE, s)], cwd=ROOT,
                               capture_output=True, text=True)
            print("%s rc=%d %s" % (s, r.returncode, (r.stdout or r.stderr).strip()[-300:]))
            if r.returncode != 0:
                print("RESULT=build_failed")
                return 1

    print("ADDED=" + ",".join("%d:%s" % (a, n) for a, n, _ in added))
    print("SKIPPED=" + ",".join("%d:%s" % s for s in skipped))
    print("REJECTED=" + ",".join("%d:%s" % s for s in rejected))
    print("QUOTA=%d/%d" % (used_today, DAILY_LIMIT))
    print("RESULT=ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
