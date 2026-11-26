#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 steam_web（唯一数据源）刷新 curated_manual.json 里 10 条「里程碑型」曲线的数值。

为什么单独一层：这些曲线的节点是 Boss / 剧情里程碑（新战神 The Journey Begins、
艾尔登法环 Margit、只狼 剑圣…），不是「第 N 章」的机械编号，没法用严格完成型正则识别，
必须指定成就名。成就名由 match_manual.py 一次性匹配，本脚本只负责按名取值。

运行：python scripts/sync_manual.py
输入：data/manual_specs.json（appid + [(label, ach)]）、data/curated_manual.json（原有元信息）
输出：data/curated_manual.json（pct 全部改由网页源现值填充）
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPECS = os.path.join(ROOT, "data", "manual_specs.json")
CUR = os.path.join(ROOT, "data", "curated_manual.json")
WEB = os.path.join(ROOT, "data", "raw", "steam_web")


def main():
    specs = json.load(open(SPECS, encoding="utf-8"))["games"]
    cur = {g["appid"]: g for g in json.load(open(CUR, encoding="utf-8"))["games"]}
    out, bad = [], 0
    for g in specs:
        p = os.path.join(WEB, "%d.json" % g["appid"])
        if not os.path.exists(p):
            print("!! %s 缺网页快照" % g["name"])
            bad += 1
            continue
        table = {a["name"]: a for a in json.load(open(p, encoding="utf-8"))["achievements"]}
        base = cur.get(g["appid"], {})
        old = {n["stage"]: n for n in base.get("nodes", [])}
        nodes = []
        for i, n in enumerate(g["nodes"]):
            a = table.get(n["ach"])
            if not a or a["pct"] is None:
                print("!! %s / %s 在快照里找不到" % (g["name"], n["ach"]))
                bad += 1
                continue
            o = old.get(n["label"], {})
            nodes.append({"code": o.get("code") or str(i), "stage": n["label"], "pct": a["pct"]})
        # 单调性校验（允许并列）
        for i in range(len(nodes) - 1):
            if nodes[i]["pct"] < nodes[i + 1]["pct"]:
                print("!! %s 非单调：%s %.1f < %s %.1f" %
                      (g["name"], nodes[i]["stage"], nodes[i]["pct"],
                       nodes[i + 1]["stage"], nodes[i + 1]["pct"]))
                bad += 1
        rec = {"appid": g["appid"], "name": base.get("name") or g["name"],
               "key": base.get("key") or "", "color": g.get("color") or base.get("color") or "#8b7bff",
               "href": base.get("href"), "note": base.get("note") or "", "nodes": nodes}
        out.append(rec)
        print("  %-40s %2d 节点  %5.1f -> %5.1f  相对 %5.1f"
              % (rec["name"][:40], len(nodes), nodes[0]["pct"], nodes[-1]["pct"],
                 nodes[-1]["pct"] / nodes[0]["pct"] * 100))
    if bad:
        print("\n有 %d 处问题，未写出（先修数据）" % bad)
        return 1
    json.dump({"games": out}, open(CUR, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n已刷新 %d 条 -> %s" % (len(out), CUR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
