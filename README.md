# Steam 留存指数 · Steam Retention Index

用 Steam 公开的成就解锁率，看玩家在单机游戏的哪一章停下来。

**在线查看：** https://maxlinkeralpha.github.io/steam-retention-index/

---

## 数据使用声明（先读这一节）

本项目只做**低频率、非商业的研究性数据引用**：

- **不批量抓取。** 每个游戏只发 3 个请求（商店信息 + 官方成就百分比 + 成就页），
  单次运行之间间隔 ≥ 8 秒，全站每天最多新增 10 款。这个量级远低于 Steam 的公开限流阈值，
  也不构成对服务的压力。
- **不绕过任何访问控制。** 只读取未登录状态下公开可见的页面与官方 Web API，
  不模拟登录、不使用代理池、不规避任何区域或年龄限制。
- **不用于商业用途。** 不售卖数据、不做付费产品、不用于广告投放。
- **数据版权归 Valve 与各游戏发行商。** 本仓库只保存公开数值用于研究与对照，
  页面与 README 均标注来源；如需引用请自行核对原始来源。
- **可随时下线。** 若 Valve 或任何发行商提出异议，会立即停止抓取并移除相关数据。

如果你的使用场景超出「看看玩家在哪一章流失」这个研究目的，请不要复用本仓库的数据。

---

## 这个页面在做什么

Steam 会公开每个成就的**全球解锁率**。多数单机游戏会为「完成第 N 章」发一个成就，
把这些成就按剧情顺序连起来，就得到一条真实的留存曲线——不需要埋点，也不需要估算。

页面提供两个互补的视角：

| 图 | 横轴 | 覆盖范围 | 回答的问题 |
|---|---|---|---|
| 章节留存曲线 | 剧情推进（节点等距） | 有章节锚点的作品 | 玩家在第几章流失得最狠 |
| 内容消耗剖面 | 成就难易分位 | 全部作品 | 玩家把内容吃到了多深 |

顶部四个数字是：收录作品数、可画曲线的作品数、平均通关率、数据快照日期。

---

## 提交想看的游戏

打开 [新建 Issue](https://github.com/MaxLinkerAlpha/steam-retention-index/issues/new?template=add-game.yml)，
填入 Steam appid（商店链接里那串数字），一次最多 3 个。

提交后会自动执行：

1. 校验 appid 是否为**游戏本体**、是否有 Steam 成就；
2. 抓取该作的成就页（含隐藏成就的官方名称与描述）；
3. 写进 `data/`，重建页面并部署；
4. 在 Issue 里回复处理结果。

**会自动退回的情况：** appid 不存在 / 不是游戏本体（DLC、原声带、工具）/ 没有 Steam 成就 /
已收录 / 当日配额已满。

新入库的作品**默认只有剖面图**。章节曲线需要人工核定节点语义（读官方描述 + 查攻略确认顺序），
不会自动生成——这也是本项目不依赖大模型的原因：入库是纯脚本，核定是人工的一次性动作。

---

## 目录

```
.
├─ index.html                     生成物：单文件页面（CSS/JS 全内联）
├─ data/
│  ├─ titles.txt                  待抓取的作品清单（也是人工维护入口）
│  ├─ games.json                  标题 → appid 解析结果
│  ├─ ladders.json                自动识别的剧情阶梯（A/B/C/X 级）
│  ├─ curated_ladders.json        人工核定的阶梯（含来源与官方描述）
│  ├─ curated_manual.json         里程碑型曲线（Boss / 剧情里程碑）
│  ├─ manual_specs.json           节点 → 成就名的绑定
│  ├─ curated_auto.json           自动识别且无需人工干预的曲线
│  ├─ submissions.json            投稿记录（含每日配额计数）
│  └─ raw/
│     ├─ steam/<appid>.json       API 口径（历史存档，不参与计算）
│     └─ steam_web/<appid>.json   ★唯一数据源：含隐藏成就的官方描述
├─ scripts/
│  ├─ fetch_steam.py              标题 → appid → 成就名/解锁率（API 口径）
│  ├─ fetch_web.py                从成就页 SSR 取名称+描述+百分比（含隐藏成就）
│  ├─ ingest.py                   投稿入库：配额、校验、抓取、重建
│  ├─ detect_ladders.py           从描述里识别章节并拼成阶梯
│  ├─ curate_auto.py              把 A 级固化为曲线
│  ├─ curate_ladders.py           人工核定阶梯（含三重校验）
│  ├─ sync_manual.py              按成就名刷新里程碑曲线的数值
│  ├─ match_manual.py             节点 → 成就名的一次性匹配
│  ├─ audit_ladders.py            用官方描述复核阶梯（找可疑点与漏收）
│  ├─ diff_sources.py             核对数据源一致性
│  ├─ diff_client_list.py         客户端成就页粘贴文本与快照比对
│  └─ build_pages.py              生成 index.html
└─ .github/
   ├─ ISSUE_TEMPLATE/add-game.yml 投稿表单
   └─ workflows/
      ├─ deploy.yml               推送即构建并部署 Pages
      └─ ingest.yml               Issue → 入库 → 重建 → 部署 → 回帖
```

---

## 本地运行

```bash
python scripts/fetch_steam.py       # 追加 titles.txt 里的新标题（需要 STEAM_WEB_API_KEY）
python scripts/fetch_web.py --all   # 抓成就页（也可只给单个 appid）
python scripts/detect_ladders.py
python scripts/curate_auto.py
python scripts/curate_ladders.py
python scripts/sync_manual.py
python scripts/build_pages.py       # 产出 index.html
python scripts/audit_ladders.py     # 复核阶梯
```

只有 `fetch_steam.py` 需要 API key，放 `.env` 的 `STEAM_WEB_API_KEY`（见 `.env.example`）。
其余脚本全部匿名可跑，投稿链路也不需要 key。

---

## 口径

- **百分比**来自 `ISteamUserStats/GetGlobalAchievementPercentagesForApp`，分母包含从未启动游戏的拥有者。
- **成就名称与描述**来自 `steamcommunity.com/achievements/<appid>` 的 SSR 数据。Valve 的
  `GetSchemaForGame` 对隐藏成就连 `description` 都不返回，而网页版把名称、描述、百分比一起内嵌，
  这是能识别隐藏剧情节点的原因。
- **节点语义读官方描述，顺序查 wiki / 攻略确认。** 解锁率只用于单调性自检（倒挂即报错），
  不用来排序。
- **判别规则：** 节点解锁率低于通关率的，一定不是必经节点（例如可跳过的 Boss 战）。
- **互斥结局**不当节点，终点取「最后一个必经节点」。
- **相对留存** = 终局节点 ÷ 起点节点，用来消除各作起点差异。

## 已知局限

1. **起点定义不统一。** 有的取开场即得，有的取首个 Boss，跨作品比较时这是主要噪音。
2. **大多数作品画不出曲线。** 策略、模拟、沙盒没有章节概念；部分作品成就整体隐藏且无语义锚点。
3. **横轴不是时长。** 节点等距排列，实际游玩时长差异很大，只能比形状。
4. **数值会漂移。** 全球百分比是滚动的，同一成就几周内可能变动零点几个百分点；页面顶部标注快照日期。
5. **Xbox 无公开数据源**，PSN 依赖第三方取样，因此本项目只做 Steam 单口径，不做跨平台换算。

## License

代码 MIT（见 `LICENSE`）。数据不适用 MIT：版权归 Valve 与各发行商，本项目只做研究性引用。
