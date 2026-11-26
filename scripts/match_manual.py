#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 curated_manual.json 的 10 条老曲线，逐节点匹配到 steam_web 里的成就名。

匹配策略（按优先级）：
  1) stage 直接是成就名 / 成就名前缀 —— GoW、FF13、RDR2、ER、BMW、BG3、Starfield、Sekiro
  2) 特殊映射 —— DS1 的「Prologue」= Delivering Is What I Do，DS2 的「Prologue」= Starting Point；
     其余按 "Complete Episode N" 的描述匹配
校验：匹配到的现价与原 pct 差必须 ≤1.0pp，否则报错列出，交由人工处理。

输出：data/manual_specs.json（可直接并入 curate_ladders 的 SPECS）
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = os.path.join(ROOT, "data", "curated_manual.json")
WEB = os.path.join(ROOT, "data", "raw", "steam_web")
OUT = os.path.join(ROOT, "data", "manual_specs.json")

# 描述性 stage 的手工映射（appid -> {stage: 成就名}）
SPECIAL = {
    1850570: {"Prologue": "Delivering Is What I Do"},
    3280350: {"Prologue": "Starting Point"},
}
RE_EP = re.compile(r"(?i)complete\s+(?:the\s+)?episode\s+(\d+)")


def seq_match(nodes, table):
    """单调序列匹配：按顺序贪心，每步在「pct 不超过上一节点」的候选里取最接近的。
    用于 stage 是里程碑名、与成就名不同名的情况（如新战神 The Stranger → The Journey Begins）。"""
    used, out, prev = set(), [], 100.0
    for n in nodes:
        cands = [a for a in table if a["name"] not in used and a["pct"] <= prev + 0.05]
        if not cands:
            return None
        a = min(cands, key=lambda x: abs(x["pct"] - n["pct"]))
        if abs(a["pct"] - n["pct"]) > 1.2:
            return None
        used.add(a["name"]); out.append(a); prev = a["pct"]
    return out


def match(appid, stage, pct, table):
    if appid in SPECIAL and stage in SPECIAL[appid]:
        name = SPECIAL[appid][stage]
        hit = [a for a in table if a["name"] == name]
        return (hit[0] if hit else None), "手工映射"
    # 1) stage 作为成就名前缀
    s = stage.lower()
    hit = [a for a in table if a["name"].lower().startswith(s)]
    if len(hit) == 1:
        return hit[0], "stage 前缀"
    # 2) 描述里的 Episode N
    m = re.match(r"(?i)episode\s+(\d+)", stage)
    if m:
        n = m.group(1)
        hit = [a for a in table if (RE_EP.search(a["desc"] or "") or [None, None])[1] == n]
        if len(hit) == 1:
            return hit[0], "描述 Episode %s" % n
    # 2b) stage 出现在描述里（DS2 的 "Complete Episode 1: Sam."）
    hit = [a for a in table if stage.lower() in (a["desc"] or "").lower()
           and re.search(r"(?i)episode|chapter|act", a["desc"] or "")]
    if len(hit) == 1:
        return hit[0], "描述含 stage 名"
    # 3) 数值最接近（±0.6 内且唯一）
    cand = [a for a in table if a["pct"] is not None and abs(a["pct"] - pct) <= 0.6]
    if len(cand) == 1:
        return cand[0], "数值最近(±0.6)"
    return None, "无法唯一确定（候选 %d 个）" % len(cand)


def main():
    man = json.load(open(MAN, encoding="utf-8"))["games"]
    out, bad = [], 0
    for g in man:
        p = os.path.join(WEB, "%d.json" % g["appid"])
        if not os.path.exists(p):
            print("!! %s 缺网页快照" % g["name"])
            bad += 1
            continue
        table = [a for a in json.load(open(p, encoding="utf-8"))["achievements"] if a["pct"] is not None]
        nodes, ok = [], True
        print("\n== %s (%d)" % (g["name"], g["appid"]))
        seq = seq_match(g["nodes"], table)
        if seq:
            print("   （逐点匹配失败时，用单调序列匹配兜底）")
        for i, n in enumerate(g["nodes"]):
            a, how = match(g["appid"], n["stage"], n["pct"], table)
            if not a and seq:
                a, how = seq[i], "单调序列匹配"
            if not a:
                print("   !! %-18s %5.1f  %s" % (n["stage"], n["pct"], how))
                ok = False
                bad += 1
                continue
            d = a["pct"] - n["pct"]
            flag = "" if abs(d) <= 1.0 else "   <<< 偏差 %.1f" % d
            if abs(d) > 1.0:
                ok = False
                bad += 1
            print("   %-18s %5.1f -> %-30s %5.1f (%+.1f, %s)%s"
                  % (n["stage"], n["pct"], a["name"][:30], a["pct"], d, how, flag))
            nodes.append({"label": n["stage"], "ach": a["name"]})
        if ok:
            out.append({"appid": g["appid"], "name": g["name"], "color": g["color"],
                        "nodes": nodes})
    json.dump({"games": out}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n成功 %d / %d 条，问题 %d 处 -> %s" % (len(out), len(man), bad, OUT))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
