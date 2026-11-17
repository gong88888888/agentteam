# backend · 后端实现

- 状态：done
- 摘要：按 arch 契约实现第一章玩法逻辑增量：combat.js（伤害公式含攻防/暴击/品质系数、闪避无敌帧、技能CD、顿帧标记）、classes.js（剑士/法师/游侠数值与技能表）、player.js（输入意图→动作状态机）、enemies.js（4类普通怪+精英词缀+Boss三阶段骨架+仇恨选择）、items.js（5部位/5品质/2-4词条生成、强化+1~+9失败不掉级、重铸保底）、loot.js（白40/绿30/蓝20/紫8/橙2权重、Boss保底蓝+紫20/橙5、独立掉落分配）、inventory.js（背包60/仓库200/分解/对比）、save.js（版本号+CRC+双备份+异常回退篝火）、coop.js（2/3/4人缩放系数与Boss+10%血、扶起3秒、掉队传送）。全部为无副作用纯逻辑模块，不触碰 DOM/Canvas，不修改基座与契约；接入与落盘方式列入 open_questions。

- 门禁：pass · G-TEST1-backend

## Claims（不参与门禁）

- 新增 gameplay 增量模块：combat/classes/player/enemies/items/loot/inventory/save/coop，均为无副作用纯逻辑 ES Module，可被 node --test 导入。
- 伤害公式、闪避无敌帧、技能CD、精英词缀、掉落权重与Boss保底、强化+1~+9不掉级、重铸保底、存档版本+CRC+双备份、多人缩放系数与扶起3秒均按 arch 契约实现。
- 未修改基座文件与契约，未引入 Web 服务/React/引擎代码。

## 写入文件

- `game/js/gameplay/classes.js` · d0d9459a64ea · role
- `game/js/gameplay/combat.js` · a09dec50782c · role
- `game/js/gameplay/player.js` · edd82d9a9738 · role
- `game/js/gameplay/enemies.js` · 4ce188f6e404 · role
- `game/js/gameplay/items.js` · 283bcc0c3d86 · role
- `game/js/gameplay/loot.js` · 28340cb50890 · role
- `game/js/gameplay/inventory.js` · fd09ea2293e4 · role
- `game/js/gameplay/save.js` · 06daa5bee473 · role
- `game/js/gameplay/coop.js` · 5b8dfc64acd4 · role

## 未决问题

- 基座 game/js/core.js 的模块注册/更新/渲染钩子具体签名未在可见摘要中给出，本模块以纯函数+状态对象形式提供，接入方式待 S0 基线说明确认。
- 输入层（键盘/手柄映射）与 Canvas 渲染接入点由 ui 角色负责，本角色仅提供逻辑状态与意图接口。
- 存档持久化介质（localStorage vs 文件）未定，save.js 只做序列化/校验/迁移，落盘由调用方注入。
- 局域网联机为 P1，本切片 coop.js 仅实现本地同屏人数缩放与扶起逻辑。

## 门禁检查

- 全部通过
