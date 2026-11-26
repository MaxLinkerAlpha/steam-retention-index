#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从原始成就数据里自动识别「剧情推进阶梯」，产出 data/ladders.json

识别规则（从严到宽）：
  A 级：描述里带显式编号的章节/幕/回，且数量 ≥4，百分比严格递减
  B 级：有明确的「完成第 N 章 / Act N」≤3 个，或「章节 + 通关」组合
  C 级：只有「起点 + 通关」两个锚点（可算相对，但没有形状）
  X 级：找不到可信的剧情锚点（策略/模拟/沙盒类常见）

所有节点都保留原始成就名与百分比，便于回查。
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "steam")
WEB = os.path.join(ROOT, "data", "raw", "steam_web")   # 含隐藏成就描述，识别率更高
GAMES = os.path.join(ROOT, "data", "games.json")
OUT = os.path.join(ROOT, "data", "ladders.json")

# 显式编号：chapter 3 / episode 2 / act 1 / 第3章 / 第三回
RE_NUM = re.compile(
    r"(?i)\b(?:chapter|episode|act|part)\s*[-:]?\s*(\d{1,2})\b"
    r"|第\s*([0-9一二三四五六七八九十]{1,3})\s*(?:章|回|幕|部)"
)
# 通关类
RE_FIN = re.compile(
    r"(?i)\b(finish|complete|beat)\s+(the\s+)?(game|story|campaign|main\s+story|main\s+quest)\b"
    r"|complete the game|finish the game|reach the end|see the credits|roll (the )?credits"
    r"|完成(游戏|主线|剧情|故事)|通关"
)
# 容易被误判的干扰词
# 容易被误判的干扰词。收集类必须排除 —— 否则会把 DLC 的「收集本幕全部道具」当成章节节点
# （实例：AC Odyssey「Collect all the Keeper's Insights in Episode 1」、
#   BioShock Infinite「Collected all Audio Diaries and Voxophones in Burial at Sea」）
BAD = re.compile(r"(?i)\b(multiplayer|online|co-?op|rank|level\s*\d+\s*times|"
                 r"collect|collectibles?|audio diaries|voxophones?|insights?|optional|photo|b-?side)\b")
# 已知误判：这三条的「通关」成就其实是收集 / 爬塔 / 小游戏，不能当通关锚点
WRONG_FIN = {894020: "Crow Gamer", 367520: "Completion", 646570: "Ruby"}
# C 级（起点+通关两点）里语义不成立的直接剔除：
#   960910 Heavy Rain —— 起点「Interactive Drama」官方描述是 "Thank you for supporting Interactive Drama"，
#                        属支持/发行类成就，不是剧情节点（该作成就是条件型，画不出阶梯）
#   646570 Slay the Spire —— 肉鸽，"通关"= 用某个角色击败第三幕 Boss，横轴与叙事作品不同义
DROP_C = {960910: "起点为支持类成就，非剧情节点",
          582160: "终止点「Complete Main Quest 'Aya'」是主线早期任务，不是通关，相对留存虚高",
          588650: "无「任意难度通关」成就，通关项全是 Boss Stem Cell 等挑战条件",
          646570: "肉鸽：通关＝角色通关，横轴语义与叙事作品不同"}


# 严格完成型：Complete/Finish (Act|Chapter|Episode) N —— 这才是真正的进度节点
RE_STRICT = re.compile(
    r"(?i)\b(?:complete|completed|finish|finished)\s+(?:the\s+)?(act|chapter|episode)\s*[-:]?\s*(\d{1,2})\b")
RE_OF_EP = re.compile(r"(?i)\bof\s+episode\s*(\d{1,2})\b")


def strict_key(desc):
    """返回排序键 (episode, act, chapter)；不匹配返回 None。
    支持三种写法：
      Complete Chapter 3            -> (0, 0, 3)
      Complete Act 2 - Chapter 1    -> (0, 2, 0)
      Complete chapter 3 of episode 1 -> (1, 0, 3)
      Completed the final chapter   -> (0, 0, 999)
    """
    d = desc or ""
    if re.search(r"(?i)\b(complete|completed|finish|finished)\s+the\s+final\s+(chapter|act|episode)", d):
        return (0, 0, 999)
    m = RE_STRICT.search(d)
    if not m:
        return None
    unit, n = m.group(1).lower(), int(m.group(2))
    mo = RE_OF_EP.search(d)
    ep = int(mo.group(1)) if mo else (n if unit == "episode" else 0)
    if unit == "act":
        return (ep, n, 0)
    return (ep, 0, n)


def num_of(text):
    # 「the final chapter / final act」视为最后一章
    if re.search(r"(?i)final\s+(chapter|act|episode)", text or ""):
        return 99
    m = RE_NUM.search(text or "")
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    cn = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8,
          "九": 9, "十": 10, "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
          "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20}
    if raw.isdigit():
        return int(raw)
    return cn.get(raw)


def build(rows, appid=None):
    """返回 (nodes, level, method)"""
    if not rows:
        return [], "X", ""
    vals = [(r["pct"], r) for r in rows if r["pct"] is not None]
    if len(vals) < 2:
        return [], "X", ""

    # 1a) 严格完成型章节链（Complete/Finish Chapter|Act|Episode N），支持「of episode M」复合排序
    strict = []
    for pct, r in vals:
        k = strict_key(r["desc"])
        if k is not None and not BAD.search(r["desc"] or ""):
            strict.append((k, pct, r))
    strict.sort(key=lambda x: (x[0], -x[1]))
    sseen_n, sseen_name, schain = set(), set(), []
    for k, pct, r in strict:
        if k in sseen_n or r["name"] in sseen_name:
            continue
        sseen_n.add(k); sseen_name.add(r["name"])
        schain.append({"n": k[-1], "name": r["name"], "desc": r["desc"], "pct": pct})
    if len(schain) >= 4:
        # 允许并列（同一章可能有多条成就），遇到倒挂就截断到最长非增前缀
        cut = len(schain)
        for i in range(len(schain) - 1):
            if schain[i]["pct"] < schain[i + 1]["pct"]:
                cut = i + 1
                break
        schain = schain[:cut]
        # 断层截断：单步跌幅超过 65%（比例 < 0.35）通常意味着从主线跨到了 DLC / 挑战关
        # 实例：Celeste Ch6 Reflection 36.7% → Ch9 Farewell 8.9%（Farewell 是免费 DLC）
        cut2 = len(schain)
        for i in range(1, len(schain)):
            if schain[i]["pct"] / schain[i - 1]["pct"] < 0.35:
                cut2 = i
                break
        schain = schain[:cut2]
        if len(schain) >= 4:
            return schain, "A", "严格完成型章节（%d 个）" % len(schain)

    # 1b) 宽松编号章节（兜底）
    numbered = []
    for pct, r in vals:
        n = num_of(r["desc"]) or num_of(r["name"])
        if n and not BAD.search(r["desc"] or ""):
            numbered.append((n, pct, r))
    numbered.sort(key=lambda x: (x[0], -x[1]))
    # 每个编号取百分比最高的那条（同编号可能有普通/硬核两个版本）
    seen, chain = set(), []
    for n, pct, r in numbered:
        if n in seen:
            continue
        seen.add(n)
        chain.append({"n": n, "name": r["name"], "desc": r["desc"], "pct": pct})
    if len(chain) >= 4 and all(chain[i]["pct"] > chain[i + 1]["pct"] for i in range(len(chain) - 1)):
        return chain, "A", "显式章节编号（%d 个）" % len(chain)

    # 2) 通关成就：只认解锁率 ≥15% 的那条（挑战向的"不受伤通关"普遍低于 5%）
    fin = None
    for pct, r in vals:
        if pct < 15 or BAD.search(r["desc"] or ""):
            continue
        if WRONG_FIN.get(appid) == r["name"]:
            continue
        if RE_FIN.search(r["desc"] or "") and (fin is None or pct > fin["pct"]):
            fin = {"n": 99, "name": r["name"], "desc": r["desc"], "pct": pct}
    if appid in DROP_C:
        return [], "X", DROP_C[appid]
    top = max(vals, key=lambda x: x[0])       # 真·最高解锁率成就（rows 顺序不可信）
    if fin and fin["pct"] < top[0] * 0.95:
        head = {"n": 0, "name": top[1]["name"], "desc": top[1]["desc"], "pct": top[0]}
        if len(chain) >= 2 and chain[-1]["pct"] > fin["pct"]:
            seq, lvl, meth = chain + [fin], "B", "编号章节 %d 个 + 通关" % len(chain)
        else:
            seq, lvl, meth = [head, fin], "C", "仅起点 + 通关（两点）"
        if all(seq[i]["pct"] > seq[i + 1]["pct"] for i in range(len(seq) - 1)):
            return seq, lvl, meth

    if len(chain) >= 2:
        return chain, "B", "编号章节（%d 个，无通关锚点）" % len(chain)
    return [], "X", ""


def main():
    games = json.load(open(GAMES, encoding="utf-8"))["games"]
    out = []
    stat = {}
    for g in games:
        # 唯一数据源：steamcommunity/achievements（含隐藏成就描述，百分比同源）
        p = os.path.join(WEB, "%d.json" % g["appid"])
        if not os.path.exists(p):
            continue
        raw = json.load(open(p, encoding="utf-8"))
        nodes, lvl, meth = build(raw["achievements"], g["appid"])
        stat[lvl] = stat.get(lvl, 0) + 1
        out.append({"appid": g["appid"], "title": g["title"], "name": g["name"],
                    "genres": g.get("genres") or [], "level": lvl, "method": meth,
                    "nodes": nodes})
    json.dump({"generated": json.load(open(GAMES, encoding="utf-8"))["snapshot"],
               "games": out}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("等级分布:", stat, " 总 %d" % len(out))
    for g in sorted(out, key=lambda x: {"A": 0, "B": 1, "C": 2, "X": 3}[x["level"]]):
        if g["level"] in ("A", "B"):
            print("  %s %-34s %-2d  %s" % (g["level"], g["name"][:34], len(g["nodes"]), g["method"]))
    print("\n-> data/ladders.json")


if __name__ == "__main__":
    main()
