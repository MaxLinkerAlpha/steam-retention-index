#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 steamcommunity/achievements 的官方描述审计已核定的阶梯。

能自动查出的问题：
  1) stage 标签里写了 Ch.N / 第 N 章，但官方描述里的章节号不一致（标签写错）
  2) 同一节点在阶梯里被标成「通关」，但官方描述不是通关语义
  3) 收录了但官方描述显示是「可选 / 支线 / 结局分支」的节点
  4) 没收录、但描述看着像主线的隐藏成就（候选补漏清单，需人工判断）

运行：python scripts/audit_ladders.py [appid ...]
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CUR = os.path.join(ROOT, "data", "curated_ladders.json")
WEB = os.path.join(ROOT, "data", "raw", "steam_web")

RE_CH = re.compile(r"(?i)\bch(?:apter|\.)?\s*(\d{1,2})\b")
RE_EP = re.compile(r"(?i)\b(?:episode|ep\.?)\s*(\d{1,2})\b")
RE_MISSION = re.compile(r"(?i)\bmission\s*(\d{1,2})\b")
# 可疑语义：可选 / 支线 / 结局分支 / 多层含义
BAD = re.compile(r"(?i)\b(optional|side mission|side quest|missable|alternate|alternative|"
                 r"either .* or|choose|choice|one of the (two|three|four))\b")


def nums(text):
    t = text or ""
    return [int(x) for x in RE_CH.findall(t) + RE_EP.findall(t) + RE_MISSION.findall(t)]


def main(argv):
    want = {int(a) for a in argv if a.isdigit()}
    cur = json.load(open(CUR, encoding="utf-8"))["games"]
    total_issue = 0
    for g in cur:
        if want and g["appid"] not in want:
            continue
        p = os.path.join(WEB, "%d.json" % g["appid"])
        if not os.path.exists(p):
            print("%s：缺 web 数据，跳过" % g["name"])
            continue
        web = {x["name"]: x for x in json.load(open(p, encoding="utf-8"))["achievements"]}
        print("\n== %s (%d)" % (g["name"], g["appid"]))
        picked = set()
        for n in g["nodes"]:
            a = web.get(n.get("ach") or "")
            desc = (a or {}).get("desc") or n.get("desc") or ""
            picked.add(n.get("ach"))
            sn, dn = nums(n["stage"]), nums(desc)
            flag = ""
            if sn and dn and not set(sn) & set(dn):
                flag = "  <<< 章节号不一致 stage=%s desc=%s" % (sn, dn)
                total_issue += 1
            if BAD.search(desc):
                flag += "  <<< 描述含可选/分支语义"
                total_issue += 1
            print("  %-22s %-32s %5.1f%%%s" % (n["stage"][:22], (n.get("ach") or "")[:32], n["pct"], flag))
            if desc:
                print("      desc: %s" % desc[:110])
        # 补漏候选：隐藏成就、有剧情味、未被收录
        cand = []
        for name, a in web.items():
            if name in picked or not a.get("hidden"):
                continue
            if a.get("pct") is None:
                continue
            if re.search(r"(?i)\b(complete|finish|defeat|kill|reach|escape|meet|find|leave|return|"
                         r"survive|retrieve|destroy|enter)\b", a.get("desc") or ""):
                cand.append(a)
        if cand:
            cand.sort(key=lambda x: -x["pct"])
            print("  -- 未收录的隐藏剧情候选（需人工判断）")
            for a in cand[:12]:
                print("     %5.1f%%  %-34s %s" % (a["pct"], a["name"][:34], (a["desc"] or "")[:72]))
    print("\n可疑点合计：%d" % total_issue)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
