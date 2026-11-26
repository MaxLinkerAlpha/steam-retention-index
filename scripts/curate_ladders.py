#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人工核定的阶梯：节点语义**逐条查过 wiki / 官方攻略**，不靠解锁率推断。

背景：Steam 对隐藏成就只返回 displayName、description 为空，自动脚本无法判断
「这个成就对应第几章」。本文件对指定作品逐条写明**节点代表什么**，来源记在 src 字段。

校验（任一不满足即拒绝写出）：
  1) 每个节点名必须在该 appid 的官方成就表里唯一命中；
  2) 序列必须单调不增（官方解锁率，同分并列允许）；
  3) 全部数值必须来自该 appid 的官方集合 —— 不做任何估算。

注意：单调性只是**数据自检**，不是排序依据。排序依据是各作品的章节/幕/任务顺序，
来自下面的 src 来源。若两者冲突，说明节点挑错或顺序错，脚本会报错退出。

运行：python scripts/curate_ladders.py
输出：data/curated_ladders.json
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "data", "raw", "steam")
WEB = os.path.join(ROOT, "data", "raw", "steam_web")   # steamcommunity/achievements：含隐藏成就描述
GAMES = os.path.join(ROOT, "data", "games.json")
OUT = os.path.join(ROOT, "data", "curated_ladders.json")

# (appid, 颜色, 来源, 备注, [(节点显示名, 成就名匹配串), ...])
SPECS = [
    (883710, "#ff7a9c",
     "Polygon 全成就表 / gameplay.tips 100% 指南 + Steam 客户端成就页（19 条非隐藏项逐条核对，偏差 0.0）",
     "5 节点，全部是里昂线的剧情推进点。RE2 没有章节制，全程只有 9 个剧情成就（另 1 个是白金），这已是能画出的上限。"
     "已排除「Hack Complete（里昂专属 Ada 段 56.5）」与「Hide and Seek（克莱尔专属 Sherry 段 39.1）」——"
     "两条是平行分支，不与主线同轨。"
     "**口径注意**：52.0% 是「完成里昂篇（A 结局）」，而真结局（B 周目的 Broken Umbrella）只有 28.1%；"
     "克莱尔篇 36.2%。这三个数字不能混用——A 结局不等于通关整个故事。",
     [("抵达警局", "Welcome to the City of the Dead", "Make it to the police station."),
      ("女神像解谜", "Path to the Goddess", "Solve the Goddess Statue puzzle."),
      ("逃出警局", "Never-Ending Rain", "Escape the police station."),
      ("逃出下水道", "A Great Need for a Shower", "Escape from the sewers."),
      ("完成里昂篇（A 结局）", "A Hero Emerges", "Complete Leon's story.")]),

    (2050650, "#e05c5c",
     "PlatGet / Neoseeker 攻略标注章节 + Steam 客户端成就页的官方描述（隐藏成就在 API 里没有 description）",
     "6 节点：1 个开局锚点 + 5 场主线 Boss（Ch.3 / 6 / 12 / 14 / 16）。"
     "「Knife Basics（用刀格挡）」是全村最早能拿的成就（86.1%），当作起点锚——本作前两章没有任何章节成就，"
     "不加这个锚，曲线会被迫从 Ch.3 起算，相对留存虚高到 78.7。"
     "带 Defeat 的成就本作共 8 个，另 3 个不进主线：Verdugo（37.5%）在 Ch.10 但可跳过直接逃，"
     "所以低于通关率 60.1%，数学上不可能是必经节点；「Separate Ways」艾达篇的两个 Boss + 萨德勒"
     "属付费 DLC 战役，自成一档 28.8 → 27.4 → 26.6，其 Standard+ 通关率为 23.8%。"
     "另附难度漏斗（供参考，不作节点）：任意难度 60.1 → Standard+ 51.6 → Hardcore+ 22.0 → Professional 13.7。",
     [("开局·首次遇敌", "Knife Basics", "Parry an enemy with a knife."),
      ("Ch.3 大鱼", "Harpoon Hurler", "Defeat Del Lago."),
      ("Ch.6 村长", "Grilled Big Cheese", "Defeat Bitores Méndez."),
      ("Ch.12 城主", "No Thanks", "Defeat Ramón Salazar."),
      ("Ch.14 克劳萨", "You Used to Be a Good Guy", "Defeat Jack Krauser."),
      ("Ch.16 萨德勒（通关）", "You're Small Time", "Defeat Osmund Saddler.")]),

    (238320, "#c084fc",
     "Neoseeker / acheev 成就表：五个均为不可错过的章节节点",
     "5 节点：行政楼供电 → 下水道排水 → 男病房洒水 → 女病房取钥匙 → 通关。"
     "Whistleblower DLC 的 GAS LEAKER / SHOCKER 在通关率之下，已排除。",
     [("行政楼·供电", "ILLUMINATED"),
      ("下水道·排水", "FLUSHED"),
      ("男病房·洒水", "SOAKED"),
      ("女病房·取钥匙", "EMANCIPATED"),
      ("通关（PUNISHED）", "PUNISHED")]),

    (1196590, "#f0b429",
     "GameWith / RE Wiki 全成就表（逐条写明击败谁、发生在哪个区域）",
     "10 节点：9 个剧情节点（含 5 场 Boss）+ 任意难度通关。"
     "DLC「Shadows of Rose」与佣兵模式成就低于通关率，已排除。",
     [("幸存狼人袭击", "Not Lycan This"),
      ("逃出矿坑", "Four Lords"),
      ("击败蒂米特雷斯库", "That Sucked"),
      ("击败唐娜与安吉", "Got No Strings"),
      ("击败莫罗", "Fish Out of Water"),
      ("据点击败乌利亚什", "Up Urs"),
      ("放置巨人圣杯", "Temporary Measures"),
      ("击败海森伯格", "Iron Giant Down"),
      ("找到巨型菌主", "The Root of the Matter"),
      ("通关（Casual+）", "Great Dad")]),

    (268050, "#57d3e0",
     "XboxAchievements / PlayStationTrophies 攻略（逐条标注章节号）",
     "8 节点，全部对应主线 Boss 的章节：Ch.3 → 5 → 6 → 7 → 10 → 12 → 14 → 15。"
     "Ch.15 的「One of the Many」即通关，故不再叠加难度通关成就。"
     "DLC「The Assignment / The Consequence」整块（9.4% 以下）已排除。",
     [("Ch.3 电锯男", "Weapon of Choice"),
      ("Ch.5 贞子", "Old Flame"),
      ("Ch.6 双守卫", "Two on Two"),
      ("Ch.7 保险箱头", "What's in the Box"),
      ("Ch.10 车库怪物", "The First, Not the Last"),
      ("Ch.12 蜘蛛（巴士）", "Arachnophobia"),
      ("Ch.14 隐形章鱼", "Slither into Oblivion"),
      ("Ch.15 鲁维克（通关）", "One of the Many")]),

    (601430, "#7fd3a0",
     "XboxAchievements 攻略（逐条给出章节号 2/3/5/6/8/10/11/12/13/15/16/17）",
     "13 节点：Ch.2 → 3 → 5 → 6 → 8 → 10 → 11 → 12 → 13 → 15 → 16 → 17，"
     "末节点「Rookie」在 Ch.17 结算时解锁（即通关）。"
     "「That Cinematic Feel…」等附加内容（5.8% 以下）已排除。",
     [("Ch.2 抵达 Union", "Welcome to Union"),
      ("Ch.3", "Taken"),
      ("Ch.5", "Not Running This Time"),
      ("Ch.6", "The Team Psychologist"),
      ("Ch.8", "Premature Finale"),
      ("Ch.10", "Another Ally"),
      ("Ch.11", "Crossing to the Other Side"),
      ("Ch.12", "Spiritual Awakening"),
      ("Ch.13", "Fire Walk With Me"),
      ("Ch.15", "Overcome the Past"),
      ("Ch.16", "Everything Comes Crumbling Down"),
      ("Ch.17 开场", "Unfortunate Consequence"),
      ("Ch.17 通关（Casual+）", "Rookie")]),

    (1328670, "#9be15d",
     "官方成就描述本身即写明「ME1: Complete Eden Prime」等，无需外部来源",
     "8 节点：三部曲级阶梯。ME1 取 4 个评价点，其后接三部曲各自的通关成就 38.5 / 27.4 / 19.6。"
     "节点间距=跨一整部游戏，不代表等时长。",
     [("ME1 · Eden Prime", "Distinguished Service Medal"),
      ("ME1 · 成为 Spectre", "Spectre Inductee"),
      ("ME1 · Noveria", "Honorarium of Corporate Service"),
      ("ME1 · Feros", "Medal of Heroism"),
      ("ME1 · Virmire", "Council Legion of Merit"),
      ("ME1 通关", "Medal of Honor"),
      ("ME2 通关", "Mission Accomplished"),
      ("ME3 通关", "Legend")]),

    (387290, "#4cc2ff",
     "官方成就描述即写明「Complete the Prologue」「Enter the Ginso Tree」等",
     "10 节点：全部取自官方描述的剧情点（Prologue → 古树 → Ginso Tree → Misty Woods → "
     "Nibel 之风 → 登顶 → Mt. Horu → 结局）。收集/技能类成就已排除。",
     [("Prologue 完成", "The Journey Begins"),
      ("初见古树", "The Ancient Being"),
      ("进入 Ginso Tree", "Rotten Inside"),
      ("净化 Ginso 之心", "Run for Your Life"),
      ("Misty Woods 净化", "Obtaining Clarity"),
      ("恢复 Nibel 之风", "Solid Ground"),
      ("登上 Nibel 之顶", "Top of the world"),
      ("进入 Mt. Horu", "Into the Fire"),
      ("重燃火焰", "Rekindle"),
      ("通关（The Journey Ends）", "The Journey Ends")]),

    (782330, "#ff9f68",
     "PowerPyx 攻略（逐条标注 Mission 1/4/7/8/9/12/13）",
     "7 节点，全部标注任务号：M1 → M4 → M7 → M8 → M9 → M12 → M13（击杀罪恶圣像=通关）。"
     "「The Once and Future Slayer」32.0% 与 M13 的 31.9% 几乎重合，只留一个。"
     "「Ancient Gods」DLC 与 BATTLEMODE 成就已排除。",
     [("M1 Hell on Earth", "Doomsday"),
      ("M4 Doom Hunter Base", "The Hunters Became the Hunted"),
      ("M7 Mars Core", "Interplanetary Fracking"),
      ("M8 Sentinel Prime", "Thumbs Down"),
      ("M9 Taras Nabad", "Reforged and Refueled"),
      ("M12 Urdak", "Nontraditionalist"),
      ("M13 罪恶圣像（通关）", "Iconoclast")]),

    (1817230, "#f472b6",
     "Hi-Fi Rush Wiki 成就表 + ChapterCheats（逐条写明击败哪个部门主管）",
     "7 节点：QA → 生产 → 开发 → 安保 → 市场 → 财务 → CEO，每条对应一个 Track 的 Boss。"
     "「Out in a puff of smoke（对 Korsica 战灭火 10 次）」是战斗条件不是章节，已排除；"
     "难度通关成就（Normal 16.9%）不作为节点。",
     [("QA 主管", "Start with a bang"),
      ("生产主管", "Cream of the Crop"),
      ("开发主管", "This will cost you big time"),
      ("安保主管", "The Negotiator"),
      ("市场主管", "Headliner"),
      ("财务主管", "Time to pay up"),
      ("CEO 卡莱（通关）", "Who's the boss now")]),

    (1091500, "#cfd6e2",
     "PlayStationTrophies / Eurogamer 隐藏成就表（逐条写明解锁任务）",
     "6 节点：序章 → Act1 结束（The Heist）→ Act2 三处主线节点 → 主线通关。"
     "Act2 的 Wheel of Fortune（Life During Wartime）与 Hermit（Transmission）是并行支线，"
     "先后不严格，顺序按解锁率排列。五种互斥结局与 Life of the Road（支线）均已排除。",
     [("序章结束", "The Fool"),
      ("Act1 结束（偷 Relic）", "The Lovers"),
      ("Act2 · Life During Wartime", "The Wheel of Fortune"),
      ("Act2 · Transmission", "The Hermit"),
      ("Act2 · Search and Destroy", "The High Priestess"),
      ("主线通关（The World）", "The World")]),

    (1237970, "#38bdf8",
     "PowerPyx 全成就攻略（逐条写明解锁条件）+ Titanfall Wiki",
     "9 节点：一个任务一格（Pilot's Gauntlet → BT-7274 → Blood and Rust → Into the Abyss → "
     "Effect and Cause → The Beacon → Trial by Fire → The Ark → The Fold Weapon）。"
     "已排除两个非任务节点：Pied Piper（激活 Stalker 机架，可选）、"
     "I'm Not Locked in Here With You（Ash 穹顶杀 Reaper，可错过，58.5% 反而低于同关末的 58.9%）。",
     [("M1 Pilot's Gauntlet", "The Graduate"),
      ("M2 BT-7274", "BT Prime"),
      ("M3 Blood and Rust", "Hot Mess"),
      ("M4 Into the Abyss", "Dust to Dust"),
      ("M5 Effect and Cause", "Unlicensed Nuclear Accelerator"),
      ("M6 The Beacon", "4 Bars"),
      ("M7 Trial by Fire", "See You at the Party"),
      ("M8 The Ark", "The Ark"),
      ("M9 The Fold Weapon", "The Real Pilot's Gauntlet")]),

    (1643320, "#b48a3c",
     "PSN Trophy Guide 的 Step 1 主线顺序（Good hunting → toast → Eyes on the prize → House of glass → "
     "Such is the will → C-Consciousness → Doctor's oath → Living legend → Pripyat）+ "
     "steamcommunity/achievements 官方 schema 的成就描述",
     "10 节点，全部为主线上不可错过的剧情点。起点是「序章完成」86.0%，不是启动率。"
     "**四个结局互斥**（Brave new world 7.4 / Today never ends 3.2 / She will never be free 10.0 / "
     "Project Y 8.6），按本库规则终点取「最后一个必经节点」= 抵达皮里皮亚季见 Degtyarev（23.7），"
     "不取任何单一结局。"
     "已排除 4 个看着像主线、实际不是的："
     "① Baptism by fire（27.4）是 missable 支线——离开 SIRCAA 后回 Zalissya 才触发，不回就没有；"
     "② Alas poor Yorick（Kill Scar 19.7）只在 4 个结局里的 3 个出现，走 Spark 路线拿不到；"
     "③ All quiet in the Zone（Kill Korshunov 16.9）与 ④ Legends never die（Kill Strelok 14.9）"
     "都属特定结局分支。"
     "另：Kilometer Zero（抵达 CNPP 6.0）低于所有结局成就，说明它不是人人必经，同样排除。",
     [("序章完成", "Welcome to the Zone", "Prologue complete, but this is so far from over."),
      ("离开小禁区", "Good hunting, stalker", "Leave the Lesser Zone to go Scanner-hunting."),
      ("会见 Scar", "Would you like some toast?", "Meet Scar."),
      ("取回被盗 Scanner", "Eyes on the prize", "Retrieve the stolen Scanner."),
      ("SIRCAA 被毁", "House of glass", "Witness the temple of science get destroyed."),
      ("击杀 Faust", "Such is the will of the Monolith", "Kill Faust."),
      ("会见 C-Consciousness", "I see you have many questions", "Meet the C-Consciousness Representative."),
      ("医生揭示真相", "Doctor's oath", "The mysterious Doctor had to reveal what he'd been hiding."),
      ("会见 Strelok", "Living legend", "Meet Strelok."),
      ("抵达皮里皮亚季", "The Prypiat guardian", "Meet Degtyarev in Prypiat.")]),

    (292030, "#c0a062",
     "Prima Games / IGN 成就表（每条都写明对应主线任务名）；顺序按主线任务链，非按解锁率",
     "7 节点：找到叶奈法 → 男爵家（Velen）→ 解救丹德里恩（Novigrad）→ 从 Skjall 取情报（Skellige）"
     "→ 找到希里（Isle of Mists）→ 说服 Ge'els（Tir ná Lia）→ 击败 Eredin（通关）。"
     "「Passed the Trial（任意难度通关）」22.0% 与「The King is Dead」完全并列，只留后者。"
     "注意 Velen 与 Novigrad 两段在 Act I 内可交错进行，先后不严格；"
     "起点 60.3% 极低是「打折囤货从未启动」的典型结果，不是第一小时劝退。",
     [("找到叶奈法（序章）", "Lilac and Gooseberries"),
      ("男爵家（Velen）", "Family Counselor"),
      ("解救丹德里恩（Novigrad）", "A Friend in Need"),
      ("Skjall 取情报（Skellige）", "Necromancer"),
      ("找到希里（Isle of Mists）", "Something More"),
      ("说服 Ge'els（Tir ná Lia）", "Xenonaut"),
      ("击败 Eredin（通关）", "The King is Dead")]),

    (379720, "#d64545",
     "SuperCheats 流程目录（Mission 9 Lazarus Labs → 赛博恶魔；Mission 11 Necropolis → 地狱守卫；"
     "Mission 13 Argent D'Nur → 蜘蛛首脑）",
     "5 节点：M1 通关 → 首次进入地狱 → 赛博恶魔（M9）→ 地狱守卫（M11）→ 蜘蛛首脑（M13=通关）。"
     "「An Old Friend（取得 BFG）40.1%」位于赛博恶魔之前，但公开资料对其所属任务说法不一，故不入链；"
     "「Knee-Deep in the Dead（任意难度通关）」32.2% 与 M13 并列，只留后者。",
     [("M1 The UAC", "E1M1"),
      ("进入地狱（M6）", "Into the Unknown"),
      ("M9 赛博恶魔", "Shoot it Until it Dies"),
      ("M11 地狱守卫", "Outnumbered? No Problem"),
      ("M13 蜘蛛首脑（通关）", "Who's Next?")]),

    (1659420, "#6ee7b7",
     "成就表逐条核对：本合集 101 个成就里没有任何章节/剧情节点成就",
     "仅 2 节点：起点 + 难度通关。UC4 与《失落的遗产》共处一个 appid，"
     "通关取 UC4 的 Charted! - Explorer 39.1%；「Legacy Found!」21.7% 属失落的遗产，"
     "不能与 UC4 的起点拼成同一条线。",
     [("首个宝藏", "First Treasure"),
      ("UC4 通关（Explorer）", "Charted! - Explorer")]),

    (637650, "#4d8bf0",
     "Final Fantasy Wiki 成就表（fandom：Final Fantasy XV achievements and trophies，逐条章节号）+ "
     "HK01 / 9game 中文奖杯表（章节名与「完成 CHAPTER 00–14」对应）+ steamcommunity/achievements 官方描述",
     "16 节点：序章（Chapter 00 王都决战）+ Ch.1–14 + Ch.15 击败伊弗利特。"
     "本作**没有 Chapter 15 完成成就**——主线最后一章只有「Chosen King（Normal 难度击败 Ifrit）」这个金杯，"
     "而 Ifrit 是 Ch.15 不可跳过的剧情战，故按「最后一个必经节点」取它（22.3%）。"
     "**口径注意**：该成就带难度条件，Easy 难度通关不解锁，因此这里的终点略低于真实通关率；"
     "Ch.14「Homecoming」25.8% 是最后一个纯章节成就。"
     "起点用序章完成 91.9%（≈启动率），不是 Ch.1 的 65.4%——序章到 Ch.1 之间是 -26.5pp 的最大单步跌落，"
     "是「进入开放世界后弃坑」的真实信号，不能截掉。"
     "已排除全部 DLC/更新成就：Episode Gladiolus（Shield of the Chosen King 10.6 等）、"
     "Episode Prompto（Unbreakable Bonds 8.6）、Episode Ignis（A Noble Sacrifice 8.8 / Another Path 6.3）、"
     "Episode Ardyn（The Nightmare Ends 5.7）、Comrades（Cleaving a Path 2.3 / Beacons of Hope 1.5）、"
     "Royal Pack（The Power Within 6.9 / Tri-Headed Triumph 26.6 / Through the Dimensional Rift 4.1）。"
     "另排除操作类与支线类：Divine Intervention（首次召唤 30.4）、Faithful Heir（集 13 把幻影剑 12.6）、"
     "Spinning a Yarn I–V / Weaving a Tapestry（支线数）。",
     [("序章·王都决战", "Insomnia's Waking Nightmare", "Completed the Prologue."),
      ("Ch.1 启程", "Departure", "Completed Chapter 1."),
      ("Ch.2 再出发", "No Turning Back", "Completed Chapter 2."),
      ("Ch.3 辽阔的世界", "The Open World", "Completed Chapter 3."),
      ("Ch.4 神话再现", "Living Legend", "Completed Chapter 4."),
      ("Ch.5 乌云", "Dark Clouds", "Completed Chapter 5."),
      ("Ch.6 奋起", "A Way Forward", "Completed Chapter 6."),
      ("Ch.7 三人行", "Party of Three", "Completed Chapter 7."),
      ("Ch.8 出航", "Seaworthy", "Completed Chapter 8."),
      ("Ch.9 各自的使命", "Callings", "Completed Chapter 9."),
      ("Ch.10 为王者应如是", "The Heart of a King", "Completed Chapter 10."),
      ("Ch.11 圈套", "In the Dark", "Completed Chapter 11."),
      ("Ch.12 危在旦夕的世界", "End of Days", "Completed Chapter 12."),
      ("Ch.13 夺回", "Redemption", "Completed Chapter 13."),
      ("Ch.14 返乡", "Homecoming", "Completed Chapter 14."),
      ("Ch.15 击败伊弗利特", "Chosen King", "Defeated Ifrit on Normal difficulty.")]),
]


def main():
    NAMES = {g["appid"]: g["name"] for g in json.load(open(GAMES, encoding="utf-8"))["games"]}
    games, bad = [], 0
    for appid, color, src, note, nodes in SPECS:
        # 唯一数据源：steamcommunity/achievements
        p = os.path.join(WEB, "%d.json" % appid)
        if not os.path.exists(p):
            print("  !! %s 缺网页快照，跳过" % appid)
            bad += 1
            continue
        raw = json.load(open(p, encoding="utf-8"))
        table = raw["achievements"]
        gname = raw.get("game") or NAMES.get(appid, "?")
        official = {a["pct"] for a in table if a["pct"] is not None}
        out = []
        for item in nodes:
            label, key = item[0], item[1]
            d = item[2] if len(item) > 2 else ""
            hit = [a for a in table if a["name"].lower().startswith(key.lower())]
            if len(hit) != 1:
                print("  !! %s / %s 命中 %d 个" % (appid, key, len(hit)))
                bad += 1
                continue
            a = hit[0]
            assert a["pct"] in official
            node = {"stage": label, "pct": a["pct"], "ach": a["name"]}
            if d:
                node["desc"] = d
            out.append(node)
        for i in range(len(out) - 1):
            if out[i]["pct"] < out[i + 1]["pct"]:
                print("  !! %s 非单调：%s %.1f < %s %.1f（节点挑错或顺序错）"
                      % (appid, out[i]["stage"], out[i]["pct"], out[i + 1]["stage"], out[i + 1]["pct"]))
                bad += 1
        games.append({"appid": appid, "name": gname, "color": color,
                      "src": src, "note": note, "nodes": out})
        print("  %-42s %2d 节点  %5.1f -> %5.1f  相对 %5.1f"
              % (gname[:42], len(out), out[0]["pct"], out[-1]["pct"],
                 out[-1]["pct"] / out[0]["pct"] * 100))

    if bad:
        raise SystemExit("校验失败 %d 处，未写出" % bad)
    json.dump({"games": games}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("已写出", OUT, "共", len(games), "款")


if __name__ == "__main__":
    main()
