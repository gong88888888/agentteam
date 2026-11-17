# 迷宫冒险家 · UI/UX 设计规范（UI Spec）

> 角色：ui · UI/UX 设计师。上游：docs/product/product-baseline.md、docs/plan/project-plan.md。
> 交付物为可运行游戏，入口 game/index.html；技术栈 HTML5 Canvas + 原生 ES Modules。
> 本文只定义信息架构、交互流程、Design Token 与可落地标注，不改变产品功能与核心流程。
> 硬约束：单人基准平衡；所有 Boss/装备/剧情单人可获取；不设必须多人才能开的门/机关；多人仅动态缩放与协作（扶起、独立掉落）。

---

## 0. 设计原则

1. **单人优先**：所有界面在 1 人状态下信息完整、无空位占位；多人元素（队友血条、扶起提示）仅在人数≥2 时出现。
2. **掉落有反馈**：品质色 + 光柱 + 拾取飘字，前 3 分钟必出首次掉落（对齐产品验收）。
3. **低门槛**：主菜单到可操作 ≤3 秒；新手 10 分钟内教会移动/打怪/捡装/回城/存档。
4. **低配可跑**：动效以 CSS/Canvas 轻量实现，无重滤镜；60 帧目标下 UI 不阻塞渲染。
5. **可落地**：每个界面给出尺寸、层级、状态与交互标注，前端可直接实现。

---

## 1. Design Token

### 1.1 色彩

| Token | 值 | 用途 |
|---|---|---|
| `--c-bg-0` | `#0e1116` | 最底层背景 |
| `--c-bg-1` | `#161b22` | 面板背景 |
| `--c-bg-2` | `#1f2630` | 卡片/行背景 |
| `--c-border` | `#2d3644` | 面板描边 |
| `--c-text-1` | `#e6edf3` | 主文字 |
| `--c-text-2` | `#9aa7b4` | 次要文字 |
| `--c-text-disabled` | `#5a6673` | 置灰文字 |
| `--c-accent` | `#f2b544` | 主强调（金币/选中） |
| `--c-hp` | `#e5484d` | 生命条 |
| `--c-mp` | `#3b82f6` | 法力条 |
| `--c-xp` | `#22c55e` | 经验条 |
| `--c-danger` | `#ef4444` | 危险/错误 |
| `--c-success` | `#22c55e` | 成功/可交互 |
| `--c-warning` | `#f59e0b` | 警告/诅咒 |

### 1.2 品质色（装备）

| 品质 | Token | 值 | 光柱 |
|---|---|---|---|
| 白 | `--q-white` | `#c9d1d9` | 无 |
| 绿 | `--q-green` | `#3fb950` | 弱 |
| 蓝 | `--q-blue` | `#58a6ff` | 中 |
| 紫 | `--q-purple` | `#bc8cff` | 强 |
| 橙 | `--q-orange` | `#f0883e` | 最强 + 脉冲 |

### 1.3 间距 / 圆角 / 字号

| Token | 值 |
|---|---|
| `--sp-1` | 4px |
| `--sp-2` | 8px |
| `--sp-3` | 12px |
| `--sp-4` | 16px |
| `--sp-6` | 24px |
| `--sp-8` | 32px |
| `--radius-s` | 4px |
| `--radius-m` | 8px |
| `--radius-l` | 12px |
| `--fs-xs` | 12px |
| `--fs-s` | 14px |
| `--fs-m` | 16px |
| `--fs-l` | 20px |
| `--fs-xl` | 28px |
| `--font-ui` | `system-ui, "Microsoft YaHei", sans-serif` |
| `--font-num` | `ui-monospace, monospace` |

### 1.4 层级（z-index）

| 层 | 值 | 内容 |
|---|---|---|
| 世界 | 0 | Canvas 游戏世界 |
| HUD | 100 | 血蓝/技能/金币/小地图 |
| 提示 | 200 | 飘字/拾取提示/扶起提示 |
| 面板 | 300 | 背包/商店/篝火/暂停 |
| 弹窗 | 400 | 确认框/错误框 |
| 加载 | 500 | 加载遮罩 |

### 1.5 动效时长

| Token | 值 | 用途 |
|---|---|---|
| `--t-fast` | 120ms | 按钮反馈/悬停 |
| `--t-mid` | 200ms | 面板开合 |
| `--t-slow` | 320ms | 结算/过场 |
| `--t-toast` | 1800ms | 飘字停留 |

---

## 2. 信息架构

```
主菜单
├─ 继续（3 世界槽摘要）
├─ 新游戏 → 选职业/难度 → 进入第一层
├─ 多人 → 本地同屏（手柄A加入）/ 局域网（房间码/列表，P1）
├─ 设置（音量/按键/画质/难度回城可改）
└─ 退出

游戏内 HUD
├─ 左上：血条/蓝条/经验条 + 等级
├─ 左下：技能栏（普攻/重击/闪避/技能1/技能2/喝药）CD
├─ 右上：小地图（已探索房间/Boss/篝火/商店图标）
├─ 右下：金币 + 复活币
├─ 顶部中：Boss 条（仅 Boss 房）
└─ 队友血条（人数≥2，左侧竖排）

面板
├─ 背包（60格）/ 仓库（200格）
├─ 商店（买药/钥匙/随机装备）
├─ 篝火（回血/存档/复活队友/快速回城）
├─ 暂停（继续/设置/回主菜单）
└─ 结算（掉落汇总/经验/金币/回城）
```

---

## 3. 逐界面交互规范

### 3.1 HUD

- **血条**：左上，宽 220px 高 14px，`--c-hp`，低于 30% 时脉冲闪烁（`--t-mid`）。
- **蓝条**：血条下方，宽 220px 高 10px，`--c-mp`。
- **经验条**：屏幕最底部通栏，高 4px，`--c-xp`。
- **技能栏**：左下，6 个 48x48 图标，CD 用半透明遮罩 + 剩余秒数（`--font-num`）。
- **金币/复活币**：右下，图标 + 数字，数字变化时 `--t-fast` 缩放反馈。
- **小地图**：右上 160x120，房间方块 12x12，已探索亮、未探索暗、当前房间描边 `--c-accent`；Boss 房红点、篝火橙点、商店蓝点。
- **Boss 条**：顶部居中，宽 60% 屏宽，高 18px，显示 Boss 名 + 阶段（1/2/3），阶段切换时 `--t-slow` 闪白。
- **队友血条**：人数≥2 时左侧竖排，每人 140x10，含职业图标与倒地状态（倒地显示“可扶起”倒计时 3s）。
- **交互提示**：靠近门/箱/篝火时底部居中显示按键提示（如 `[E] 开门`）。

### 3.2 主菜单

- 布局：左侧竖排按钮（继续/新游戏/多人/设置/退出），右侧世界槽摘要卡片。
- 继续：无存档置灰（`--c-text-disabled`），悬停 `--t-fast` 高亮。
- 世界槽卡片：章节名、层数、角色等级、最后存档时间；损坏槽显示“存档损坏，已回退备份”并禁用。
- 键盘方向键 + 确认；手柄 A/十字键；焦点环 `--c-accent` 2px。

### 3.3 背包

- 布局：左 60 格网格（每格 56x56），右详情面板（装备名/品质色/词条/对比箭头）。
- 品质色：格子描边用对应 `--q-*`；橙装加脉冲光。
- 对比箭头：与当前装备对比，↑绿 ↓红，显示差值。
- 一键分解白绿：按钮“分解白/绿”，二次确认弹窗（`--c-danger`）。
- 空状态：背包为空显示“背包空空如也，去迷宫捡装备吧”+ 插画占位。
- 操作：鼠标点击/键盘方向 + 确认；分解/装备/重铸按钮在详情面板底部。

### 3.4 商店

- 布局：商品列表（药/钥匙/随机装备），每项显示价格与库存；底部金币余额。
- 购买：金币不足按钮置灰并提示“金币不足”；购买成功 `--t-fast` 飘字“-100 金币”。
- 随机装备：显示品质范围与价格，购买后进背包并高亮。

### 3.5 篝火

- 布局：居中面板，四个按钮（回血/存档/复活队友/快速回城）。
- 存档：点击后显示“已存档”`--t-toast`；多人时“复活队友”仅在有倒地队友时可用。
- 快速回城：二次确认，提示“未保存进度将丢失”（实际自动存档已触发，文案以防误解）。

### 3.6 结算

- 布局：掉落汇总（按品质分组）、经验/金币获取、回城按钮。
- 动效：逐条掉落 `--t-slow` 依次出现；橙装额外光效。

### 3.7 多人状态

- **本地同屏加入**：2P 按手柄 A 加入，HUD 出现队友血条；掉队 3 秒自动传送，提示“已传送至队友”。
- **局域网加入（P1）**：房间码输入 / 局域网列表；加入时校验主机世界难度，版本不匹配只读提示。
- **独立掉落**：每人只看到自己的光柱，拾取飘字仅本人可见。
- **扶起**：队友倒地显示“可扶起 3s”，靠近按交互键扶起，进度条 3 秒。
- **全员倒地**：显示“全员倒地，回城”`--t-slow` 过场。

---

## 4. 状态覆盖

| 状态 | 触发 | 表现 | 恢复 |
|---|---|---|---|
| 空 | 背包/仓库/商店无内容 | 占位文案 + 插画 | 引导去迷宫/刷新商店 |
| 加载 | 进房间/读档 | 全屏遮罩 `--c-bg-0` + 进度条 + 提示文案 | 加载<2 秒；失败回退上一存档房间 |
| 错误 | 存档损坏/加载失败 | 弹窗 `--c-danger` + 说明 + “回退备份”/“返回主菜单” | 双备份回退；均损坏标记槽不可用 |
| 暂停 | ESC/Start | 半透明遮罩 + 面板（继续/设置/回主菜单） | 继续恢复；回主菜单自动存档 |

---

## 5. game/css 增量样式建议

> 仅新增 `game/css/ui.css`，不覆盖基座文件；类名以 `ui-` 前缀避免冲突。

```css
:root{
  --c-bg-0:#0e1116;--c-bg-1:#161b22;--c-bg-2:#1f2630;--c-border:#2d3644;
  --c-text-1:#e6edf3;--c-text-2:#9aa7b4;--c-text-disabled:#5a6673;
  --c-accent:#f2b544;--c-hp:#e5484d;--c-mp:#3b82f6;--c-xp:#22c55e;
  --c-danger:#ef4444;--c-success:#22c55e;--c-warning:#f59e0b;
  --q-white:#c9d1d9;--q-green:#3fb950;--q-blue:#58a6ff;--q-purple:#bc8cff;--q-orange:#f0883e;
  --sp-1:4px;--sp-2:8px;--sp-3:12px;--sp-4:16px;--sp-6:24px;--sp-8:32px;
  --radius-s:4px;--radius-m:8px;--radius-l:12px;
  --fs-xs:12px;--fs-s:14px;--fs-m:16px;--fs-l:20px;--fs-xl:28px;
  --font-ui:system-ui,"Microsoft YaHei",sans-serif;--font-num:ui-monospace,monospace;
  --t-fast:120ms;--t-mid:200ms;--t-slow:320ms;--t-toast:1800ms;
}
.ui-hud{position:absolute;inset:0;pointer-events:none;z-index:100;font-family:var(--font-ui);color:var(--c-text-1)}
.ui-panel{position:absolute;background:var(--c-bg-1);border:1px solid var(--c-border);border-radius:var(--radius-m);z-index:300}
.ui-btn{background:var(--c-bg-2);border:1px solid var(--c-border);border-radius:var(--radius-s);color:var(--c-text-1);padding:var(--sp-2) var(--sp-4);transition:all var(--t-fast)}
.ui-btn:hover{border-color:var(--c-accent)}
.ui-btn:disabled{color:var(--c-text-disabled);cursor:not-allowed}
.ui-q-white{border-color:var(--q-white)}.ui-q-green{border-color:var(--q-green)}
.ui-q-blue{border-color:var(--q-blue)}.ui-q-purple{border-color:var(--q-purple)}
.ui-q-orange{border-color:var(--q-orange);animation:ui-pulse 1.2s infinite}
@keyframes ui-pulse{0%,100%{box-shadow:0 0 0 0 rgba(240,136,62,.6)}50%{box-shadow:0 0 0 6px rgba(240,136,62,0)}}
.ui-loading{position:absolute;inset:0;background:var(--c-bg-0);z-index:500;display:flex;align-items:center;justify-content:center}
.ui-toast{position:absolute;z-index:200;animation:ui-fade var(--t-toast) forwards}
@keyframes ui-fade{0%{opacity:0;transform:translateY(6px)}15%{opacity:1;transform:none}85%{opacity:1}100%{opacity:0}}
```

---

## 6. 可落地标注

- 所有面板最小安全边距 `--sp-4`；1280x720 与 1920x1080 下等比缩放。
- 交互键位：键盘 E 交互、ESC 暂停、Tab 背包；手柄 A 确认、B 返回、Start 暂停。
- 焦点环统一 `--c-accent` 2px，键盘/手柄导航必须可见。
- 动效不阻塞输入；加载遮罩期间禁用世界输入。
- 多人元素（队友血条/扶起提示）仅在人数≥2 渲染，单人界面无空位。

---

## 7. 验收对照

| 产品指标 | UI 支撑 |
|---|---|
| 首蓝装≤10min | 品质色光柱 + 拾取飘字即时反馈 |
| 首精英/Boss≤30min | Boss 条阶段提示 + 精英房图标 |
| 单局 15-30min | 小地图进度 + 结算汇总 |
| 读档成功率>99.5% | 加载/错误状态回退备份 |
| 本地多人使用率>25% | 2P 手柄 A 一键加入 |
