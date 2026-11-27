#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 index.html：自选曲线 + 内容消耗剖面 + 全库明细。

信息层级（见 info-hierarchy-design 规范）：
  L1  状态行：收录量 / 可画曲线数 / 数据快照日期
  L2  主操作区：两张图 + 「添加作品」选择器（勾选不再藏在 130 行表格里）
  L3  明细：全库表格、口径与方法 —— 默认折叠

运行：python scripts/build_pages.py
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

D = lambda n: json.load(open(os.path.join(ROOT, "data", n), encoding="utf-8"))
PALETTE = ["#4cc2ff", "#8b7bff", "#e0a95a", "#ff7a9c", "#e05c5c", "#7fd3a0", "#f0b429",
           "#9be15d", "#57d3e0", "#cfd6e2", "#c084fc", "#ff9f68", "#6ee7b7", "#f472b6",
           "#facc15", "#38bdf8"]
DROP = {1190460, 261570}          # DS 基础版 / Ori 原版：各留当前在售版
REPO = "MaxLinkerAlpha/steam-retention-index"


def clean(n):
    n = re.sub(r"[™®]", "", n or "")
    return re.sub(r"\s{2,}", " ", n).strip()


def load():
    games = [g for g in D("games.json")["games"] if g["appid"] not in DROP]
    ladders = {g["appid"]: g for g in D("ladders.json")["games"]}
    manual = [g for g in D("curated_manual.json")["games"] if g["appid"] not in DROP]
    auto = [g for g in D("curated_auto.json")["games"] if g["appid"] not in DROP]
    cur = {g["appid"]: g for g in D("curated_ladders.json")["games"] if g["appid"] not in DROP}
    man_map = {str(g["appid"]): g for g in manual if "color" in g}
    snap = D("games.json").get("snapshot", "")

    names, recs, prof = {}, [], {}
    for g in games:
        p = os.path.join(ROOT, "data", "raw", "steam_web", "%d.json" % g["appid"])
        if not os.path.exists(p):
            continue
        raw = json.load(open(p, encoding="utf-8"))
        rows = [a for a in raw["achievements"] if a.get("pct") is not None]
        if not rows:
            continue
        pcts = [a["pct"] for a in rows]
        sv = sorted(pcts, reverse=True)
        if len(sv) >= 5:
            pr = []
            for q in range(0, 101, 5):
                x = q / 100.0 * (len(sv) - 1)
                i = int(x)
                f = x - i
                pr.append(sv[i] * (1 - f) + sv[min(i + 1, len(sv) - 1)] * f)
            prof[g["appid"]] = pr
        nm = clean(g["name"] or raw.get("game") or "?")
        names[g["appid"]] = nm
        l = ladders.get(g["appid"], {})
        cg = cur.get(g["appid"])
        if not cg and str(g["appid"]) in man_map:
            cg = man_map[str(g["appid"])]
        if cg:
            lv = "C" if len(cg["nodes"]) <= 2 else "A"
            fin, nt = cg["nodes"][-1]["pct"], cg["note"]
            sr = cg.get("src", "")
        else:
            ln0 = l.get("nodes") or []
            lv = l.get("level", "X")
            fin = ln0[-1]["pct"] if lv in ("A", "B") and ln0 else None
            nt, sr = "", ""
        st = cg["nodes"][0]["pct"] if cg and cg.get("nodes") else max(pcts)
        recs.append(dict(appid=g["appid"], name=nm, genres=", ".join(g.get("genres") or []) or "—",
                         n=len(rows), start=st, deep=min(pcts), rel=min(pcts) / max(pcts) * 100,
                         level=lv, lnodes=(cg["nodes"] if cg else ln0), note=nt, src=sr, finish=fin,
                         p50=(prof[g["appid"]][10] if g["appid"] in prof else None)))
    recs.sort(key=lambda r: -r["rel"])

    curves, seen = [], set()
    for i, g in enumerate(manual + auto):
        key = str(g["appid"])
        nodes = g["nodes"]
        seen.add(key)
        curves.append(dict(key=key, name=names.get(g["appid"], g["name"]),
                           color=g["color"] if "color" in g else PALETTE[i % len(PALETTE)],
                           nodes=nodes, base=nodes[0]["pct"], manual=("color" in g), dash=False))
    for g in cur.values():
        key = str(g["appid"])
        if key in seen or not g["nodes"]:
            continue
        seen.add(key)
        nodes = g["nodes"]
        curves.append(dict(key=key, name=names.get(g["appid"], g["name"]), color=g["color"],
                           nodes=nodes, base=nodes[0]["pct"], manual=False,
                           dash=(len(nodes) <= 2)))
    for j, g in enumerate([x for x in ladders.values() if x["level"] == "C" and x["nodes"]]):
        key = str(g["appid"])
        if key in seen or g["appid"] in DROP:
            continue
        nodes = [{"stage": n["name"], "pct": n["pct"]} for n in g["nodes"]]
        curves.append(dict(key=key, name=names.get(g["appid"], g["name"]),
                           color=PALETTE[(j + len(manual) + len(auto)) % len(PALETTE)],
                           nodes=nodes, base=nodes[0]["pct"], manual=False, dash=True))
    cmap0 = {c["key"]: c["color"] for c in curves}
    for i, r in enumerate(recs):
        r["color"] = cmap0.get(str(r["appid"]), PALETTE[i % len(PALETTE)])
    return recs, curves, snap, prof


def line_chart(curves, mobile=False, default_on=()):
    if mobile:
        W, H, L, R, T, Bm = 400, 306, 34, 44, 18, 40
    else:
        W, H, L, R, T, Bm = 960, 440, 52, 168, 26, 52
    cls = "axm" if mobile else "ax"
    cls2 = "axm2" if mobile else "ax2"
    pw, ph = W - L - R, H - T - Bm
    X = lambda p: L + p / 100.0 * pw
    Y = lambda v: T + (100.0 - v) / 90.0 * ph
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    o = ['<svg viewBox="0 0 %d %d" role="img" aria-label="所选作品的章节留存曲线">' % (W, H)]
    ystep = 20 if mobile else 10
    for g in range(ystep, 101, ystep):
        o.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#1b222c"/>' % (L, Y(g), L + pw, Y(g)))
        o.append('<text class="%s" x="%d" y="%.1f" text-anchor="end">%d%%</text>' % (cls, L - 6, Y(g) + 3.5, g))
    o.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#39445a" stroke-dasharray="4 5"/>'
             % (L, Y(50), L + pw, Y(50)))
    if not mobile:
        o.append('<text class="%s" x="%d" y="%.1f">一半玩家留到这里</text>' % (cls2, L + 6, Y(50) - 6))
    xstep = 50 if mobile else 20
    for p in range(0, 101, xstep):
        o.append('<text class="%s" x="%.1f" y="%d" text-anchor="middle">%d%%</text>'
                 % (cls, X(p), H - (22 if mobile else 28), p))
    o.append('<text class="%s" x="%.1f" y="%d" text-anchor="middle">%s</text>'
             % (cls2, L + pw / 2, H - (6 if mobile else 8),
                '剧情推进（按节点等距）' if mobile else '剧情推进（起点 → 结局，按节点等距）'))
    o.append('<g class="ghostwrap" style="display:none">')
    for c in curves:
        rel = [n["pct"] / c["base"] * 100 for n in c["nodes"]]
        n = len(rel)
        pts = [(X(j / (n - 1) * 100.0), Y(v)) for j, v in enumerate(rel)]
        d = "M %.1f %.1f " % pts[0] + " ".join("L %.1f %.1f" % p for p in pts[1:])
        hid = ' style="display:none"' if c["key"] in default_on else ""
        o.append('<g class="gh" data-k="%s"%s><path d="%s" fill="none" stroke="#7c879b" '
                 'stroke-width="0.85" opacity=".17"/></g>' % (c["key"], hid, d))
    o.append('</g>')
    o.append('<g class="curves">')
    ends = []
    for c in curves:
        rel = [n["pct"] / c["base"] * 100 for n in c["nodes"]]
        n = len(rel)
        pts = [(X(j / (n - 1) * 100.0), Y(v)) for j, v in enumerate(rel)]
        d = "M %.1f %.1f " % pts[0] + " ".join("L %.1f %.1f" % p for p in pts[1:])
        o.append('<g class="ser" data-k="%s" style="display:none">' % c["key"])
        ctip = "%s｜%d 个节点 · 起点 %.1f%% → 终局 %.1f%%（相对 %.1f）" % (
            esc(c["name"]), len(c["nodes"]), c["base"], c["nodes"][-1]["pct"], rel[-1])
        o.append('<path class="hit" d="%s" fill="none" stroke="transparent" stroke-width="14" '
                 'pointer-events="stroke"><title>%s</title></path>' % (d, ctip))
        o.append('<path class="ln" d="%s" fill="none" stroke="%s" stroke-width="2" stroke-linejoin="round" '
                 'stroke-linecap="round"%s><title>%s</title></path>'
                 % (d, c["color"], ' stroke-dasharray="6 5"' if c.get("dash") else "", ctip))
        for j, (x, y) in enumerate(pts):
            nd = c["nodes"][j]
            tip = "%s｜%s %.1f%%（相对 %.1f）" % (esc(c["name"]), esc(nd["stage"]), nd["pct"], rel[j])
            if nd.get("ach") and nd["ach"] != nd["stage"]:
                tip += " · 成就「%s」" % esc(nd["ach"])
            if nd.get("desc"):
                tip += " · 官方描述：%s" % esc(nd["desc"])
            o.append('<circle cx="%.1f" cy="%.1f" r="2.6" fill="#0b0e13" stroke="%s" stroke-width="1.6">'
                     '<title>%s</title></circle>' % (x, y, c["color"], tip))
        o.append('</g>')
        ends.append([c["key"], pts[-1][0] + 9, pts[-1][1] + 4, c["color"], rel[-1]])
    ecls = "elm" if mobile else "el"
    for k, ex, ey, col, val in ends:
        o.append('<text class="%s" data-k="%s" data-y="%.1f" fill="%s" x="-99" y="-99" '
                 'style="display:none">%.1f</text>' % (ecls, k, ey, col, val))
    o.append('</g></svg>')
    return "".join(o)


def profile_chart(recs, prof, mobile=False):
    if mobile:
        W, H, L, R, T, Bm = 400, 300, 34, 16, 18, 40
    else:
        W, H, L, R, T, Bm = 960, 380, 52, 20, 22, 52
    cls = "axm" if mobile else "ax"
    cls2 = "axm2" if mobile else "ax2"
    pw, ph = W - L - R, H - T - Bm
    X = lambda q: L + q / 100.0 * pw
    Y = lambda v: T + (100.0 - v) / 100.0 * ph
    esc = lambda t: t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    o = ['<svg viewBox="0 0 %d %d" role="img" aria-label="内容消耗剖面：成就难易分位与解锁率">' % (W, H)]
    ystep = 25 if mobile else 20
    for v in range(0, 101, ystep):
        o.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#1b222c"/>' % (L, Y(v), L + pw, Y(v)))
        o.append('<text class="%s" x="%d" y="%.1f" text-anchor="end">%d%%</text>' % (cls, L - 6, Y(v) + 3.5, v))
    xstep = 50 if mobile else 20
    for q in range(0, 101, xstep):
        o.append('<text class="%s" x="%.1f" y="%d" text-anchor="middle">%d%%</text>'
                 % (cls, X(q), H - (22 if mobile else 28), q))
    o.append('<text class="%s" x="%.1f" y="%d" text-anchor="middle">%s</text>'
             % (cls2, L + pw / 2, H - (6 if mobile else 8),
                '成就难易分位' if mobile else '成就难易分位（0%% = 最容易拿到 · 100%% = 最难）'))
    o.append('<text class="%s" x="%d" y="%d">解锁率</text>' % (cls2, L, T - 5))

    o.append('<g class="prof-all" style="display:none">')
    for r in recs:
        pr = prof.get(r["appid"])
        if not pr:
            continue
        d = "M %.1f %.1f " % (X(0), Y(pr[0])) + " ".join(
            "L %.1f %.1f" % (X(i * 5), Y(v)) for i, v in enumerate(pr) if i)
        o.append('<path d="%s" fill="none" stroke="#7c879b" stroke-width="0.7" opacity=".13"/>' % d)
    o.append('</g>')

    for r in recs:
        pr = prof.get(r["appid"])
        if not pr:
            continue
        k = str(r["appid"])
        d = "M %.1f %.1f " % (X(0), Y(pr[0])) + " ".join(
            "L %.1f %.1f" % (X(i * 5), Y(v)) for i, v in enumerate(pr) if i)
        o.append('<g class="ser" data-k="%s" style="display:none">' % k)
        ptip = "%s｜最简单成就 %.1f%% · 中位成就 %.1f%% · 最难 %.1f%% · 共 %d 个成就" % (
            esc(r["name"]), pr[0], pr[10], pr[-1], r.get("n") or 0)
        o.append('<path class="hit" d="%s" fill="none" stroke="transparent" stroke-width="14" '
                 'pointer-events="stroke"><title>%s</title></path>' % (d, ptip))
        o.append('<path class="ln" d="%s" fill="none" stroke="%s" stroke-width="2" stroke-linejoin="round">'
                 '<title>%s</title></path>' % (d, r["color"], ptip))
        o.append('<circle cx="%.1f" cy="%.1f" r="3.2" fill="#0b0e13" stroke="%s" stroke-width="1.5">'
                 '<title>%s</title></circle>' % (X(100), Y(pr[-1]), r["color"], ptip))
        o.append('</g>')
    o.append('</svg>')
    return "".join(o)


CSS = """
:root{
  --bg:#0b0e13; --panel:#11151c; --panel2:#151a22; --line:#1f2632; --line2:#2b3442;
  --tx:#e8ecf4; --tx2:#9aa4b5; --tx3:#66707f;
  --accent:#4cc2ff; --ok:#3fd08a; --warn:#ffb977; --bad:#ff8080;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font-size:14px;line-height:1.6;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
  padding-bottom:56px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px}
header{padding:34px 0 6px}
.eyebrow{font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--tx3)}
h1{font-size:26px;line-height:1.3;font-weight:600;margin:8px 0 6px;letter-spacing:-.01em}
h1 small{display:block;font-size:13px;font-weight:400;color:var(--tx2);margin-top:8px;line-height:1.65}
h2{font-size:16px;font-weight:600;margin:0 0 4px;display:flex;align-items:baseline;gap:9px}
h2 .n{font-size:11px;font-weight:400;color:var(--tx3);letter-spacing:.1em}
section{margin:30px 0 0}
.sub{font-size:12.5px;color:var(--tx2);margin:0 0 12px;max-width:760px}
.statbar{display:flex;gap:26px;flex-wrap:wrap;margin:18px 0 2px;padding:14px 0;
  border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.stat{display:flex;align-items:baseline;gap:7px}
.stat b{font-size:22px;font-weight:600;letter-spacing:-.02em}
.stat span{font-size:11.5px;color:var(--tx3)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px}
.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
button{font:inherit;font-size:12.5px;color:var(--tx2);background:var(--panel2);
  border:1px solid var(--line2);border-radius:8px;padding:6px 11px;cursor:pointer;transition:.12s}
button:hover{color:var(--tx);border-color:#3a465c}
button.primary{background:rgba(76,194,255,.12);border-color:rgba(76,194,255,.5);color:#8fd8ff}
button.primary:hover{background:rgba(76,194,255,.2);color:#bfe9ff}
.chip-sel{display:inline-flex;align-items:center;gap:6px;background:var(--panel2);white-space:nowrap;
  border:1px solid var(--line2);border-radius:999px;padding:3px 6px 3px 9px;font-size:12px;color:var(--tx)}
.chip-sel i{width:8px;height:8px;border-radius:2px;display:inline-block}
.chip-sel b{font-weight:400}
.chip-sel button{border:0;background:none;padding:0 3px;color:var(--tx3);font-size:14px;line-height:1}
.chip-sel button:hover{color:var(--bad)}
.chips-wrap{display:flex;gap:6px;flex-wrap:wrap;flex:1;min-width:0}
.empty{padding:44px 18px;text-align:center;color:var(--tx2);font-size:13.5px;border:1px dashed var(--line2);
  border-radius:10px;margin:6px 0;line-height:1.75}
.empty b{color:var(--tx);font-weight:400}
.empty .acts{margin-top:16px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap;align-items:center}
.empty .acts .hint{font-size:12px;color:var(--tx3)}
.chart svg{display:block;width:100%;height:auto}
.chart svg text.ax{fill:#66707f;font-size:10.5px}
.chart svg text.ax2{fill:#5b677d;font-size:10.5px}
.chart svg text.el{font-size:10.5px;font-weight:600}
.chart svg text.axm{fill:#8b95a6;font-size:12.5px}
.chart svg text.axm2{fill:#7a8595;font-size:12.5px}
.chart svg text.elm{font-size:12.5px;font-weight:600}
.only-mob{display:none}
.chart svg .ser:hover .ln{stroke-width:3.2}
.chart svg .hit{cursor:help}
.tip{font-size:11.5px;color:var(--tx3);margin:8px 0 0}
details.fold{border:1px solid var(--line);border-radius:12px;background:var(--panel);margin-top:10px}
details.fold>summary{cursor:pointer;padding:11px 14px;font-size:12.5px;color:var(--tx2);
  list-style:none;display:flex;justify-content:space-between;align-items:center}
details.fold>summary::-webkit-details-marker{display:none}
details.fold>summary:after{content:"展开";font-size:11px;color:var(--tx3)}
details.fold[open]>summary:after{content:"收起"}
details.fold[open]>summary{border-bottom:1px solid var(--line)}
details.fold .body{padding:14px}
.tblwrap{overflow:auto;max-height:64vh}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
th{position:sticky;top:0;background:var(--panel);color:var(--tx3);font-weight:400;font-size:11.5px;
  z-index:1;cursor:default}
th.s{cursor:pointer;user-select:none}
th.s:hover{color:var(--tx)}
td.num{text-align:right;font-variant-numeric:tabular-nums}
tbody tr:hover{background:var(--panel2)}
.cdot{width:9px;height:9px;border-radius:2px;display:inline-block;margin-right:8px;vertical-align:0}
.sid{color:#3f4857;font-size:10.5px;margin-left:7px;font-variant-numeric:tabular-nums}
.c0{width:30px;text-align:center;padding-right:0}
.c0 input{accent-color:var(--accent);cursor:pointer;width:15px;height:15px}
.tag{font-size:10.5px;color:var(--tx3);border:1px solid var(--line2);border-radius:5px;padding:1px 5px}
.tag.has{color:#8fd8ff;border-color:rgba(76,194,255,.4)}
.swipe{display:none}
.pickbox{position:fixed;inset:0;z-index:50;background:rgba(4,6,10,.72);display:none;
  align-items:flex-start;justify-content:center;padding:64px 16px 16px}
.pickbox.on{display:flex}
.pickinner{background:var(--panel);border:1px solid var(--line2);border-radius:14px;width:100%;max-width:520px;
  max-height:80vh;display:flex;flex-direction:column;overflow:hidden}
.pickinner input{font:inherit;font-size:13px;background:var(--bg);border:0;border-bottom:1px solid var(--line);
  color:var(--tx);padding:14px 16px;outline:none;width:100%}
.plist{overflow:auto;padding:6px}
.pick{display:flex;align-items:center;gap:9px;width:100%;text-align:left;background:none;border:0;
  color:var(--tx2);padding:8px 10px;border-radius:8px;font-size:12.5px;cursor:pointer}
.pick:hover{background:var(--panel2);color:var(--tx)}
.pick i{width:8px;height:8px;border-radius:2px;flex:none}
.pick span{margin-left:auto;font-size:10.5px;color:var(--tx3);flex:none}
.pick.on{color:var(--tx);background:rgba(76,194,255,.08)}
.pick.on span{color:#8fd8ff}
.pick.on i{box-shadow:0 0 0 2px rgba(76,194,255,.35)}
.pickfoot{padding:9px 16px;border-top:1px solid var(--line);font-size:11px;color:var(--tx3);display:flex;
  justify-content:space-between;align-items:center}
ul.tight{margin:0;padding-left:18px;font-size:12.5px;color:var(--tx2);line-height:1.75}
ul.tight li{margin-bottom:7px}
ul.tight b{color:var(--tx)}
code{background:#0d1117;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:11.5px;
  color:#9fb4cc;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
footer{margin-top:40px;padding-top:18px;border-top:1px solid var(--line);font-size:11.5px;color:var(--tx3);line-height:1.8}
.toplink{display:flex;gap:8px;align-items:center;margin-top:14px;flex-wrap:wrap}
.pill{display:inline-block;font-size:11px;color:var(--tx2);background:var(--panel2);border:1px solid var(--line2);
  border-radius:6px;padding:1px 7px}
@media(max-width:720px){
  .wrap{padding:0 14px}
  header{padding:22px 0 4px}
  h1{font-size:21px}
  h1 small{font-size:12.5px}
  .statbar{display:grid;grid-template-columns:1fr 1fr;gap:14px 18px;padding:14px 0}
  .stat b{font-size:19px}
  .stat span{font-size:11px}
  section{margin:24px 0 0}
  .panel{padding:11px;border-radius:10px}
  .only-desk{display:none}
  .only-mob{display:block}
  .toolbar{gap:6px}
  .toolbar button{padding:6px 9px;font-size:12px}
  .bgroup button{margin-left:-1px}
  .chips-wrap{order:3;flex:1 0 100%;flex-wrap:nowrap;overflow-x:auto;padding-bottom:2px}
  .chips-wrap::-webkit-scrollbar{height:0}
  #chartcnt{order:4;flex:1 0 100%;margin:0}
  th.m-hide,td.m-hide{display:none}
  .pickbox{padding:0;align-items:flex-end}
  .pickinner{max-width:none;border-radius:16px 16px 0 0;max-height:86vh}
  .tblwrap{max-height:70vh}
}
"""

JS = r"""
(function(){
  var HAS={};
  document.querySelectorAll('.pick[data-c="1"]').forEach(function(p){HAS[p.dataset.k]=1;});
  var boxes=[].slice.call(document.querySelectorAll('input.ck'));
  var chips=document.getElementById('chips');
  var empty1=document.getElementById('empty1'), empty2=document.getElementById('empty2');
  var cnt1=document.getElementById('chartcnt');

  function curveEl(k){return document.querySelector('#curves g.ser[data-k="'+k+'"]');}
  function profEls(k){return document.querySelectorAll('#prof-all + g.ser[data-k="'+k+'"], svg g.ser[data-k="'+k+'"]');}

  function paint(k,on){
    document.querySelectorAll('g.ser[data-k="'+k+'"]').forEach(function(g){g.style.display=on?'':'none';});
    document.querySelectorAll('g.gh[data-k="'+k+'"]').forEach(function(g){g.style.display=on?'none':'';});
  }
  function hasCurve(k){return !!HAS[k];}

  function shown(k){
    var g=document.querySelector('.curves g.ser[data-k="'+k+'"]');
    return g&&g.style.display!=='none';
  }
  function layoutSet(sel,ncol,x0,dx,gap,maxOff){
    var els=[].slice.call(document.querySelectorAll('text.'+sel));
    els.forEach(function(e){e.style.display='none';});
    var on=els.filter(function(e){return shown(e.dataset.k);});
    on.sort(function(a,b){return a.dataset.y-b.dataset.y;});
    var cols=[];
    for(var i=0;i<ncol;i++)cols.push([]);
    on.forEach(function(e){
      var y0=+e.dataset.y,best=null;
      for(var c=0;c<ncol;c++){
        var last=cols[c].length?cols[c][cols[c].length-1]:-1e9;
        var y=Math.max(y0,last+gap);
        if(y-y0>maxOff)continue;
        if(!best||y<best.y)best={c:c,y:y};
      }
      if(!best)return;
      cols[best.c].push(best.y);
      e.setAttribute('x',(x0+best.c*dx).toFixed(1));
      e.setAttribute('y',best.y.toFixed(1));
      e.style.display='';
    });
  }
  function layout(){layoutSet('el',3,801,40,11,90);layoutSet('elm',1,360,0,13,110);}

  function renderChips(){
    var on=boxes.filter(function(b){return b.checked;});
    chips.innerHTML='';
    if(!on.length){
      chips.innerHTML='';
    }
    on.forEach(function(b){
      var tr=b.closest('tr');
      var name=tr?tr.dataset.name:b.dataset.k;
      var col=tr?tr.dataset.color:'#4cc2ff';
      var s=document.createElement('span');
      s.className='chip-sel';
      s.innerHTML='<i style="background:'+col+'"></i><b>'+name+'</b>';
      var x=document.createElement('button');
      x.textContent='\u00d7';x.title='移除';
      x.onclick=function(){set(b.dataset.k,false);};
      s.appendChild(x);
      chips.appendChild(s);
    });
  }

  function countCurves(){
    return boxes.filter(function(b){return b.checked&&hasCurve(b.dataset.k);}).length;
  }

  function refresh(){
    var on=boxes.filter(function(b){return b.checked;});
    var m=countCurves();
    cnt1.textContent=on.length?('已选 '+on.length+' 款 · 曲线 '+m+' 条'):'';
    document.querySelectorAll('.prof-all').forEach(function(g){g.style.display=on.length?'':'none';});
    document.querySelectorAll('.ghostwrap').forEach(function(g){g.style.display=on.length?'':'none';});
    if(empty1){
      empty1.style.display=m?'none':'';
      empty1.querySelector('.msg').innerHTML=on.length
        ? '所选作品没有章节曲线 —— 换一款，或看下一张「内容消耗剖面」。'
        : '还没有选择作品。<br><b>点「添加作品」挑几款</b>，曲线会立刻出现在这里。';
    }
    if(empty2)empty2.style.display=on.length?'none':'';
    layout();renderChips();
    boxes.forEach(function(b){
      var p=document.querySelector('.pick[data-k="'+b.dataset.k+'"]');
      if(p)p.classList.toggle('on',b.checked);
    });
  }

  function set(k,on){
    boxes.forEach(function(b){if(b.dataset.k===k)b.checked=on;});
    paint(k,on);refresh();
  }

  boxes.forEach(function(b){
    b.addEventListener('change',function(){paint(b.dataset.k,b.checked);refresh();});
  });

  document.getElementById('add').onclick=function(){openPicker();};
  var pb=document.getElementById('pickbox');
  pb.onclick=function(e){if(e.target===pb)closePicker();};
  function openPicker(){
    pb.classList.add('on');
    var q=document.getElementById('pq');q.value='';filter('');
    setTimeout(function(){q.focus();},30);
  }
  function closePicker(){pb.classList.remove('on');}
  document.addEventListener('keydown',function(e){if(e.key==='Escape')closePicker();});

  var picks=[].slice.call(document.querySelectorAll('.pick'));
  picks.forEach(function(p){
    p.onclick=function(){set(p.dataset.k,!p.classList.contains('on'));};
  });
  function filter(kw){
    kw=(kw||'').toLowerCase();
    picks.forEach(function(p){
      var t=(p.dataset.name||'').toLowerCase();
      p.style.display=(!kw||t.indexOf(kw)>=0)?'':'none';
    });
  }
  document.getElementById('pq').addEventListener('input',function(e){filter(e.target.value);});

  function rowVisible(b){
    var tr=b.closest('tr');
    return !tr || tr.style.display!=='none';
  }
  function bulk(fn){
    boxes.forEach(function(b){
      if(!rowVisible(b))return;
      var v=fn(b);
      if(b.checked!==v){b.checked=v;paint(b.dataset.k,v);}
    });
    refresh();
  }
  document.getElementById('sel-all').onclick=function(){bulk(function(){return true;});};
  document.getElementById('sel-inv').onclick=function(){bulk(function(b){return !b.checked;});};
  document.getElementById('clr').onclick=function(){bulk(function(){return false;});};
  var demo=document.getElementById('demo');
  if(demo)demo.onclick=function(){
    (demo.dataset.k||'').split(',').forEach(function(k){if(k)set(k,true);});
    closePicker();
  };

  boxes.forEach(function(b){if(b.checked)paint(b.dataset.k,true);});
  refresh();
  renderTable();
  function renderTable(){
    var tbl=document.getElementById('tbl');if(!tbl)return;
    var tb=tbl.tBodies[0],q=document.getElementById('q'),c2=document.getElementById('cnt'),
        trs=[].slice.call(tb.rows);
    var data=trs.map(function(tr){return {tr:tr,name:(tr.dataset.name||'').toLowerCase(),
        g:tr.dataset.g,n:+tr.cells[2].innerText,start:parseFloat(tr.cells[3].innerText),
        deep:parseFloat(tr.cells[4].innerText),rel:parseFloat(tr.cells[5].innerText)};});
    function render(){
      var kw=(q.value||'').toLowerCase(),shown=0;
      data.forEach(function(d){
        var ok=!kw||d.name.indexOf(kw)>=0||d.g.indexOf(kw)>=0;
        d.tr.style.display=ok?'':'none';if(ok)shown++;
      });
      c2.textContent='显示 '+shown+' / '+data.length;
    }
    q.addEventListener('input',render);render();
    var asc={};
    tbl.tHead.addEventListener('click',function(e){
      var th=e.target.closest('th.s');if(!th)return;
      var key=th.dataset.k;asc[key]=!asc[key];
      data.sort(function(a,b){var x=a[key],y=b[key];
        if(typeof x==='string')return asc[key]?x.localeCompare(y):y.localeCompare(x);
        return asc[key]?x-y:y-x;});
      data.forEach(function(d){tb.appendChild(d.tr);});
    });
  }
})();
"""


def main():
    recs, curves, snap, prof = load()
    cmap = {c["key"]: c for c in curves}
    default_on = set()
    for k in ("1245620",      # Elden Ring
              "1086940",      # Baldur's Gate 3
              "1091500",      # Cyberpunk 2077
              "1850570",      # Death Stranding Director's Cut
              "2050650"):     # Resident Evil 4
        if k in cmap:
            default_on.add(k)
    nc = len(curves)
    fin_vals = [r["finish"] for r in recs if r["finish"] is not None]
    avg_fin = sum(fin_vals) / len(fin_vals)
    snapday = snap[:10]

    rows, picks = [], []
    for r in recs:
        k = str(r["appid"])
        c = cmap.get(k)
        tag = ('<span class="tag has">%d 段</span>' % len(c["nodes"])) if c else '<span class="tag">—</span>'
        box = ('<input type="checkbox" class="ck" data-k="%s"%s>'
               % (k, " checked" if k in default_on else ""))
        rows.append(
            '<tr data-k="%s" data-g="%s" data-name="%s" data-color="%s">'
            '<td class="c0">%s</td>'
            '<td><span class="nm"><span class="cdot" style="background:%s"></span>%s</span>'
            '<span class="sid">%d</span></td>'
            '<td class="num">%d</td><td class="num">%.1f%%</td><td class="num">%.1f%%</td>'
            '<td class="num"><b style="color:%s">%.1f</b></td>'
            '<td class="num m-hide">%s</td><td>%s</td></tr>'
            % (k, r["genres"].lower(), r["name"].replace('"', "&quot;"), r["color"],
               box, r["color"], r["name"], r["appid"], r["n"], r["start"], r["deep"],
               "#7fe0b2" if r["rel"] >= 40 else "#ffb977" if r["rel"] >= 20 else "#ff8080", r["rel"],
               ("%.1f%%" % r["finish"]) if r["finish"] is not None else "—", tag))
        picks.append(((0 if c else 1, r["name"].lower()),
                      '<button class="pick" data-k="%s" data-c="%s" data-name="%s">'
                      '<i style="background:%s"></i>%s<span>%s</span></button>'
                      % (k, "1" if c else "0", r["name"].replace('"', "&quot;"), r["color"], r["name"],
                         ("%d 段" % len(c["nodes"])) if c else "仅剖面")))
    picks = [h for _, h in sorted(picks, key=lambda t: t[0])]
    demo_attr = ",".join(sorted(default_on))
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="用 Steam 官方成就解锁率，看玩家在单机游戏的哪个节点停下来。{len(recs)} 款作品、{nc} 条章节曲线。">
<meta name="theme-color" content="#0b0e13">
<title>Steam 留存指数 · {len(recs)} 款单机游戏</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="eyebrow">Steam retention index</div>
  <h1>玩家在哪一章停下
    <small>Steam 会公开每个成就的全球解锁率。把「完成第 N 章」这类成就按剧情顺序连起来，就是一条真实的留存曲线——
    不需要埋点，也不靠估算。目前收录 {len(recs)} 款单机 / 买断制作品，其中 {nc} 款能画出章节曲线。</small>
  </h1>
  <div class="statbar">
    <div class="stat"><b>{len(recs)}</b><span>款作品</span></div>
    <div class="stat"><b>{nc}</b><span>条章节曲线</span></div>
    <div class="stat"><b>{avg_fin:.0f}%</b><span>平均通关率</span></div>
    <div class="stat"><b>{snapday}</b><span>数据快照</span></div>
  </div>
  <div class="toplink">
    <a class="pill" href="https://github.com/{REPO}" target="_blank" rel="noopener">GitHub 仓库</a>
    <a class="pill" href="https://github.com/{REPO}/issues/new?template=add-game.yml" target="_blank" rel="noopener">提交想看的游戏</a>
    <a class="pill" href="https://github.com/{REPO}#readme" target="_blank" rel="noopener">方法说明</a>
  </div>
</header>

<section>
  <h2><span class="n">01</span>章节留存曲线</h2>
  <p class="sub">纵轴是「相对第一个节点的留存比例」，所以起点统一为 100%，不同作品才能横向比较。悬停任意节点可以看到成就原名与绝对到达率。</p>
  <div class="panel">
    <div class="toolbar">
      <button class="primary" id="add">＋ 添加作品</button>
      <span class="bgroup">
        <button id="sel-all" title="勾选当前筛选结果里的全部作品">全选</button>
        <button id="sel-inv" title="在当前筛选结果内反转勾选">反选</button>
        <button id="clr" title="取消当前筛选结果里的全部勾选">清空</button>
      </span>
      <div class="chips-wrap" id="chips"></div>
      <span class="tip" id="chartcnt" style="margin:0"></span>
    </div>
    <div class="empty" id="empty1"><div class="msg"></div>
      <div class="acts">
        <button id="demo" data-k="{demo_attr}">看三款代表作</button>
        <span class="hint">或从上方「添加作品」自己挑</span>
      </div>
    </div>
    <div class="chart only-desk">{line_chart(curves, default_on=default_on)}</div>
    <div class="chart only-mob">{line_chart(curves, mobile=True, default_on=default_on)}</div>
    <p class="tip">实线 = 多节点章节 · 虚线 = 只有「起点 → 通关」两个点 · <span style="color:var(--tx2)">灰线是未选中的其余作品，只作参照，悬停不显示信息</span></p>
  </div>
</section>

<section>
  <h2><span class="n">02</span>内容消耗剖面</h2>
  <p class="sub">换一个不依赖章节的尺度：横轴把所有成就按解锁率从易到难排开，看玩家把内容吃到了多深。{len(recs)} 款全部可画。</p>
  <div class="panel">
    <div class="empty" id="empty2">勾选作品后，这里会显示它的成就难易剖面，并叠在全库灰底之上。</div>
    <div class="chart only-desk">{profile_chart(recs, prof)}</div>
    <div class="chart only-mob">{profile_chart(recs, prof, mobile=True)}</div>
    <p class="tip">曲线越平、越靠上 = 内容消耗越深；越早贴地 = 大多数人只摸了开头。灰底为全部作品。</p>
  </div>
</section>

<section>
  <details class="fold" open>
    <summary>全库明细 · {len(recs)} 款（可勾选、可搜索、可排序）</summary>
    <div class="body">
      <div class="toolbar">
        <input id="q" placeholder="搜索游戏名 / 类型…" style="flex:1;min-width:180px;background:var(--bg);
          border:1px solid var(--line2);color:var(--tx);border-radius:8px;padding:7px 11px;font:inherit;font-size:12.5px;outline:none">
        <span class="tip" id="cnt" style="margin:0"></span>
      </div>
      <div class="tblwrap">
        <table id="tbl">
          <thead><tr><th class="c0"></th><th class="s" data-k="name">作品</th>
          <th class="s num" data-k="n">成就</th><th class="s num" data-k="start">起点</th>
          <th class="s num" data-k="deep">最深</th><th class="s num" data-k="rel">深层留存</th>
          <th class="num m-hide">通关</th><th>曲线</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
      <p class="tip">「起点」= 该作最容易被拿到的成就（近似启动率）；「最深」= 解锁率最低的成就；「深层留存」= 最深 ÷ 起点；
      「通关」只有能定位结局节点的作品才有。曲线列的数字是节点数，悬停可看切分依据。</p>
    </div>
  </details>

  <details class="fold">
    <summary>口径、来源与已知局限</summary>
    <div class="body">
      <ul class="tight">
        <li><b>百分比来自 Valve 官方接口</b> <code>GetGlobalAchievementPercentagesForApp</code>，分母包含从未启动过游戏的拥有者。
        这意味着「起点」本身就已经是一次流失筛选，不是「买了就玩」。</li>
        <li><b>成就名称与描述来自成就页的 SSR 数据</b>（<code>steamcommunity.com/achievements/&lt;appid&gt;</code>）。
        Valve 的 <code>GetSchemaForGame</code> 对隐藏成就连 <code>description</code> 都不返回，而网页版把名称、官方描述、全球百分比一起内嵌，
        这是本库能识别隐藏剧情节点的原因。</li>
        <li><b>节点语义读官方描述，顺序查维基/攻略。</b>解锁率只用来做单调性自检（出现倒挂就报错），不用来排顺序。
        每款的来源写在明细表「曲线」标签的悬浮说明里。</li>
        <li><b>只有 {nc} 款能画曲线。</b>其余作品没有章节概念（策略、模拟、沙盒），或成就被整体隐藏且无任何语义锚点，只进剖面图与明细表。</li>
        <li><b>横轴不是时长。</b>节点按序号等距排列，实际游玩时长差异很大，这张图只能比较形状，不能比较「多久流失」。</li>
        <li><b>「起点」定义不完全统一。</b>有的取开场即得，有的取首个 Boss。这是跨作品比较时最主要的噪音来源。</li>
        <li><b>数据会漂移。</b>全球解锁率是滚动的，同一个成就几周内可能变动零点几个百分点。页面顶部的快照日期就是读数时间。</li>
      </ul>
    </div>
  </details>
</section>

<footer>
  数据快照 {snap} · 由 <code>scripts/fetch_web.py</code> 低频率抓取，仅用于学习与研究，不用于任何商业用途 ·
  成就百分比版权归 Valve 及各游戏发行商所有 ·
  <a href="https://github.com/{REPO}" target="_blank" rel="noopener">源码与原始数据</a>
</footer>
</div>

<div class="pickbox" id="pickbox">
  <div class="pickinner">
    <input id="pq" placeholder="搜索作品名…（共 {len(recs)} 款）">
    <div class="plist">{''.join(picks)}</div>
    <div class="pickfoot"><span>带「段」的才能画曲线</span><button onclick="document.getElementById('pickbox').classList.remove('on')">完成</button></div>
  </div>
</div>
<script>{JS}</script>
</body></html>
"""
    out = os.path.join(ROOT, "index.html")
    open(out, "w", encoding="utf-8").write(html)
    print("-> index.html (%d KB)  游戏 %d  曲线 %d  示例 %s"
          % (len(html) // 1024, len(recs), nc, demo_attr))


if __name__ == "__main__":
    main()
