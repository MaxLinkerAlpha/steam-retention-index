#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 detect_ladders 识别出的 A 级（显式章节编号）固化为可画曲线的数据。

A 级的判定完全自动：成就描述里带 chapter / episode / act / 第 N 章 等显式编号，
且编号序列的解锁率严格单调递减。这类不需要人工干预，所以单独抽成一层，
与 curated_manual（人工核定）、curated_ladders（隐藏成就人工切分）分开。

运行：python scripts/curate_auto.py   （需先跑 detect_ladders.py）
输出：data/curated_auto.json
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAD = os.path.join(ROOT, "data", "ladders.json")
OUT = os.path.join(ROOT, "data", "curated_auto.json")
# 已被人工核定覆盖的作品不再出自动版：人工版更完整（如 DS1/DS2 含序章、RDR2 含第 6 章与尾声、
# The Evil Within 的自动版其实是「The Assignment」DLC 的章节名）
MANUAL = [os.path.join(ROOT, "data", n) for n in
          ("curated_manual.json", "curated_ladders.json")]


def main():
    d = json.load(open(LAD, encoding="utf-8"))
    skip = set()
    for p in MANUAL:
        if os.path.exists(p):
            skip |= {g["appid"] for g in json.load(open(p, encoding="utf-8"))["games"]}
    games = []
    for g in d["games"]:
        if g["level"] != "A" or len(g["nodes"]) < 4:
            continue
        if g["appid"] in skip:
            continue
        games.append({
            "appid": g["appid"], "name": g["name"], "level": "auto",
            "note": "自动识别：成就描述含显式章节编号（%d 个），解锁率严格单调" % len(g["nodes"]),
            "nodes": [{"code": str(i + 1), "stage": n["name"], "pct": n["pct"]}
                      for i, n in enumerate(g["nodes"])],
        })
    games.sort(key=lambda x: x["name"])
    json.dump({"games": games}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("写出 %d 条自动曲线 -> %s" % (len(games), OUT))
    for g in games:
        print("  %-42s %2d 节点 %5.1f -> %5.1f" %
              (g["name"][:42], len(g["nodes"]), g["nodes"][0]["pct"], g["nodes"][-1]["pct"]))


if __name__ == "__main__":
    main()
