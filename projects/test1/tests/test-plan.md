# 迷宫冒险家 · 第一章测试计划（QA）

> 角色：qa。上游：docs/plan/project-plan.md、docs/product/product-baseline.md、docs/architecture/architecture.md、contracts/openapi.yaml。
> 交付物：可运行游戏 game/index.html；技术栈 HTML5 Canvas + 原生 ES Modules。
> 不可改基线：game/tests/game_logic.test.mjs、game/tests/smoke.mjs。QA 只新增 game/tests/qa_*.mjs。

## 1. 测试范围与策略

| 层 | 内容 | 方式 |
|---|---|---|
| 基线 | 基座逻辑 + smoke | `node --test game/tests/game_logic.test.mjs`、`node game/tests/smoke.mjs`（只运行，不修改） |
| 契约单元 | mapgen/combat/items/loot/save/coop 纯函数不变量 | `node --test game/tests/qa_*.mjs` |
| 集成 | 模块落盘 + ESM 加载 + index.html 可跑 | 手动/后续补 |
| 体验 | 首蓝装≤10min、首精英/Boss≤30min、单局15-30min | 人工试玩记录 |

## 2. 用例矩阵（正常/异常/边界/权限）

### 2.1 地图生成（qa_mapgen.mjs）
- 正常：同 seed 确定性；房间数[8,12]+Boss房；主路径连通；篝火/商店各1；宝箱房[2,4]。
- 边界：seed=1/2/3/99/12345 多组；钥匙门=0 与 =1 两态。
- 异常：钥匙门不得锁主路径（无钥匙仍可达 Boss）。

### 2.2 战斗（qa_combat.mjs）
- 正常：伤害随攻击升、随防御降；暴击率0/1 边界。
- 边界：闪避无敌帧内不受伤；技能CD=0 可释放、>0 不可。
- 异常：精英词缀（护盾/加速）生效。

### 2.3 装备/掉落（qa_loot.mjs）
- 正常：5 部位、2-4 词条。
- 边界：品质权重 20000 次采样近似 40/30/20/8/2（容差）。
- 异常：Boss 保底蓝（500 次不低于 blue）；强化失败不掉级（100 次）。

### 2.4 存档（qa_save.mjs）
- 正常：序列化含版本号+CRC；往返一致。
- 异常：CRC 损坏回退最近篝火。
- 边界：双备份均损坏 → 槽不可用（待 save.js 落盘后补）。

### 2.5 双人缩放（qa_coop.mjs）
- 正常：2/3/4 人系数精确匹配产品口径。
- 边界：Boss 额外 +10% 血。
- 异常：扶起 3 秒、掉队 3 秒传送。

## 3. 执行命令

```
node --test game/tests/game_logic.test.mjs
node game/tests/smoke.mjs
node --test game/tests/qa_mapgen.mjs
node --test game/tests/qa_combat.mjs
node --test game/tests/qa_loot.mjs
node --test game/tests/qa_save.mjs
node --test game/tests/qa_coop.mjs
```

## 4. 缺陷与风险（详见 docs/qa/findings.md）

- F-01 交付路径违规：frontend 产物在 src/frontend/game/js/ui/hud.js，不在 game/js/ui/，ESM 无法加载。
- F-02 gameplay 模块落盘未证实，qa_*.mjs 以契约纯函数为断言目标，模块缺失时显式失败。
- F-03 无基线运行证据，读档成功率>99.5%、崩溃率<0.5% 无法量化。

## 5. 退出标准

- 基线两条命令通过。
- 五个 qa_*.mjs 全部通过（或缺口以显式失败暴露并登记 findings）。
- 人工试玩记录首蓝装/首精英/单局时长。
