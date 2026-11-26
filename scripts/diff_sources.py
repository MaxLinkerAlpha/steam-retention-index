#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核对数据源：steam_web（唯一数据源）vs 旧的 API 快照 / 上一轮网页快照。

输出三类问题：
  1) 成就条目差异：数量、名称只在一边出现的
  2) 百分比差异：>0.15pp 的条目数、最大差、均值差
  3) 缺百分比的条目（网页源没有 percentages 的情况）

用法：
    python scripts/diff_sources.py            # web vs API(raw/steam)
    python scripts/diff_sources.py --old-web  # web vs 上一轮网页快照(_tmp/snap_old_web)
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "data", "raw", "steam_web")
API = os.path.join(ROOT, "data", "raw", "steam")
OLD = os.path.join(ROOT, "_tmp", "snap_old_web")


def load(p):
    d = json.load(open(p, encoding="utf-8"))
    return d, {a["name"]: a for a in d["achievements"]}


def main(argv):
    base = OLD if "--old-web" in argv else API
    rows = []
    for p in sorted(glob.glob(os.path.join(WEB, "*.json"))):
        appid = os.path.basename(p)[:-5]
        q = os.path.join(base, appid + ".json")
        if not os.path.exists(q):
            rows.append((appid, None, "缺对比源"))
            continue
        w, wm = load(p)
        a, am = load(q)
        only_w = [n for n in wm if n not in am]
        only_a = [n for n in am if n not in wm]
        diffs = []
        for n, x in wm.items():
            if n in am and x["pct"] is not None and am[n]["pct"] is not None:
                diffs.append((abs(x["pct"] - am[n]["pct"]), n, am[n]["pct"], x["pct"]))
        diffs.sort(reverse=True)
        big = [d for d in diffs if d[0] > 0.15]
        nullw = sum(1 for x in wm.values() if x["pct"] is None)
        rows.append((appid, dict(name=w.get("game") or "?", nw=len(wm), na=len(am),
                                 only_w=only_w, only_a=only_a, big=big,
                                 maxd=(diffs[0][0] if diffs else 0.0),
                                 nullw=nullw), ""))

    clean = sum(1 for r in rows if r[1] and not r[1]["only_w"] and not r[1]["only_a"]
                and not r[1]["big"] and not r[1]["nullw"] and r[1]["nw"] == r[1]["na"])
    print("对比基线：%s" % ("上一轮网页快照" if "--old-web" in argv else "API raw/steam"))
    print("总 %d 款，完全一致的 %d 款\n" % (len(rows), clean))
    for appid, info, err in rows:
        if err:
            print("  %-9s  %s" % (appid, err))
            continue
        flag = ""
        if info["nw"] != info["na"] or info["only_w"] or info["only_a"]:
            flag += "  条目:web=%d api=%d +%d/-%d" % (info["nw"], info["na"],
                                                     len(info["only_w"]), len(info["only_a"]))
        if info["big"]:
            flag += "  偏差>0.15 的 %d 条(最大 %.1f)" % (len(info["big"]), info["maxd"])
        if info["nullw"]:
            flag += "  缺百分比 %d 条" % info["nullw"]
        if flag:
            print("  %-9s %-40s%s" % (appid, info["name"][:40], flag))
            for d, n, av, wv in info["big"][:4]:
                print("        %-34s api %5.1f -> web %5.1f  (%+.1f)" % (n[:34], av, wv, wv - av))
            for n in info["only_w"][:3]:
                print("        仅 web 有: %s" % n[:50])
            for n in info["only_a"][:3]:
                print("        仅 api 有: %s" % n[:50])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
