#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 Steam 客户端成就页复制出来的一段文本，与本地 API 快照逐条比对。

客户端显示的是它自己缓存的统计，API 是服务端快照，两者常有 0.1pp 级差异；
更重要的是客户端会显示**隐藏成就的描述**，而 API 里 hidden:1 的条目连 description 字段都没有。

用法：
    python scripts/diff_client_list.py 2050650 某文件.txt
    # 或把文本直接管道进来
    python scripts/diff_client_list.py 2050650 -  < list.txt
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw", "steam")
WEB = os.path.join(ROOT, "data", "raw", "steam_web")   # 优先用网页源（唯一数据源）
PCT = re.compile(r"^([0-9]{1,3}(?:\.[0-9])?)\s*%$")


def parse(text):
    """从「名称 / 名称 / 描述 / 87.6%」这种块里抽出 (名称, 描述, 百分比)。
    名称在客户端列表里通常是连续两行重复，取倒数第二行；描述取倒数第一行。"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out = []
    for i, line in enumerate(lines):
        m = PCT.match(line)
        if not m or i < 2:
            continue
        name, desc = lines[i - 2], lines[i - 1]
        if PCT.match(desc) or PCT.match(name):     # 没有描述行的情况，跳过
            continue
        out.append((name, desc, float(m.group(1))))
    return out


def main():
    appid = int(sys.argv[1])
    src = sys.argv[2]
    text = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    rows = parse(text)
    if not rows:
        raise SystemExit("没解析出任何条目，检查粘贴格式")

    api = {a["name"].lower(): a for a in
           json.load(open(os.path.join(RAW, "%d.json" % appid), encoding="utf-8"))["achievements"]}

    hit, miss, diffs = 0, [], []
    print("%-38s %7s %7s %6s" % ("成就", "客户端", "API", "差"))
    for name, desc, pct in rows:
        a = api.get(name.lower())
        if not a:
            miss.append(name)
            print("%-38s %7.1f %7s %6s" % (name[:38], pct, "未收录", "—"))
            continue
        hit += 1
        d = pct - a["pct"]
        if abs(d) > 0.05:
            diffs.append((name, a["pct"], pct))
        print("%-38s %7.1f %7.1f %+6.1f%s" % (name[:38], pct, a["pct"], d,
                                              "   <<<" if abs(d) > 0.05 else ""))
    print("\n解析 %d 条，命中 %d 条，未收录 %d 条，偏差>0.05 的 %d 条"
          % (len(rows), hit, len(miss), len(diffs)))
    if miss:
        print("  未收录（名字对不上）：", "；".join(miss))
    if diffs:
        print("  偏差：", "；".join("%s %.1f→%.1f" % (n, a, c) for n, a, c in diffs))
    else:
        print("  无实质偏差（≤0.1pp 视为客户端刷新延迟）")


if __name__ == "__main__":
    main()
